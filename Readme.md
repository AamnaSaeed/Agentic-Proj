# Agentic AI Video Pipeline

This project generates short animated videos from a prompt using a multi-phase agent pipeline and a Phase 4 web app.

## What The Project Does

The pipeline is organized into four phases:

| Phase | Name | Output |
|------|------|--------|
| 1 | Story | `story.json`, `characters.json`, `script.json`, Phase 2/3 handoff JSON |
| 2 | Audio | dialogue audio, background music, scene mixes, `timing_manifest.json` |
| 3 | Video | generated images, animated clips, subtitles, final MP4 |
| 4 | Web App | FastAPI backend, React/Vite frontend, job status, reruns, media preview |

Phase 4 runs Phase 1 -> Phase 2 -> Phase 3 as a job and stores every output under `data/jobs/<job_id>/`.

## Project Structure

```text
.
├── agents/
│   ├── story_agent/        # Phase 1
│   ├── audio_agent/        # Phase 2
│   ├── video_agent/        # Phase 3
│   └── edit_agent/         # Future Phase 5 placeholder
├── backend/
│   ├── app.py              # FastAPI app and API routes
│   ├── schemas.py          # API request/response schemas
│   └── services/
│       ├── job_store.py
│       └── pipeline_runner.py
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.js
├── mcp/                    # Tool layer used by agents
├── shared/schemas/         # Pydantic schemas and handoff contracts
├── state_manager/          # JSON state persistence helpers
├── tests/
├── data/
│   ├── jobs/               # Generated Phase 4 jobs, ignored by Git
│   ├── outputs/            # Older/manual generated outputs, ignored by Git
│   ├── temp/               # Ignored by Git
│   └── state_versions/     # Ignored by Git
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

## Prerequisites

Install these before running the full app:

- Python 3.11+ recommended
- Node.js 20+ or 22+
- FFmpeg
- A Google Gemini API key for Phase 1

Check your versions:

```bash
python --version
node --version
npm --version
ffmpeg -version
```

On Ubuntu/Debian, install FFmpeg with:

```bash
sudo apt update
sudo apt install ffmpeg
```

## Environment Setup

Create a local `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
GOOGLE_API_KEY=your_google_api_key_here
PHASE1_MODEL=gemini-2.0-flash
PHASE1_OUTPUT_DIR=data/outputs
PHASE2_OUTPUT_DIR=data/outputs/phase2
BURN_SUBTITLES=true
USE_OLLAMA=false
IMAGES_PER_SCENE=3
```

`.env` is ignored by Git. Do not commit real API keys.

## Install Backend

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Install Frontend

From the project root:

```bash
cd frontend
npm install
cd ..
```

## Run The Phase 4 App Locally

Terminal 1, start the backend:

```bash
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2, start the frontend:

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend proxies API requests to:

```text
http://localhost:8000
```

## Run A Full Video Job

In the web app:

1. Enter a prompt.
2. Click `Generate Video`.
3. Watch the progress tracker for Phase 1, Phase 2, and Phase 3.
4. When the job completes, inspect the JSON preview.
5. Play generated audio if available.
6. Play or download the final video.

Generated files are stored like this:

```text
data/jobs/<job_id>/
├── state.json
├── phase1/
│   ├── story.json
│   ├── characters.json
│   ├── script.json
│   ├── phase2_audio_handoff.json
│   ├── phase3_video_handoff.json
│   └── summary.json
├── phase2/
│   ├── segments/
│   ├── bgm/
│   ├── scenes/
│   ├── full_audio.wav
│   ├── timing_manifest.json
│   └── summary.json
└── phase3/
    ├── images/
    ├── clips/
    ├── scenes/
    ├── subtitles.srt
    ├── final_raw.mp4
    ├── final_output.mp4
    ├── final_output_subtitled.mp4
    └── summary.json
```

Depending on subtitle settings, the final playable video is usually one of:

```text
data/jobs/<job_id>/phase3/final_output.mp4
data/jobs/<job_id>/phase3/final_output_subtitled.mp4
```

## Backend API

### Health Check

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

### Start Full Pipeline

```bash
curl -X POST http://localhost:8000/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"prompt":"A tiny robot discovers music on a silent moon."}'
```

Response:

```json
{
  "job_id": "example_job_id",
  "status": "pending"
}
```

### Check Job Status

```bash
curl http://localhost:8000/status/<job_id>
```

The status object includes:

- `status`: `pending`, `running`, `completed`, or `failed`
- `current_phase`
- `phases`
- `progress`
- `message`
- `errors`
- `outputs`

### Stream Live Progress

```bash
curl http://localhost:8000/events/<job_id>
```

This endpoint uses Server-Sent Events.

### Get Results

```bash
curl http://localhost:8000/result/<job_id>
```

The result includes:

