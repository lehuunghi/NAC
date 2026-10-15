"""Build a disposable local dashboard using synthetic data, with no network calls."""
import argparse
from datetime import timedelta

from nac20_security import Store
from security_ops import Operations, render_dashboard, utcnow


def generate(destination):
    store = Store(":memory:")
    try:
        ops = Operations(store)
        now = utcnow()
        bindings, assets = [], []
        vendors = ("mikrotik", "fortigate", "ruijie")
        for index in range(1, 4):
            mac = f"02:00:00:00:00:{index:02d}"
            bindings.append({"ip": f"10.20.0.{index}", "mac": mac, "username": f"lab-user-{index}",
                             "valid_from": (now - timedelta(hours=1)).isoformat(),
                             "valid_until": (now + timedelta(hours=1)).isoformat()})
            assets.append({"mac": mac, "name": f"Laptop Lab {index:02d}", "vlan": 20,
                           "vendor": vendors[index - 1], "protected": index == 2})
        ops.register("lab", assets, "lab-admin")
        ops.inventory("lab", bindings, "lab-import")
        signatures = ("LAB · Kết nối tới đích cần kiểm tra", "LAB · Dò quét cổng",
                      "LAB · Mẫu truy vấn DNS bất thường", "LAB · Thử kết nối lặp lại")
        ids = []
        for index, signature in enumerate(signatures):
            store.ingest({"event_type": "alert", "timestamp": (now - timedelta(seconds=20 + index)).isoformat(),
                          "src_ip": f"10.20.0.{index % 3 + 1}", "dest_ip": "203.0.113.10",
                          "src_port": 50100 + index, "dest_port": 443, "proto": "TCP", "flow_id": index,
                          "alert": {"signature_id": 1001 + index, "signature": signature,
                                    "severity": index % 3 + 1}}, "lab-sensor-01", "lab")
            ids.append(store.events()[0]["event_id"] if index == 0 else next(
                e["event_id"] for e in store.events() if e["signature_id"] == 1001 + index))
        plan = ops.propose(ids[0], "src", 999, "lab-analyst", "Kiểm tra quy trình cách ly", now=now)
        ops.decide(plan["id"], "simulate", "lab-reviewer", now)
        ops.decide(plan["id"], "restore", "lab-reviewer", now)
        ops.propose(ids[2], "src", 999, "lab-analyst", "Chờ rà soát bằng chứng", now=now)
        ops.enqueue(ids[0], "telegram", "lab-analyst")
        ops.enqueue(ids[0], "email", "lab-analyst")
        store.transition(ids[0], "acknowledged", "lab-analyst")
        store.transition(ids[1], "closed", "lab-analyst")
        render_dashboard(ops.snapshot(), destination)
    finally:
        store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    generate(parser.parse_args().out)
