from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict, Iterable, List

from mcp.tools.audio_tools.tts_tool import SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS


def _read_wav(path: str | Path) -> list[int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        framerate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())

    if sample_width != SAMPLE_WIDTH:
        raise ValueError(f"Unsupported sample width for {path}: {sample_width}")

    frame_size = sample_width * channels
    mono: list[int] = []
    for frame_start in range(0, len(raw), frame_size):
        channel_values = [
            int.from_bytes(
                raw[frame_start + channel * sample_width : frame_start + (channel + 1) * sample_width],
                "little",
                signed=True,
            )
            for channel in range(channels)
        ]
        mono.append(int(sum(channel_values) / max(1, len(channel_values))))

    if framerate == SAMPLE_RATE:
        return mono

    if not mono:
        return []

    target_len = max(1, int(len(mono) * SAMPLE_RATE / framerate))
    resampled: list[int] = []
    for index in range(target_len):
        source_pos = index * framerate / SAMPLE_RATE
        left = int(source_pos)
        right = min(left + 1, len(mono) - 1)
        frac = source_pos - left
        value = int(mono[left] * (1 - frac) + mono[right] * frac)
        resampled.append(value)
    return resampled


def _write_wav(path: str | Path, samples: list[int]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples))


def mix_tracks(
    tracks: Iterable[Dict[str, float | str]],
    output_path: str | Path,
    duration_seconds: float | None = None,
) -> Dict[str, float | str]:
    """Overlay WAV tracks by their start offsets and write a mixed WAV file."""
    track_list = list(tracks)
    if not track_list:
        duration_seconds = duration_seconds or 1.0
        samples = [0] * int(duration_seconds * SAMPLE_RATE)
        _write_wav(output_path, samples)
        return {"audio_file": str(output_path), "duration_seconds": duration_seconds}

    loaded: List[tuple[list[int], int]] = []
    total_samples = int((duration_seconds or 0) * SAMPLE_RATE)
    for track in track_list:
        data = _read_wav(str(track["audio_file"]))
        offset = int(float(track.get("start_seconds", 0.0)) * SAMPLE_RATE)
        loaded.append((data, offset))
        total_samples = max(total_samples, offset + len(data))

    mix = [0] * max(total_samples, 1)
    for data, offset in loaded:
        for idx, sample in enumerate(data):
            target = offset + idx
            if target >= len(mix):
                break
            mix[target] = max(-32768, min(32767, mix[target] + sample))

    _write_wav(output_path, mix)
    return {"audio_file": str(output_path), "duration_seconds": len(mix) / SAMPLE_RATE}


def concatenate_wavs(input_paths: Iterable[str | Path], output_path: str | Path) -> Dict[str, float | str]:
    samples: list[int] = []
    for path in input_paths:
        samples.extend(_read_wav(path))
    if not samples:
        samples = [0] * SAMPLE_RATE
    _write_wav(output_path, samples)
    return {"audio_file": str(output_path), "duration_seconds": len(samples) / SAMPLE_RATE}
