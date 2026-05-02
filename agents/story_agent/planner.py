"""
Phase 1 Pipeline Entry Point — Story, Script & Character Design
===============================================================

Usage (programmatic):
    from agents.story_agent.planner import run_phase1

    result = run_phase1("A young astronaut discovers a hidden ocean on Mars")
    if result["success"]:
        print(result["story"]["title"])

Usage (CLI):
    python -m agents.story_agent.planner "A young astronaut discovers a hidden ocean on Mars"

Environment variables:
    GOOGLE_API_KEY     — required
    PHASE1_MODEL       — Gemini model ID (default: gemini-2.0-flash)
    PHASE1_OUTPUT_DIR  — artifact output root  (default: data/outputs)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_phase1(
    user_prompt: str,
    save_artifacts: bool = True,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the complete Phase 1 pipeline: Story → Character → Script.

    Args:
        user_prompt:    Free-form story idea from the user.
        save_artifacts: Write JSON artifacts to disk (default True).
        output_dir:     Override PHASE1_OUTPUT_DIR env var.

    Returns:
        dict with keys:
          story, characters, script      — dicts from each agent
          phase2_handoff, phase3_handoff — dicts ready for downstream phases
          artifact_paths                 — map of name → file path
          errors                         — list of error strings
          tools_log                      — list of tool-call records
          success                        — bool
    """
    if not user_prompt or not user_prompt.strip():
        return _error_result("user_prompt must not be empty.")

    if not os.environ.get("GOOGLE_API_KEY"):
        return _error_result(
            "GOOGLE_API_KEY is not set. Add it to your .env file."
        )

    if output_dir:
        os.environ["PHASE1_OUTPUT_DIR"] = output_dir

    logger.info("Phase 1 started — prompt: '%s...'", user_prompt[:80])

    from shared.schemas.pipeline_state import Phase1State
    from agents.story_agent.agent import create_phase1_graph
    from agents.story_agent.serializer import serialize_phase1_outputs

    initial_state: Phase1State = {
        "user_prompt": user_prompt.strip(),
        "story_output": None,
        "character_roster": None,
        "script_output": None,
        "errors": [],
        "tools_log": [],
        "retry_counts": {},
    }

    try:
        graph = create_phase1_graph()
        final_state: Phase1State = graph.invoke(initial_state)
    except Exception as exc:
        logger.error("Pipeline graph execution failed: %s", exc)
        return _error_result(f"Pipeline execution error: {exc}")

    story = final_state.get("story_output")
    roster = final_state.get("character_roster")
    script = final_state.get("script_output")
    errors: List[str] = final_state.get("errors", [])
    tools_log: List[Dict[str, Any]] = final_state.get("tools_log", [])

    success = bool(story and roster and script and not errors)
    artifact_paths: Dict[str, str] = {}
    phase2_handoff: Optional[Dict[str, Any]] = None
    phase3_handoff: Optional[Dict[str, Any]] = None

    if save_artifacts and story and roster and script:
        artifact_paths = serialize_phase1_outputs(
            story=story,
            roster=roster,
            script=script,
            tools_log=tools_log,
            errors=errors,
            run_status="success" if success else "partial",
        )
        # Load handoff dicts back so callers don't need to re-read files
        if "phase2_audio_handoff" in artifact_paths:
            with open(artifact_paths["phase2_audio_handoff"], encoding="utf-8") as fh:
                phase2_handoff = json.load(fh)
        if "phase3_video_handoff" in artifact_paths:
            with open(artifact_paths["phase3_video_handoff"], encoding="utf-8") as fh:
                phase3_handoff = json.load(fh)

    if success:
        logger.info(
            "Phase 1 complete — story: '%s', %d scenes, %d characters, %d dialogue lines",
            story.get("title", "Untitled"),
            len(story.get("scenes", [])),
            len(roster.get("characters", [])),
            sum(len(s.get("dialogue", [])) for s in script.get("scenes", [])),
        )
    else:
        logger.warning("Phase 1 finished with errors: %s", errors)

    return {
        "story": story,
        "characters": roster,
        "script": script,
        "phase2_handoff": phase2_handoff,
        "phase3_handoff": phase3_handoff,
        "artifact_paths": artifact_paths,
        "errors": errors,
        "tools_log": tools_log,
        "success": success,
    }


def _error_result(message: str) -> Dict[str, Any]:
    logger.error(message)
    return {
        "story": None,
        "characters": None,
        "script": None,
        "phase2_handoff": None,
        "phase3_handoff": None,
        "artifact_paths": {},
        "errors": [message],
        "tools_log": [],
        "success": False,
    }


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    prompt = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "A young astronaut discovers a hidden ocean on Mars"
    )

    result = run_phase1(prompt)

    if result["success"]:
        story = result["story"]
        chars = result["characters"]
        script = result["script"]
        print("\n[OK] Phase 1 complete!")
        print(f"  Story  : {story['title']} ({story['genre']})")
        print(f"  Premise: {story['premise']}")
        print(f"  Scenes : {len(story['scenes'])}  (~{story['total_estimated_duration_seconds']}s)")
        print(f"  Cast   : {len(chars['characters'])} characters")
        print(f"  Lines  : {sum(len(s['dialogue']) for s in script['scenes'])} dialogue lines")
        print(f"  Art    : {chars['global_art_style']}")
        print(f"\n  Artifacts → {result['artifact_paths'].get('summary', 'N/A')}")
    else:
        print(f"\n[FAILED] Phase 1 failed: {result['errors']}", file=sys.stderr)
        sys.exit(1)
