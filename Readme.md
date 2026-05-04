AgenticAI_Project_<GroupName>/
│
├── README.md
├── requirements.txt
├── .env
├── .gitignore
│
├── docs/
├── data/
│   ├── outputs/
│   ├── temp/
│   └── state_versions/
│
├── shared/
│   ├── schemas/
│   ├── utils/
│   └── constants/
│
├── mcp/                              # 🧩 MCP Layer (Tool Abstraction)
│   ├── base_tool.py                  # Base Tool Interface
│   ├── tool_registry.py              # Register & discover tools
│   ├── tool_executor.py              # Executes tools dynamically
│   │
│   ├── tools/                        # 🔧 Actual Tools
│   │   ├── llm_tools/
│   │   │   ├── text_generator.py
│   │   │   └── json_structurer.py
│   │   │
│   │   ├── audio_tools/
│   │   │   ├── tts_tool.py
│   │   │   ├── bgm_tool.py
│   │   │   └── audio_merger.py
│   │   │
│   │   ├── vision_tools/
│   │   │   ├── image_gen_tool.py
│   │   │   ├── image_edit_tool.py
│   │   │   └── style_transfer.py
│   │   │
│   │   ├── video_tools/
│   │   │   ├── ffmpeg_tool.py
│   │   │   ├── compositor_tool.py
│   │   │   └── subtitle_tool.py
│   │   │
│   │   └── system_tools/
│   │       ├── file_tool.py
│   │       ├── state_tool.py
│   │       └── logger_tool.py
│
├── agents/                           # 🤖 Agents use MCP tools
│   ├── orchestrator/
│   │   ├── graph.py
│   │   ├── workflow.py
│   │   └── state.py
│   │
│   ├── story_agent/                  # Phase 1
│   │   ├── agent.py                  # Uses LLM tools
│   │   ├── planner.py
│   │   └── tests/
│   │
│   ├── audio_agent/                  # Phase 2
│   │   ├── agent.py                  # Uses TTS + BGM tools
│   │   └── tests/
│   │
│   ├── video_agent/                  # Phase 3
│   │   ├── agent.py                  # Uses vision + video tools
│   │   └── tests/
│   │
│   └── edit_agent/                   # Phase 5 ⭐
│       ├── agent.py
│       ├── intent_classifier.py
│       ├── planner.py
│       ├── executor.py               # Calls MCP tools
│       └── tests/
│
├── backend/
│   ├── app.py
│   ├── routes/
│   ├── services/
│   └── websocket/
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── state_manager/
│   ├── state_manager.py
│   ├── snapshot.py
│   ├── history.py
│   └── storage.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
└── scripts/


## Phase 2: Audio Generation

Phase 2 consumes the Phase 1 `phase2_audio_handoff.json` file and produces:

- one WAV file per dialogue line in `segments/`
- optional procedural background music per scene in `bgm/`
- one mixed scene audio file per scene in `scenes/`
- a combined `full_audio.wav`
- `timing_manifest.json` for Phase 3 video synchronization
- `summary.json`

Run the bundled sample handoff:

```bash
python -m agents.audio_agent.agent
```

Run with a custom handoff path:

```bash
set PHASE2_HANDOFF_PATH=data/outputs/phase1/<run_id>/phase2_audio_handoff.json
python -m agents.audio_agent.agent
```

PowerShell equivalent:

```powershell
$env:PHASE2_HANDOFF_PATH="data/outputs/phase1/<run_id>/phase2_audio_handoff.json"
python -m agents.audio_agent.agent
```

The current implementation uses Microsoft Edge neural TTS through `edge-tts`, so it produces more natural spoken dialogue without paid API credentials. Edge TTS writes MP3 internally, then `imageio-ffmpeg` converts it to WAV so the existing mixer can build scene tracks and `full_audio.wav`. Windows SAPI and a tiny tone renderer remain as fallbacks if Edge TTS is unavailable. A cloud TTS provider can later replace `mcp/tools/audio_tools/tts_tool.py` while preserving the same manifest contract.

