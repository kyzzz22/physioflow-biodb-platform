"""
分析结果（analysis results）的 MongoDB 操作层。

存储位置：MongoDB `event_database.analysis_results` 集合。
文档结构：
{
  "analysis_id": str,          # 唯一 ID（自动生成 UUID）
  "model_id": str,             # 模型 ID（一次训练产生一个模型，可被多次推理引用）
  "type": str,                 # "kmeans" | "linear_regression" | "custom"
  "participant_id": str,       # 数据所有者（与 JWT participant_id 对应）
  "experiment_id": Optional[str],
  "rows": list[str],           # 参与建模的通道（读回 rows）
  "start_time": str,           # 数据时间窗（ISO8601）
  "end_time": str,
  "parameters": dict,          # 模型参数（如 KMeans centroids / 回归系数）
  "metrics": dict,             # 训练指标（如 inertia、n_clusters、n_samples）
  "result": dict,              # 训练/推理结果摘要（如标签分布、预测值）
  "created_by": str,
  "created_at": str (ISO8601)
}
"""
from datetime import datetime, timezone
from typing import Optional, Dict
import uuid

from pymongo import MongoClient

import env

client = MongoClient(host=env.MONGO_HOST, port=env.MONGO_PORT, username=env.MONGO_USER, password=env.MONGO_PASSWORD)

db = client["event_database"]
collection = db["analysis_results"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_json_dict(doc) -> Optional[dict]:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


def _generate_unique_analysis_id() -> str:
    while True:
        new_uuid = str(uuid.uuid4())
        if not collection.find_one({"analysis_id": new_uuid}):
            return new_uuid


def save_analysis(
        model_id: str,
        analysis_type: str,
        participant_id: str,
        experiment_id: Optional[str],
        rows: list,
        start_time,
        end_time,
        parameters: Dict,
        metrics: Optional[Dict],
        result: Optional[Dict],
        created_by: str,
        ) -> dict:
    """保存一次训练/推理的分析结果。返回完整文档。"""
    analysis_id = _generate_unique_analysis_id()
    doc = {
        "analysis_id": analysis_id,
        "model_id": model_id,
        "type": analysis_type,
        "participant_id": participant_id,
        "experiment_id": experiment_id,
        "rows": list(rows),
        "start_time": start_time.isoformat() if hasattr(start_time, "isoformat") else str(start_time),
        "end_time": end_time.isoformat() if hasattr(end_time, "isoformat") else str(end_time),
        "parameters": parameters,
        "metrics": metrics or {},
        "result": result or {},
        "created_by": created_by,
        "created_at": _now_iso(),
    }
    collection.insert_one(doc)
    return _to_json_dict(collection.find_one({"analysis_id": analysis_id}))


def get_analysis_by_id(analysis_id: str) -> Optional[dict]:
    return _to_json_dict(collection.find_one({"analysis_id": analysis_id}))


def get_analyses(
        participant_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        analysis_type: Optional[str] = None,
        model_id: Optional[str] = None,
        limit: int = 100,
        ) -> list[dict]:
    filter_dict = {}
    if participant_id:
        filter_dict["participant_id"] = participant_id
    if experiment_id:
        filter_dict["experiment_id"] = experiment_id
    if analysis_type:
        filter_dict["type"] = analysis_type
    if model_id:
        filter_dict["model_id"] = model_id
    cursor = collection.find(filter_dict).sort("created_at", -1).limit(int(limit))
    return [_to_json_dict(doc) for doc in cursor]


def delete_analysis(analysis_id: str) -> bool:
    result = collection.delete_one({"analysis_id": analysis_id})
    return result.deleted_count > 0
