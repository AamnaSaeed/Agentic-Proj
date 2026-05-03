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
