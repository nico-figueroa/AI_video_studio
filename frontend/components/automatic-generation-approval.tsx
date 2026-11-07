"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type AutomaticGenerationState, type RenderMode } from "@/services/api";
import { Button, Notice } from "@/components/ui";
import { ProductionEstimateDisclosure } from "@/components/production-estimate";

export function AutomaticGenerationApproval({ projectId, initialMode = "local_animation", onApprovalChange }: {
  projectId: number; initialMode?: RenderMode; onApprovalChange?: (approved: boolean) => void;
}) {
  const [mode, setMode] = useState<RenderMode>(initialMode);
  const [state, setState] = useState<AutomaticGenerationState | null>(null);
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const next = await api.getAutomaticGeneration(projectId, mode);
    setState(next);
    onApprovalChange?.(next.approved);
    setChecked(false);
  }, [projectId, mode, onApprovalChange]);
  useEffect(() => { load().catch((reason: Error) => setError(reason.message)); }, [load]);
  async function approve() {
    if (!state || !checked) return;
    setBusy(true); setError("");
    try {
      const next = await api.approveAutomaticGeneration(projectId, state.estimate.estimate_id, mode);
      setState(next);
      onApprovalChange?.(next.approved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not approve automatic generation.");
    } finally { setBusy(false); }
  }
  return <section className="editor-panel">
    <h2>Automatic stage generation</h2>
    <label>Video source <select aria-label="Automatic video source" value={mode} disabled={busy}
      onChange={(event) => { setState(null); onApprovalChange?.(false); setMode(event.target.value === "still_images" ? "still_images" : "local_animation"); }}>
      <option value="local_animation">Local generated motion (non-commercial SVD)</option>
      <option value="still_images">Still images only — do not run the video model</option>
    </select></label>
    {error && <Notice tone="error">{error}</Notice>}
    {state && <>
      <ProductionEstimateDisclosure estimate={state.estimate} title="Automatic artwork and motion budget" />
      <details><summary>How stage approval works</summary><p>One approval enables all missing portraits on Characters, all missing scene images on Scenes,
        and {mode === "local_animation" ? "all missing GPU clips on Render" : "explicit still-image rendering"}.
        Every asset still needs review; regeneration is never automatic.</p></details>
      {state.approved ? <Notice tone="success">Automatic generation approved for this prompt and model. Follow Story → Characters → Scenes → Timeline → Render.</Notice> : <>
        <label className="production-approval"><input type="checkbox" checked={checked} disabled={busy}
          onChange={(event) => setChecked(event.target.checked)} />
          I approve the displayed estimates for automatic stage entry. Local motion is non-commercial, two seconds per scene; narration and final export are separate.</label>
        <div className="progression-actions"><Button disabled={busy || !checked} onClick={approve}>Approve automatic stage generation</Button></div>
      </>}
    </>}
  </section>;
}
