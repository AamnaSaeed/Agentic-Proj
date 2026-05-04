"""
tests/unit/test_phase3.py — Unit tests for Phase 3: Video Generation & Composition

Run from project root:
    python -m pytest tests/unit/test_phase3.py -v
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

# ── helpers ────────────────────────────────────────────────────────────────────

def make_dummy_audio(path: str, duration_sec: float = 3.0):
    """Create a silent WAV file for testing."""
    import wave, struct, math
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 22050
    n_samples = int(sample_rate * duration_sec)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        data = struct.pack("<" + "h" * n_samples, *([0] * n_samples))
        wf.writeframes(data)


def make_dummy_scene_handoff():
    return {
        "title": "Test Story",
        "scenes": [
            {
                "scene_id": "scene_001",
                "description": "A bright meadow with flowers",
                "visual_prompt": "Sunlit meadow, vibrant green grass, wildflowers",
                "tone": "peaceful",
                "setting": "outdoor meadow",
                "duration_sec": 5.0,
            },
            {
                "scene_id": "scene_002",
                "description": "Dark stormy skies over a city",
                "visual_prompt": "Ominous storm clouds looming over urban skyline at dusk",
                "tone": "tense",
                "setting": "city rooftop",
                "duration_sec": 5.0,
            },
        ],
    }


def make_dummy_timing_manifest():
    return [
        {
            "scene_id": "scene_001",
            "audio_file": "scene_001_mix.wav",
            "start_ms": 0,
            "end_ms": 4000,
            "text": "It was a beautiful morning.",
            "character": "Narrator",
        },
        {
            "scene_id": "scene_002",
            "audio_file": "scene_002_mix.wav",
            "start_ms": 4000,
            "end_ms": 9000,
            "text": "Then the storm arrived.",
            "character": "Narrator",
        },
    ]


# ── ImageGenTool ───────────────────────────────────────────────────────────────

class TestImageGenTool:
    def test_generates_png(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import ImageGenTool
        tool = ImageGenTool()
        out = str(tmp_path / "test_scene.png")
        result = tool.execute(
            scene_id="test_scene_001",
            visual_prompt="A futuristic city at night",
            tone="mysterious",
            setting="urban",
            output_path=out,
            use_ollama=False,  # skip Ollama in unit tests
        )
        assert result["success"] is True
        assert Path(out).exists()
        assert Path(out).stat().st_size > 0

    def test_different_moods_produce_files(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import ImageGenTool
        tool = ImageGenTool()
        for mood in ["happy", "sad", "mysterious", "tense", "peaceful"]:
            out = str(tmp_path / f"{mood}.png")
            result = tool.execute(
                scene_id=f"scene_{mood}",
                visual_prompt=f"A {mood} scene",
                tone=mood,
                setting="",
                output_path=out,
                use_ollama=False,
            )
            assert result["success"] is True, f"Failed for mood: {mood}"
            assert Path(out).exists()

    def test_space_scene_with_stars(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import ImageGenTool
        tool = ImageGenTool()
        out = str(tmp_path / "space_scene.png")
        result = tool.execute(
            scene_id="space_scene_001",
            visual_prompt="Astronaut floating in deep space among stars and galaxies",
            tone="mysterious",
            setting="outer space",
            output_path=out,
            use_ollama=False,
        )
        assert result["success"] is True
        assert Path(out).exists()

    def test_city_scene(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import ImageGenTool
        tool = ImageGenTool()
        out = str(tmp_path / "city_scene.png")
        result = tool.execute(
            scene_id="city_scene_001",
            visual_prompt="Busy city street at night with neon signs and tall skyscrapers",
            tone="exciting",
            setting="city",
            output_path=out,
            use_ollama=False,
        )
        assert result["success"] is True
        assert Path(out).exists()


# ── SubtitleTool ───────────────────────────────────────────────────────────────

class TestSubtitleTool:
    def test_generates_srt(self, tmp_path):
        from mcp.tools.video_tools.subtitle_tool import SubtitleTool
        tool = SubtitleTool()
        manifest = make_dummy_timing_manifest()
        out = str(tmp_path / "subs.srt")
        result = tool.execute(timing_manifest=manifest, output_path=out)
        assert result["success"] is True
        content = Path(out).read_text()
        assert "1\n" in content
        assert "-->" in content
        assert "Narrator" in content

    def test_empty_manifest_creates_file(self, tmp_path):
        from mcp.tools.video_tools.subtitle_tool import SubtitleTool
        tool = SubtitleTool()
        out = str(tmp_path / "empty.srt")
        result = tool.execute(timing_manifest=[], output_path=out)
        assert result["success"] is True
        assert Path(out).exists()

    def test_ms_to_srt_time(self):
        from mcp.tools.video_tools.subtitle_tool import ms_to_srt_time
        assert ms_to_srt_time(0) == "00:00:00,000"
        assert ms_to_srt_time(1000) == "00:00:01,000"
        assert ms_to_srt_time(65500) == "00:01:05,500"
        assert ms_to_srt_time(3_600_000) == "01:00:00,000"
        assert ms_to_srt_time(3_661_500) == "01:01:01,500"


# ── FFmpegTool ─────────────────────────────────────────────────────────────────

class TestFFmpegTool:
    def test_ken_burns_zoom_in(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import generate_scene_image
        from mcp.tools.video_tools.ffmpeg_tool import FFmpegTool
        # Generate a test image
        img_path = str(tmp_path / "test.png")
        generate_scene_image(
            "test", "A test scene", "neutral", "", 1280, 720, img_path
        )
        tool = FFmpegTool()
        out = str(tmp_path / "ken_burns.mp4")
        result = tool.execute(
            operation="ken_burns",
            image_path=img_path,
            output_path=out,
            duration_sec=3.0,
            effect="zoom_in",
            fps=24,
        )
        assert result["success"] is True
        assert Path(out).exists()

    def test_ken_burns_static(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import generate_scene_image
        from mcp.tools.video_tools.ffmpeg_tool import FFmpegTool
        img_path = str(tmp_path / "test2.png")
        generate_scene_image("test2", "Static scene", "happy", "", 1280, 720, img_path)
        tool = FFmpegTool()
        out = str(tmp_path / "static.mp4")
        result = tool.execute(
            operation="ken_burns",
            image_path=img_path,
            output_path=out,
            duration_sec=2.0,
            effect="static",
        )
        assert result["success"] is True
        assert Path(out).exists()

    def test_add_audio_to_video(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import generate_scene_image
        from mcp.tools.video_tools.ffmpeg_tool import FFmpegTool
        # Create image → silent video
        img_path = str(tmp_path / "img.png")
        generate_scene_image("s", "scene", "neutral", "", 1280, 720, img_path)
        raw_mp4 = str(tmp_path / "raw.mp4")
        FFmpegTool().execute(
            operation="ken_burns",
            image_path=img_path,
            output_path=raw_mp4,
            duration_sec=3.0,
            effect="static",
        )
        audio_path = str(tmp_path / "audio.wav")
        make_dummy_audio(audio_path, 3.0)
        out = str(tmp_path / "with_audio.mp4")
        result = FFmpegTool().execute(
            operation="add_audio",
            video_path=raw_mp4,
            audio_path=audio_path,
            output_path=out,
        )
        assert result["success"] is True
        assert Path(out).exists()

    def test_invalid_operation_raises(self):
        from mcp.tools.video_tools.ffmpeg_tool import FFmpegTool
        with pytest.raises(ValueError):
            FFmpegTool().execute(operation="does_not_exist")


# ── CompositorTool ─────────────────────────────────────────────────────────────

class TestCompositorTool:
    def test_compositor_two_clips(self, tmp_path):
        from mcp.tools.vision_tools.image_gen_tool import generate_scene_image
        from mcp.tools.video_tools.ffmpeg_tool import FFmpegTool
        from mcp.tools.video_tools.compositor_tool import CompositorTool

        clips = []
        for i in range(2):
            img = str(tmp_path / f"img_{i}.png")
            generate_scene_image(f"s{i}", f"Scene {i}", "neutral", "", 1280, 720, img)
            clip = str(tmp_path / f"clip_{i}.mp4")
            FFmpegTool().execute(
                operation="ken_burns",
                image_path=img,
                output_path=clip,
                duration_sec=2.0,
                effect="static",
            )
            clips.append(clip)

        out = str(tmp_path / "final.mp4")
        result = CompositorTool().execute(
            scene_clip_paths=clips,
            output_path=out,
            story_title="Test Story",
            transition_duration=0.3,
            add_title_card=False,
            add_end_card=False,
        )
        assert result["success"] is True
        assert Path(out).exists()
        assert Path(out).stat().st_size > 0


# ── VideoAgent integration ─────────────────────────────────────────────────────

class TestVideoAgentIntegration:
    def test_full_pipeline_two_scenes(self, tmp_path):
        from agents.video_agent.agent import VideoAgent

        # Set up fake phase1 dir
        p1_dir = tmp_path / "phase1"
        p1_dir.mkdir()
        handoff = make_dummy_scene_handoff()
        (p1_dir / "phase3_video_handoff.json").write_text(json.dumps(handoff))

        # Set up fake phase2 dir
        p2_dir = tmp_path / "phase2"
        (p2_dir / "scenes").mkdir(parents=True)
        manifest = make_dummy_timing_manifest()
        (p2_dir / "timing_manifest.json").write_text(json.dumps(manifest))
        # Create dummy audio
        for sid in ["scene_001", "scene_002"]:
            make_dummy_audio(str(p2_dir / "scenes" / f"{sid}_mix.wav"), 4.0)

        out_dir = str(tmp_path / "phase3_output")

        agent = VideoAgent(
            phase1_run_dir=str(p1_dir),
            phase2_run_dir=str(p2_dir),
            output_dir=out_dir,
            burn_subtitles=False,
            use_ollama=False,
            fps=24,
        )
        summary = agent.run()

        assert summary["status"] == "success"
        assert Path(summary["final_video"]).exists()
        assert summary["scenes_processed"] >= 1

    def test_missing_audio_still_produces_video(self, tmp_path):
        """Agent should produce a video even with no audio files."""
        from agents.video_agent.agent import VideoAgent

        p1_dir = tmp_path / "phase1"
        p1_dir.mkdir()
        handoff = {
            "title": "Silent Movie",
            "scenes": [
                {
                    "scene_id": "s001",
                    "visual_prompt": "A quiet forest",
                    "tone": "peaceful",
                    "setting": "forest",
                    "duration_sec": 3.0,
                }
            ],
        }
        (p1_dir / "phase3_video_handoff.json").write_text(json.dumps(handoff))

        p2_dir = tmp_path / "phase2_empty"
        p2_dir.mkdir()

        out_dir = str(tmp_path / "phase3_silent")
        agent = VideoAgent(
            phase1_run_dir=str(p1_dir),
            phase2_run_dir=str(p2_dir),
            output_dir=out_dir,
            use_ollama=False,
            fps=24,
        )
        summary = agent.run()
        assert summary["status"] == "success"
        assert Path(summary["final_video"]).exists()