import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
import json
import requests
from typing import Optional

import pandas as pd
import numpy as np


def escape_key_or_tag_value(s_val):
    return str(s_val).replace(',', '\\,').replace('=', '\\=').replace(' ', '\\ ')

def escape_string_field_value(s_val):
    return str(s_val).replace('\\', '\\\\').replace('"', '\\"')

def dataframe_to_line_protocol(df: pd.DataFrame, measurement_name, tag_columns=[]):
    """
    Pandas DataFrameをInfluxDB Line Protocolに変換する。
    DataFrameのインデックスがタイムスタンプであるか、'time'という名前の列があることを前提とする。
    """
    lines = []

    df_copy = df.copy()

    if not isinstance(df_copy.index, pd.DatetimeIndex):
        if 'time' in df_copy.columns and pd.api.types.is_datetime64_any_dtype(df_copy['time']):
            df_copy.set_index('time', inplace=True)
        else:
            raise ValueError("DataFrame index must be a DatetimeIndex or a 'time' column must exist.")

    escaped_measurement_name = escape_key_or_tag_value(measurement_name)

    field_column_names = [col for col in df_copy.columns if col not in tag_columns]

    for timestamp, row in df_copy.iterrows():
        tags = []
        for tag_col in tag_columns:
            if tag_col in row and pd.notna(row[tag_col]):
                tag_key = escape_key_or_tag_value(tag_col)
                tag_val = escape_key_or_tag_value(row[tag_col])
                tags.append(f"{tag_key}={tag_val}")
        tags_str = ",".join(tags)

        fields = []
        for field_col in field_column_names:
            if field_col not in row:
                continue
            value = row[field_col]
            if pd.isna(value):
                continue

            field_key = escape_key_or_tag_value(field_col)

            if isinstance(value, (int, np.integer)):
                fields.append(f"{field_key}={value}i")
            elif isinstance(value, (float, np.floating)):
                if np.isinf(value) or np.isnan(value):
                    continue
                fields.append(f"{field_key}={value}")
            elif isinstance(value, bool):
                fields.append(f"{field_key}={str(value).lower()}")
            else:
                str_value = escape_string_field_value(value)
                fields.append(f"{field_key}=\"{str_value}\"")
        fields_str = ",".join(fields)

        if not fields_str:
            continue

        # pandasのTimestampオブジェクトの .value はナノ秒単位の整数値を返す
        timestamp_ns = timestamp.value

        line = f"{escaped_measurement_name}"
        if tags_str:
            line += f",{tags_str}"
        line += f" {fields_str} {timestamp_ns}"
        lines.append(line)
    return "\n".join(lines)

def write_to_victoria_metrics(payload, vm_write_url, auth=None, timeout=60):
    if not payload:
        return False

    headers = {
        'Content-Type': 'text/plain; charset=utf-8'
    }
    response = requests.post(vm_write_url, data=payload.encode('utf-8'), headers=headers, auth=auth, timeout=timeout)
    response.raise_for_status()

    if response.status_code == 204:
        print("Data written to VictoriaMetrics successfully.")
        return True
    else:
        return False



async def fetch_vm_export_chunk(session, export_url, metric_selector_regex, start_iso, end_iso, request_timeout_seconds=60, auth=None):
    params = {
        'match[]': metric_selector_regex,
        'start': start_iso,
        'end': end_iso,
    }
    fetched_json_lines = []
    try:
        async with session.get(export_url, params=params, auth=auth, timeout=aiohttp.ClientTimeout(total=request_timeout_seconds)) as response:
            if response.status == 200:
                # 整块读取后按行切分：response.content 的逐行迭代有 ~8KB 行大小上限，
                # 大数据量 chunk（如 86.4s×100Hz=8640 点单行 JSON ~95KB）会抛
                # "Chunk too big" 导致读回失败，故改为 body.split 处理。
                body = await response.read()
                for line_bytes in body.split(b"\n"):
                    if line_bytes.strip():
                        try:
                            json_obj = json.loads(line_bytes.decode('utf-8'))
                            fetched_json_lines.append(json_obj)
                        except json.JSONDecodeError as e_json:
                            print(f"    JSON Decode Error in VM chunk: {line_bytes.decode('utf-8', errors='replace')[:200]} - Error: {e_json}")
                            return None
                return fetched_json_lines
            else:
                return None
    except asyncio.TimeoutError:
        return None
    except aiohttp.ClientError as e_client:
        return None
    except Exception as e_unknown:
        return None

