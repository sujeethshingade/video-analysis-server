import json
from typing import Dict, List, Tuple
import base64
from openai import OpenAI

from .config import get_settings
from .video_processor import hms


client = None

def _get_client():
    global client
    if client is None:
        client = OpenAI(api_key=get_settings().openai_api_key)
    return client


def analyze_frame(frame_path: str, timestamp: int) -> str:
    s = get_settings()
    if not s.vision_enabled:
        return f"At {hms(timestamp)}, the screen shows an application window with typical work UI elements."
    try:
        with open(frame_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"
        cl = _get_client()
        msg = [
            {"role": "system", "content": "Describe this image in detail focusing on work activity."},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": f"Analyze this video frame at ({timestamp}). Describe: 1) Main subjects/people and their actions, 2) Key objects and environment, 3) Text/graphics visible, 4) Overall scene context. Be specific and concise about what tasks or activities are being performed."},
                    {"type": "input_image", "image_url": data_url},
                ],
            },
        ]
        completion = cl.chat.completions.create(model=s.openai_model, messages=msg, temperature=0.2, max_tokens=200)
        return completion.choices[0].message.content or "No description"
    except Exception:
        return f"At {hms(timestamp)}, the screen shows an application window with typical work UI elements."


def build_instruction(filename: str, videolink: str, duration_hms: str, transcript_block: str, employee_id: str, fullname: str, team: str, date: str) -> str:
    instruction = f"""
Role: You are an AI analyst converting screen recordings of employee work sessions into a fine-grained, process-mining event log. Employees belong to different teams.
INPUTS:
- Video file: {filename}
- Video preview link: {videolink}
- Video duration: {duration_hms}
- Transcript: {transcript_block}
- EmployeeID: {employee_id}
- FullName: {fullname}
- Team: {team}
- Date: {date}
OBJECTIVES (must do all):
1. Produce a chronological event log of what the employee did during this {duration_hms} session, with multiple rows (one per detected event).
2. Each row must capture:
     - What happened (activities, tools, files, details).
     - When it happened (real timestamps: StartTime, EndTime, Duration_Min).
     - How it happened (rework, exceptions, switches, idle).
     - So what (value vs waste, AI automation potential).
3. Work unsupervised: infer activities and generic stages without relying on a fixed taxonomy. If unsure, label as "Unknown" and lower confidence.
SEGMENTATION RULES:
- Default block size: 2–10 minutes.
- Split events when ANY of these occur:
    * Active window/app change (Excel → PDF → Browser).
    * File/document change (different workbook, new filename).
    * Action mode change (typing → scrolling → copy/paste → refresh).
    * Idle > 5 minutes (mark event as "Idle", IdleTime_Flag=Yes).
- Merge micro-bursts <60s into adjacent event if same app/context; else keep as MicroTask_Flag=Yes.
- Events must strictly follow chronological order.
FIELDS TO POPULATE PER EVENT:
- CaseID: Unique session ID (EmployeeID + Date).
- EmployeeID: {employee_id}
- Team: {team}
- Date: {date}
- StartTime / EndTime: Real timestamps within the video (or "Unknown" if ambiguous).
- DurationMin: Duration in minutes for this event.
- StageSequenceID: Strictly increasing integer sequence for the session.
- ActivityName: Standardized, short (e.g., "Variance Analysis", "Journal Draft", "Email Thread", "Spreadsheet Cleanup", "Idle", "Unknown").
- ActivityDetail: 2–3 lines describing what exactly happened.
- ProcessStageGeneric: One of {"Setup | Data Handling | Analysis | Exception/Break Handling | Adjustments/Entries | Validation/Checks | Reporting/Documentation | Communication | Navigation/Overhead | Idle | Unknown/Other"}.
- ToolsUsed: List (Excel, Outlook, Browser, PDF viewer, File Explorer, Jira, etc.).
- FileTypeHandled: Infer by extension/title/headers (Excel, PDF, Email, Report, Other).
- CategoryType: {"Repetitive | Analytical | Knowledge Work | Communication | Decision-Making | Unknown"}.
- ValueType: {"Value-Added | Required Non-Value | Pure Waste | Unknown"}.
- Frequency: Count of similar occurrences in this session.
- ReworkFlag: Yes if same file/step repeated shortly after.
- ExceptionFlag: Yes if error/mismatch/break handled.
- IdleTimeFlag: Yes if >5 min inactivity.
- SwitchCount: Approx number of app/window/tab switches during event.
- MicroTaskFlag: Yes if <60s and standalone.
- ComplianceCheckFlag: Yes/No if compliance validation inferred.
- ErrorRiskLevel: Low/Medium/High if applicable.
- AIOpportunityLevel: {"High | Medium | Low"}.
- EliminationPotential: Yes if duplicative or non-value work.
- RootCauseTag: If ExceptionFlag=Yes, choose one (Unsettled_Trade | Accrual_Mismatch | FX_Mismatch | Stale_Price | Data_Gap | Manual_Error | System_Error | Other/Unknown).
- Observation: Note inefficiency or unusual pattern.
- Confidence: Float 0–1. Drop ≤0.6 if uncertain.
QUALITY CHECKS (strict):
- No overlapping times; StartTime < EndTime.
- StageSequenceID strictly increasing.
- Sum(Duration_Min) ≈ {duration_hms} (±5%) including Idle.
- Use "Unknown" if unsure; never hallucinate.
FORMATTING CONSTRAINTS (strict):
- Do NOT use ellipses ("..." or "…") or truncated phrases in any field.
- "ActivityDetail" must be 2–3 COMPLETE sentences (roughly 100–200 characters) with concrete and detailed actions
- "Observation" must be 2–3 COMPLETE sentences (roughly 100–200 characters) with concrete and detailed observations
OUTPUT FORMAT:
Return only valid JSON with this schema:
{{
    "filename": "{filename}",
    "videolink": "{videolink}",
    "caseid": "{employee_id}_{date}",
    "employeeid": "{employee_id}",
    "fullname": "{fullname}",
    "team": "{team}",
    "date": "{date}",
    "events": [
        {{
            "StageSequenceID": 1,
            "StartTime": "HH:MM:SS" or "Unknown",
            "EndTime": "HH:MM:SS" or "Unknown",
            "DurationMin": ""HH:MM:SS" or "Unknown",
            "ActivityName": "string",
            "ActivityDetail": "string",
            "ProcessStageGeneric": "string",
            "ToolsUsed": "list",
            "FileTypeHandled": "string",
            "CategoryType": "string",
            "ValueType": "string",
            "Frequency": "int",
            "ReworkFlag": "Yes/No",
            "ExceptionFlag": "Yes/No",
            "IdleTimeFlag": "Yes/No",
            "SwitchCount": "int",
            "MicroTaskFlag": "Yes/No",
            "ComplianceCheckFlag": "Yes/No",
            "ErrorRiskLevel": "Low/Medium/High/Unknown",
            "AIOpportunityLevel": "High/Medium/Low",
            "EliminationPotential": "Yes/No",
            "RootCauseTag": "string",
            "Observation": "string",
            "Confidence": "float (0-1)"
        }}
    ]
}}
"""
    return instruction


def coerce_json(text: str) -> Dict:
    try:
        return json.loads(text)
    except Exception:
        # try to find the nearest JSON block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def analyze_video_frames_to_events(
    filename: str,
    videolink: str,
    duration_hms: str,
    frames: List[Tuple[str, int]],
    employee_id: str,
    fullname: str,
    team: str,
    date: str,
) -> Dict:
    # Build transcript from per-frame captions
    lines: List[str] = []
    for fp, ts in frames:
        desc = analyze_frame(fp, ts)
        lines.append(f"[{hms(ts)}] {desc}")
    transcript_block = "\n".join(lines)

    prompt = build_instruction(
        filename=filename,
        videolink=videolink,
        duration_hms=duration_hms,
        transcript_block=transcript_block,
        employee_id=employee_id,
        fullname=fullname,
        team=team,
        date=date,
    )

    # Call OpenAI (placeholder minimal text call; adapt for GPT-5-mini when available)
    s = get_settings()
    cl = _get_client()
    completion = cl.chat.completions.create(
        model=s.openai_model,
        messages=[
            {"role": "system", "content": "You output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )
    text = completion.choices[0].message.content or "{}"
    return coerce_json(text)
