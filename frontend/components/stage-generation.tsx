"use client";

import { useEffect, useRef, useState } from "react";
import { api, type GenerationStage, type StageGenerationState } from "@/services/api";
import { Button, Loading, Notice } from "@/components/ui";

export function StageGeneration({ projectId, stage, onComplete, onActive }: {
  projectId: number; stage: GenerationStage;
  onComplete: () => Promise<void>; onActive: (active: boolean) => void;
}) {
  const [state, setState] = useState<StageGenerationState | null>(null);
  const [error, setError] = useState("");
  const callbacks = useRef({ onComplete, onActive });
  useEffect(() => { callbacks.current = { onComplete, onActive }; }, [onComplete, onActive]);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function watch(next: StageGenerationState) {
      if (cancelled) return;
      setState(next);
      const running = next.job?.status === "queued" || next.job?.status === "running";
      callbacks.current.onActive(running);
      if (!running) {
        await callbacks.current.onComplete();
        return;
      }
      timer = setTimeout(async () => {
        try { await watch(await api.getStageGeneration(projectId, stage)); }
        catch (reason) {
          if (!cancelled) {
            setError(reason instanceof Error ? reason.message : "Could not read generation progress.");
            callbacks.current.onActive(true);
          }
        }
      }, 2000);
    }
    async function start() {
      callbacks.current.onActive(true);
      try { await watch(await api.startStageGeneration(projectId, stage, attempt > 0)); }
      catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Automatic stage generation could not start.");
          callbacks.current.onActive(false);
        }
      }
    }
    void start();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [projectId, stage, attempt]);
  const active = state?.job?.status === "queued" || state?.job?.status === "running";
  return <section className="generation-panel" aria-live="polite">
    <h2>{stage === "animations" ? "Local video-model generation" : `Automatic ${stage} artwork`}</h2>
    {error && <Notice tone="error">{error} Review automatic-generation approval on Plan if needed.</Notice>}
    {state?.job?.error && <Notice tone="error">{state.job.error}</Notice>}
    {state?.job && <><p>{state.job.current_stage}</p><progress value={state.job.progress} max={100} /><p>{state.job.progress}%</p></>}
    {active && <Loading workflow={stage === "animations" ? "render" : stage} label="Generating all missing assets in sequence. Completed assets are retained." />}
    {state && !active && <p>{state.missing ? `${state.missing} assets still need generation.` : "All assets generated. Preview and approve them below."}</p>}
    {(error || state?.job?.status === "failed") && <Button variant="secondary" onClick={() => {
      setError(""); setAttempt((value) => value + 1);
    }}>Retry missing assets / reconnect</Button>}
  </section>;
}
