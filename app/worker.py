import json
import os
from typing import Dict, List

from .config import get_settings
from .db_utils import is_processed, mark_processed, save_event_log
from .s3_utils import download_to_tmp, list_videos_for_employee_date
from .video_processor import extract_keyframes_every_n_seconds, get_video_duration_seconds, hms
from .gpt_processor import analyze_video_frames_to_events


def load_employee_map() -> Dict[str, Dict[str, str]]:
    base = os.path.dirname(__file__)
    path = os.path.join(base, "employee_map.json")
    if not os.path.exists(path):
        return {}

    with open(path, "r") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        normalized: Dict[str, Dict[str, str]] = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                first = v.get("First Name") or v.get("first_name") or v.get("firstName") or ""
                last = v.get("Last Name") or v.get("last_name") or v.get("lastName") or ""
                if not v.get("fullName"):
                    full = f"{str(first).strip()} {str(last).strip()}".strip()
                else:
                    full = str(v.get("fullName", "")).strip()
                team = v.get("Department") or v.get("Team") or v.get("department") or v.get("team") or v.get("group") or "Unknown"
                normalized[str(k)] = {"fullName": full or "Unknown", "team": str(team) or "Unknown"}
        return normalized

    if isinstance(raw, list):
        mapping: Dict[str, Dict[str, str]] = {}
        for row in raw:
            if not isinstance(row, dict):
                continue
            emp_id = row.get("Employee ID") or row.get("employee_id") or row.get("id")
            if not emp_id:
                continue
            emp_id = str(emp_id).strip()
            first = row.get("First Name") or row.get("first_name") or row.get("FirstName") or ""
            last = row.get("Last Name") or row.get("last_name") or row.get("LastName") or ""
            first_str = str(first).strip() if first is not None else ""
            last_str = str(last).strip() if last is not None and str(last) != "0" else ""
            full = f"{first_str} {last_str}".strip() if last_str else first_str
            dept = row.get("Department") or row.get("Team") or row.get("department") or row.get("team") or row.get("group") or "Unknown"
            team = str(dept).strip() if dept is not None else "Unknown"
            mapping[emp_id] = {"fullName": full or "Unknown", "team": team or "Unknown"}
        return mapping

    return {}


EMP_MAP = load_employee_map()

def get_employee_info(employee_id: str) -> Dict[str, str]:
    mapping = load_employee_map()
    if not isinstance(mapping, dict):
        return {"fullName": "Unknown", "team": "Unknown"}
    info = mapping.get(str(employee_id))
    if not isinstance(info, dict):
        return {"fullName": "Unknown", "team": "Unknown"}
    full = info.get("fullName") or info.get("name") or "Unknown"
    team = info.get("team") or info.get("Department") or info.get("department") or "Unknown"
    return {"fullName": str(full), "team": str(team)}


def process_employee_date(employee_id: str, date: str, force: bool = False) -> Dict:
    settings = get_settings()
    videos = list_videos_for_employee_date(employee_id, date)
    processed_count = 0
    skipped: List[str] = []
    errors: List[str] = []

    emp_info = get_employee_info(employee_id)

    for v in videos:
        fname = v["file_name"]
        if not force and is_processed(employee_id, fname):
            skipped.append(fname)
            continue
        try:
            local_path = download_to_tmp(v["key"])
            duration_sec = get_video_duration_seconds(local_path)
            duration_hms = hms(duration_sec)
            frames = extract_keyframes_every_n_seconds(local_path, n=settings.frame_interval_sec)
            events_doc = analyze_video_frames_to_events(
                filename=fname,
                duration_hms=duration_hms,
                frames=frames,
                employee_id=employee_id,
                fullname=emp_info.get("fullName", "Unknown"),
                team=emp_info.get("team", "Unknown"),
                date=date,
            )

            save_event_log(
                {
                    "fileName": fname,
                    "caseID": f"{employee_id}_{date}",
                    "employeeID": employee_id,
                    "fullName": emp_info.get("fullName", "Unknown"),
                    "team": emp_info.get("team", "Unknown"),
                    "date": date,
                    "events": events_doc.get("events", []),
                }
            )
            mark_processed(employee_id, fname)
            processed_count += 1
        except Exception as e:
            errors.append(f"{fname}: {e}")

    return {"processedCount": processed_count, "skipped": skipped, "errors": errors}
