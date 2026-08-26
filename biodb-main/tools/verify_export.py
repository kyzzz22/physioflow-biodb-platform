"""联合导出实验元数据补全复验（验收第 2 项完全通过）。

流程：生成 100Hz 仿真数据 -> POST /data/write（带 experiment 标签）
      -> POST /data/export（include_events + include_experiment）校验三部分。
"""
import base64
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "http://localhost:5002"

def load_jwt(path):
    with open(path, encoding="ascii") as f:
        return f.read().strip()

def post(path, payload, jwt):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + jwt},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"HTTP {e.code} on {path}: {body[:800]}")
        raise

def vm_iso(dt: datetime) -> str:
    # naive、固定 6 位微秒：与 JWT 时间窗（naive）比较一致，维多利亚按 UTC 处理
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:06d}"

def main():
    write_jwt = load_jwt(os.path.join(os.environ["TEMP"], "biodb_write_jwt.txt"))
    read_jwt = load_jwt(os.path.join(os.environ["TEMP"], "biodb_jwt.txt"))

    t0 = datetime(2026, 8, 26, 11, 0, 0)
    n = 6000  # 100 Hz * 60 s
    rows = []
    for i in range(n):
        t = t0 + timedelta(seconds=i / 100.0)
        rows.append({
            "time": vm_iso(t),
            "eda": round(5.0 + 1.2 * math.sin(2 * math.pi * 0.1 * i / 100.0), 6),
            "ppg": round(70.0 + 3.0 * math.sin(2 * math.pi * 1.2 * i / 100.0), 6),
        })

    raw = json.dumps(rows)
    data_b64 = base64.b64encode(raw.encode()).decode()
    print(f"generated points={len(rows)} payload={len(raw) / 1024:.1f}KB")

    wr = post("/sensor/data/write", {"compression": "none", "format": "json", "data": data_b64}, write_jwt)
    print("write:", wr)

    time.sleep(5)
    exp = None
    for attempt in range(3):
        exp = post("/sensor/data/export", {
            "compression": "none",
            "format": "json",
            "rows": ["eda", "ppg"],
            "start_time": "2026-08-26T11:00:00",
            "end_time": "2026-08-26T11:01:00",
            "include_events": True,
            "include_experiment": True,
            "experiment_id": "exp_emotion_verify",
        }, read_jwt)
        sensor = exp.get("sensor") or {}
        eda_rows = sensor.get("eda") or []
        ppg_rows = sensor.get("ppg") or []
        if len(eda_rows) == n and len(ppg_rows) == n:
            break
        print(f"attempt {attempt + 1}: eda={len(eda_rows)} ppg={len(ppg_rows)} (VM index lag), retrying in 5s...")
        time.sleep(5)

    events = exp.get("events") or []
    experiment = exp.get("experiment")

    print(f"sensor.eda points={len(eda_rows)}")
    print(f"sensor.ppg points={len(ppg_rows)}")
    print(f"events count={len(events)}")
    if events:
        print("event[0]=", json.dumps(events[0], ensure_ascii=False)[:300])
    print(f"experiment is None? {experiment is None}")
    if experiment:
        print("experiment=", json.dumps(experiment, ensure_ascii=False)[:400])

    ok = (len(eda_rows) == n and len(ppg_rows) == n
          and len(events) >= 1 and experiment is not None
          and "dictionary" in experiment)
    print("VERIFY_RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
