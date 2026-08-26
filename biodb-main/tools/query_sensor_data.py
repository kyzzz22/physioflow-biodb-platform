"""BioDB sensor 数据查询脚本（可复用）
用法:
  python query_sensor_data.py [--start 2026-08-26T10:00:00] [--end 2026-08-26T11:02:00] [--rows eda,ppg] [--experiment exp_emotion_verify] [--api read|export]

前提:
  - 本脚本内置长期 token（scope=all），自动换取 sensor_read JWT 后经 NGINX 查询
  - --api read: /sensor/data/read（大时间窗自动分片）; 默认 export: /sensor/data/export（联合导出）
"""
import base64
import json
import sys
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:5002"
USER_ID = "sYLepkQgUlFdtpRkp3rYo"
PARTICIPANT_ID = "7C64JubjmS5mpecsFkBTU"
TOKEN = "yKyjvh6cLISaIaoik5V6hj3NUBUGeROKfD1tFexhEb8"  # scope=all 长期 token（30 天）


def parse_args():
    args = sys.argv[1:]
    kv = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            kv[args[i][2:]] = args[i + 1] if i + 1 < len(args) else ""
            i += 2
        else:
            i += 1
    return kv


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


def get_read_jwt(start, end, experiment=None):
    body = {
        "user_id": USER_ID,
        "token": TOKEN,
        "participant_id": PARTICIPANT_ID,
        "start_time": start,
        "end_time": end,
    }
    if experiment:
        body["experiment_id"] = experiment
    r = post("/auth/jwt/sensors/readjwt", body, "")
    return r["jwt"]


def main():
    kv = parse_args()
    start = kv.get("start", "2026-08-26T10:00:00")
    end = kv.get("end", "2026-08-26T11:02:00")
    rows = [r.strip() for r in kv.get("rows", "eda,ppg").split(",") if r.strip()]
    experiment = kv.get("experiment") or None
    api = kv.get("api") or "export"

    jwt = get_read_jwt(start, end, experiment)
    print(f"read JWT OK (len={len(jwt)})")

    payload = {
        "compression": "none",
        "format": "json",
        "rows": rows,
        "start_time": start,
        "end_time": end,
    }
    if experiment:
        payload["experiment_id"] = experiment

    if api == "read":
        res = post("/sensor/data/read", payload, jwt)
        raw = res.get("data")
        print("raw len:", len(raw) if raw else 0, "preview:", repr(raw[:60]) if raw else "")
        if isinstance(raw, str) and raw.strip():
            data = json.loads(base64.b64decode(raw))
        else:
            print("WARN raw data empty:", repr(raw))
            data = {}
        print("data keys:", list(data.keys()) if isinstance(data, dict) else type(data))
        for r in rows:
            pts = data.get(r) or []
            if pts:
                print(f"{r}: {len(pts)} 点  首={pts[0]}  末={pts[-1]}")
            else:
                print(f"{r}: 0 点（无数据，请检查时间窗/experiment_id）")
        print("api=read（大时间窗自动分片）")
        return

    exp = post("/sensor/data/export", payload, jwt)
    sensor = exp.get("sensor") or {}
    for r in rows:
        pts = sensor.get(r) or []
        if pts:
            print(f"{r}: {len(pts)} 点  首={pts[0]}  末={pts[-1]}")
        else:
            print(f"{r}: 0 点（无数据，请检查时间窗/experiment_id）")
    events = exp.get("events") or []
    ex = exp.get("experiment")
    print(f"events: {len(events)} 条; experiment: {'有' if ex else '无'}")


if __name__ == "__main__":
    main()
