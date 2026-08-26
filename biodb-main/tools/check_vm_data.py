import urllib.request, json, urllib.parse
from datetime import datetime, timezone

base = 'http://victoria:8428'
sel = '{participant="7C64JubjmS5mpecsFkBTU",experimenter="sYLepkQgUlFdtpRkp3rYo"}'
u = base + '/api/v1/export?match[]=' + urllib.parse.quote(sel) + '&start=2026-08-26T00:00:00Z&end=2026-08-27T00:00:00Z'
r = urllib.request.urlopen(u, timeout=20)
data = r.read().decode().strip()
lines = data.splitlines()
print('series_lines=', len(lines))
for l in lines:
    obj = json.loads(l)
    ts = obj.get('timestamps') or []
    vals = obj.get('values') or []
    m = obj.get('metric', {})
    t0 = datetime.fromtimestamp(ts[0] / 1000, tz=timezone.utc).isoformat() if ts else None
    t1 = datetime.fromtimestamp(ts[-1] / 1000, tz=timezone.utc).isoformat() if ts else None
    print(f'metric={m.get("__name__")} exp={m.get("experiment")} points={len(ts)} range={t0} ~ {t1} first_vals={vals[:5]}')
