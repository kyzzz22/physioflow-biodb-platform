import base64, json, sys
import pandas as pd
from datetime import datetime
sys.path.insert(0, '/app')
from sensor_server import decompress_and_parse

data = []
for i in range(3):
    t = datetime(2026, 8, 26, 10, 10, 0) + pd.Timedelta(seconds=i * 0.1)
    data.append({"time": t.isoformat(), "eda": 1.0 + i * 0.1, "ppg": 60.0 + i})
raw = json.dumps(data)
print("RAW=", raw[:200])
parsed = decompress_and_parse(data_b64=base64.b64encode(raw.encode()).decode(), compression="none", format="json")
print("PARSED type=", type(parsed), "len=", len(parsed))
df = pd.DataFrame(parsed)
df["time"] = pd.to_datetime(df["time"])
print("TIME dtype=", df["time"].dtype)
print("TIME values=", df["time"].tolist())
s = datetime.fromisoformat("2026-08-25T00:00:00")
e = datetime.fromisoformat("2026-08-27T00:00:00")
print("range check=", ((df["time"] >= s) & (df["time"] <= e)).tolist())
