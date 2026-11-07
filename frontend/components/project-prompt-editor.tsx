"use client";

import { useState } from "react";
import { api, type Project } from "@/services/api";
import { Button, Notice } from "@/components/ui";

export function ProjectPromptEditor({ project, onRestart }: { project: Project; onRestart: () => void }) {
  const [prompt, setPrompt] = useState(project.prompt);
  const [seconds, setSeconds] = useState(project.target_seconds);
  const [budget, setBudget] = useState(project.max_budget);
  const [wait, setWait] = useState(project.max_wait_minutes);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function restart(event: React.FormEvent) {
    event.preventDefault();
    if (!window.confirm("Restart this project with the edited prompt? All story, character/scene artwork, imports, narration, motion clips and videos will be deleted. Recorded spending is retained. No generation starts until you approve the new estimates.")) return;
    setBusy(true); setError("");
    try {
      await api.restartProject(project.id, {
        expected_prompt:project.prompt, prompt, target_seconds:seconds, max_budget:budget, max_wait_minutes:wait,
      });
      onRestart();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not restart project.");
    } finally { setBusy(false); }
  }
  return <details className="editor-panel"><summary>Edit original prompt / restart project</summary>
    <form onSubmit={restart}>
      <label htmlFor="original-prompt">Original prompt</label>
      <textarea id="original-prompt" className="text-input" minLength={12} maxLength={4000} required value={prompt}
        disabled={busy} onChange={(event) => setPrompt(event.target.value)} />
      <div className="form-grid">
        <label>Target length (seconds)<input type="number" min={1} max={600} step={1} required value={seconds} onChange={(event) => setSeconds(Number(event.target.value))} /></label>
        <label>Maximum budget (USD)<input type="number" min={0} max={1000} step={0.01} required value={budget} onChange={(event) => setBudget(Number(event.target.value))} /></label>
        <label>Maximum wait (minutes)<input type="number" min={1} max={1440} required value={wait} onChange={(event) => setWait(Number(event.target.value))} /></label>
      </div>
      <Notice>Restart deletes the previous sequence and all supplied inputs after confirmation. Spending is not refunded. Target length is a planning goal; speech is never truncated to force it.</Notice>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="progression-actions"><Button type="submit" disabled={busy}>Save prompt and restart from Plan</Button></div>
    </form>
  </details>;
}
