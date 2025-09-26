import os
import re
import tempfile
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import boto3  # type: ignore
    from botocore.config import Config  # type: ignore
    
except Exception:
    boto3 = None  # type: ignore

from .config import get_settings

logger = logging.getLogger("video-analysis.s3")

FILENAME_RE = re.compile(
    r"^ScreenRecording_File_"
    r"(?P<date>\d{8})_"
    r"(?P<time>\d{6})_"
    r"vt1-"
    r"(?P<employee>[0-9a-f-]+)"
    r"(?:-(?P<platform>[^-]+)-(?P<session>[0-9a-f-]+))?" 
    r"\.webm$",
    re.IGNORECASE,
)


def _client():
    if boto3 is None:
        raise ImportError(
            "boto3 is required for S3 operations. Install it with 'pip install boto3' or 'pip install -r requirements.txt' in your active venv."
        )
    settings = get_settings()
    cfg = Config(
        region_name=settings.aws_region,
        connect_timeout=settings.s3_connect_timeout,
        read_timeout=settings.s3_read_timeout,
        retries={"max_attempts": 3, "mode": "standard"},
    )
    return boto3.client("s3", config=cfg)


def list_employees() -> List[str]:
    s = get_settings()
    client = _client()
    prefix = s.s3_prefix.rstrip("/") + "/"
    resp = client.list_objects_v2(Bucket=s.s3_bucket, Prefix=prefix, Delimiter="/")
    employees = []
    for p in resp.get("CommonPrefixes", []):
        sub = p.get("Prefix", "").rstrip("/")
        emp = sub.split("/")[-1]
        if emp:
            employees.append(emp)
    return employees


def parse_timestamp_from_filename(file_name: str) -> Optional[datetime]:
    m = FILENAME_RE.search(file_name)
    if not m:
        return None
    yyyymmdd = m.group("date")
    hhmmss = m.group("time")
    try:
        return datetime.strptime(yyyymmdd + hhmmss, "%Y%m%d%H%M%S")
    except Exception:
        return None


def extract_employee_from_filename(file_name: str) -> Optional[str]:
    m = FILENAME_RE.search(file_name)
    if not m:
        return None
    emp = m.groupdict().get("employee")
    return emp.lower() if isinstance(emp, str) else None


def list_videos_for_employee_date(employee_id: str, date_str: str) -> List[Dict]:
    s = get_settings()
    client = _client()
    base = f"{s.s3_prefix.rstrip('/')}/{employee_id}/"
    logger.info(f"Listing S3 bucket={s.s3_bucket} prefix={base} date={date_str}")
    paginator = client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=s.s3_bucket, Prefix=base)
    results: List[Dict] = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.lower().endswith(".webm"):
                continue
            fname = os.path.basename(key)
            ts = parse_timestamp_from_filename(fname)
            if not ts:
                continue
            # Optional extra guard: ensure filename's embedded employee matches folder
            embedded_emp = extract_employee_from_filename(fname)
            if embedded_emp and embedded_emp != employee_id.lower():
                continue
            if ts.strftime("%Y-%m-%d") != date_str:
                continue
            results.append(
                {
                    "key": key,
                    "file_name": fname,
                    "timestamp": ts,
                }
            )
    results.sort(key=lambda x: x["timestamp"])
    logger.info(f"Found {len(results)} videos for employee={employee_id} date={date_str}")
    return results


def download_to_tmp(key: str) -> str:
    s = get_settings()
    client = _client()
    fname = os.path.basename(key)
    tmp_path = os.path.join(tempfile.gettempdir(), fname)
    logger.info(f"Downloading s3://{s.s3_bucket}/{key} -> {tmp_path}")
    client.download_file(s.s3_bucket, key, tmp_path)
    return tmp_path


def presigned_url(key: str, expires: int = 3600) -> str:
    s = get_settings()
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": s.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )
