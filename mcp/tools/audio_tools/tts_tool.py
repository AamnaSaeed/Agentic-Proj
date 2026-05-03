from __future__ import annotations

import hashlib
import math
import os
import subprocess
import wave
import asyncio
from pathlib import Path
from typing import Any, Dict


SAMPLE_RATE = 22_050
SAMPLE_WIDTH = 2
CHANNELS = 1
EDGE_VOICES = {
    "female": ["en-US-JennyNeural", "en-US-AriaNeural", "en-US-AvaNeural"],
    "male": ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-EricNeural"],
    "neutral": ["en-US-EmmaNeural", "en-US-AvaNeural", "en-US-AndrewNeural"],
}


def _stable_frequency(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return 150.0 + (digest[0] / 255.0) * 220.0


def _emotion_gain(emotion: str) -> float:
    emotion = emotion.lower()
    if emotion in {"excited", "awe", "hopeful", "determined"}:
        return 0.42
    if emotion in {"sad", "fearful", "whispered", "calm"}:
        return 0.25
    if emotion in {"angry", "tense"}:
        return 0.5
    return 0.34


def _write_mono_wav(path: Path, samples: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples))


def _edge_voice(segment: Dict[str, Any]) -> str:
    configured = os.environ.get("PHASE2_EDGE_TTS_VOICE", "").strip()
    if configured:
        return configured

    voice_config = segment.get("voice_config", {})
    gender = str(voice_config.get("gender", "neutral")).lower()
    voices = EDGE_VOICES.get(gender, EDGE_VOICES["neutral"])
    character_id = str(segment.get("character_id", "neutral"))
    digest = hashlib.sha256(character_id.encode("utf-8")).digest()
    return voices[digest[0] % len(voices)]


def _edge_rate(segment: Dict[str, Any]) -> str:
    voice_config = segment.get("voice_config", {})
    speed = float(voice_config.get("speed", 1.0) or 1.0)
    emotion = str(segment.get("emotion", "neutral")).lower()
    percent = round((speed - 1.0) * 18)
    if emotion in {"excited", "awe", "hopeful", "determined"}:
        percent += 6
    if emotion in {"sad", "calm", "whispered"}:
        percent -= 6
    percent = max(-35, min(35, percent))
    return f"{percent:+d}%"


def _edge_pitch(segment: Dict[str, Any]) -> str:
    emotion = str(segment.get("emotion", "neutral")).lower()
    if emotion in {"excited", "awe", "hopeful"}:
        return "+18Hz"
    if emotion in {"sad", "calm", "whispered"}:
        return "-12Hz"
    if emotion in {"tense", "angry"}:
        return "+8Hz"
    return "+0Hz"


