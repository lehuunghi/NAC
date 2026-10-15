import io
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from nac20_security import Store
from security_ops import Operations, NoRedirect, render_dashboard, send_notification
from test_security import alert, binding

NOW = datetime(2026, 10, 15, 3, 1, tzinfo=timezone.utc)


def asset(**changes):
    record = {"mac": binding()["mac"], "name": "Laptop thử nghiệm", "vendor": "mikrotik",
              "protected": False, "vlan": 20}
    record.update(changes)
    return record


def policy(**changes):
    record = {"id": "lab-rule-1", "enabled": True, "max_age_seconds": 300,
              "max_severity": 2, "max_plans_per_hour": 5, "cooldown_seconds": 600,
              "scopes": ["site"], "sensors": ["sensor"], "signature_ids": [1001]}
    record.update(changes)
    return record


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.ops = Operations(self.store)
        self.ops.inventory("site", [binding(username="lab-user")], "operator")
        self.ops.register("site", [asset()], "operator")
        self.store.ingest(alert(), "sensor", "site")
        self.event_id = self.store.events()[0]["event_id"]

    def propose(self, **kwargs):
        return self.ops.propose(self.event_id, "src", 999, "requester", "Lab test", now=NOW, **kwargs)

    def test_user_correlation_and_conflicts(self):
        self.assertEqual(self.store.events()[0]["src_device"]["user"],
                         {"state": "resolved", "username": "lab-user"})
        self.ops.inventory("site", [binding(username="user-a"), binding(username="user-b")], "operator")
        resolved = self.store.resolve("site", "10.0.0.2", NOW.isoformat())
        self.assertEqual(resolved["state"], "resolved")
        self.assertEqual(resolved["user"], {"state": "ambiguous"})

    def test_manual_propose_simulate_restore_and_audit(self):
        plan = self.propose()
        self.assertEqual(plan["restore_vlan"], 20)
        self.assertEqual(plan["mode"], "simulation")
        with self.assertRaises(ValueError):
            self.ops.decide(plan["id"], "simulate", "requester", NOW)
        self.assertEqual(self.ops.decide(plan["id"], "simulate", "reviewer", NOW), "simulated_quarantined")
        self.assertEqual(self.ops.decide(plan["id"], "restore", "reviewer", NOW), "simulated_restored")
        self.assertEqual(self.ops.assets()[0]["vlan"], 20)
        actions = [a["operation"] for a in self.ops.snapshot()["audit"]]
        self.assertIn("plan.restore", actions)
        with self.assertRaises(ValueError):
            self.ops.decide(plan["id"], "restore", "reviewer", NOW)

    def test_duplicate_active_plan_and_reject(self):
        plan = self.propose()
        with self.assertRaises(sqlite3.IntegrityError):
            self.propose()
        self.assertEqual(len(self.ops.snapshot()["plans"]), 1)
        self.ops.decide(plan["id"], "reject", "reviewer", NOW)
        self.assertTrue(self.propose()["id"])

    def test_protected_stale_closed_and_ambiguous_blocked(self):
        self.ops.register("site", [asset(protected=True)], "operator")
        with self.assertRaises(ValueError):
            self.propose()
        self.ops.register("site", [asset()], "operator")
        with self.assertRaises(ValueError):
            self.ops.propose(self.event_id, "src", 999, "requester", "Test",
                             now=NOW + timedelta(hours=1))
        self.store.transition(self.event_id, "closed", "operator")
        with self.assertRaises(ValueError):
            self.propose()

    def test_revalidation_prevents_changed_mac_protection_and_vlan(self):
        plan = self.propose()
        self.ops.inventory("site", [binding(mac="02:00:00:00:00:02", username="lab-user")], "operator")
        with self.assertRaises(ValueError):
            self.ops.decide(plan["id"], "simulate", "reviewer", NOW)
        self.ops.inventory("site", [binding(username="lab-user")], "operator")
        self.ops.register("site", [asset(vlan=30)], "operator")
        with self.assertRaises(ValueError):
            self.ops.decide(plan["id"], "simulate", "reviewer", NOW)
        self.assertEqual(self.ops.snapshot()["plans"][0]["status"], "pending_review")

    def test_plan_expiry(self):
        plan = self.propose()
        with self.assertRaises(ValueError):
            self.ops.decide(plan["id"], "simulate", "reviewer", NOW + timedelta(minutes=6))

    def test_automatic_policy_allowlists_disabled_and_user_match(self):
        for changes in ({"enabled": False}, {"scopes": []}, {"sensors": ["other"]},
                        {"signature_ids": [9]}, {"max_severity": 1}, {"max_plans_per_hour": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.propose(policy=policy(**changes))
        self.ops.inventory("site", [binding(username="new-user")], "operator")
        with self.assertRaises(ValueError):
            self.propose(policy=policy())
        self.ops.inventory("site", [binding(username="lab-user")], "operator")
        self.assertEqual(self.propose(policy=policy())["policy"], "lab-rule-1")

    def test_automatic_cooldown_and_quota_survive_rejected_requests(self):
        plan = self.propose(policy=policy())
        self.ops.decide(plan["id"], "reject", "reviewer", NOW)
        with self.assertRaises(ValueError):
            self.propose(policy=policy())
        with self.assertRaises(ValueError):
            self.propose(policy=policy(max_plans_per_hour=1))

    def test_bounded_policy_evaluation_and_idempotent_alert_queue(self):
        with self.assertRaises(ValueError):
            self.ops.evaluate(policy(enabled=False), "src", 999, "policy", NOW)
        self.assertEqual(self.ops.evaluate(policy(), "src", 999, "policy", NOW)["proposed"], 1)
        self.assertEqual(self.ops.evaluate(policy(), "src", 999, "policy", NOW)["skipped"], 1)
        self.assertEqual(self.ops.notify_active("email", "operator")["queued"], 1)
        self.assertEqual(self.ops.notify_active("email", "operator")["queued"], 0)

    def test_policy_is_validated_before_evaluating_and_rechecks_user(self):
        with self.assertRaises(ValueError):
            self.ops.evaluate(policy(signature_ids=[True]), "src", 999, "policy", NOW)
        plan = self.propose(policy=policy())
        self.ops.inventory("site", [binding(username="another-user")], "operator")
        with self.assertRaises(ValueError):
            self.ops.decide(plan["id"], "simulate", "reviewer", NOW)

    def test_atomic_inventory_audit_rollback(self):
        before = self.ops.snapshot()["audit"]
        with patch.object(self.ops, "audit", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.ops.inventory("site", [], "operator")
        self.assertEqual(self.store.resolve("site", "10.0.0.2", NOW.isoformat())["state"], "resolved")
        self.assertEqual(self.ops.snapshot()["audit"], before)

    def test_notification_preview_duplicate_and_delivery(self):
        self.assertTrue(self.ops.enqueue(self.event_id, "telegram", "operator"))
        self.assertFalse(self.ops.enqueue(self.event_id, "telegram", "operator"))
        sender = MagicMock()
        preview = self.ops.dispatch(1, "operator", sender=sender)
        sender.assert_not_called()
        self.assertNotIn("10.0.0.2", preview["body"])
        self.assertNotIn("lab-user", preview["body"])
        self.assertEqual(self.ops.dispatch(1, "operator", send=True, sender=sender), "sent")
        sender.assert_called_once()
        with self.assertRaises(ValueError):
            self.ops.dispatch(1, "operator", send=True, sender=sender)

    def test_delivery_failure_never_retries_or_leaks_secrets(self):
        self.ops.enqueue(self.event_id, "email", "operator")
        sender = MagicMock(side_effect=RuntimeError("TOKEN-secret"))
        self.assertEqual(self.ops.dispatch(1, "operator", send=True, sender=sender), "uncertain")
        with self.assertRaises(ValueError):
            self.ops.dispatch(1, "operator", send=True, sender=sender)
        self.assertNotIn("TOKEN-secret", json.dumps(self.ops.snapshot()))

    def test_html_escapes_embedded_json(self):
        self.ops.register("site", [asset(name="</script><script>alert(1)</script>")], "operator")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dashboard.html"
            render_dashboard(self.ops.snapshot(), path)
            report = path.read_text(encoding="utf-8")
            self.assertNotIn("</script><script>alert(1)", report)
            self.assertIn("\\u003c/script>", report)
            self.assertIn("textContent", report)

    def test_invalid_asset_batch_does_not_partially_apply(self):
        with self.assertRaises(ValueError):
            self.ops.register("site", [asset(name="changed"), asset(vendor="unknown")], "operator")
        self.assertEqual(self.ops.assets()[0]["name"], "Laptop thử nghiệm")


class TransportTests(unittest.TestCase):
    def test_telegram_contract_with_mock_transport(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b'{"ok":true}'
        with patch.dict(os.environ, {"NAC20_TELEGRAM_TOKEN": "123:lab_token", "NAC20_TELEGRAM_CHAT_ID": "-123"}), \
                patch("security_ops.build_opener", return_value=opener):
            send_notification("telegram", "Lab message")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.telegram.org/bot123:lab_token/sendMessage")
        self.assertEqual(json.loads(request.data), {"chat_id": "-123", "text": "Lab message"})
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test")

    def test_smtp_tls_and_no_plaintext_fallback(self):
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value.send_message.return_value = {}
        env = {"NAC20_SMTP_HOST": "smtp.example.test", "NAC20_SMTP_FROM": "nac@example.test",
               "NAC20_SMTP_TO": "soc@example.test", "NAC20_SMTP_USER": "nac", "NAC20_SMTP_PASSWORD": "secret"}
        with patch.dict(os.environ, env), patch("security_ops.smtplib.SMTP_SSL", smtp):
            send_notification("email", "Lab message")
        self.assertEqual(smtp.call_args.args, ("smtp.example.test", 465))
        smtp.return_value.__enter__.return_value.login.assert_called_once_with("nac", "secret")

    def test_schema_one_migration_preserves_events_and_bindings(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "old.db"
            db = sqlite3.connect(path)
            db.executescript("""CREATE TABLE bindings(scope TEXT,ip TEXT,mac TEXT,valid_from TEXT,
                valid_until TEXT,PRIMARY KEY(scope,ip,mac,valid_from,valid_until));
                PRAGMA user_version=1;""")
            row = binding()
            db.execute("INSERT INTO bindings VALUES (?,?,?,?,?)", ("site", row["ip"], row["mac"],
                       "2026-10-15T02:00:00.000000+00:00", "2026-10-15T04:00:00.000000+00:00"))
            db.commit()
            db.close()
            store = Store(path)
            try:
                self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertEqual(store.resolve("site", row["ip"], NOW.isoformat())["mac"], row["mac"])
                store.ingest(alert(), "sensor", "site")
            finally:
                store.close()
            store = Store(path)
            try:
                self.assertEqual(len(store.events()), 1)
                self.assertEqual(store.events()[0]["signature_id"], 1001)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
