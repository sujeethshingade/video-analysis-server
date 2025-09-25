import argparse
from fastapi import FastAPI

from .models import StatusResponse
from .worker import process_employee_date
from .s3_utils import list_videos_for_employee_date
from .db_utils import get_status, unmark_processed

app = FastAPI(title="Video Analysis")


@app.get("/process/{employee_id}/{date}")
def process_endpoint(employee_id: str, date: str):
    employees = [e.strip() for e in employee_id.split(",") if e.strip()]
    dates = [d.strip() for d in date.split(",") if d.strip()]
    total_processed = 0
    all_skipped = []
    all_errors = []
    detail = []
    for emp in employees:
        for dt in dates:
            res = process_employee_date(emp, dt, force=False)
            total_processed += res.get("processedCount", 0)
            # annotate skipped/errors with context
            all_skipped.extend([f"{emp}:{dt}:{f}" for f in res.get("skipped", [])])
            all_errors.extend([f"{emp}:{dt}:{err}" for err in res.get("errors", [])])
            detail.append({"employeeID": emp, "date": dt, **res})
    return {
        "message": "Processing finished",
        "processedCount": total_processed,
        "skipped": all_skipped,
        "errors": all_errors,
        "detail": detail,
    }


@app.get("/status/{employee_id}/{date}", response_model=StatusResponse)
def status_endpoint(employee_id: str, date: str):
    vids = list_videos_for_employee_date(employee_id, date)
    s3_list = [v["file_name"] for v in vids]
    return get_status(employee_id, date, s3_list)


@app.post("/reprocess/{employee_id}/{date}")
def reprocess_endpoint(employee_id: str, date: str):
    # Unmark all files for that date so they can be reprocessed
    vids = list_videos_for_employee_date(employee_id, date)
    for v in vids:
        unmark_processed(employee_id, v["file_name"])
    result = process_employee_date(employee_id, date, force=True)
    return {"message": "Reprocessing finished", "count": result.get("processedCount", 0)}


# CLI passthrough when running under uvicorn with --employee ... --date ...
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--employee", dest="employee_id", default=None)
parser.add_argument("--date", dest="date", default=None)
args, _ = parser.parse_known_args()

if args.employee_id and args.date:
    emp_list = [e.strip() for e in args.employee_id.split(",") if e.strip()]
    date_list = [d.strip() for d in args.date.split(",") if d.strip()]

    @app.on_event("startup")
    def trigger_cli_processing():
        for emp in emp_list:
            for dt in date_list:
                process_employee_date(emp, dt, force=False)
