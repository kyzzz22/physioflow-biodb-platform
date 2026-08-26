from datetime import datetime
from typing import Optional
import uuid

from pymongo import MongoClient

import env
import pvalid

client = MongoClient(host=env.MONGO_HOST, port=env.MONGO_PORT, username=env.MONGO_USER, password=env.MONGO_PASSWORD)

db = client["event_database"]
collection = db["events"]

def _generate_uuid():
    return str(uuid.uuid4())

def _generate_unique_event_id():
    while True:
        new_uuid = _generate_uuid()
        if not collection.find_one({"event_id": new_uuid}):
            return new_uuid

def create_event(
        start_time: datetime,
        end_time: Optional[datetime],
        user_id: str,
        event: str,
        description: Optional[str],
        details: Optional[dict],
        created_by: str,
        experiment_id: Optional[str] = None
        ) -> str:
    event_id = _generate_unique_event_id()
    event_data = pvalid.EventData(event_id=event_id,
                                  user_id=user_id,
                                  start_time=start_time,
                                  end_time=end_time,
                                  event=event,
                                  description=description,
                                  details=details,
                                  experiment_id=experiment_id,
                                  created_by=created_by
                                  ).model_dump()
    collection.insert_one(event_data)
    return event_id

def get_event_by_event_id(event_id: str) -> pvalid.EventData:
    return pvalid.EventData.model_validate(collection.find_one({"event_id": event_id}))

def get_events(
        user_id: Optional[str] = None,
        event: Optional[str] = None,
        description: Optional[str] = None,
        created_user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        experiment_id: Optional[str] = None
        ) -> list[pvalid.EventData]:
    filter_dict = dict()
    if user_id:
        filter_dict["user_id"] = user_id
    if event:
        filter_dict["event"] = event
    if description:
        filter_dict["description"] = description
    if created_user_id:
        filter_dict["created_by"] = created_user_id
    if experiment_id:
        filter_dict["experiment_id"] = experiment_id
    if start_time:
        filter_dict["start_time"] = {"$gte": start_time}
    if end_time:
        filter_dict["end_time"] = {"$lte": end_time}
    event_cursor = collection.find(filter_dict)
    return [pvalid.EventData.model_validate(event).model_dump(mode="json") for event in event_cursor]

def update_event(event_data: pvalid.EventData):
    """
    権限周りは呼び出し側の責任
    """
    operation = {"$set": event_data.model_dump()}
    return collection.update_one({"event_id": event_data.event_id}, operation)

def delete_event(event_id: str):
    """
    権限周りは呼び出し側の責任
    """
    return collection.delete_one({"event_id": event_id})