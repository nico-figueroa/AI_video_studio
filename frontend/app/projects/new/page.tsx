"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/services/api";
import { Button, Notice } from "@/components/ui";

export default function NewProjectPage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [minutes, setMinutes] = useState(1);
  const [budget, setBudget] = useState(5);
  const [wait, setWait] = useState(20);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getAISettings()
      .then((settings) => {
        setBudget(settings.default_budget);
        setWait(settings.default_wait_minutes);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject({
        prompt,
        target_minutes: minutes,
        max_budget: budget,
        max_wait_minutes: wait,
      });
      router.push(`/projects/${project.project_id}/analysis`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the project.");
      setBusy(false);
    }
  }

  return (
    <main className="form-page">
      <header className="workspace-head">
        <a className="brand" href="/dashboard"><span className="brand-mark">✳</span> Framewise</a>
        <div className="crumb"><a href="/dashboard">Projects</a><span>/</span><span>New project</span></div>
        <span className="avatar">N</span>
      </header>
      <div className="create-wrap">
        <a href="/dashboard" className="back-link">← &nbsp;All projects</a>
        <div className="eyebrow">LET’S MAKE SOMETHING</div>
        <h1>Start with the <em>story.</em></h1>
        <p className="form-intro">Set your creative idea and your limits. We’ll show you what’s possible before anything is generated.</p>
        <form className="create-form" onSubmit={submit}>
          <label htmlFor="prompt">What’s your video about?<span>YOUR IDEA</span></label>
          <textarea id="prompt" minLength={12} maxLength={4000} required placeholder="A retired astronaut discovers an underwater civilization…" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
          <div className="form-grid">
            <label htmlFor="minutes">Target length <span>MINUTES</span><input id="minutes" type="number" min={1} max={10} value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /></label>
            <label htmlFor="budget">Max budget <span>USD · ESTIMATE CEILING</span><div className="input-prefix"><i>$</i><input id="budget" type="number" min={0} step={0.25} value={budget} onChange={(event) => setBudget(Number(event.target.value))} /></div></label>
            <label htmlFor="wait">Max wait <span>MINUTES</span><input id="wait" type="number" min={1} max={1440} value={wait} onChange={(event) => setWait(Number(event.target.value))} /></label>
          </div>
          <Notice>Creating the project does not call an AI provider. The next page shows the model, estimated cost, duration, and call count before you choose to generate a story bible.</Notice>
          {error && <Notice tone="error">{error}</Notice>}
          <div className="form-actions"><span>Next: review estimate before generation</span><Button type="submit" disabled={busy || prompt.trim().length < 12}>{busy ? "Creating project…" : "Review estimate"} {!busy && <span>→</span>}</Button></div>
        </form>
      </div>
    </main>
  );
}
