"""
ffmpeg_tool.py — FFmpeg wrapper for Phase 3 video operations.

Handles:
- Ken Burns (zoom/pan) animation on a still image → video clip
- Adding audio track to a video clip
- Scene transitions (fade, crossfade)
- Concatenating clips into final MP4
- Subtitle burn-in (optional)
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from mcp.base_tool import BaseTool


def _run(cmd: List[str], label: str = "ffmpeg") -> subprocess.CompletedProcess:
    """Run an ffmpeg command, raising on failure."""
    print(f"  [{label}] Running: {' '.join(cmd[:8])} …")
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"[{label}] FFmpeg failed (rc={result.returncode}):\n{result.stderr[-800:]}"
        )
    return result


def image_to_video_ken_burns(
    image_path: str,
    output_path: str,
    duration_sec: float,
    effect: str = "zoom_in",  # zoom_in | zoom_out | pan_left | pan_right | static
    fps: int = 24,
    width: int = 1280,
    height: int = 720,
) -> str:
    """
    Animate a still image with a Ken Burns effect and output an MP4 clip.
    No audio is embedded here — audio is added in a later step.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Build zoompan filter
    # z = zoom expression, x/y = pan
    frames = int(duration_sec * fps)
    zoom_speed = 0.0008

    if effect == "zoom_in":
        vf = (
            f"zoompan=z='min(zoom+{zoom_speed},1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={width}x{height}:fps={fps}"
        )
    elif effect == "zoom_out":
        vf = (
            f"zoompan=z='if(lte(zoom,1.0),1.3,max(1.0,zoom-{zoom_speed}))':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={width}x{height}:fps={fps}"
        )
    elif effect == "pan_left":
        vf = (
            f"zoompan=z=1.1:x='if(gte(x,iw-iw/zoom),iw-iw/zoom,x+1)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={width}x{height}:fps={fps}"
        )
    elif effect == "pan_right":
        vf = (
            f"zoompan=z=1.1:x='max(0,x-1)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={width}x{height}:fps={fps}"
        )
    else:  # static
        vf = f"scale={width}:{height},setsar=1"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", vf,
        "-t", str(duration_sec),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        output_path,
    ]
    _run(cmd, "ken_burns")
    return output_path


def add_audio_to_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    video_duration: Optional[float] = None,
) -> str:
    """
    Mux audio into video. Audio is trimmed/padded to match video duration.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Get video duration if not provided
    if video_duration is None:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", video_path],
            capture_output=True, text=True,
        )
        info = json.loads(probe.stdout)
        video_duration = float(info["format"]["duration"])

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-t", str(video_duration),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path,
    ]
    _run(cmd, "add_audio")
    return output_path


def apply_fade(
    video_path: str,
    output_path: str,
    fade_in_sec: float = 0.5,
    fade_out_sec: float = 0.5,
) -> str:
    """Apply fade-in and fade-out to a clip."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Get duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", video_path],
        capture_output=True, text=True,
    )
    info = json.loads(probe.stdout)
    dur = float(info["format"]["duration"])
    fade_out_start = max(0, dur - fade_out_sec)

    vf = f"fade=t=in:st=0:d={fade_in_sec},fade=t=out:st={fade_out_start:.3f}:d={fade_out_sec}"
    af = f"afade=t=in:st=0:d={fade_in_sec},afade=t=out:st={fade_out_start:.3f}:d={fade_out_sec}"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    _run(cmd, "fade")
    return output_path


def concatenate_clips(
    clip_paths: List[str],
    output_path: str,
    width: int = 1280,
    height: int = 720,
) -> str:
    """
    Concatenate multiple MP4 clips into one final video using concat demuxer.
    All clips must have the same resolution and codec.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Write concat list file
    list_file = Path(output_path).parent / "_concat_list.txt"
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "concat")
    list_file.unlink(missing_ok=True)
    return output_path


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
) -> str:
    """Burn SRT subtitles into video."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={srt_path}:force_style='FontSize=22,PrimaryColour=&Hffffff&'",
        "-c:a", "copy",
        output_path,
    ]
    _run(cmd, "subtitles")
    return output_path


def get_audio_duration(audio_path: str) -> float:
    """Return duration in seconds of an audio file."""
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", audio_path],
        capture_output=True, text=True,
    )
    info = json.loads(probe.stdout)
    return float(info["format"]["duration"])


# ── MCP Tool classes ───────────────────────────────────────────────────────────

class FFmpegTool(BaseTool):
    """MCP tool: general FFmpeg operations for Phase 3."""

    name = "ffmpeg_tool"
    description = "Applies Ken Burns animation, audio muxing, fades, and concatenation."

    def execute(self, **kwargs) -> Dict[str, Any]:
        operation = kwargs.get("operation")
        if not operation:
            raise ValueError("operation is required (ken_burns|add_audio|fade|concat|subtitles)")

        if operation == "ken_burns":
            self.validate_inputs(["image_path", "output_path", "duration_sec"], kwargs)
            path = image_to_video_ken_burns(
                image_path=kwargs["image_path"],
                output_path=kwargs["output_path"],
                duration_sec=float(kwargs["duration_sec"]),
                effect=kwargs.get("effect", "zoom_in"),
                fps=kwargs.get("fps", 24),
                width=kwargs.get("width", 1280),
                height=kwargs.get("height", 720),
            )
            return {"success": True, "output_path": path}

        elif operation == "add_audio":
            self.validate_inputs(["video_path", "audio_path", "output_path"], kwargs)
            path = add_audio_to_video(
                kwargs["video_path"],
                kwargs["audio_path"],
                kwargs["output_path"],
                kwargs.get("video_duration"),
            )
            return {"success": True, "output_path": path}

        elif operation == "fade":
            self.validate_inputs(["video_path", "output_path"], kwargs)
            path = apply_fade(
                kwargs["video_path"],
                kwargs["output_path"],
                kwargs.get("fade_in_sec", 0.5),
                kwargs.get("fade_out_sec", 0.5),
            )
            return {"success": True, "output_path": path}

        elif operation == "concat":
            self.validate_inputs(["clip_paths", "output_path"], kwargs)
            path = concatenate_clips(
                kwargs["clip_paths"],
                kwargs["output_path"],
                kwargs.get("width", 1280),
                kwargs.get("height", 720),
            )
            return {"success": True, "output_path": path}

        elif operation == "subtitles":
            self.validate_inputs(["video_path", "srt_path", "output_path"], kwargs)
            path = burn_subtitles(
                kwargs["video_path"],
                kwargs["srt_path"],
                kwargs["output_path"],
            )
            return {"success": True, "output_path": path}

        else:
            raise ValueError(f"Unknown operation: {operation}")