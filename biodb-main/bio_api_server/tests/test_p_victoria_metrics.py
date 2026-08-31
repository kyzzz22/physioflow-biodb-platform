import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import p_victoria_metrics


class VictoriaMetricsExportTests(unittest.IsolatedAsyncioTestCase):
    async def call_export(self):
        start = datetime(2026, 8, 31, tzinfo=timezone.utc)
        return await p_victoria_metrics.victoria_metrics_export_and_format_data(
            session=object(),
            base_metric_name="biodb",
            field_indices_list=["eda"],
            participant_id_val="participant",
            experimenter_id_val="experimenter",
            overall_start_dt=start,
            overall_end_dt=start + timedelta(seconds=5),
            chunk_timedelta=timedelta(seconds=5),
            export_url="http://victoria.invalid/api/v1/export",
        )

    async def test_empty_success_is_not_an_error(self):
        with patch.object(p_victoria_metrics, "fetch_vm_export_chunk", new=AsyncMock(return_value=[])):
            self.assertEqual(await self.call_export(), {"time": []})

    async def test_export_failure_is_not_misreported_as_empty_data(self):
        with patch.object(p_victoria_metrics, "fetch_vm_export_chunk", new=AsyncMock(return_value=None)):
            with self.assertRaisesRegex(
                p_victoria_metrics.VictoriaMetricsExportError,
                "VictoriaMetrics export failed",
            ):
                await self.call_export()


if __name__ == "__main__":
    unittest.main()
