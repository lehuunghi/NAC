"""Offline, observe-only NAC20 Security foundation. Python 3.10+, stdlib only."""
import argparse
import hashlib
import ipaddress
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone

MAX_LINE = 262144
MAC = re.compile(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.utcoffset() is None:
        raise ValueError("timestamp requires timezone")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def text(value, name, limit=256):
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValueError(name + " must be a nonempty bounded string")
    if any(ord(c) < 32 for c in value):
        raise ValueError(name + " contains control characters")
    return value


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name + " is out of range")
    return value


def address(value):
    text(value, "IP address", 45)
    if "%" in value:
        raise ValueError("use scope instead of IPv6 zone identifiers")
    return str(ipaddress.ip_address(value))


def normalize(eve, sensor, scope):
    """Only alert records; never infer a device from EVE ethernet metadata."""
    if not isinstance(eve, dict):
        raise ValueError("EVE record must be an object")
    if eve.get("event_type") != "alert":
        return None
    alert = eve.get("alert")
    if not isinstance(alert, dict):
        raise ValueError("alert object required")
    event = {
        "schema_version": 1,
        "sensor": text(sensor, "sensor"), "scope": text(scope, "scope"),
        "occurred_at": timestamp(eve.get("timestamp")),
        "source": "suricata", "mode": "observe",
        "src_ip": address(eve.get("src_ip")),
        "dest_ip": address(eve.get("dest_ip")),
        "signature_id": integer(alert.get("signature_id"), "signature_id", 1, 2**32-1),
        "signature": text(alert.get("signature"), "signature", 4096),
        "severity": integer(alert.get("severity"), "severity", 1, 255),
        "category": text(alert.get("category", "unknown"), "category", 1024),
        "proto": text(eve.get("proto", "unknown"), "proto", 32),
    }
    for key in ("src_port", "dest_port"):
        if key in eve:
            event[key] = integer(eve[key], key, 0, 65535)
    for key in ("flow_id", "pcap_cnt", "tx_id"):
        if key in eve:
            event[key] = integer(eve[key], key, 0, 2**64-1)
    # Metadata/payloads are deliberately omitted: they can contain credentials/PII.
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"))
    event["event_id"] = hashlib.sha256(encoded.encode()).hexdigest()
    return event


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            self.db.close()
            raise ValueError("unsupported database schema version")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS bindings (
                scope TEXT NOT NULL, ip TEXT NOT NULL, mac TEXT NOT NULL,
                valid_from TEXT NOT NULL, valid_until TEXT NOT NULL,
                PRIMARY KEY(scope, ip, mac, valid_from, valid_until));
            CREATE INDEX IF NOT EXISTS bindings_lookup ON bindings(scope, ip);
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL,
                sensor TEXT NOT NULL, scope TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open','acknowledged','closed')),
                document TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_time ON events(occurred_at);
            CREATE TABLE IF NOT EXISTS transitions (
                id INTEGER PRIMARY KEY, event_id TEXT NOT NULL,
                changed_at TEXT NOT NULL, actor TEXT NOT NULL,
                old_status TEXT NOT NULL, new_status TEXT NOT NULL);
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(bindings)")}
        if "username" not in columns:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                self.db.execute("""CREATE TABLE bindings_v2 (
                    scope TEXT NOT NULL, ip TEXT NOT NULL, mac TEXT NOT NULL,
                    valid_from TEXT NOT NULL, valid_until TEXT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(scope,ip,mac,valid_from,valid_until,username))""")
                self.db.execute("INSERT INTO bindings_v2 SELECT *, '' FROM bindings")
                self.db.execute("DROP TABLE bindings")
                self.db.execute("ALTER TABLE bindings_v2 RENAME TO bindings")
                self.db.execute("CREATE INDEX bindings_lookup ON bindings(scope,ip)")
                self.db.execute("PRAGMA user_version=2")

    def close(self):
        self.db.close()

    def replace_inventory(self, scope, records, audit=None):
        """Atomic replacement for one network scope, validated before deletion."""
        text(scope, "scope")
        if not isinstance(records, list):
            raise ValueError("inventory must be a JSON array")
        rows = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("binding must be an object")
            ip = address(record.get("ip"))
            mac = text(record.get("mac"), "mac").lower().replace("-", ":")
            if not MAC.fullmatch(mac) or int(mac[:2], 16) & 1 or mac == "00:00:00:00:00:00":
                raise ValueError("unicast device MAC required")
            start, end = timestamp(record.get("valid_from")), timestamp(record.get("valid_until"))
            if end <= start:
                raise ValueError("binding validity must have a positive duration")
            username = record.get("username", "")
            if username:
                text(username, "username")
            elif username != "":
                raise ValueError("username must be a string")
            rows.append((scope, ip, mac, start, end, username))
        with self.db:
            self.db.execute("DELETE FROM bindings WHERE scope=?", (scope,))
            self.db.executemany("INSERT OR IGNORE INTO bindings VALUES (?,?,?,?,?,?)", rows)
            if audit is not None:
                audit(len(set(rows)))
        return len(set(rows))

    def resolve(self, scope, ip, at):
        ip, at = address(ip), timestamp(at)
        rows = self.db.execute("""SELECT DISTINCT mac,username FROM bindings
            WHERE scope=? AND ip=? AND valid_from<=? AND valid_until>? ORDER BY mac""",
            (scope, ip, at, at)).fetchall()
        macs = {row["mac"] for row in rows}
        if len(macs) == 1:
            result = {"state": "resolved", "mac": rows[0]["mac"], "evidence": "inventory_interval"}
            users = {row["username"] for row in rows if row["username"]}
            if users:
                result["user"] = ({"state": "resolved", "username": next(iter(users))}
                                  if len(users) == 1 and all(row["username"] for row in rows)
                                  else {"state": "ambiguous"})
            else:
                result["user"] = {"state": "unresolved"}
            return result
        return {"state": "ambiguous" if rows else "unresolved"}

    def ingest(self, eve, sensor, scope):
        event = normalize(eve, sensor, scope)
        if event is None:
            return "ignored"
        for endpoint in ("src", "dest"):
            event[endpoint + "_device"] = self.resolve(scope, event[endpoint + "_ip"], event["occurred_at"])
        with self.db:
            cursor = self.db.execute("""INSERT OR IGNORE INTO events
                (event_id,occurred_at,sensor,scope,document) VALUES (?,?,?,?,?)""",
                (event["event_id"], event["occurred_at"], sensor, scope, json.dumps(event)))
        return "inserted" if cursor.rowcount else "duplicate"

    def events(self, limit=100):
        integer(limit, "limit", 1, 1000)
        return [dict(json.loads(row["document"]), status=row["status"])
                for row in self.db.execute(
                    "SELECT document,status FROM events ORDER BY occurred_at DESC,event_id LIMIT ?", (limit,))]

    def transition(self, event_id, status, actor):
        text(actor, "actor")
        allowed = {"open": {"acknowledged", "closed"}, "acknowledged": {"closed"}, "closed": set()}
        with self.db:
            # Acquire write lock before reading to prevent conflicting state/audit records.
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT status FROM events WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                raise ValueError("unknown event")
            old = row["status"]
            if status not in allowed[old]:
                raise ValueError("invalid status transition")
            self.db.execute("UPDATE events SET status=? WHERE event_id=?", (status, event_id))
            self.db.execute("""INSERT INTO transitions
                (event_id,changed_at,actor,old_status,new_status) VALUES (?,?,?,?,?)""",
                (event_id, datetime.now(timezone.utc).isoformat(), actor, old, status))