Background music is generated per scene from the Phase 1 `music_moods` map. The current BGM provider is `offline_procedural_bgm`, which creates soft mood pads locally and mixes them under the dialogue in each scene track.

Phase 2 sample output has been generated at:

```text
data/outputs/phase2/20260503_110433/
```

Test coverage for Phase 2 lives in `tests/unit/test_phase2.py`.

---

## Phase 3: Video Generation & Composition

Phase 3 consumes the Phase 1 `phase3_video_handoff.json` and Phase 2 `timing_manifest.json` to produce a complete animated short video.

### What It Produces

```
data/outputs/phase3/<run_id>/
├── images/
│   └── <scene_id>/
│       ├── scene_001_01_wide.png         # wide establishing shot
│       ├── scene_001_02_mid.png          # medium / character shot
│       └── scene_001_03_closeup.png      # close-up / detail shot
├── clips/
│   ├── scene_001_01_raw.mp4              # Ken Burns animated clip (per image)
│   ├── scene_001_02_raw.mp4
│   ├── scene_001_03_raw.mp4
│   ├── scene_001_merged.mp4             # crossfaded image clips
│   └── scene_001_audio.mp4             # merged clip + scene audio
├── scenes/
│   └── scene_001_final.mp4             # final scene clip (with fades)
├── subtitles.srt                        # SRT subtitle file
├── final_raw.mp4                        # pre-optimization composite
├── final_output.mp4                     # 🎬 finished video (CRF 18 optimized)
├── final_output_subtitled.mp4           # optional: subtitles burned in
└── summary.json
```

### Pipeline (per scene)

| Step | What Happens |
|------|-------------|
| 1 | **Multi-image generation** — Pollinations AI (FLUX model) generates 3 images per scene, each with a different framing: wide establishing shot → medium character shot → close-up detail shot |
| 2 | **Audio-synced duration** — scene duration is read from the actual Phase 2 WAV file length so visuals always match the narration exactly |
| 3 | **Varied Ken Burns** — each image gets a different motion effect: `zoom_in` → `pan_left` → `zoom_out` → `pan_right`, cycling per shot type |
| 4 | **Crossfade between images** — FFmpeg `xfade` transition (0.35s) joins the 3 image clips into one smooth scene clip |
| 5 | **Audio mux** — Phase 2 scene WAV is muxed into the clip with perfect duration sync |
| 6 | **Scene fades** — 0.3s fade-in and fade-out applied to each scene clip |

Final assembly:

| Step | What Happens |
|------|-------------|
| 7 | **MoviePy composite** — all scene clips concatenated with 0.5s crossfade transitions, title card, and end card |
| 8 | **FFmpeg quality pass** — re-encoded at CRF 18 (`slow` preset) for high-quality delivery |
| 9 | **Subtitle burn-in** — SRT generated from timing manifest and optionally burned into the video |

### MCP Tools

| Tool | File | Responsibility |
|------|------|---------------|
| `ImageGenTool` | `mcp/tools/vision_tools/image_gen_tool.py` | Generates 3 PNG images per scene via Pollinations AI (FLUX); PIL gradient fallback |
| `FFmpegTool` | `mcp/tools/video_tools/ffmpeg_tool.py` | Ken Burns animation, audio mux, fades, concatenation, subtitle burn-in |
| `CompositorTool` | `mcp/tools/video_tools/compositor_tool.py` | MoviePy final composition with crossfade transitions, title/end cards |
| `SubtitleTool` | `mcp/tools/video_tools/subtitle_tool.py` | Converts timing manifest to SRT format |

### Dependencies

**System (install once):**

```bash
# Windows — download installer from https://ffmpeg.org/download.html
# Then add to PATH. Verify with:
ffmpeg -version
```

