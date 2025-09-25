from datetime import datetime
from typing import Dict, List, Optional

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

from .config import get_settings


_client: Optional[MongoClient] = None

def _get_client() -> MongoClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = MongoClient(s.mongodb_uri)
    return _client


def _db():
    s = get_settings()
    return _get_client()[s.mongodb_db]


def processed_col() -> Collection:
    col = _db()["processed"]
    col.create_index([("employeeID", ASCENDING), ("fileName", ASCENDING)], unique=True)
    return col


def logs_col() -> Collection:
    return _db()["event_logs"]


def is_processed(employee_id: str, file_name: str) -> bool:
    doc = processed_col().find_one({"employeeID": employee_id, "fileName": file_name})
    return doc is not None


def mark_processed(employee_id: str, file_name: str):
    processed_col().update_one(
        {"employeeID": employee_id, "fileName": file_name},
        {"$set": {"processedAt": datetime.utcnow()}},
        upsert=True,
    )


def unmark_processed(employee_id: str, file_name: str):
    processed_col().delete_one({"employeeID": employee_id, "fileName": file_name})


def save_event_log(document: Dict):
    document["processedAt"] = datetime.utcnow()
    logs_col().insert_one(document)


def get_status(employee_id: str, date: str, s3_list: List[str]) -> Dict:
    processed_files = set(
        d["fileName"] for d in processed_col().find({"employeeID": employee_id}, {"fileName": 1, "_id": 0})
    )
    s3_set = set(s3_list)
    processed = sorted(list(s3_set & processed_files))
    pending = sorted(list(s3_set - processed_files))
    return {"employeeID": employee_id, "date": date, "processed": processed, "pending": pending}