def format_vm_data_with_original_metric_names(
    aggregated_vm_data, # perform_victoria_metrics_export_task が返すデータ
    base_metric_name: str
):
    """
    VictoriaMetricsからエクスポート・集約されたデータを指定のJSON形式に整形する。
    JSONのデータキーには元のメトリクス名 (__name__) を使用する。
    """
    if not aggregated_vm_data:
        return {"time": []}

    all_timestamps_ms_set = set()
    for series_content in aggregated_vm_data.values():
        all_timestamps_ms_set.update(series_content.get("timestamps", []))
    
    if not all_timestamps_ms_set:
        return {"time": []}

    master_timestamps_ms = sorted(list(all_timestamps_ms_set))
    time_custom_format_list = []
    for ts_ms in master_timestamps_ms:
        dt_obj_utc = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        formatted_ts_str = dt_obj_utc.strftime('%Y-%m-%dT%H:%M:%S.%f') + "Z"
        time_custom_format_list.append(formatted_ts_str)

    result_json = {"time": time_custom_format_list}
    timestamp_to_index_map = {ts: i for i, ts in enumerate(master_timestamps_ms)}

    prefix_to_remove = f"{base_metric_name}_" 

    # 收集本次读回涉及的 experiment 维度集合：
    # - 多个不同 experiment 的 series 存在同名 metric（key 相同）时，输出 key 附加 @<experiment> 后缀，避免互相覆盖（无过滤读回并集）。
    # - 仅单一 experiment（含按实验过滤读回）时保持原 key，向后兼容。
    experiment_value_set = set()
    for series_content in aggregated_vm_data.values():
        exp_val = series_content.get("metric", {}).get("experiment")
        if exp_val:
            experiment_value_set.add(exp_val)
    need_experiment_suffix = len(experiment_value_set) > 1

    for series_key, series_content in aggregated_vm_data.items():
        metric_info = series_content.get("metric", {})
        original_metric_name = metric_info.get("__name__")

        if not original_metric_name:
            continue

        if original_metric_name.startswith(prefix_to_remove):
            final_json_key = original_metric_name[len(prefix_to_remove):]
        else:
            final_json_key = original_metric_name

        if need_experiment_suffix:
            exp_val = metric_info.get("experiment")
            if exp_val:
                final_json_key = f"{final_json_key}@{exp_val}"
            
        values_for_output_col = [None] * len(master_timestamps_ms)
        series_timestamps = series_content.get("timestamps", [])
        series_values = series_content.get("values", [])
        
        for ts, val in zip(series_timestamps, series_values):
            if ts in timestamp_to_index_map:
                idx = timestamp_to_index_map[ts]
                values_for_output_col[idx] = val
        
        result_json[final_json_key] = values_for_output_col
        
    return result_json


def _parse_vm_time_ms(ts_str):
    """解析读回格式化的时间字符串（%Y-%m-%dT%H:%M:%S.%fZ）为毫秒时间戳。"""
    try:
        dt = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S.%fZ')
    except ValueError:
        dt = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%SZ')
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _format_vm_time(ts_ms):
    dt_obj_utc = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt_obj_utc.strftime('%Y-%m-%dT%H:%M:%S.%f') + "Z"


