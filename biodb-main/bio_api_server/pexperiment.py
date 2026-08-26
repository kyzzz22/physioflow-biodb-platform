"""
实验（experiment）注册表 + 数据字典（dictionary）的 MongoDB 操作层。

存储位置：MongoDB `event_database.experiments` 集合。
文档结构：
{
  "experiment_id": str,        # 唯一 ID（可指定或自动生成 UUID）
  "name": str,                 # 实验唯一名称（时序/事件写入时使用的 experiment 标签值）
  "label": Optional[str],      # 人类可读标签
  "description": Optional[str],
  "dictionary": dict,          # 数据字典：通道名 -> 定义（label/unit/type 等）
  "created_by": str,
  "created_at": str (ISO8601),
  "updated_at": str (ISO8601)
}
"""
from datetime import datetime, timezone
from typing import Optional, Dict
import uuid

from pymongo import MongoClient

import env

client = MongoClient(host=env.MONGO_HOST, port=env.MONGO_PORT, username=env.MONGO_USER, password=env.MONGO_PASSWORD)

db = client["event_database"]
collection = db["experiments"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_json_dict(doc) -> Optional[dict]:
    """将 Mongo 文档转换为纯 JSON 字典（剔除 _id、日期序列化）。"""
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


def _generate_unique_experiment_id() -> str:
    while True:
        new_uuid = str(uuid.uuid4())
        if not collection.find_one({"experiment_id": new_uuid}):
            return new_uuid


def is_name_taken(name: str, exclude_experiment_id: Optional[str] = None) -> bool:
    """检查实验名称是否已被占用（可选排除指定实验）。"""
    query = {"name": name}
    if exclude_experiment_id:
        query["experiment_id"] = {"$ne": exclude_experiment_id}
    return collection.find_one(query) is not None


def create_experiment(
        name: str,
        label: Optional[str],
        description: Optional[str],
        dictionary: Optional[Dict],
        created_by: str,
        experiment_id: Optional[str] = None,
        ) -> dict:
    """创建实验。name 必须唯一；experiment_id 不提供时自动生成。"""
    if experiment_id:
        if collection.find_one({"experiment_id": experiment_id}):
            raise ValueError("Experiment ID already exists")
    else:
        experiment_id = _generate_unique_experiment_id()

    now = _now_iso()
    doc = {
        "experiment_id": experiment_id,
        "name": name,
        "label": label,
        "description": description,
        "dictionary": dictionary or {},
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    collection.insert_one(doc)
    return _to_json_dict(collection.find_one({"experiment_id": experiment_id}))


def get_experiment_by_id(experiment_id: str) -> Optional[dict]:
    return _to_json_dict(collection.find_one({"experiment_id": experiment_id}))


def get_experiment_by_name(name: str) -> Optional[dict]:
    return _to_json_dict(collection.find_one({"name": name}))


def get_experiments() -> list[dict]:
    cursor = collection.find({}).sort("created_at", 1)
    return [_to_json_dict(doc) for doc in cursor]


def update_experiment(experiment_id: str, data: dict) -> Optional[dict]:
    """更新实验字段（仅更新传入的键）。返回更新后的文档；实验不存在返回 None。"""
    if not data:
        return get_experiment_by_id(experiment_id)
    data = dict(data)
    data["updated_at"] = _now_iso()
    result = collection.update_one({"experiment_id": experiment_id}, {"$set": data})
    if result.matched_count == 0:
        return None
    return _to_json_dict(collection.find_one({"experiment_id": experiment_id}))


def delete_experiment(experiment_id: str) -> bool:
    result = collection.delete_one({"experiment_id": experiment_id})
    return result.deleted_count > 0


def get_experiment_dictionary(experiment_id: str) -> Optional[Dict]:
    doc = collection.find_one({"experiment_id": experiment_id})
    if doc is None:
        return None
    return doc.get("dictionary") or {}


def update_experiment_dictionary(experiment_id: str, dictionary: Dict) -> Optional[dict]:
    """整体替换数据字典。返回更新后的文档；实验不存在返回 None。"""
    result = collection.update_one(
        {"experiment_id": experiment_id},
        {"$set": {"dictionary": dictionary, "updated_at": _now_iso()}},
    )
    if result.matched_count == 0:
        return None
    return _to_json_dict(collection.find_one({"experiment_id": experiment_id}))
