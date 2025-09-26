import json
from typing import Dict, List, Tuple
import base64
import logging
from openai import OpenAI

from .config import get_settings
from .video_processor import hms


client = None
logger = logging.getLogger("video-analysis.gpt")

def _get_client():
    global client
    if client is None:
        api_key = get_settings().openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set; set it in environment or .env")
        client = OpenAI(api_key=api_key)
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
            {"role": "system", "content": "You are analyzing work session screenshots. Identify specific applications, documents, and activities only from what is visible."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Screenshot at {hms(timestamp)}. Identify: 1) Application and window title, 2) Document/file names visible, 3) Specific UI elements (buttons, menus, dialogs), 4) Any readable text (headers, cell values, email subjects), 5) Current user action (typing, clicking, scrolling). Be specific about what you see; do not infer beyond the image."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]
        completion = cl.chat.completions.create(
            model=s.openai_model,
            messages=msg,
        )
        content = (completion.choices[0].message.content or "").strip()
        if not content:
            logger.warning("Video frame description is empty; vision haved no response")
            return f"At {hms(timestamp)}, the screen shows an application window with typical work UI elements."
        return content
    except Exception as ex:
        logger.exception(f"analyze_frame failed at {hms(timestamp)}: {ex}")
        return f"At {hms(timestamp)}, the screen shows an application window with typical work UI elements."


def build_instruction(filename: str, duration_hms: str, transcript_block: str, employee_id: str, fullname: str, team: str, date: str) -> str:
    instruction = f"""
Role: You are an AI analyst converting screen recordings of employee work sessions into a fine-grained, process-mining event log. Employees belong to different teams.
INPUTS:
- Video file: {filename}
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
     - When it happened (real timestamps: StartTime, EndTime, DurationMin).
     - How it happened (rework, exceptions, switches, idle).
     - So what (value vs waste, AI automation potential).
3. Work unsupervised: infer activities and generic stages without relying on a fixed taxonomy. If unsure, label as "Unknown" and lower confidence.
SEGMENTATION RULES:
- Split events when ANY of these occur:
    * Active window/app change (Excel → PDF → Browser).
    * File/document change (different workbook, new filename).
    * Action mode change (typing → scrolling → copy/paste → refresh).
    * Idle > 5 minutes (mark event as "Idle", IdleTimeFlag=Yes).
- Merge micro-bursts <60s into adjacent event if same app/context; else keep as MicroTaskFlag=Yes.
- Events must strictly follow chronological order.
FIELDS TO POPULATE PER EVENT:
- CaseID: Unique session ID (EmployeeID + Date).
- EmployeeID: {employee_id}
- Team: {team}
- Date: {date}
- StartTime / EndTime: Real timestamps within the video (or "Unknown" if ambiguous).
- DurationMin: Numeric minutes for this event (float).
- StageSequenceID: Strictly increasing integer sequence for the session.
- ActivityName: Short and standardized (e.g., "Variance Analysis", "Journal Draft", "Email Thread", "Spreadsheet Cleanup", "Idle", "Unknown").
- ActivityDetail: 2 to 3 sentences describing exactly what happened.
- ProcessStageGeneric: One of ["Setup","Data Handling","Analysis","Exception/Break Handling","Adjustments/Entries","Validation/Checks","Reporting/Documentation","Communication","Navigation/Overhead","Idle","Unknown/Other"].
- ToolsUsed: JSON array of strings (e.g., ["Excel","Outlook","Browser","PDF viewer","File Explorer","Jira"]).
- FileTypeHandled: One of ["Excel","PDF","Email","Report","Other","Unknown"].
- CategoryType: One of ["Repetitive","Analytical","Knowledge Work","Communication","Decision-Making","Unknown"].
- ValueType: One of ["Value-Added","Required Non-Value","Pure Waste","Unknown"].
- Frequency: Integer count of similar occurrences in this session.
- ReworkFlag: "Yes" if same file/step repeated shortly after else "No".
- ExceptionFlag: "Yes"/"No".
- IdleTimeFlag: "Yes"/"No".
- SwitchCount: Integer approx number of app/window/tab switches during event.
- MicroTaskFlag: "Yes"/"No".
- ComplianceCheckFlag: "Yes"/"No".
- ErrorRiskLevel: "Low"/"Medium"/"High"/"Unknown".
- AIOpportunityLevel: "High"/"Medium"/"Low".
- EliminationPotential: "Yes"/"No".
- RootCauseTag: If ExceptionFlag="Yes", choose one of ["Unsettled_Trade","Accrual_Mismatch","FX_Mismatch","Stale_Price","Data_Gap","Manual_Error","System_Error","Other/Unknown"].
- Observation: 2 to 3 complete sentences noting inefficiency or unusual patterns.
- Confidence: Float 0 to 1. Drop ≤0.6 if uncertain.
QUALITY CHECKS (strict):
- No overlapping times; StartTime < EndTime.
- StageSequenceID strictly increasing.
- Sum(DurationMin) ≈ total session duration {duration_hms} (±5%) including Idle.
- Use "Unknown" if unsure; never hallucinate.
FORMATTING CONSTRAINTS (strict):
- Do NOT use ellipses or truncated phrases in any field.
- "ActivityDetail" must be 2 to 3 COMPLETE sentences (roughly 100 to 200 characters) with concrete and detailed actions.
- "Observation" must be 2 to 3 COMPLETE sentences (roughly 100 to 200 characters) with concrete and detailed observations.
OUTPUT FORMAT:
Return only valid JSON with this schema example:
{{
    "filename": "{filename}",
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
            "DurationMin": "float minutes or \"Unknown\"",
            "ActivityName": "string",
            "ActivityDetail": "string",
            "ProcessStageGeneric": "string",
            "ToolsUsed": ["string", "string"],
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
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def analyze_video_frames_to_events(
    filename: str,
    duration_hms: str,
    frames: List[Tuple[str, int]],
    employee_id: str,
    fullname: str,
    team: str,
    date: str,
) -> Dict:
    lines: List[str] = []
    for fp, ts in frames:
        desc = analyze_frame(fp, ts)
        lines.append(f"[{hms(ts)}] {desc}")
    transcript_block = "\n".join(lines)

    prompt = build_instruction(
        filename=filename,
        duration_hms=duration_hms,
        transcript_block=transcript_block,
        employee_id=employee_id,
        fullname=fullname,
        team=team,
        date=date,
    )

    s = get_settings()
    try:
        cl = _get_client()
        completion = cl.chat.completions.create(
            model=s.openai_model,
            messages=[
                {"role": "system", "content": "You output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        text = (completion.choices[0].message.content or "{}").strip()
        if not text:
            logger.warning("Video frame description is empty; vision haved no response")
            return {
                "filename": filename,
                "caseid": f"{employee_id}_{date}",
                "employeeid": employee_id,
                "fullname": fullname,
                "team": team,
                "date": date,
                "events": [],
            }
        return coerce_json(text)
    except Exception as ex:
        logger.exception(f"analyze_video_frames_to_events failed: {ex}")
        return {
            "filename": filename,
            "caseid": f"{employee_id}_{date}",
            "employeeid": employee_id,
            "fullname": fullname,
            "team": team,
            "date": date,
            "events": [],
        }
