"use client";

import { useCallback, useEffect, useState } from "react";
import { api, assetUrl, type AnimationState } from "@/services/api";
import { Button, Loading, Notice } from "@/components/ui";
import { ProductionEstimateDisclosure } from "@/components/production-estimate";

export function SceneAnimation({ projectId, sceneId, disabled, onReview, open = false, pollActive = false, batch = false }: {
  projectId: number; sceneId: number; disabled: boolean; onReview: () => Promise<void>;
  open?: boolean; pollActive?: boolean; batch?: boolean;
}) {
  const [state, setState] = useState<AnimationState | null>(null);
  const [error, setError] = useState("");
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    setState(await api.getAnimation(projectId, sceneId));
  }, [projectId, sceneId]);
  useEffect(() => { refresh().catch((e: Error) => setError(e.message)); }, [refresh]);
  const running = state?.job?.status === "queued" || state?.job?.status === "running";
  useEffect(() => {
    if (!running && !pollActive) return;
    const timer = setInterval(() => {
      api.getAnimation(projectId, sceneId).then(async (next) => {
        setState(next);
        if (running && next.job && !["queued","running"].includes(next.job.status)) await onReview();
      }).catch((e: Error) => setError(e.message));
    }, 4000);
    return () => clearInterval(timer);
  }, [running, pollActive, projectId, sceneId, onReview]);
  async function act(review?: boolean) {
    if (!state) return;
    setBusy(true); setError("");
    try {
      if (review !== undefined && state.job) {
        await api.reviewAnimation(projectId, sceneId, state.job.job_id, review);
        await onReview();
      } else {
        await api.startAnimation(projectId, sceneId, state.estimate.estimate_id);
        await onReview();
      }
      setApproved(false);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Local animation failed.");
    } finally { setBusy(false); }
  }
  return <details open={open}><summary>{batch ? "Preview and approve local model clip" : "Experimental local image-to-video"}</summary>
    <details><summary>Model license and limitations</summary><p>Powered by Stability AI. <a href="https://huggingface.co/stabilityai/stable-video-diffusion-img2vid/blob/main/LICENSE.md" target="_blank" rel="noreferrer">Model license</a> / non-commercial deployment only.</p></details>
    {error && <Notice tone="error">{error}</Notice>}
    {state ? <>
      <ProductionEstimateDisclosure estimate={state.estimate} title="Local animation estimate" />
      {!batch && <><label className="production-approval"><input type="checkbox" checked={approved}
        disabled={disabled || busy || running} onChange={(e) => setApproved(e.target.checked)} />
        I approve local GPU execution for non-commercial use and understand the motion limitations.</label>
      <div className="progression-actions"><Button disabled={disabled || busy || running || !approved} onClick={() => act()}>Generate local motion clip</Button></div></>}
      {running && <><Loading workflow="render" label="Local GPU: loading model / generating 14 frames." />
        <progress value={state.job?.progress ?? 0} max={100} aria-label="Local animation progress" />
        <p>{state.job?.progress}% / frame-generation steps, followed by encoding and validation.</p></>}
      {state.job?.error && <Notice tone="error">{state.job.error}</Notice>}
      {state.job?.stale && <Notice>Source content changed. This clip cannot be approved for the current scene.</Notice>}
      {state.job?.clip_url && <video src={assetUrl(state.job.clip_url)} controls preload="metadata" style={{ maxWidth:"100%" }} />}
      {state.job?.status === "completed" && <>
        <p>{state.job.approved ? "Selected for final rendering." : "Preview and explicitly approve before using this clip."}</p>
        <div className="progression-actions"><Button disabled={disabled || busy || running || state.job.stale || state.job.approved}
          onClick={() => act(true)}>Approve animation for render</Button></div>
      </>}
      {state.job && !running && <Button variant="secondary" disabled={disabled || busy}
        onClick={() => act(false)}>Deselect all clips / use still-image camera effects</Button>}
    </> : <Button variant="secondary" onClick={() => refresh().catch((e: Error) => setError(e.message))}>Load animation estimate</Button>}
  </details>;
}
