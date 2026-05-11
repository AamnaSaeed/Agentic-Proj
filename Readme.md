# Agentic AI Video Pipeline

An end-to-end multi-agent system that generates short animated videos (2–5 minutes) from a single text prompt. The pipeline orchestrates four sequential phases — story generation, audio synthesis, video composition, and a web application — each powered by dedicated AI agents.

---

## Table of Contents

- [Demo](#demo)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [Using the Web UI](#using-the-web-ui)
- [Backend API Reference](#backend-api-reference)
- [Running Individual Phases](#running-individual-phases)
- [Agent Details](#agent-details)
- [MCP Tool Layer](#mcp-tool-layer)
- [Data Output Structure](#data-output-structure)
- [Docker](#docker)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Environment Variables Reference](#environment-variables-reference)

---

## Demo

Enter a prompt like:

> *"A hopeful astronaut discovers a glowing ocean beneath Mars."*

The system generates a complete animated short film: narrative structure, character voices, scene images with Ken Burns animation, and a final MP4 with optional subtitles — all from that single sentence.

---

## How It Works

The pipeline runs four sequential phases:

| Phase | Agent | What It Does | Key Outputs |
|-------|-------|-------------|-------------|
| **1** | Story Agent | LLM-driven narrative generation using LangGraph | `story.json`, `characters.json`, `script.json`, handoff files |
| **2** | Audio Agent | Text-to-speech synthesis + procedural background music | Dialogue WAV files, BGM tracks, `timing_manifest.json` |
| **3** | Video Agent | Image generation + Ken Burns animation + video assembly | Scene images, animated clips, `final_output.mp4` |
| **4** | Web App | FastAPI backend + React/Vite frontend with live job tracking | Job status, phase re-runs, media preview, download |

**End-to-end flow:**

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────┐
│  Phase 1 — Story Agent (LangGraph)          │
│  story_node → character_node → script_node  │
│  LLM: GPT-4o / Gemini-2.0-Flash            │
└──────────────────┬──────────────────────────┘
                   │  phase2_audio_handoff.json
                   │  phase3_video_handoff.json
                   ▼
┌─────────────────────────────────────────────┐
│  Phase 2 — Audio Agent                      │
│  Edge TTS dialogue synthesis                │
│  Procedural background music                │
│  Scene audio mixing + timing manifest       │
└──────────────────┬──────────────────────────┘
                   │  timing_manifest.json
                   │  full_audio.wav
                   ▼
┌─────────────────────────────────────────────┐
│  Phase 3 — Video Agent                      │
│  Pollinations AI / FLUX image generation    │
│  Ken Burns animation (FFmpeg)               │
│  Scene assembly + subtitle burn-in          │
│  FFmpeg quality optimization (CRF 18)       │
└──────────────────┬──────────────────────────┘
                   │  final_output.mp4
                   ▼
            Web App (Phase 4)
         Preview + Download
```

---

## Architecture

```
agentic-project/
│
├── agents/                  ← AI agent pipeline
│   ├── story_agent/         ← Phase 1: LangGraph story/character/script nodes
│   ├── audio_agent/         ← Phase 2: TTS + BGM synthesis
│   ├── video_agent/         ← Phase 3: Image gen + video composition
│   ├── edit_agent/          ← Future Phase 5 (placeholder)
│   └── orchestrator/        ← Multi-phase coordination utilities
│
├── backend/                 ← FastAPI REST server
│   ├── app.py               ← All routes, CORS, media serving
│   ├── schemas.py           ← Request/response Pydantic models
│   └── services/
│       ├── job_store.py     ← JSON-backed job persistence
│       └── pipeline_runner.py  ← Async phase orchestration
│
├── frontend/                ← React 18 / Vite web app
│   └── src/
│       ├── main.jsx         ← App, PhaseTracker, JsonPreview, Outputs
│       └── styles.css
│
├── mcp/                     ← Model Context Protocol tool abstraction
│   ├── base_tool.py
│   ├── tool_registry.py
│   ├── tool_executor.py
│   └── tools/
│       ├── audio_tools/     ← TTS, BGM, audio merging
│       ├── video_tools/     ← FFmpeg, MoviePy compositor, subtitles
│       ├── vision_tools/    ← Image generation, style transfer
│       ├── llm_tools/       ← Text generation, JSON structuring
│       └── system_tools/    ← File I/O, logging, state
│
├── shared/                  ← Shared Pydantic schemas
│   └── schemas/
│       ├── pipeline_state.py
│       ├── story_schema.py
│       ├── character_schema.py
│       ├── script_schema.py
│       └── handoff_schema.py
│
├── state_manager/           ← JSON state versioning & snapshots
├── tests/                   ← Unit and integration tests
├── data/                    ← Generated outputs (git-ignored)
│   ├── jobs/                ← Phase 4 job outputs
│   ├── outputs/             ← Manual/standalone run outputs
│   ├── temp/
│   └── state_versions/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Tech Stack

### Backend (Python 3.11+)

| Category | Library | Purpose |
|----------|---------|---------|
| **AI/Agents** | `langchain>=0.3.0` | LLM chaining and tool use |
| | `langchain-google-genai>=2.0.0` | Google Gemini integration |
| | `langchain-openai>=0.2.0` | OpenAI GPT integration |
| | `langgraph>=0.2.56` | Stateful agentic graph orchestration |
| **API Server** | `fastapi>=0.111.0` | REST API framework |
| | `uvicorn[standard]>=0.29.0` | ASGI server |
| | `websockets>=12.0` | Server-Sent Events support |
| **Audio** | `edge-tts>=7.2.8` | Microsoft Edge neural TTS |
| | `imageio-ffmpeg>=0.6.0` | Bundled FFmpeg bindings |
| **Video** | `moviepy>=1.0.3` | Video composition and editing |
| | `ffmpeg-python>=0.2.0` | Low-level FFmpeg Python bindings |
| | `Pillow>=10.0.0` | Image processing |
| | `opencv-python>=4.8.0` | Image filtering and computer vision |
| **Validation** | `pydantic>=2.0.0` | Schema validation and serialization |
| | `python-dotenv>=1.0.0` | Environment variable management |
| **Testing** | `pytest>=7.4.0` | Test framework |
| | `pytest-asyncio>=0.23.0` | Async test support |

### Frontend (Node.js 20+)

| Library | Version | Purpose |
|---------|---------|---------|
| React | 18.3.1 | UI framework |
| Vite | 6.0.5 | Build tool and dev server |
| lucide-react | 0.468.0 | Icon library |
| TypeScript | 5.7.2 | Type checking |

### External Services

| Service | Required | Used By |
|---------|----------|---------|
| Google Gemini API | Optional | Phase 1 (alternative LLM) |
| OpenAI API | Recommended | Phase 1 story/character/script nodes |
| Pollinations AI / FLUX | No (free) | Phase 3 image generation (no key needed) |
| Microsoft Edge TTS | No (free) | Phase 2 dialogue synthesis (no key needed) |

---

## Project Structure

```text
.
├── agents/
│   ├── story_agent/
│   │   ├── agent.py            # LangGraph graph entry point
│   │   ├── story_node.py       # Scene + narrative generation
│   │   ├── character_node.py   # Character roster with voice configs
│   │   ├── script_node.py      # Dialogue lines with timing/emotion
│   │   ├── serializer.py       # Phase 1 → Phase 2/3 handoff files
│   │   ├── utils.py            # LLM init, tool-loop execution
│   │   └── tools/
│   │       ├── story_tools.py
│   │       ├── character_tools.py
│   │       └── script_tools.py
│   ├── audio_agent/
│   │   └── agent.py            # run_phase2() entry point
│   ├── video_agent/
│   │   └── agent.py            # CLI entry point with argparse
│   └── orchestrator/
│       ├── workflow.py
│       ├── graph.py
│       └── state.py
├── backend/
│   ├── app.py
│   ├── schemas.py
│   └── services/
│       ├── job_store.py
│       └── pipeline_runner.py
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.js
├── mcp/
│   ├── base_tool.py
│   ├── tool_registry.py
│   ├── tool_executor.py
│   └── tools/
│       ├── audio_tools/
│       │   ├── tts_tool.py
│       │   ├── bgm_tool.py
│       │   └── audio_merger.py
│       ├── video_tools/
│       │   ├── ffmpeg_tool.py
│       │   ├── compositor_tool.py
│       │   └── subtitle_tool.py
│       ├── vision_tools/
│       │   ├── image_gen_tool.py
│       │   ├── style_transfer.py
│       │   └── image_edit_tool.py
│       ├── llm_tools/
│       │   ├── text_generator.py
│       │   └── json_structurer.py
│       └── system_tools/
│           ├── file_tool.py
│           ├── logger_tool.py
│           └── state_tool.py
├── shared/
│   └── schemas/
│       ├── pipeline_state.py
│       ├── story_schema.py
│       ├── character_schema.py
│       ├── script_schema.py
│       └── handoff_schema.py
├── state_manager/
│   ├── state_manager.py
│   ├── storage.py
│   ├── snapshot.py
│   └── history.py
├── tests/
│   ├── unit/
│   │   ├── test_phase1.py
│   │   ├── test_phase2.py
│   │   └── test_phase3.py
│   └── integration/
├── data/                       # git-ignored
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Prerequisites

Ensure the following are installed before running:

- **Python 3.11+**
- **Node.js 20+ or 22+**
- **FFmpeg** (required for audio and video processing)
- **An OpenAI or Google Gemini API key** (for Phase 1 story generation)

Verify your installations:

```bash
python --version
node --version
npm --version
ffmpeg -version
```

### Installing FFmpeg

**Windows** — download from https://ffmpeg.org/download.html and add to PATH, or use Chocolatey:
```powershell
choco install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

---

## Environment Setup

Copy the example environment file:

```bash
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Edit `.env` and fill in your API keys:

```env
# ── Required for Phase 1 (pick one or both) ───────────────────────────────

# OpenAI — recommended (used by default in .env.example)
OPENAI_API_KEY=sk-your-openai-key-here

# Google Gemini — alternative LLM for Phase 1
GOOGLE_API_KEY=your-google-gemini-key-here

# ── Phase 1 Settings ───────────────────────────────────────────────────────
# Options: gpt-4o, gpt-4o-mini, gpt-4-turbo, gemini-2.0-flash, gemini-1.5-flash
PHASE1_MODEL=gpt-4o
PHASE1_OUTPUT_DIR=data/outputs

# ── Phase 2 Settings ───────────────────────────────────────────────────────
PHASE2_OUTPUT_DIR=data/outputs/phase2
# Optional: override Edge TTS voice for all characters
# Examples: en-US-JennyNeural, en-US-GuyNeural, en-US-AriaNeural
PHASE2_EDGE_TTS_VOICE=

# ── Phase 3 Settings ───────────────────────────────────────────────────────
BURN_SUBTITLES=true
USE_OLLAMA=false
IMAGES_PER_SCENE=3
```

> **Note:** `.env` is git-ignored. Never commit real API keys.

### Getting API Keys

- **OpenAI:** https://platform.openai.com/api-keys
- **Google Gemini:** https://aistudio.google.com/app/apikey (free tier available)

---

## Installation

### Backend

```bash
# Create and activate virtual environment
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
cd ..
```

---

## Running the App

You need two terminals running simultaneously.

**Terminal 1 — Start the backend:**

```bash
# macOS / Linux
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Start the frontend:**

```bash
cd frontend
npm run dev
```

Open the app at:

```
http://localhost:5173
```

The frontend automatically proxies API calls to `http://localhost:8000`.

---

## Using the Web UI

1. **Enter a prompt** in the text area (e.g., *"A tiny robot discovers music on a silent moon."*)
2. **Click "Generate Video"** — a job is created and the pipeline starts
3. **Watch the Phase Tracker** — Phase 1, 2, and 3 cards update in real time via Server-Sent Events
4. **Inspect JSON outputs** — expand the collapsible JSON previews for story, characters, and script
5. **Play the audio** — the full mixed audio player appears after Phase 2 completes
6. **Play or download the video** — the video player appears after Phase 3 completes with a download button
7. **Re-run any phase** — each phase card has a "Re-run" button for iterative refinement without restarting the full pipeline

---

## Backend API Reference

### Health Check

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok"}
```

### Start Full Pipeline

```bash
curl -X POST http://localhost:8000/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A tiny robot discovers music on a silent moon."}'
```

```json
{
  "job_id": "abc123...",
  "status": "pending"
}
```

### Check Job Status

```bash
curl http://localhost:8000/status/<job_id>
```

Response fields:

| Field | Values |
|-------|--------|
| `status` | `pending`, `running`, `completed`, `failed` |
| `current_phase` | `1`, `2`, `3`, or `null` |
| `phases` | Per-phase status objects |
| `progress` | `0`–`100` |
| `message` | Human-readable status |
| `errors` | List of error strings |
| `outputs` | Output file paths |

### Stream Live Progress (Server-Sent Events)

```bash
curl http://localhost:8000/events/<job_id>
```

Streams real-time progress updates as the pipeline runs. The frontend connects to this endpoint automatically.

### Get Results

```bash
curl http://localhost:8000/result/<job_id>
```

Returns:
- Full job state
- JSON previews (story, characters, script, timing manifest)
- Audio URL at `/media/...`
- Video URL at `/media/...`
- Download URL for final MP4

### Re-run a Specific Phase

Re-run Phase 1 (with optional new prompt):

```bash
curl -X POST http://localhost:8000/run-phase/<job_id>/1 \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A revised story prompt."}'
```

Re-run Phase 2 (re-synthesize audio from existing Phase 1 outputs):

```bash
curl -X POST http://localhost:8000/run-phase/<job_id>/2 \
  -H "Content-Type: application/json" \
  -d '{}'
```

Re-run Phase 3 (regenerate video from existing Phase 1 + 2 outputs):

```bash
curl -X POST http://localhost:8000/run-phase/<job_id>/3 \
  -H "Content-Type: application/json" \
  -d '{}'
```

Re-run the latest job's Phase 2 (shorthand):

```bash
curl -X POST http://localhost:8000/run-phase/2 \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Running Individual Phases

### Phase 1 (Story Generation)

Phase 1 is normally run via the Phase 4 backend. It requires `OPENAI_API_KEY` or `GOOGLE_API_KEY`. The backend calls:

```python
create_phase1_graph().invoke({"user_prompt": "..."})
```

Artifacts are then serialized to disk by `serialize_phase1_outputs()`.

### Phase 2 (Audio Synthesis)

Run with the default sample handoff bundled with the project:

```bash
python -m agents.audio_agent.agent
```

Run with a specific Phase 1 output:

```bash
# macOS / Linux
PHASE2_HANDOFF_PATH=data/jobs/<job_id>/phase1/phase2_audio_handoff.json \
python -m agents.audio_agent.agent

# Windows PowerShell
$env:PHASE2_HANDOFF_PATH="data/jobs/<job_id>/phase1/phase2_audio_handoff.json"
python -m agents.audio_agent.agent
```

### Phase 3 (Video Generation)

Run with explicit Phase 1 and Phase 2 directories:

```bash
python -m agents.video_agent.agent \
  --phase1-dir data/jobs/<job_id>/phase1 \
  --phase2-dir data/jobs/<job_id>/phase2
```

Skip subtitle burn-in:

```bash
python -m agents.video_agent.agent \
  --phase1-dir data/jobs/<job_id>/phase1 \
  --phase2-dir data/jobs/<job_id>/phase2 \
  --no-subtitles
```

Control number of generated images per scene:

```bash
python -m agents.video_agent.agent \
  --phase1-dir data/jobs/<job_id>/phase1 \
  --phase2-dir data/jobs/<job_id>/phase2 \
  --images-per-scene 4
```

---

## Agent Details

### Phase 1 — Story Agent (`agents/story_agent/`)

Runs as a **LangGraph StateGraph** with three sequential nodes:

```
story_node → character_node → script_node
```

**story_node** (`story_node.py`)
- Generates `StoryOutput`: title, genre, themes, narrative arc, list of scenes, estimated duration
- Each scene has: scene_id, title, setting, tone, arc_position, summary, duration

**character_node** (`character_node.py`)
- Generates `CharacterRoster`: list of characters with voice and appearance configs
- Each character has: name, role (protagonist/antagonist/supporting), personality traits, `VoiceConfig` (gender, age, tone, speed, emotion baseline, TTS style tags), `AppearanceDescription` (physical description, clothing, color palette, art style prompt)

**script_node** (`script_node.py`)
- Generates `ScriptOutput`: dialogue lines grouped by scene
- Each `DialogueLine` has: character_id, text, emotion, timing_offset_seconds

**serializer** (`serializer.py`)
- Writes all Phase 1 artifacts to disk
- Produces `phase2_audio_handoff.json` (audio segments + voice configs + music moods)
- Produces `phase3_video_handoff.json` (scene visual specs + character appearance prompts)

**Validation tools:**
- `validate_story_arc` — checks narrative coherence
- `estimate_duration` — verifies scene timing
- `check_consistency` — validates character appearances across scenes

### Phase 2 — Audio Agent (`agents/audio_agent/`)

Entry point: `run_phase2()` in `agent.py`

**Process per scene:**
1. Load Phase 1 audio handoff (dialogue segments with emotion tags)
2. Synthesize each dialogue line via **Microsoft Edge TTS** (neural voices)
   - Applies emotion-based gain adjustment per line
   - Voice selection by character gender/age/tone config
3. Generate per-scene **procedural background music** based on mood keywords
4. Mix dialogue audio + BGM per scene using FFmpeg
5. Concatenate all scene audio into `full_audio.wav`
6. Build `timing_manifest.json` — frame-accurate sync data for Phase 3

### Phase 3 — Video Agent (`agents/video_agent/`)

**Process per scene:**
1. Generate 3–4 images via **Pollinations AI (FLUX model)**
   - Shot types: wide, mid, closeup, atmosphere
   - Character-consistent prompts built from Phase 1 appearance data
   - Falls back to PIL gradient if API unavailable
2. Calculate per-image duration from actual scene audio timing
3. Animate each image with **Ken Burns effects** via FFmpeg
   - Effects: zoom_in, zoom_out, pan_left, pan_right
4. Crossfade animated images into a scene clip
5. Mux in scene audio (frame-perfectly synced from timing manifest)

**Final assembly:**
1. Concatenate all scene clips with crossfade transitions (MoviePy)
2. Add title card + end card
3. Optionally burn SRT subtitles (FFmpeg)
4. Run quality optimization: CRF 18, slow preset
5. Output `final_output.mp4` or `final_output_subtitled.mp4`

---

## MCP Tool Layer

The **Model Context Protocol (MCP)** layer provides a unified tool abstraction used by all agents. All tools inherit from `BaseTool` in `mcp/base_tool.py` and are registered in `mcp/tool_registry.py`.

### Audio Tools (`mcp/tools/audio_tools/`)

| Tool | File | Purpose |
|------|------|---------|
| TTS Tool | `tts_tool.py` | Edge TTS synthesis — takes dialogue segment + voice config, outputs WAV |
| BGM Tool | `bgm_tool.py` | Procedural background music generation from mood keywords |
| Audio Merger | `audio_merger.py` | `mix_tracks()` for dialogue+BGM, `concatenate_wavs()` for scenes |

### Video Tools (`mcp/tools/video_tools/`)

| Tool | File | Purpose |
|------|------|---------|
| FFmpeg Tool | `ffmpeg_tool.py` | `image_to_video_ken_burns()`, `apply_fade()`, `concatenate_clips()`, `add_audio_to_video()`, `burn_subtitles()` |
| Compositor | `compositor_tool.py` | MoviePy scene concatenation, crossfades, title/end cards |
| Subtitle Tool | `subtitle_tool.py` | SRT generation from timing_manifest |

### Vision Tools (`mcp/tools/vision_tools/`)

| Tool | File | Purpose |
|------|------|---------|
| Image Gen | `image_gen_tool.py` | Pollinations AI / FLUX image generation with shot-type framing |
| Style Transfer | `style_transfer.py` | Optional style transformation |
| Image Edit | `image_edit_tool.py` | Image manipulation utilities |

### LLM Tools (`mcp/tools/llm_tools/`)

| Tool | File | Purpose |
|------|------|---------|
| Text Generator | `text_generator.py` | LLM completion and generation |
| JSON Structurer | `json_structurer.py` | Structured output extraction from LLM responses |

### System Tools (`mcp/tools/system_tools/`)

| Tool | File | Purpose |
|------|------|---------|
| File Tool | `file_tool.py` | File read/write utilities |
| Logger Tool | `logger_tool.py` | Logging interface |
| State Tool | `state_tool.py` | State persistence |

---

## Data Output Structure

Every Phase 4 job stores its outputs at `data/jobs/<job_id>/`:

```text
data/jobs/<job_id>/
├── state.json                         # Job metadata, status, progress, errors
├── phase1/
│   ├── story.json                     # Narrative structure, scenes, arc
│   ├── characters.json                # Character roster with voice/appearance configs
│   ├── script.json                    # Full dialogue with timing and emotions
│   ├── phase2_audio_handoff.json      # Audio synthesis instructions for Phase 2
│   ├── phase3_video_handoff.json      # Visual generation instructions for Phase 3
│   └── summary.json                   # Phase 1 execution summary
├── phase2/
│   ├── segments/                      # Individual TTS WAV files per dialogue line
│   ├── bgm/                           # Per-scene background music tracks
│   ├── scenes/                        # Per-scene mixed audio (dialogue + BGM)
│   ├── full_audio.wav                 # All scenes concatenated
│   ├── timing_manifest.json           # Frame-accurate sync data for Phase 3
│   └── summary.json
└── phase3/
    ├── images/                        # Generated scene images (FLUX/Pollinations)
    ├── clips/                         # Animated image clips with Ken Burns effects
    ├── scenes/                        # Per-scene assembled video
    ├── subtitles.srt                  # Generated subtitle file
    ├── final_raw.mp4                  # Pre-optimization video
    ├── final_output.mp4               # Quality-optimized output
    ├── final_output_subtitled.mp4     # With subtitles burned in
    └── summary.json
```

The final playable video (served by the web app) is:

```text
data/jobs/<job_id>/phase3/final_output_subtitled.mp4   # if BURN_SUBTITLES=true
data/jobs/<job_id>/phase3/final_output.mp4              # if BURN_SUBTITLES=false
```

---

## Docker

Build and start both backend and frontend:

```bash
docker compose up --build
```

Open the app at `http://localhost:5173`. The backend API is at `http://localhost:8000`.

The compose setup mounts `./data` into the backend container so all generated jobs persist on your local machine.

**Environment variables with Docker:** Create a `.env` file (from `.env.example`) in the project root before running `docker compose up`. Docker Compose will pick it up automatically.

---

## Testing

Run Python syntax checks across all source modules:

```bash
python -m compileall backend state_manager agents
```

Run all tests:

```bash
pytest -q
```

Run tests for a specific phase:

```bash
pytest tests/unit/test_phase1.py -q
pytest tests/unit/test_phase2.py -q
pytest tests/unit/test_phase3.py -q
```

Build the frontend (production build verification):

```bash
cd frontend
npm run build
```

Preview the production build locally:

```bash
cd frontend
npm run preview
```

---

## Troubleshooting

### Backend imports fail on startup

Make sure the virtual environment is active and all dependencies are installed:

```bash
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Phase 1 fails immediately

Check that your API key is set correctly in `.env`:

```env
OPENAI_API_KEY=sk-your-real-key-here
# or
GOOGLE_API_KEY=your-real-key-here
```

And that `PHASE1_MODEL` matches the provider whose key you set (e.g., `gpt-4o` for OpenAI, `gemini-2.0-flash` for Google). Restart the backend after changing `.env`.

### Phase 2 audio fails

Phase 2 requires FFmpeg for audio conversion. Verify it is installed and accessible:

```bash
ffmpeg -version
```

On Windows, if FFmpeg is not on PATH after installation, restart your terminal or add it manually:
```powershell
$env:PATH += ";C:\path\to\ffmpeg\bin"
```

### Phase 3 video fails

Confirm FFmpeg is accessible from the same shell running the backend:

```bash
ffmpeg -version
```

Check the job's error details:

```bash
curl http://localhost:8000/status/<job_id>
```

Also inspect `data/jobs/<job_id>/phase3/summary.json` for a detailed error trace.

### Frontend cannot reach backend

Verify the backend is running and healthy:

```bash
curl http://localhost:8000/health
```

Ensure the frontend is configured to proxy to port `8000` (check `frontend/vite.config.js`). Restart both services if needed.

### Video or audio does not play in the browser

Check the result endpoint for media URLs:

```bash
curl http://localhost:8000/result/<job_id>
```

Look for:

```json
{
  "assets": {
    "audio_url": "/media/jobs/<job_id>/phase2/full_audio.wav",
    "video_url": "/media/jobs/<job_id>/phase3/final_output.mp4"
  }
}
```

If these paths are missing or null, the relevant phase did not complete successfully. Check `state.json` and `summary.json` in the job directory.

### Frontend node_modules issues

```bash
cd frontend
rm -rf node_modules    # macOS/Linux
# or: Remove-Item -Recurse -Force node_modules   # Windows PowerShell
npm install
npm run build
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Recommended | — | OpenAI API key for Phase 1 LLM (GPT-4o, etc.) |
| `GOOGLE_API_KEY` | Optional | — | Google Gemini API key for Phase 1 LLM |
| `PHASE1_MODEL` | No | `gpt-4o` | LLM model for Phase 1. Options: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gemini-2.0-flash`, `gemini-1.5-flash` |
| `PHASE1_OUTPUT_DIR` | No | `data/outputs` | Root directory for standalone Phase 1 outputs |
| `PHASE2_HANDOFF_PATH` | No | bundled sample | Path to Phase 1 audio handoff JSON for standalone Phase 2 runs |
| `PHASE2_OUTPUT_DIR` | No | `data/outputs/phase2` | Root directory for standalone Phase 2 outputs |
| `PHASE2_EDGE_TTS_VOICE` | No | auto | Override Edge TTS voice for all characters (e.g., `en-US-JennyNeural`) |
| `BURN_SUBTITLES` | No | `true` | Burn SRT subtitles into the final video |
| `USE_OLLAMA` | No | `false` | Use a local Ollama model for Phase 3 image prompt enhancement |
| `IMAGES_PER_SCENE` | No | `3` | Number of images generated per scene in Phase 3 (3–4 recommended) |

---

## Git Notes

The following are excluded from version control via `.gitignore`:

- `data/` — all generated jobs, outputs, and temporary files
- `.env` — your local API keys
- `.venv/` — Python virtual environment
- `frontend/node_modules/` — Node.js packages
- `__pycache__/` — Python bytecode

Commit only: source code, configuration, tests, and documentation.
