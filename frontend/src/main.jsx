import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Download, FileJson, Film, Music2, Play, RefreshCcw, Wand2 } from "lucide-react";
import "./styles.css";

const PHASES = [
  { id: 1, title: "Story", detail: "Structured story, scenes, characters" },
  { id: 2, title: "Audio", detail: "Dialogue, BGM, timing manifest" },
  { id: 3, title: "Video", detail: "Images, motion, final MP4" }
];

function statusLabel(value) {
  if (!value) return "pending";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function PhaseTracker({ job, onRerun, disabled }) {
  return (
    <section className="phase-list" aria-label="Pipeline progress">
      {PHASES.map((phase) => {
        const status = job?.phases?.[String(phase.id)] ?? "pending";
        return (
          <article className={`phase phase-${status}`} key={phase.id}>
            <div className="phase-index">{phase.id}</div>
            <div className="phase-main">
              <div className="phase-title-row">
                <h3>{phase.title}</h3>
                <span>{statusLabel(status)}</span>
              </div>
              <p>{phase.detail}</p>
            </div>
            <button
              className="icon-button"
              type="button"
              onClick={() => onRerun(phase.id)}
              disabled={disabled || !job?.job_id}
              title={`Re-run Phase ${phase.id}`}
              aria-label={`Re-run Phase ${phase.id}`}
            >
              <RefreshCcw size={17} />
            </button>
          </article>
        );
      })}
    </section>
  );
}

function JsonPreview({ result }) {
  const payload = useMemo(() => {
    if (!result?.preview) return {};
    return {
      story: result.preview.story,
      characters: result.preview.characters,
      script: result.preview.script,
      timing_manifest: result.preview.timing_manifest
    };
  }, [result]);

  return (
    <section className="panel json-panel">
      <div className="panel-heading">
        <FileJson size={18} />
        <h2>JSON Preview</h2>
      </div>
      <pre>{JSON.stringify(payload, null, 2)}</pre>
    </section>
  );
}

function Outputs({ result }) {
  const audioUrl = result?.assets?.audio_url;
  const videoUrl = result?.assets?.video_url;

  return (
    <section className="panel output-panel">
      <div className="panel-heading">
        <Film size={18} />
        <h2>Outputs</h2>
      </div>

      <div className="media-block video-block">
        {videoUrl ? (
          <video controls src={videoUrl} />
        ) : (
          <div className="empty-media">
            <Play size={24} />
            <span>Final video will appear here</span>
          </div>
        )}
      </div>

      <div className="asset-row">
        <Music2 size={17} />
        {audioUrl ? <audio controls src={audioUrl} /> : <span>Audio pending</span>}
      </div>

      <a
        className={`download-button ${videoUrl ? "" : "disabled"}`}
        href={videoUrl || "#"}
        download
        aria-disabled={!videoUrl}
      >
        <Download size={17} />
        Download MP4
      </a>
    </section>
  );
}

function App() {
  const [prompt, setPrompt] = useState("A hopeful astronaut discovers a glowing ocean beneath Mars.");
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const eventSourceRef = useRef(null);

  const isRunning = job?.status === "running" || job?.status === "pending";

  useEffect(() => {
    return () => eventSourceRef.current?.close();
  }, []);

  async function fetchResult(jobId) {
    const response = await fetch(`/result/${jobId}`);
    if (response.ok) {
      setResult(await response.json());
    }
  }

  function subscribe(jobId) {
    eventSourceRef.current?.close();
    const stream = new EventSource(`/events/${jobId}`);
    eventSourceRef.current = stream;
    stream.onmessage = (event) => {
      const nextJob = JSON.parse(event.data);
      setJob(nextJob);
      fetchResult(nextJob.job_id);
      if (nextJob.status === "completed" || nextJob.status === "failed") {
        stream.close();
      }
    };
    stream.onerror = () => {
      stream.close();
    };
  }

  async function startPipeline() {
    setError("");
    setResult(null);
    const response = await fetch("/run-pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt })
    });
    if (!response.ok) {
      setError(await response.text());
      return;
    }
    const created = await response.json();
    setJob({ ...created, phases: { 1: "pending", 2: "pending", 3: "pending" }, progress: 0 });
    subscribe(created.job_id);
  }

  async function rerunPhase(phaseId) {
    if (!job?.job_id) return;
    setError("");
    const response = await fetch(`/run-phase/${job.job_id}/${phaseId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt })
    });
    if (!response.ok) {
      setError(await response.text());
      return;
    }
    subscribe(job.job_id);
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <div className="prompt-panel">
          <div className="brand-row">
            <Wand2 size={22} />
            <h1>Agentic Video Pipeline</h1>
          </div>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Describe the short video you want to generate..."
          />
          <div className="actions-row">
            <button className="primary-button" type="button" onClick={startPipeline} disabled={isRunning}>
              <Play size={18} />
              Generate Video
            </button>
            <div className="job-meta">
              <span>{job?.job_id ? `Job ${job.job_id.slice(0, 8)}` : "No job yet"}</span>
              <strong>{statusLabel(job?.status ?? "idle")}</strong>
            </div>
          </div>
          {error ? <p className="error-text">{error}</p> : null}
        </div>

        <div className="progress-panel">
          <div className="progress-heading">
            <span>{job?.message ?? "Ready"}</span>
            <strong>{job?.progress ?? 0}%</strong>
          </div>
          <div className="progress-track">
            <div style={{ width: `${job?.progress ?? 0}%` }} />
          </div>
          <PhaseTracker job={job} onRerun={rerunPhase} disabled={isRunning} />
        </div>
      </section>

      <section className="results-grid">
        <Outputs result={result} />
        <JsonPreview result={result} />
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
