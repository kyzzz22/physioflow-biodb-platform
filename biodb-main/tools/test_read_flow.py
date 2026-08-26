import asyncio, aiohttp, json, sys
sys.path.insert(0, '/app')
import env, p_victoria_metrics
from datetime import datetime

async def main():
    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    session = aiohttp.ClientSession(connector=connector)
    try:
        base = env.VICTORIA_METRICS_BASE_METRIC_NAME
        sel = f'{{__name__=~"{base}_(eda|ppg)", participant="7C64JubjmS5mpecsFkBTU", experimenter="sYLepkQgUlFdtpRkp3rYo"}}'
        lines = await p_victoria_metrics.fetch_vm_export_chunk(
            session=session,
            export_url=env.VICTORIA_METRICS_HOST + env.VICTORIA_METRICS_EXPORT_PATH,
            metric_selector_regex=sel,
            start_iso="2026-08-26T10:00:00+00:00",
            end_iso="2026-08-26T10:05:00+00:00",
        )
        print("fetch series_count=", len(lines))
        # 手工构造 aggregated 结构
        agg = {}
        for l in lines:
            m = l.get("metric", {})
            key = json.dumps(m, sort_keys=True)
            agg[key] = {"metric": m, "values": l.get("values", []), "timestamps": l.get("timestamps", [])}
        total = sum(len(v["timestamps"]) for v in agg.values())
        uniq = set()
        for v in agg.values():
            uniq.update(v["timestamps"])
        print(f"agg series={len(agg)} total_ts={total} unique_ts={len(uniq)}")
        fmt = p_victoria_metrics.format_vm_data_with_original_metric_names(agg, base)
        print("format time_len=", len(fmt.get("time", [])))
        cols = {k: len(v) for k, v in fmt.items() if k != "time"}
        print("format cols=", cols)
        print("time_head=", fmt["time"][:3])
        print("time_tail=", fmt["time"][-3:])
    finally:
        await session.close()

asyncio.run(main())