def compute_data_quality_stats(result_json: dict) -> dict:
    """
    读回格式化结果（format_vm_data_with_original_metric_names 的输出）的采集质量统计。

    对每个数据列计算：
    - points / total_points / completeness：点数、总时间点、完整率
    - min/max/mean/median/std：数值统计（忽略缺失值）
    - interval_ms：相邻实际样本时间戳间隔统计（min/max/median/mean）
    - max_gap_seconds：最大时间戳间隔（秒）
    - expected_points / estimated_missing_rate：以中位间隔为期望采样间隔的期望点数与缺失率估计
    """
    time_strs = result_json.get("time", [])
    if not time_strs:
        return {"total_points": 0, "columns": {}}

    master_timestamps_ms = [_parse_vm_time_ms(t) for t in time_strs]
    total_points = len(master_timestamps_ms)

    columns_stats = {}
    for key, values in result_json.items():
        if key == "time":
            continue

        stats = {"points": 0, "completeness": 0.0}
        present_ts_ms = []
        present_values = []
        for ts_ms, val in zip(master_timestamps_ms, values):
            if val is not None:
                present_ts_ms.append(ts_ms)
                present_values.append(float(val))
                stats["points"] += 1

        if stats["points"] == 0:
            columns_stats[key] = stats
            continue

        stats["completeness"] = round(stats["points"] / total_points, 4)
        stats["min"] = float(np.min(present_values))
        stats["max"] = float(np.max(present_values))
        stats["mean"] = float(np.mean(present_values))
        stats["median"] = float(np.median(present_values))
        stats["std"] = float(np.std(present_values))
        stats["first_ts"] = _format_vm_time(present_ts_ms[0])
        stats["last_ts"] = _format_vm_time(present_ts_ms[-1])

        if stats["points"] >= 2:
            diffs_ms = np.diff(np.array(present_ts_ms, dtype=np.int64))
            interval_stats = {
                "min": int(diffs_ms.min()),
                "max": int(diffs_ms.max()),
                "median": float(np.median(diffs_ms)),
                "mean": float(np.mean(diffs_ms)),
            }
            stats["interval_ms"] = interval_stats
            stats["max_gap_seconds"] = round(interval_stats["max"] / 1000.0, 4)

            median_interval_ms = float(np.median(diffs_ms))
            if median_interval_ms > 0:
                span_ms = present_ts_ms[-1] - present_ts_ms[0]
                expected_points = int(span_ms / median_interval_ms) + 1
                stats["expected_points"] = expected_points
                stats["estimated_missing_rate"] = (
                    round(1 - stats["points"] / expected_points, 4)
                    if expected_points > stats["points"]
                    else 0.0
                )
            else:
                stats["expected_points"] = stats["points"]
                stats["estimated_missing_rate"] = 0.0
        else:
            stats["interval_ms"] = None
            stats["max_gap_seconds"] = None
            stats["expected_points"] = stats["points"]
            stats["estimated_missing_rate"] = None

        columns_stats[key] = stats

    return {"total_points": total_points, "columns": columns_stats}


