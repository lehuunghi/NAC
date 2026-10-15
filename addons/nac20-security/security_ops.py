"""Security operations for the isolated lab store; enforcement is simulation only."""
import argparse
import hashlib
import json
import os
import re
import smtplib
import sqlite3
import ssl
import sys
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

from nac20_security import MAC, Store, integer, text, timestamp


def utcnow():
    return datetime.now(timezone.utc)


def mac_address(value):
    value = text(value, "mac").lower().replace("-", ":")
    if not MAC.fullmatch(value) or int(value[:2], 16) & 1 or value == "00:00:00:00:00:00":
        raise ValueError("unicast MAC required")
    return value


def validate_policy(policy):
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        raise ValueError("automatic planning is disabled")
    integer(policy.get("max_age_seconds"), "max_age_seconds", 1, 3600)
    integer(policy.get("max_severity"), "max_severity", 1, 3)
    integer(policy.get("max_plans_per_hour"), "max_plans_per_hour", 1, 100)
    integer(policy.get("cooldown_seconds"), "cooldown_seconds", 1, 86400)
    text(policy.get("id"), "policy id")
    for key in ("scopes", "sensors", "signature_ids"):
        if not isinstance(policy.get(key), list) or not policy[key]:
            raise ValueError("explicit policy allowlists required")
        for item in policy[key]:
            if key == "signature_ids":
                integer(item, key, 1, 2**32-1)
            else:
                text(item, key)