def ingest_file(store, stream, sensor, scope):
    """Bounded JSONL records; incomplete final writes are retried by replaying file."""
    counts = dict(inserted=0, duplicate=0, ignored=0, rejected=0, incomplete=0)
    while True:
        line = stream.readline(MAX_LINE + 1)
        if not line:
            break
        if len(line) > MAX_LINE:
            while line and not line.endswith(b"\n"):
                line = stream.readline(MAX_LINE + 1)
            counts["rejected"] += 1
            continue
        if not line.endswith(b"\n"):
            counts["incomplete"] += 1
            break
        try:
            result = store.ingest(json.loads(line), sensor, scope)
        except (ValueError, TypeError, OverflowError, RecursionError):
            counts["rejected"] += 1
        else:
            counts[result] += 1
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="dedicated Security SQLite database, never PacketFence DB")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory", help="replace a scope's exported bindings")
    inventory.add_argument("--scope", required=True)
    inventory.add_argument("--file", required=True)
    ingest = commands.add_parser("ingest", help="replay passive Suricata EVE JSONL")
    ingest.add_argument("--scope", required=True)
    ingest.add_argument("--sensor", required=True)
    ingest.add_argument("--file", required=True)
    listing = commands.add_parser("events")
    listing.add_argument("--limit", type=int, default=100)
    change = commands.add_parser("status")
    change.add_argument("event_id")
    change.add_argument("status", choices=["acknowledged", "closed"])
    change.add_argument("--actor", required=True)
    args = parser.parse_args(argv)
    store = None
    try:
        store = Store(args.db)
        if args.command == "inventory":
            with open(args.file, encoding="utf-8") as stream:
                result = {"bindings": store.replace_inventory(args.scope, json.load(stream))}
        elif args.command == "ingest":
            text(args.sensor, "sensor")
            text(args.scope, "scope")
            with open(args.file, "rb") as stream:
                result = ingest_file(store, stream, args.sensor, args.scope)
            print(json.dumps(result))
            return 2 if result["rejected"] or result["incomplete"] else 0
        elif args.command == "events":
            result = store.events(args.limit)
        else:
            store.transition(args.event_id, args.status, args.actor)
            result = {"status": args.status}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, TypeError, sqlite3.Error):
        # Avoid echoing untrusted records, credentials, or local database details.
        print("Operation failed: check input format, paths and database permissions.", file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
