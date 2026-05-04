from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


JobStatus = Literal["pending", "running", "completed", "failed"]
PhaseStatus = Literal["pending", "running", "completed", "failed", "skipped"]


class PipelineRequest(BaseModel):
    prompt: str = Field(min_length=3)


class RunPhaseRequest(BaseModel):
    prompt: Optional[str] = Field(default=None, min_length=3)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobState(BaseModel):
    job_id: str
    prompt: str
    status: JobStatus = "pending"
    current_phase: Optional[int] = None
    phases: Dict[str, PhaseStatus]
    progress: int = 0
    message: str = ""
    errors: list[str] = Field(default_factory=list)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