def _ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _convert_mp3_to_wav(mp3_path: Path, wav_path: Path) -> bool:
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return False
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(mp3_path),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-sample_fmt",
            "s16",
            str(wav_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 44


async def _edge_save_mp3(segment: Dict[str, Any], mp3_path: Path) -> None:
    import edge_tts

    text = str(segment.get("text", "")).strip() or " "
    communicate = edge_tts.Communicate(
        text=text,
        voice=_edge_voice(segment),
        rate=_edge_rate(segment),
        pitch=_edge_pitch(segment),
    )
    await communicate.save(str(mp3_path))


def _synthesize_with_edge_tts(segment: Dict[str, Any], path: Path) -> bool:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False

    mp3_path = path.with_suffix(".mp3")
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(_edge_save_mp3(segment, mp3_path))
    except Exception:
        return False

    if not mp3_path.exists() or mp3_path.stat().st_size <= 0:
        return False
    return _convert_mp3_to_wav(mp3_path, path)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _voice_gender(gender: str) -> str:
    if gender == "male":
        return "Male"
    if gender == "female":
        return "Female"
    return "NotSet"


def _voice_age(age_range: str) -> str:
    if age_range == "child":
        return "Child"
    if age_range in {"young_adult", "adult"}:
        return "Adult"
    if age_range == "elderly":
        return "Senior"
    return "NotSet"


def _sapi_rate(speed: float, emotion: str) -> int:
    rate = round((speed - 1.0) * 5)
    if emotion.lower() in {"excited", "awe", "hopeful"}:
        rate += 1
    if emotion.lower() in {"sad", "calm", "whispered"}:
        rate -= 1
    return max(-10, min(10, rate))


def _synthesize_with_windows_sapi(segment: Dict[str, Any], path: Path) -> bool:
    voice_config = segment.get("voice_config", {})
    gender = _voice_gender(str(voice_config.get("gender", "neutral")))
    age = _voice_age(str(voice_config.get("age_range", "adult")))
    speed = float(voice_config.get("speed", 1.0) or 1.0)
    emotion = str(segment.get("emotion", "neutral"))
    rate = _sapi_rate(speed, emotion)
    text = str(segment.get("text", "")).strip()
    if not text:
        text = " "

    path.parent.mkdir(parents=True, exist_ok=True)
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
  $gender = [System.Speech.Synthesis.VoiceGender]::{gender}
  $age = [System.Speech.Synthesis.VoiceAge]::{age}
  $synth.SelectVoiceByHints($gender, $age)
}} catch {{}}
$synth.Rate = {rate}
$synth.Volume = 100
$synth.SetOutputToWaveFile({_ps_quote(str(path))})
$synth.Speak({_ps_quote(text)})
$synth.Dispose()
"""
    encoded = script.encode("utf-16-le")
    import base64

    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(encoded).decode("ascii")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0 and path.exists() and path.stat().st_size > 44


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate())


def _synthesize_with_tone_fallback(segment: Dict[str, Any], path: Path) -> float:
    segment_id = segment["segment_id"]
    voice_config = segment.get("voice_config", {})
    speed = float(voice_config.get("speed", 1.0) or 1.0)
    duration_seconds = max(0.5, float(segment["duration_hint_seconds"]) / speed)
    total_samples = int(duration_seconds * SAMPLE_RATE)

    base = _stable_frequency(
        str(segment.get("character_id", "unknown")),
        str(voice_config.get("gender", "neutral")),
        str(voice_config.get("tone", "")),
    )
    emotion = str(segment.get("emotion", "neutral"))
    gain = _emotion_gain(emotion)
    text = str(segment.get("text", ""))
    word_pulse = max(2.0, min(7.0, len(text.split()) / max(duration_seconds, 0.5)))

    samples: list[int] = []
    for index in range(total_samples):
        t = index / SAMPLE_RATE
        syllable = 0.6 + 0.4 * max(0.0, math.sin(2 * math.pi * word_pulse * t))
        vibrato = 1.0 + 0.015 * math.sin(2 * math.pi * 5.0 * t)
        carrier = math.sin(2 * math.pi * base * vibrato * t)
        harmonic = 0.35 * math.sin(2 * math.pi * base * 2.0 * t)
        envelope = min(1.0, t / 0.06, (duration_seconds - t) / 0.08)
        value = int(32767 * gain * syllable * envelope * (carrier + harmonic) / 1.35)
        samples.append(max(-32768, min(32767, value)))

    _write_mono_wav(path, samples)
    return duration_seconds


def synthesize_tts_segment(segment: Dict[str, Any], output_dir: str | Path) -> Dict[str, Any]:
    """Create a WAV for one dialogue segment.

    Microsoft Edge neural TTS is tried first for natural spoken dialogue without
    API keys. Windows SAPI and the tone renderer remain fallbacks so the phase
    can still run offline or when Edge's service is unavailable.
    """
    segment_id = segment["segment_id"]
    path = Path(output_dir) / f"{segment_id}.wav"
    provider = "edge_tts"

    if _synthesize_with_edge_tts(segment, path):
        duration_seconds = _wav_duration(path)
    elif _synthesize_with_windows_sapi(segment, path):
        provider = "windows_sapi"
        duration_seconds = _wav_duration(path)
    else:
        provider = "offline_tone_fallback"
        duration_seconds = _synthesize_with_tone_fallback(segment, path)

    return {
        "segment_id": segment_id,
        "audio_file": str(path),
        "duration_seconds": duration_seconds,
        "provider": provider,
    }
