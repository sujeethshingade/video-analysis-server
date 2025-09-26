# Video Analysis

FastAPI-based service to process screen recording videos stored in S3 and extract structured activity events via OpenAI model analysis of sampled keyframes.

## Quick Start

Start the server (dev reload):

```bash
uvicorn app.main:app --reload --port 8000
```

Basic processing flow (replace placeholders):

```bash
# Check status (processed vs pending files) for one employee/date
curl "http://127.0.0.1:8000/status/<EMPLOYEE_ID>/<YYYY-MM-DD>"

# Process just that employee/date (skips already processed files)
curl "http://127.0.0.1:8000/process/<EMPLOYEE_ID>/<YYYY-MM-DD>"

# Force reprocess (clears processed flags for those files first)
curl -X POST "http://127.0.0.1:8000/reprocess/<EMPLOYEE_ID>/<YYYY-MM-DD>"

# Multiple employees and multiple dates (Cartesian processing)
curl "http://127.0.0.1:8000/process/empA,empB/2025-09-20,2025-09-21"
```

Open the interactive docs at: <http://127.0.0.1:8000/docs>

### Process Videos (Multiple Employees / Dates)

```text
GET /process/{employee_ids}/{dates}
```

- `employee_ids`: one or more IDs separated by commas.
- `dates`: one or more ISO dates (YYYY-MM-DD) separated by commas.

All combinations (Cartesian product) are processed in nested order: for each employee ID, iterate each date. Concretely, if you pass `empA,empB` and `2025-09-20,2025-09-21`, processing runs in this sequence:

1) empA on 2025-09-20
2) empA on 2025-09-21
3) empB on 2025-09-20
4) empB on 2025-09-21

Within each employee/date, the service lists all S3 videos for that day and processes them in timestamp order. Already-processed files are skipped unless you use the reprocess endpoint.

Example:

```text
GET /process/empA,empB/2025-09-20,2025-09-21
```

Response structure:

```json
{
  "message": "Processing finished",
  "processedCount": 5,
  "skipped": ["empA:2025-09-20:ScreenRecording_File_...webm"],
  "errors": ["empB:2025-09-21:ScreenRecording_File_...webm: <error>"] ,
  "detail": [
    {
      "employeeID": "empA",
      "date": "2025-09-20",
      "processedCount": 3,
      "skipped": ["..."],
      "errors": []
    }
  ]
}
```

### Status

```text
GET /status/{employee_id}/{date}
```

Returns processed vs pending filenames for that date.

### Reprocess (Force)

```text
POST /reprocess/{employee_id}/{date}
```

Unmarks files and processes again.

## CLI One-Shot Processing on Startup

You can trigger processing immediately for specific employees and dates when launching uvicorn:

```bash
uvicorn app.main:app -- --employee empA,empB --date 2025-09-20,2025-09-21
```

This runs each combination once. (No background scheduler.)
