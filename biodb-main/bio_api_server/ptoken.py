from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from pymongo import MongoClient

import env

client = MongoClient(host=env.MONGO_HOST, port=env.MONGO_PORT, username=env.MONGO_USER, password=env.MONGO_PASSWORD)

db = client["auth_database"]
tokens_collection = db["tokens"]

def create_token(user_id: str, scopes: list[str], expiration_days: int, description: str) -> str:
    for _ in range(10):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        existing = tokens_collection.find_one({"token_id": token_hash})

        if existing:
            continue

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expiration_days)
        token_data = {
            "user_id": user_id,
            "token_id": token_hash,
            "created_at": now,
            "expired_at": expires_at,
            "scopes": scopes,
            "is_active": True,
            "description": description
        }
        tokens_collection.insert_one(token_data)
        return raw_token
    raise Exception("Unable to generate a unique token")

def update_token(token_id: str, is_active: bool, user_id: str) -> bool:
    token_data = tokens_collection.find_one({"token_id": token_id})
    if token_data:
        if token_data["user_id"] == user_id:
            tokens_collection.update_one({"token_id": token_id}, {"$set": {"is_active": is_active}})
            return True
        else:
            return False
    else:
        return False

def delete_token(token_id: str, user_id: str) -> bool:
    token_data = tokens_collection.find_one({"token_id": token_id})
    if token_data:
        if token_data["user_id"] == user_id:
            tokens_collection.delete_one({"token_id": token_id})
            return True
        else:
            return False
    else:
        return False

def check_token(raw_token: str, user_id: str) -> bool:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_data = tokens_collection.find_one({"token_id": token_hash})
    if token_data:
        if token_data["user_id"] == user_id:
            if token_data["expired_at"].astimezone(timezone.utc) > datetime.now(timezone.utc):
                return True
            return False
        else:
            return False
    else:
        return False

def get_token_scope(raw_token: str):
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_data = tokens_collection.find_one({"token_id": token_hash})
    return token_data["scopes"]

def get_token_list(user_id: str) -> list[dict]:
    return list(tokens_collection.find({"user_id": user_id}, {"_id": 0}))