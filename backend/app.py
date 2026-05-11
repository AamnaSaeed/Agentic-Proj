from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.schemas import JobResponse, PipelineRequest, RunPhaseRequest
from backend.services.job_store import JOBS_ROOT, PROJECT_ROOT, JobStore
from backend.services.pipeline_runner import PipelineRunner, load_json_file


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_ROOT = PROJECT_ROOT / "data"

app = FastAPI(title="Agentic Video Pipeline API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=str(DATA_ROOT)), name="media")

store = JobStore()
runner = PipelineRunner(store)


def _require_job(job_id: str) -> dict[str, Any]:
    state = store.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return state


def _media_url(path: str | None) -> str | None:
    if not path:
        return None
    target = Path(path).resolve()
    try:
        relative = target.relative_to(DATA_ROOT.resolve())
    except ValueError:
        return None
    return f"/media/{relative.as_posix()}"


def _decorate_result(state: dict[str, Any]) -> dict[str, Any]:
    outputs = state.get("outputs", {})
    phase1 = outputs.get("phase1", {})
    phase2 = outputs.get("phase2", {})
    phase3 = outputs.get("phase3", {})
    artifacts = phase1.get("artifacts", {})

    return {
        "job": state,
        "preview": {
            "story": load_json_file(artifacts.get("story")),
            "characters": load_json_file(artifacts.get("characters")),
            "script": load_json_file(artifacts.get("script")),
            "timing_manifest": load_json_file(phase2.get("timing_manifest")),
            "phase3_summary": load_json_file(phase3.get("summary")),
        },
        "assets": {
            "audio": phase2.get("full_audio"),
            "audio_url": _media_url(phase2.get("full_audio")),
            "video": phase3.get("final_video"),
            "video_url": _media_url(phase3.get("final_video")),
            "download_url": _media_url(phase3.get("final_video")),
        },
    }


def _reset_for_rerun(state: dict[str, Any], phase_id: int, prompt: str | None) -> dict[str, Any]:
    if prompt:
        state["prompt"] = prompt
    state["status"] = "pending"
    state["current_phase"] = None
    state["progress"] = {1: 0, 2: 35, 3: 70}[phase_id]
    state["message"] = f"Phase {phase_id} re-run queued"
    state["errors"] = []

    outputs = state.setdefault("outputs", {})
    phases = state.setdefault("phases", {})
    for phase in range(phase_id, 4):
        phases[str(phase)] = "pending"
        outputs.pop(f"phase{phase}", None)
    return state


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run-pipeline", response_model=JobResponse)
async def run_pipeline(payload: PipelineRequest) -> JobResponse:
    state = store.create(payload.prompt)
    asyncio.create_task(runner.run_pipeline(state["job_id"], start_phase=1))
    return JobResponse(job_id=state["job_id"], status=state["status"])


@app.post("/run-phase/{phase_id}", response_model=JobResponse)
async def run_phase(phase_id: int, payload: RunPhaseRequest) -> JobResponse:
    if phase_id not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="phase_id must be 1, 2, or 3")
    if not JOBS_ROOT.exists():
        raise HTTPException(status_code=404, detail="No jobs exist yet")

    latest_state_file = max(JOBS_ROOT.glob("*/state.json"), key=lambda p: p.stat().st_mtime, default=None)
    if latest_state_file is None:
        raise HTTPException(status_code=404, detail="No jobs exist yet")

    state = load_json_file(str(latest_state_file))
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    if state["status"] == "running":
        raise HTTPException(status_code=409, detail="Cannot re-run while the latest job is running")

    state = _reset_for_rerun(state, phase_id, payload.prompt)
    store.save(state["job_id"], state)
    asyncio.create_task(runner.run_pipeline(state["job_id"], start_phase=phase_id))
    return JobResponse(job_id=state["job_id"], status=state["status"])


@app.post("/run-phase/{job_id}/{phase_id}", response_model=JobResponse)
async def run_phase_for_job(job_id: str, phase_id: int, payload: RunPhaseRequest) -> JobResponse:
    if phase_id not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="phase_id must be 1, 2, or 3")
    state = _require_job(job_id)
    if state["status"] == "running":
        raise HTTPException(status_code=409, detail="Cannot re-run while job is running")

    state = _reset_for_rerun(state, phase_id, payload.prompt)
    store.save(job_id, state)
    asyncio.create_task(runner.run_pipeline(job_id, start_phase=phase_id))
    return JobResponse(job_id=job_id, status=state["status"])


@app.get("/status/{job_id}")
async def get_status(job_id: str) -> dict[str, Any]:
    return _require_job(job_id)


@app.get("/result/{job_id}")
async def get_result(job_id: str) -> dict[str, Any]:
    return _decorate_result(_require_job(job_id))


@app.get("/events/{job_id}")
async def job_events(job_id: str) -> StreamingResponse:
    _require_job(job_id)

    async def event_stream():
        last_updated = None
        while True:
            state = store.get(job_id)
            if state is None:
                yield "event: error\ndata: {\"message\":\"Job not found\"}\n\n"
                break
            if state.get("updated_at") != last_updated:
                last_updated = state.get("updated_at")
                yield f"data: {json.dumps(state)}\n\n"
            if state.get("status") in {"completed", "failed"}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