class Operations:
    def __init__(self, store):
        self.store, self.db = store, store.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS assets (
                scope TEXT NOT NULL, mac TEXT NOT NULL, document TEXT NOT NULL,
                PRIMARY KEY(scope,mac));
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL,
                operation TEXT NOT NULL, subject TEXT NOT NULL, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS action_plans (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, mac TEXT NOT NULL,
                event_id TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL,
                document TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_plan ON action_plans(scope,mac)
                WHERE status IN ('pending_review','simulated_quarantined');
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY, event_id TEXT NOT NULL, channel TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                body TEXT NOT NULL, UNIQUE(event_id,channel));
        """)

    def audit(self, actor, operation, subject, document):
        text(actor, "actor")
        self.db.execute("INSERT INTO audit(at,actor,operation,subject,document) VALUES (?,?,?,?,?)",
                        (timestamp(utcnow().isoformat()), actor, operation, subject, json.dumps(document)))

    def register(self, scope, records, actor):
        """Upsert assets; explicit protected flag, observed VLAN and vendor required."""
        text(scope, "scope")
        text(actor, "actor")
        if not isinstance(records, list):
            raise ValueError("asset list required")
        assets = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("asset object required")
            asset = {"scope": scope, "mac": mac_address(record.get("mac")),
                     "name": text(record.get("name"), "name"),
                     "vendor": record.get("vendor"), "protected": record.get("protected"),
                     "vlan": integer(record.get("vlan"), "vlan", 1, 4094)}
            if asset["vendor"] not in ("fortigate", "mikrotik", "ruijie") or type(asset["protected"]) is not bool:
                raise ValueError("supported vendor and explicit protected flag required")
            assets.append(asset)
        with self.db:
            for asset in assets:
                self.db.execute("INSERT OR REPLACE INTO assets VALUES (?,?,?)",
                                (scope, asset["mac"], json.dumps(asset)))
            digest = hashlib.sha256(json.dumps(assets, sort_keys=True).encode()).hexdigest()
            self.audit(actor, "assets.upsert", scope, {"count": len(assets), "sha256": digest})
        return len(assets)

    def inventory(self, scope, records, actor):
        text(actor, "actor")
        return self.store.replace_inventory(scope, records, audit=lambda count:
            self.audit(actor, "inventory.replace", scope, {"bindings": count}))

    def assets(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT document FROM assets ORDER BY scope,mac")]

    def event(self, event_id):
        row = self.db.execute("SELECT document,status FROM events WHERE event_id=?", (event_id,)).fetchone()
        if row is None:
            raise ValueError("unknown event")
        return dict(json.loads(row["document"]), status=row["status"])

    def _target(self, event, endpoint, now, max_age):
        if endpoint not in ("src", "dest") or event["status"] == "closed":
            raise ValueError("select an endpoint on an active event")
        age = (now - datetime.fromisoformat(event["occurred_at"])).total_seconds()
        if not 0 <= age <= max_age:
            raise ValueError("event is stale or in the future")
        evidence = event[endpoint + "_device"]
        if evidence["state"] != "resolved":
            raise ValueError("endpoint is not resolved")
        current = self.store.resolve(event["scope"], event[endpoint + "_ip"], now.isoformat())
        if current.get("mac") != evidence["mac"] or current["state"] != "resolved":
            raise ValueError("current binding no longer matches event")
        row = self.db.execute("SELECT document FROM assets WHERE scope=? AND mac=?",
                              (event["scope"], evidence["mac"])).fetchone()
        if row is None:
            raise ValueError("unmanaged device")
        asset = json.loads(row[0])
        if asset["protected"]:
            raise ValueError("protected device")
        return asset

    def propose(self, event_id, endpoint, vlan, actor, reason, policy=None, now=None):
        text(actor, "actor")
        text(reason, "reason", 1024)
        integer(vlan, "quarantine VLAN", 1, 4094)
        now = now or utcnow()
        max_age = 300
        if policy is not None:
            validate_policy(policy)
            max_age = policy["max_age_seconds"]
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            event = self.event(event_id)
            asset = self._target(event, endpoint, now, max_age)
            if vlan == asset["vlan"]:
                raise ValueError("quarantine VLAN equals original VLAN")
            if policy is not None:
                if (event["scope"] not in policy["scopes"] or event["sensor"] not in policy["sensors"]
                        or event["signature_id"] not in policy["signature_ids"]
                        or event["severity"] > policy["max_severity"]):
                    raise ValueError("event does not match policy")
                if event[endpoint + "_device"].get("user", {}).get("state") != "resolved":
                    raise ValueError("automatic planning requires user evidence")
                current = self.store.resolve(event["scope"], event[endpoint + "_ip"], now.isoformat())
                if current.get("user") != event[endpoint + "_device"].get("user"):
                    raise ValueError("user evidence changed")
                cutoff = timestamp((now - timedelta(hours=1)).isoformat())
                # All requests count, so repeated rejected/released requests cannot bypass quota.
                count = self.db.execute("SELECT count(*) FROM action_plans WHERE created_at>?", (cutoff,)).fetchone()[0]
                if count >= policy["max_plans_per_hour"]:
                    raise ValueError("hourly plan limit reached")
                recent = timestamp((now - timedelta(seconds=policy["cooldown_seconds"])).isoformat())
                if self.db.execute("SELECT 1 FROM action_plans WHERE scope=? AND mac=? AND created_at>?",
                                   (asset["scope"], asset["mac"], recent)).fetchone():
                    raise ValueError("device cooldown active")
            plan = {"id": uuid.uuid4().hex, "scope": asset["scope"], "mac": asset["mac"],
                    "event_id": event_id, "endpoint": endpoint, "ip": event[endpoint + "_ip"],
                    "vendor": asset["vendor"], "restore_vlan": asset["vlan"], "quarantine_vlan": vlan,
                    "requester": actor, "reason": reason, "mode": "simulation",
                    "policy": policy["id"] if policy is not None else None,
                    "expires_at": (now + timedelta(minutes=5)).isoformat()}
            self.db.execute("INSERT INTO action_plans VALUES (?,?,?,?,?,?,?)",
                            (plan["id"], plan["scope"], plan["mac"], event_id, timestamp(now.isoformat()),
                             "pending_review", json.dumps(plan)))
            self.audit(actor, "plan.proposed", plan["id"], plan)
        return plan

    def decide(self, plan_id, decision, actor, now=None):
        text(actor, "actor")
        now = now or utcnow()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT * FROM action_plans WHERE id=?", (plan_id,)).fetchone()
            if row is None:
                raise ValueError("unknown plan")
            plan = json.loads(row["document"])
            if decision == "reject" and row["status"] == "pending_review":
                status = "rejected"
            elif decision == "simulate" and row["status"] == "pending_review":
                if actor == plan["requester"]:
                    raise ValueError("reviewer must differ from requester")
                if now >= datetime.fromisoformat(plan["expires_at"]):
                    raise ValueError("plan expired; reject and propose again")
                asset = self._target(self.event(plan["event_id"]), plan["endpoint"], now, 600)
                if asset["vlan"] != plan["restore_vlan"] or asset["vendor"] != plan["vendor"]:
                    raise ValueError("asset configuration changed; review again")
                if plan["policy"]:
                    original = self.event(plan["event_id"])[plan["endpoint"] + "_device"].get("user")
                    current = self.store.resolve(plan["scope"], plan["ip"], now.isoformat()).get("user")
                    if current != original:
                        raise ValueError("user evidence changed")
                status = "simulated_quarantined"
            elif decision == "restore" and row["status"] == "simulated_quarantined":
                status = "simulated_restored"
            else:
                raise ValueError("invalid action transition")
            self.db.execute("UPDATE action_plans SET status=? WHERE id=?", (status, plan_id))
            self.audit(actor, "plan." + decision, plan_id,
                       {"from": row["status"], "to": status, "mode": "simulation",
                        "restore_vlan": plan["restore_vlan"]})
        return status

    def evaluate(self, policy, endpoint, vlan, actor, now=None):
        """One bounded pass; create proposals automatically, never execute quarantine."""
        validate_policy(policy)
        text(actor, "actor")
        if endpoint not in ("src", "dest"):
            raise ValueError("invalid endpoint")
        integer(vlan, "quarantine VLAN", 1, 4094)
        result = {"proposed": 0, "skipped": 0, "mode": "simulation"}
        for event in self.store.events(1000):
            try:
                self.propose(event["event_id"], endpoint, vlan, actor,
                             "Conditional policy proposal", policy=policy, now=now)
            except (ValueError, sqlite3.IntegrityError):
                result["skipped"] += 1
            else:
                result["proposed"] += 1
        return result

    def notify_active(self, channel, actor):
        count = 0
        for event in self.store.events(1000):
            if event["status"] != "closed":
                count += self.enqueue(event["event_id"], channel, actor)
        return {"queued": count, "channel": channel}

    def enqueue(self, event_id, channel, actor):
        if channel not in ("telegram", "email"):
            raise ValueError("unknown notification channel")
        event = self.event(event_id)
        body = "NAC20 | severity {severity} | {scope} | {signature}\n{event_id}".format(**event)
        # IP/MAC/user deliberately excluded from external notification bodies by default.
        with self.db:
            cursor = self.db.execute("INSERT OR IGNORE INTO outbox(event_id,channel,body) VALUES (?,?,?)",
                                     (event_id, channel, body[:4000]))
            if cursor.rowcount:
                self.audit(actor, "notification.queued", event_id, {"channel": channel})
        return bool(cursor.rowcount)

    def dispatch(self, notification_id, actor, send=False, sender=None):
        """Preview by default. No automatic retry after ambiguous transport failure."""
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT * FROM outbox WHERE id=?", (notification_id,)).fetchone()
            if row is None:
                raise ValueError("unknown notification")
            if not send:
                return {"channel": row["channel"], "body": row["body"], "status": row["status"]}
            if row["status"] != "pending":
                raise ValueError("notification already attempted; inspect receipt before any resend")
            text(actor, "actor")
            self.db.execute("UPDATE outbox SET status='sending',attempts=attempts+1 WHERE id=?", (notification_id,))
            self.audit(actor, "notification.sending", str(notification_id), {"channel": row["channel"]})
        try:
            (sender or send_notification)(row["channel"], row["body"])
        except Exception:
            # Delivery may have succeeded remotely: explicit review required, never retry silently.
            with self.db:
                self.db.execute("UPDATE outbox SET status='uncertain' WHERE id=?", (notification_id,))
                self.audit(actor, "notification.uncertain", str(notification_id), {})
            return "uncertain"
        with self.db:
            self.db.execute("UPDATE outbox SET status='sent' WHERE id=?", (notification_id,))
            self.audit(actor, "notification.sent", str(notification_id), {})
        return "sent"

    def snapshot(self):
        now = timestamp(utcnow().isoformat())
        devices = self.assets()
        for asset in devices:
            asset["bindings"] = []
            for row in self.db.execute("""SELECT DISTINCT ip FROM bindings
                    WHERE scope=? AND mac=? AND valid_from<=? AND valid_until>?""",
                    (asset["scope"], asset["mac"], now, now)):
                evidence = self.store.resolve(asset["scope"], row["ip"], now)
                asset["bindings"].append(dict(evidence, ip=row["ip"]))
        return {"generated_at": now, "mode": "simulation",
                "devices": devices, "events": self.store.events(1000),
                "plans": [dict(json.loads(row["document"]), status=row["status"])
                          for row in self.db.execute("SELECT * FROM action_plans ORDER BY created_at DESC LIMIT 1000")],
                "notifications": [dict(row) for row in self.db.execute(
                    "SELECT id,event_id,channel,status,attempts FROM outbox ORDER BY id DESC LIMIT 1000")],
                "audit": [dict(row) for row in self.db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 1000")],
                "event_transitions": [dict(row) for row in self.db.execute(
                    "SELECT * FROM transitions ORDER BY id DESC LIMIT 1000")]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect refused")


def send_notification(channel, body):
    """Only invoked by explicit dispatch --send; credentials supplied via environment."""
    if channel == "telegram":
        token, chat_id = os.environ["NAC20_TELEGRAM_TOKEN"], os.environ["NAC20_TELEGRAM_CHAT_ID"]
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            raise ValueError("invalid Telegram token")
        request = Request("https://api.telegram.org/bot" + token + "/sendMessage",
                          data=json.dumps({"chat_id": chat_id, "text": body}).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        # No user-configurable endpoint, redirects or token logging.
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            result = json.loads(response.read(65536))
        if result.get("ok") is not True:
            raise ValueError("Telegram rejected delivery")
    elif channel == "email":
        message = EmailMessage()
        message["From"] = text(os.environ["NAC20_SMTP_FROM"], "sender")
        message["To"] = text(os.environ["NAC20_SMTP_TO"], "recipient")
        message["Subject"] = "NAC20 Security alert"
        message.set_content(body)
        with smtplib.SMTP_SSL(os.environ["NAC20_SMTP_HOST"],
                              int(os.environ.get("NAC20_SMTP_PORT", "465")),
                              context=ssl.create_default_context(), timeout=10) as smtp:
            smtp.login(os.environ["NAC20_SMTP_USER"], os.environ["NAC20_SMTP_PASSWORD"])
            if smtp.send_message(message):
                raise ValueError("SMTP recipient refused")
    else:
        raise ValueError("unknown channel")


def render_dashboard(snapshot, destination):
    """Static local report: no external dependencies or inline untrusted markup."""
    template = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
    data = json.dumps(snapshot, ensure_ascii=True).replace("<", "\\u003c").replace("&", "\\u0026")
    Path(destination).write_text(template.replace("__NAC20_DATA__", data), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--actor", required=True, help="local audit label, not authenticated identity")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("assets", "inventory"):
        sub = commands.add_parser(command)
        sub.add_argument("--scope", required=True)
        sub.add_argument("--file", required=True)
    dashboard = commands.add_parser("dashboard")
    dashboard.add_argument("--out", required=True)
    commands.add_parser("snapshot")
    plan = commands.add_parser("plan")
    plan.add_argument("--event", required=True)
    plan.add_argument("--endpoint", choices=["src", "dest"], required=True)
    plan.add_argument("--vlan", type=int, required=True)
    plan.add_argument("--reason", required=True)
    plan.add_argument("--policy", help="optional explicit automatic planning policy JSON")
    evaluate = commands.add_parser("evaluate", help="create conditional proposals for up to 1000 recent events")
    evaluate.add_argument("--policy", required=True)
    evaluate.add_argument("--endpoint", choices=["src", "dest"], required=True)
    evaluate.add_argument("--vlan", type=int, required=True)
    decision = commands.add_parser("decide")
    decision.add_argument("id")
    decision.add_argument("decision", choices=["reject", "simulate", "restore"])
    queue = commands.add_parser("notify")
    queue.add_argument("--event", required=True)
    queue.add_argument("--channel", choices=["telegram", "email"], required=True)
    active = commands.add_parser("notify-active", help="queue alerts, never send automatically")
    active.add_argument("--channel", choices=["telegram", "email"], required=True)
    dispatch = commands.add_parser("dispatch")
    dispatch.add_argument("id", type=int)
    dispatch.add_argument("--send", action="store_true", help="explicitly deliver queued alert to configured recipient")
    args = parser.parse_args(argv)
    store = None
    try:
        store = Store(args.db)
        text(args.actor, "actor")
        ops = Operations(store)
        if args.command in ("assets", "inventory"):
            records = json.loads(Path(args.file).read_text(encoding="utf-8"))
            result = getattr(ops, "register" if args.command == "assets" else "inventory")(
                args.scope, records, args.actor)
        elif args.command == "dashboard":
            render_dashboard(ops.snapshot(), args.out)
            result = {"output": str(Path(args.out).resolve()), "mode": "simulation"}
        elif args.command == "snapshot":
            result = ops.snapshot()
        elif args.command == "plan":
            policy = json.loads(Path(args.policy).read_text(encoding="utf-8")) if args.policy else None
            result = ops.propose(args.event, args.endpoint, args.vlan, args.actor, args.reason, policy)
        elif args.command == "decide":
            result = ops.decide(args.id, args.decision, args.actor)
        elif args.command == "evaluate":
            policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
            result = ops.evaluate(policy, args.endpoint, args.vlan, args.actor)
        elif args.command == "notify-active":
            result = ops.notify_active(args.channel, args.actor)
        elif args.command == "notify":
            result = {"queued": ops.enqueue(args.event, args.channel, args.actor)}
        else:
            result = ops.dispatch(args.id, args.actor, args.send)
        print(json.dumps(result, ensure_ascii=True))
        return 2 if result == "uncertain" else 0
    except (ValueError, TypeError, OSError, KeyError, sqlite3.Error):
        print("Operation refused or failed; check local input and audit. No device enforcement was performed.", file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
