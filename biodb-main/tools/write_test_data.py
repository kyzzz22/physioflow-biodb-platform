import json, base64, urllib.request, math, random, datetime, os

random.seed(42)
jwt = open(os.path.expandvars(r'%TEMP%\biodb_write_jwt.txt')).read().strip()
t0 = datetime.datetime(2026, 8, 26, 10, 10, 0)  # naive, 视为 UTC
fs = 10
n = 3000  # 5 分钟 @10Hz

data = []
for i in range(n):
    t = t0 + datetime.timedelta(seconds=i / fs)
    eda = 2.0 + 0.5 * math.sin(2 * math.pi * 0.1 * i / fs) + random.uniform(-0.15, 0.15)
    ppg = 60.0 + 10.0 * math.sin(2 * math.pi * 1.0 * i / fs) + random.uniform(-1.0, 1.0)
    t_str = t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond:06d}"
    data.append({"time": t_str, "eda": round(eda, 6), "ppg": round(ppg, 6)})

payload = json.dumps({"compression": "none", "format": "json", "data": base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")})
req = urllib.request.Request(
    "http://localhost:5002/sensor/data/write",
    data=payload.encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + jwt},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print("STATUS=", resp.status)
        print("BODY=", resp.read().decode()[:500])
except urllib.error.HTTPError as e:
    print("HTTPERR=", e.code, e.read().decode()[:500])
except Exception as e:
    print("EXC=", repr(e))
