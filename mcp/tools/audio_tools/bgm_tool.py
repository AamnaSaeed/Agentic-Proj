from __future__ import annotations

import hashlib
import math
import wave
from pathlib import Path
from typing import Any, Dict

from mcp.tools.audio_tools.tts_tool import SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS


def _mood_frequency(mood: str) -> float:
    digest = hashlib.sha256(mood.encode("utf-8")).digest()
    return 85.0 + (digest[0] / 255.0) * 80.0


def generate_bgm_track(
    scene_id: str,
    mood: str,
    duration_seconds: float,
    output_dir: str | Path,
) -> Dict[str, Any]:
    """Generate a soft procedural background pad for a scene."""
    duration_seconds = max(1.0, float(duration_seconds))
    total_samples = int(duration_seconds * SAMPLE_RATE)
    base = _mood_frequency(mood)
    samples: list[int] = []

    for index in range(total_samples):
        t = index / SAMPLE_RATE
        slow_lfo = 0.65 + 0.35 * math.sin(2 * math.pi * 0.18 * t)
        tone = (
            math.sin(2 * math.pi * base * t)
            + 0.45 * math.sin(2 * math.pi * (base * 1.5) * t)
            + 0.25 * math.sin(2 * math.pi * (base * 2.0) * t)
        )
        fade = min(1.0, t / 0.4, (duration_seconds - t) / 0.6)
        value = int(32767 * 0.12 * slow_lfo * fade * tone / 1.7)
        samples.append(max(-32768, min(32767, value)))

    path = Path(output_dir) / f"{scene_id}_bgm.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples))

    return {
        "scene_id": scene_id,
        "audio_file": str(path),
        "duration_seconds": duration_seconds,
        "mood": mood,
        "provider": "offline_procedural_bgm",
    }
