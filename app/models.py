from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Event(BaseModel):
    StageSequenceID: int
    StartTime: str
    EndTime: str
    DurationMin: str
    ActivityName: str
    ActivityDetail: str
    ProcessStageGeneric: str
    ToolsUsed: List[str] = Field(default_factory=list)
    FileTypeHandled: str
    CategoryType: str
    ValueType: str
    Frequency: int
    ReworkFlag: str
    ExceptionFlag: str
    IdleTimeFlag: str
    SwitchCount: int
    MicroTaskFlag: str
    ComplianceCheckFlag: str
    ErrorRiskLevel: str
    AIOpportunityLevel: str
    EliminationPotential: str
    RootCauseTag: str
    Observation: str
    Confidence: float


class EventLog(BaseModel):
    fileName: str
    videoLink: str
    caseID: str
    employeeID: str
    fullName: str
    team: str
    date: str
    timeframe: str
    events: List[Event]
    processedAt: datetime


class StatusResponse(BaseModel):
    employeeID: str
    date: str
    processed: List[str]
    pending: List[str]


class ProcessResponse(BaseModel):
    message: str
    processedCount: int
    skipped: List[str]
    errors: List[str]


class ReprocessResponse(BaseModel):
    message: str
    count: int