def compute_signal_features(values: list, sample_rate_hz: float) -> dict:
    """
    单通道时序的时域+频域特征（numpy 实现，无 scipy 依赖）。

    返回特征字典：
    - 时域：count/mean/std/var/min/max/median/rms/peak_to_peak/zero_crossing_rate/
      mean_abs_slope/skewness/kurtosis/hjorth_activity/hjorth_mobility/hjorth_complexity
    - 频域：dominant_freq_hz/dominant_power/band_energy_ratio（delta/theta/alpha/beta 定义见下）
    - 缺失处理：忽略 None；不足 2 个有效点时频域/派生特征为 null
    """
    arr = np.asarray([float(v) for v in values if v is not None], dtype=np.float64)
    features = {"count": int(len(arr))}

    if len(arr) == 0:
        features.update({
            "mean": None, "std": None, "var": None, "min": None, "max": None,
            "median": None, "rms": None, "peak_to_peak": None,
            "zero_crossing_rate": None, "mean_abs_slope": None,
            "skewness": None, "kurtosis": None,
            "hjorth_activity": None, "hjorth_mobility": None, "hjorth_complexity": None,
            "dominant_freq_hz": None, "dominant_power": None, "band_energy_ratio": None,
        })
        return features

    features["mean"] = float(np.mean(arr))
    features["std"] = float(np.std(arr))
    features["var"] = float(np.var(arr))
    features["min"] = float(np.min(arr))
    features["max"] = float(np.max(arr))
    features["median"] = float(np.median(arr))
    features["rms"] = float(np.sqrt(np.mean(arr ** 2)))
    features["peak_to_peak"] = float(np.max(arr) - np.min(arr))

    if len(arr) >= 2:
        # 过零率：信号跨越零点的比例
        if features["mean"] != 0:
            centered = arr - features["mean"]
        else:
            centered = arr
        zc = np.sum((centered[:-1] <= 0) & (centered[1:] > 0)) + np.sum((centered[:-1] >= 0) & (centered[1:] < 0))
        features["zero_crossing_rate"] = float(zc / (len(arr) - 1))
        features["mean_abs_slope"] = float(np.mean(np.abs(np.diff(arr))))
        # 偏度/峰度（样本无偏估计）
        n = len(arr)
        m2 = np.mean((arr - features["mean"]) ** 2)
        m3 = np.mean((arr - features["mean"]) ** 3)
        m4 = np.mean((arr - features["mean"]) ** 4)
        g1 = (np.sqrt(n * (n - 1)) / (n - 2)) * (m3 / (m2 ** 1.5)) if m2 > 0 else None
        g2 = ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * (m4 / (m2 ** 2) - 3) + 6) if m2 > 0 and n > 3 else None
        features["skewness"] = float(g1) if g1 is not None else None
        features["kurtosis"] = float(g2) if g2 is not None else None
        # Hjorth 参数（基于一阶/二阶差分）
        diff1 = np.diff(arr)
        diff2 = np.diff(diff1)
        activity = float(np.var(arr))
        mobility = float(np.sqrt(np.var(diff1) / activity)) if activity > 0 else None
        complexity = float(np.sqrt(np.var(diff2) / np.var(diff1)) / mobility) if (mobility and np.var(diff1) > 0) else None
        features["hjorth_activity"] = activity
        features["hjorth_mobility"] = mobility
        features["hjorth_complexity"] = complexity
    else:
        features["zero_crossing_rate"] = None
        features["mean_abs_slope"] = None
        features["skewness"] = None
        features["kurtosis"] = None
        features["hjorth_activity"] = None
        features["hjorth_mobility"] = None
        features["hjorth_complexity"] = None

    # 频域特征：仅当采样率有效且点数足够（>=4 个点可做 FFT）
    fs = max(sample_rate_hz, 1.0)
    if len(arr) >= 4:
        fft_vals = np.fft.rfft(arr - features["mean"])
        freqs = np.fft.rfftfreq(len(arr), d=1.0 / fs)
        power = np.abs(fft_vals) ** 2
        power[0] = 0  # 忽略 DC 分量
        if power.sum() > 0:
            dominant_idx = int(np.argmax(power))
            features["dominant_freq_hz"] = float(freqs[dominant_idx])
            features["dominant_power"] = float(power[dominant_idx])
            total_power = float(power.sum())
            # 频带能量占比：delta(0.5-4Hz)/theta(4-8)/alpha(8-13)/beta(13-30)/gamma(30-50)
            band_ranges = {
                "delta": (0.5, 4.0),
                "theta": (4.0, 8.0),
                "alpha": (8.0, 13.0),
                "beta": (13.0, 30.0),
                "gamma": (30.0, 50.0),
            }
            band_energy = {}
            for band_name, (lo, hi) in band_ranges.items():
                mask = (freqs >= lo) & (freqs < hi)
                band_energy[band_name] = float(power[mask].sum() / total_power) if mask.any() else 0.0
            features["band_energy_ratio"] = band_energy
        else:
            features["dominant_freq_hz"] = None
            features["dominant_power"] = None
            features["band_energy_ratio"] = None
    else:
        features["dominant_freq_hz"] = None
        features["dominant_power"] = None
        features["band_energy_ratio"] = None

    return features