**Python packages:**

```bash
pip install moviepy==1.0.3 Pillow numpy requests
```

> **No API keys required.** Pollinations AI is a free, open image generation service — no account or token needed. Ollama is optional and runs fully locally.

### Environment Variables

All variables are optional — the agent auto-detects the latest Phase 1 and Phase 2 output directories if not set.

| Variable | Default | Description |
|----------|---------|-------------|
| `PHASE1_RUN_DIR` | latest in `data/outputs/phase1/` | Path to Phase 1 run directory |
| `PHASE2_RUN_DIR` | latest in `data/outputs/phase2/` | Path to Phase 2 run directory |
| `PHASE3_OUTPUT_DIR` | `data/outputs/phase3/<timestamp>/` | Where to write Phase 3 outputs |
| `BURN_SUBTITLES` | `true` | Set `false` to skip subtitle burn-in |
| `USE_OLLAMA` | `false` | Set `true` to enhance prompts via local Ollama |
| `IMAGES_PER_SCENE` | `3` | Number of images to generate per scene (2–4 recommended) |

### Running

**Auto-detect latest Phase 1 & 2 outputs (recommended):**

```bash
python -m agents.video_agent.agent
```

**Point to specific run directories:**

```bash
python -m agents.video_agent.agent \
  --phase1-dir data/outputs/phase1/20260502_173240 \
  --phase2-dir data/outputs/phase2/20260503_110433
```

**Skip subtitle burn-in:**

```bash
python -m agents.video_agent.agent --no-subtitles
```

**Control images per scene:**

```bash
python -m agents.video_agent.agent --images-per-scene 4
```

**PowerShell equivalent:**

```powershell
$env:PHASE1_RUN_DIR="data/outputs/phase1/20260502_173240"
$env:PHASE2_RUN_DIR="data/outputs/phase2/20260503_110433"
python -m agents.video_agent.agent
```

**With Ollama prompt enhancement (optional — requires Ollama running locally):**

```bash
# Terminal 1 — start Ollama (if not already running)
ollama pull llama3.1:8b
ollama serve

# Terminal 2 — run agent with Ollama enabled
python -m agents.video_agent.agent --images-per-scene 3
# (USE_OLLAMA defaults to false; set env var to enable)
```

### Unit Tests

```bash
python -m pytest tests/unit/test_phase3.py -v
```

15 tests covering all MCP tools and the full agent integration pipeline including edge cases (missing audio, PIL fallback, all Ken Burns effects, all mood palettes).

### Phase 3 Sample Output

Sample output has been generated at:

```text
data/outputs/phase3/20260503_151806/
```

The final video is at:

```text
data/outputs/phase3/20260503_151806/final_output.mp4
```

---

## API Keys & Environment File

The `.env` file is included in `.gitignore` and should **never be committed to GitHub**.

| Phase | Service | Key Required | Notes |
|-------|---------|-------------|-------|
| Phase 1 | Ollama / Claude / GPT-4 | Optional | Ollama is free and local; cloud APIs need keys |
| Phase 2 | Edge TTS | ❌ None | Free, no account needed |
| Phase 2 | ElevenLabs (optional) | ✅ `ELEVENLABS_API_KEY` | Only if replacing Edge TTS |
| Phase 3 | Pollinations AI | ❌ None | Free, no account needed |
| Phase 3 | Ollama | ❌ None | Free, runs locally |

**Current `.env` template:**

```env
# Phase 1 — LLM (only needed if using cloud APIs)
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# OLLAMA_MODEL=llama3.1:8b

# Phase 2 — TTS (only needed if replacing Edge TTS)
# ELEVENLABS_API_KEY=...

# Phase 3 — all free, no keys needed
# IMAGES_PER_SCENE=3
# BURN_SUBTITLES=true
# USE_OLLAMA=false
```

Everything commented out means the project runs fully offline and free out of the box.