- job state
- JSON previews
- audio path and `/media/...` URL
- video path and `/media/...` URL
- download URL

### Re-run A Specific Phase

Re-run Phase 1 for a specific job:

```bash
curl -X POST http://localhost:8000/run-phase/<job_id>/1 \
  -H "Content-Type: application/json" \
  -d '{"prompt":"A brighter revised story prompt."}'
```

Re-run Phase 2:

```bash
curl -X POST http://localhost:8000/run-phase/<job_id>/2 \
  -H "Content-Type: application/json" \
  -d '{}'
```

Re-run Phase 3:

```bash
curl -X POST http://localhost:8000/run-phase/<job_id>/3 \
  -H "Content-Type: application/json" \
  -d '{}'
```

There is also a latest-job endpoint:

```bash
curl -X POST http://localhost:8000/run-phase/2 \
  -H "Content-Type: application/json" \
  -d '{}'
```

The frontend uses the job-specific endpoint.

## Run Individual Phases

### Phase 1

Phase 1 is normally run by the Phase 4 backend. It requires `GOOGLE_API_KEY`.

The backend calls:

```python
create_phase1_graph().invoke(...)
```

and writes artifacts through:

```python
serialize_phase1_outputs(...)
```

### Phase 2

Run Phase 2 with the sample handoff path from `.env.example`:

```bash
python -m agents.audio_agent.agent
```

Run Phase 2 with a specific handoff:

```bash
PHASE2_HANDOFF_PATH=data/jobs/<job_id>/phase1/phase2_audio_handoff.json \
python -m agents.audio_agent.agent
```

### Phase 3

Run Phase 3 with explicit Phase 1 and Phase 2 directories:

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

Control image count:

```bash
python -m agents.video_agent.agent \
  --phase1-dir data/jobs/<job_id>/phase1 \
  --phase2-dir data/jobs/<job_id>/phase2 \
  --images-per-scene 4
```

## Testing

Run Python syntax checks:

```bash
python -m compileall backend state_manager agents
```

Run all tests:

```bash
pytest -q
```

Run phase-specific tests:

```bash
pytest tests/unit/test_phase1.py -q
pytest tests/unit/test_phase2.py -q
pytest tests/unit/test_phase3.py -q
```

Run frontend build:

```bash
cd frontend
npm run build
```

If tests fail with missing Python packages:

```bash
pip install -r requirements.txt
```

If frontend install/build fails, check Node and reinstall:

```bash
cd frontend
rm -rf node_modules
npm install
npm run build
```

## Docker

Build and run both services:

```bash
docker compose up --build
```

Open:

```text
http://localhost:5173
```

Backend:

```text
http://localhost:8000
```

The compose setup mounts local `./data` into the backend container, so generated jobs remain on your machine.

## Useful Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GOOGLE_API_KEY` | Yes for Phase 1 | none | Gemini API key |
| `PHASE1_MODEL` | No | `gemini-1.5-flash` in code, example uses `gemini-2.0-flash` | Gemini model for story generation |
| `PHASE1_OUTPUT_DIR` | No | `data/outputs` | Manual Phase 1 output root |
| `PHASE2_HANDOFF_PATH` | No | bundled sample path | Manual Phase 2 handoff |
| `PHASE2_OUTPUT_DIR` | No | `data/outputs/phase2` | Manual Phase 2 output root |
| `BURN_SUBTITLES` | No | `true` | Burn subtitles into final video |
| `USE_OLLAMA` | No | `false` | Optional prompt enhancement in Phase 3 |
| `IMAGES_PER_SCENE` | No | `3` | Number of generated images per scene |

## Troubleshooting

### Backend imports fail

Make sure the virtual environment is active and dependencies are installed:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Phase 1 fails

Check `.env`:

```env
GOOGLE_API_KEY=your_real_key
PHASE1_MODEL=gemini-2.0-flash
```

Then restart the backend.

### Phase 2 audio fails

Phase 2 uses Edge TTS and FFmpeg conversion. Confirm FFmpeg works:

```bash
ffmpeg -version
```

### Phase 3 video fails

Confirm FFmpeg is installed and visible from the same shell running the backend:

```bash
which ffmpeg
ffmpeg -version
```

Also check the job's `state.json` and `phase3/summary.json` if present.

### Frontend cannot reach backend

Make sure FastAPI is running on port `8000`:

```bash
curl http://localhost:8000/health
```

Then restart Vite:

```bash
cd frontend
npm run dev
```

### Video or audio does not play in browser

Check `/result/<job_id>` and look for:

```json
{
  "assets": {
    "audio_url": "/media/...",
    "video_url": "/media/..."
  }
}
```

If paths are missing, the relevant phase did not complete.

## Git Notes

Generated jobs, output media, caches, virtual environments, and `.env` are ignored by Git. Commit source code, configs, tests, and documentation only.