def compute_feature_stats(result_json: dict, default_sample_rate_hz: float = 100.0) -> dict:
    """
    读回格式化结果（format_vm_data_with_original_metric_names 输出）的逐通道特征统计。

    返回：{total_points, columns: {channel: {...features}}, sample_rate_hz}
    - sample_rate_hz 由 interval_ms 中位值推算（1000/median_interval_ms）；推算失败用默认值。
    """
    time_strs = result_json.get("time", [])
    if not time_strs:
        return {"total_points": 0, "columns": {}, "sample_rate_hz": default_sample_rate_hz}

    master_timestamps_ms = [_parse_vm_time_ms(t) for t in time_strs]
    total_points = len(master_timestamps_ms)

    sample_rate_hz = default_sample_rate_hz
    if total_points >= 2:
        diffs_ms = np.diff(np.array(master_timestamps_ms, dtype=np.int64))
        median_interval_ms = float(np.median(diffs_ms))
        if median_interval_ms > 0:
            sample_rate_hz = round(1000.0 / median_interval_ms, 4)

    columns_features = {}
    for key, values in result_json.items():
        if key == "time":
            continue
        columns_features[key] = compute_signal_features(values, sample_rate_hz)

    return {
        "total_points": total_points,
        "columns": columns_features,
        "sample_rate_hz": sample_rate_hz,
    }


async def victoria_metrics_export_and_format_data(
    session: aiohttp.ClientSession,
    base_metric_name: str,
    field_indices_list: list[str],
    participant_id_val: str,
    experimenter_id_val: str,
    overall_start_dt: datetime,
    overall_end_dt: datetime,
    chunk_timedelta: timedelta,
    export_url: str,
    experiment_id_val: Optional[str] = None
):
    
    field_regex_part = "|".join(field_indices_list)
    metric_name_regex = f"{base_metric_name}_({field_regex_part})"
    tmp_str = f'__name__=~"{metric_name_regex}", participant="{participant_id_val}", experimenter="{experimenter_id_val}"'
    if experiment_id_val:
        tmp_str += f', experiment="{experiment_id_val}"'
    selector_for_all_fields = f'{{{tmp_str}}}'

    current_start_dt = overall_start_dt
    task_successful = True
    aggregated_series_data = {}

    def _to_vm_iso(dt: datetime) -> str:
        """转为带 UTC 时区的 ISO 字符串，避免动态分片产生的小数秒无时区时间（如 00:01:26.400000）被 Victoria export 拒绝。"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    while current_start_dt < overall_end_dt:
        current_end_dt = min(current_start_dt + chunk_timedelta, overall_end_dt)
        start_iso_for_chunk = _to_vm_iso(current_start_dt)
        end_iso_for_chunk = _to_vm_iso(current_end_dt)
        
        chunk_json_lines = await fetch_vm_export_chunk(
            session=session,
            export_url=export_url,
            metric_selector_regex=selector_for_all_fields, 
            start_iso=start_iso_for_chunk, 
            end_iso=end_iso_for_chunk
        )
        
        if chunk_json_lines is None: 
            task_successful = False
            break 
        
        for series_in_chunk in chunk_json_lines:
            metric_info = series_in_chunk.get("metric", {})
            metric_key = json.dumps(metric_info, sort_keys=True)
            
            if metric_key not in aggregated_series_data:
                aggregated_series_data[metric_key] = {
                    "metric": metric_info,
                    "values": [],
                    "timestamps": []
                }
            aggregated_series_data[metric_key]["values"].extend(series_in_chunk.get("values", []))
            aggregated_series_data[metric_key]["timestamps"].extend(series_in_chunk.get("timestamps", []))

        if current_end_dt >= overall_end_dt:
            break 
        current_start_dt = current_end_dt
    
    formatted_json_output = None
    if task_successful and aggregated_series_data:
        try:
            # 新しいフォーマット関数を呼び出す
            formatted_json_output = format_vm_data_with_original_metric_names(
                aggregated_series_data,
                base_metric_name
            )
        except Exception as e_format:
            task_successful = False
    elif task_successful and not aggregated_series_data:
        formatted_json_output = {"time": []} # データキーも空になる

    return formatted_json_output