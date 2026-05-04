from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from backend.services.job_store import JobStore, PROJECT_ROOT


logger = logging.getLogger(__name__)
OUTPUTS_ROOT = PROJECT_ROOT / "data" / "outputs"


class PipelineRunner:
    def __init__(self, store: JobStore):
        self.store = store

    async def run_pipeline(self, job_id: str, start_phase: int = 1) -> None:
        try:
            state = self.store.get(job_id)
            if state is None:
                raise KeyError(f"Unknown job_id: {job_id}")

            for phase in range(start_phase, 4):
                await asyncio.to_thread(self._run_phase, job_id, phase)

            self.store.update(
                job_id,
                status="completed",
                current_phase=None,
                progress=100,
                message="Pipeline completed",
            )
        except Exception as exc:
            logger.exception("Pipeline job %s failed", job_id)
            self.store.update(
                job_id,
                status="failed",
                current_phase=None,
                message=str(exc),
                errors=[str(exc)],
            )

    def _run_phase(self, job_id: str, phase: int) -> None:
        phase_name = {1: "Story", 2: "Audio", 3: "Video"}[phase]
        self.store.update(
            job_id,
            status="running",
            current_phase=phase,
            phases={str(phase): "running"},
            progress={1: 10, 2: 45, 3: 75}[phase],
            message=f"Phase {phase}: {phase_name} running",
        )
        logger.info("Job %s: starting Phase %s", job_id, phase)

        if phase == 1:
            outputs = self._run_phase1(job_id)
        elif phase == 2:
            outputs = self._run_phase2(job_id)
        elif phase == 3:
            outputs = self._run_phase3(job_id)
        else:
            raise ValueError(f"Unsupported phase: {phase}")

        self.store.update(
            job_id,
            phases={str(phase): "completed"},
            outputs=outputs,
            progress={1: 35, 2: 70, 3: 95}[phase],
            message=f"Phase {phase}: {phase_name} completed",
        )
        logger.info("Job %s: completed Phase %s", job_id, phase)

    def _run_phase1(self, job_id: str) -> Dict[str, Any]:
        from agents.story_agent.agent import create_phase1_graph
        from agents.story_agent.serializer import serialize_phase1_outputs

        state = self.store.get(job_id)
        if state is None:
            raise KeyError(f"Unknown job_id: {job_id}")

        job_dir = self.store.job_dir(job_id)
        phase1_dir = job_dir / "phase1"
        phase1_dir.mkdir(parents=True, exist_ok=True)

        graph = create_phase1_graph()
        initial_state = {
            "user_prompt": state["prompt"],
            "story_output": None,
            "character_roster": None,
            "script_output": None,
            "errors": [],
            "tools_log": [],
            "retry_counts": {},
        }
        result = graph.invoke(initial_state)
        errors = result.get("errors", [])
        if errors or not all(
            result.get(key) for key in ("story_output", "character_roster", "script_output")
        ):
            raise RuntimeError("; ".join(errors) or "Phase 1 did not produce all outputs")

        artifact_paths = serialize_phase1_outputs(
            result["story_output"],
            result["character_roster"],
            result["script_output"],
            result.get("tools_log", []),
            errors,
            output_dir=phase1_dir,
        )
        return {
            "phase1": {
                "output_dir": str(phase1_dir),
                "artifacts": artifact_paths,
                "story": result["story_output"],
                "characters": result["character_roster"],
                "script": result["script_output"],
            }
        }

    def _run_phase2(self, job_id: str) -> Dict[str, Any]:
        from agents.audio_agent.agent import run_phase2 as phase2_agent

        state = self.store.get(job_id)
        if state is None:
            raise KeyError(f"Unknown job_id: {job_id}")

        handoff = state.get("outputs", {}).get("phase1", {}).get("artifacts", {}).get(
            "phase2_audio_handoff"
        )
        if not handoff:
            raise RuntimeError("Phase 2 requires phase2_audio_handoff from Phase 1")

        phase2_dir = self.store.job_dir(job_id) / "phase2"
        result = phase2_agent(handoff, output_dir=phase2_dir)
        if not result.get("success"):
            raise RuntimeError("; ".join(result.get("errors", ["Phase 2 failed"])))

        return {
            "phase2": {
                "output_dir": str(phase2_dir),
                "timing_manifest": result["timing_manifest"],
                "full_audio": result["full_audio"],
                "summary": str(phase2_dir / "summary.json"),
                "scene_count": result["scene_count"],
                "segment_count": result["segment_count"],
            }
        }

    def _run_phase3(self, job_id: str) -> Dict[str, Any]:
        from agents.video_agent.agent import VideoAgent

        state = self.store.get(job_id)
        if state is None:
            raise KeyError(f"Unknown job_id: {job_id}")

        outputs = state.get("outputs", {})
        phase1_dir = outputs.get("phase1", {}).get("output_dir")
        phase2_dir = outputs.get("phase2", {}).get("output_dir")
        if not phase1_dir or not phase2_dir:
            raise RuntimeError("Phase 3 requires Phase 1 and Phase 2 outputs")

        phase3_dir = self.store.job_dir(job_id) / "phase3"
        agent = VideoAgent(
            phase1_run_dir=phase1_dir,
            phase2_run_dir=phase2_dir,
            output_dir=str(phase3_dir),
            burn_subs=os.environ.get("BURN_SUBTITLES", "true").lower() != "false",
            use_ollama=os.environ.get("USE_OLLAMA", "false").lower() == "true",
            images_per_scene=int(os.environ.get("IMAGES_PER_SCENE", "3")),
        )
        result = agent.run()
        return {
            "phase3": {
                "output_dir": str(phase3_dir),
                "final_video": result["final_video"],
                "subtitles": result.get("subtitles"),
                "summary": str(phase3_dir / "summary.json"),
                "scene_clips": result.get("scene_clips", []),
            }
        }


def load_json_file(path: str | None) -> Any:
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)
