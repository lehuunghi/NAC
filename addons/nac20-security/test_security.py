import io
import json
import tempfile
import unittest
from pathlib import Path

from nac20_security import MAX_LINE, Store, ingest_file, main, normalize


def alert(**changes):
    event = {"event_type": "alert", "timestamp": "2026-10-15T10:00:00+07:00",
             "src_ip": "10.0.0.2", "dest_ip": "203.0.113.10", "src_port": 12345,
             "dest_port": 443, "proto": "TCP", "flow_id": 123,
             "alert": {"signature_id": 1001, "signature": "LAB alert", "severity": 2}}
    event.update(changes)
    return event


def binding(**changes):
    row = {"ip": "10.0.0.2", "mac": "02:00:00:00:00:01",
           "valid_from": "2026-10-15T02:00:00Z", "valid_until": "2026-10-15T04:00:00Z"}
    row.update(changes)
    return row


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)

    def test_normalization_and_privacy(self):
        event = normalize(alert(payload="secret", http={"authorization": "secret"}), "sensor", "site")
        self.assertEqual(event["occurred_at"], "2026-10-15T03:00:00.000000+00:00")
        self.assertNotIn("secret", json.dumps(event))
        self.assertEqual(event["mode"], "observe")
        self.assertIsNone(normalize({"event_type": "stats"}, "sensor", "site"))

    def test_replay_scope_sensor_and_timestamp_identity(self):
        self.assertEqual(self.store.ingest(alert(), "a", "site"), "inserted")
        self.assertEqual(self.store.ingest(alert(timestamp="2026-10-15T03:00:00Z"), "a", "site"), "duplicate")
        for sensor, scope in [("b", "site"), ("a", "other")]:
            self.assertEqual(self.store.ingest(alert(), sensor, scope), "inserted")
        self.assertEqual(len(self.store.events()), 3)

    def test_temporal_resolution_and_conflict(self):
        self.store.replace_inventory("site", [binding()])
        at = "2026-10-15T03:00:00Z"
        self.assertEqual(self.store.resolve("site", "10.0.0.2", at)["state"], "resolved")
        self.assertEqual(self.store.resolve("other", "10.0.0.2", at)["state"], "unresolved")
        self.assertEqual(self.store.resolve("site", "10.0.0.2", "2026-10-15T04:00:00Z")["state"], "unresolved")
        self.store.replace_inventory("site", [binding(), binding(mac="02:00:00:00:00:02")])
        self.assertEqual(self.store.resolve("site", "10.0.0.2", at), {"state": "ambiguous"})

    def test_ip_reassignment_and_ipv6(self):
        self.store.replace_inventory("site", [binding(valid_until="2026-10-15T03:00:00Z"),
            binding(mac="02:00:00:00:00:02", valid_from="2026-10-15T03:00:00Z"),
            binding(ip="2001:db8::1")])
        self.assertEqual(self.store.resolve("site", "10.0.0.2", "2026-10-15T03:00:00Z")["mac"], "02:00:00:00:00:02")
        self.assertEqual(self.store.resolve("site", "2001:db8:0::1", "2026-10-15T03:00:00Z")["state"], "resolved")

    def test_snapshot_atomicity_and_scope(self):
        self.store.replace_inventory("site", [binding()])
        self.store.replace_inventory("other", [binding()])
        with self.assertRaises(ValueError):
            self.store.replace_inventory("site", [binding(), binding(mac="ff:ff:ff:ff:ff:ff")])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM bindings").fetchone()[0], 2)
        self.store.replace_inventory("site", [])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM bindings").fetchone()[0], 1)

    def test_enrichment_is_evidence_at_ingestion_and_never_guesses_remote(self):
        self.store.replace_inventory("site", [binding()])
        self.store.ingest(alert(), "a", "site")
        event = self.store.events()[0]
        self.assertEqual(event["src_device"]["mac"], binding()["mac"])
        self.assertEqual(event["dest_device"], {"state": "unresolved"})
        self.store.replace_inventory("site", [])
        self.assertEqual(self.store.ingest(alert(), "a", "site"), "duplicate")
        self.assertEqual(self.store.events()[0], event)

    def test_malformed_alerts(self):
        records = [[], alert(timestamp="2026-10-15T03:00:00"), alert(src_ip="bad"),
                   alert(src_port=True), alert(src_ip=123), alert(src_ip="fe80::1%eth0"),
                   alert(alert=[]), alert(proto="TCP\n"),
                   alert(alert={"signature_id": True, "signature": "x", "severity": 1}),
                   alert(alert={"signature_id": 1, "signature": "x", "severity": 0})]
        for record in records:
            with self.subTest(record=record), self.assertRaises((ValueError, TypeError)):
                self.store.ingest(record, "a", "site")
        self.assertEqual(self.store.events(), [])

    def test_bounded_ingestion_partial_and_replay(self):
        record = json.dumps(alert()).encode() + b"\n"
        stream = io.BytesIO(b"{bad}\n" + b"x" * (MAX_LINE + 10) + b"\n" + record + b"{}")
        counts = ingest_file(self.store, stream, "a", "site")
        self.assertEqual(counts, dict(inserted=1, duplicate=0, ignored=0, rejected=2, incomplete=1))
        self.assertEqual(ingest_file(self.store, io.BytesIO(record), "a", "site")["duplicate"], 1)

    def test_lifecycle_audit_and_invalid_transition_rollback(self):
        self.store.ingest(alert(), "a", "site")
        event_id = self.store.events()[0]["event_id"]
        self.store.transition(event_id, "acknowledged", "operator")
        self.store.transition(event_id, "closed", "operator")
        with self.assertRaises(ValueError):
            self.store.transition(event_id, "acknowledged", "operator")
        self.assertEqual(self.store.events()[0]["status"], "closed")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM transitions").fetchone()[0], 2)

    def test_persistence_and_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            db, file = Path(temp) / "security.db", Path(temp) / "eve.json"
            file.write_text(json.dumps(alert()) + "\n", encoding="utf-8")
            args = ["--db", str(db), "ingest", "--scope", "site", "--sensor", "a", "--file", str(file)]
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args), 0)
            store = Store(db)
            try:
                self.assertEqual(len(store.events()), 1)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
