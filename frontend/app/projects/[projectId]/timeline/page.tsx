"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, assetUrl, type Narration, type Project, type Timeline, type MotionPlan } from "@/services/api";
import { Button, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";
import { ProductionEstimateDisclosure } from "@/components/production-estimate";
import { SceneAnimation } from "@/components/scene-animation";

export default function TimelinePage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [project, setProject] = useState<Project | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [narration, setNarration] = useState<Narration | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [dirty, setDirty] = useState(false);
  const [approveText, setApproveText] = useState(false);
  const [approveAudio, setApproveAudio] = useState(false);
  const refresh = useCallback(async () => {
    const [projectData, timelineData, narrationData] = await Promise.all([
      api.getProject(id), api.getTimeline(id), api.getNarration(id),
    ]);
    setProject(projectData); setTimeline(timelineData); setNarration(narrationData);
    setDirty(false); setApproveText(false); setApproveAudio(false);
  }, [id]);
  useEffect(() => { refresh().catch((reason: Error) => setError(reason.message)); }, [refresh]);

  async function act(operation: "text" | "audio" | "save") {
    if (!timeline || !narration) return;
    setBusy(operation); setError("");
    let succeeded = false;
    try {
      if (operation === "text") await api.generateNarration(id, narration.narration_estimate.estimate_id, narration.items.length > 0);
      if (operation === "audio") await api.generateAudio(id, narration.audio_estimate.estimate_id);
      if (operation === "save") await api.saveTimeline(id, timeline);
      succeeded = true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Production request failed.");
    } finally {
      if (operation !== "save" || succeeded) {
        try { await refresh(); }
        catch (reason) { setError((message) => `${message} ${reason instanceof Error ? reason.message : "Refresh failed."}`.trim()); }
      }
      setBusy("");
    }
  }

  function move(index: number, offset: number) {
    if (!timeline) return;
    const scenes = [...timeline.scenes];
    [scenes[index], scenes[index + offset]] = [scenes[index + offset], scenes[index]];
    setTimeline({ ...timeline, scenes }); setDirty(true);
  }
  async function motion(sceneId: number, plan: MotionPlan) {
    if (!timeline || dirty) return;
    setBusy("motion"); setError("");
    try { await api.saveMotion(id,sceneId,timeline.revision,plan); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save motion plan."); }
    finally { setBusy(""); }
  }

  const remaining = project ? Math.max(0, project.max_budget - project.estimated_spend) : 0;
  const locked = Boolean(busy) || Boolean(project && ["rendering", "narrating", "generating_audio", "planning", "animating"].includes(project.status));
  const currentNarration = narration && timeline && narration.items.length === timeline.scenes.length && narration.items.length > 0 && narration.items.every((item) => !item.stale);
  return <ProjectLayout projectId={id} title={project?.title ?? "Timeline"}>
    <PageHeading label="05 / TIMELINE" title="Give every scene a voice." description="Review scenes, then narration/audio and the timeline. New synthetic speech is AI-generated; supplied narration and original audio are preserved." />
    {error && <Notice tone="error">{error}</Notice>}
    {!timeline || !narration || !project ? <><Loading /><Button variant="secondary" onClick={() => { setError(""); refresh().catch((reason: Error) => setError(reason.message)); }}>Retry loading</Button></> : <>
      <Notice>Remaining estimated budget: ${remaining.toFixed(4)}. Audio retries reuse completed files; estimates are not actual invoices.</Notice>
      <Notice>Target length: {project.target_seconds} seconds; current timeline: {timeline.duration_seconds} seconds.
        Narration may extend the target and is never truncated. In local-motion mode, entering Render generates all missing clips under your approved automatic stage budget.</Notice>
      <ProductionEstimateDisclosure estimate={narration.narration_estimate} title="Narration generation estimate" />
      <label className="production-approval"><input type="checkbox" checked={approveText} disabled={locked || dirty} onChange={(event) => setApproveText(event.target.checked)} /> I approve this narration estimate{narration.items.length > 0 ? " and replacement of existing narration/audio links" : ""}.</label>
      <div className="progression-actions"><Button disabled={locked || dirty || !approveText || narration.narration_estimate.estimated_cost > remaining} onClick={() => act("text")}>{narration.narration_estimate.model_usage.startsWith("Supplied narration") ? "Restore supplied narration locally" : narration.items.length ? "Regenerate narration" : "Generate narration"}</Button></div>
      <ProductionEstimateDisclosure estimate={narration.audio_estimate} title="Speech audio estimate" />
      <label className="production-approval"><input type="checkbox" checked={approveAudio} disabled={locked || dirty || !currentNarration} onChange={(event) => setApproveAudio(event.target.checked)} /> {narration.audio_estimate.model_usage.startsWith("Supplied audio") ? "I approve local restoration using the original supplied audio, not a synthetic voice." : "I approve this speech estimate using the standard synthetic voice."}</label>
      <div className="progression-actions"><Button disabled={locked || dirty || !currentNarration || !approveAudio || (!narration.audio_estimate.estimated_api_calls && !narration.audio_estimate.estimated_runtime_seconds) || narration.audio_estimate.estimated_cost > remaining} onClick={() => act("audio")}>{narration.audio_estimate.model_usage.startsWith("Supplied audio") ? "Restore missing original audio locally" : "Generate missing speech audio"}</Button></div>
      {busy && <Loading workflow={busy === "save" || busy === "motion" ? "scenes" : "narration"} label={busy === "text" ? "Preparing connected narration..." : busy === "audio" ? "Preparing narration audio..." : "Saving timeline..."} />}
      {!timeline.ready && <Notice>Rendering requires every scene image to be approved, current narration, and a generated audio file for each scene.</Notice>}
      <div className="timeline-list">{timeline.scenes.map((scene, index) => <article className="timeline-row" key={scene.scene_id}>
        {scene.image_url ? <img src={assetUrl(scene.image_url)} alt={scene.title} /> : <div>Scene image missing</div>}
        <div><h3>{index + 1}. {scene.title}</h3><details className="card-details"><summary>Narration, timing and scene controls</summary><p>{scene.narration ?? "Narration not generated or outdated."}</p>
          {scene.audio_url && <audio src={assetUrl(scene.audio_url)} controls preload="metadata" aria-label={`Narration for ${scene.title}`} />}
          <label>Duration (seconds) <input type="number" min={Math.max(1, Math.ceil((scene.audio_seconds ?? 0) + 0.25))} max={3600} value={scene.duration_seconds} disabled={locked} onChange={(event) => {
            const value = Number(event.target.value);
            setTimeline({ ...timeline, scenes: timeline.scenes.map((item) => item.scene_id === scene.scene_id ? { ...item, duration_seconds: value } : item) }); setDirty(true);
          }} /></label>
          <p>{scene.ready ? "Ready" : "Needs approved image and current speech audio"}</p>
          {scene.animation_issue && <Notice tone="error">{scene.animation_issue}</Notice>}
          {scene.animation_url && <p>Approved generated animation selected; short clips hold their final frame.</p>}
          <SceneAnimation projectId={id} sceneId={scene.scene_id} disabled={locked || dirty} onReview={refresh} />
          <details><summary>Motion and deferred animation plan</summary>
            <label>Camera <select aria-label={`Camera for ${scene.title}`} value={scene.motion_plan.camera} disabled={locked || dirty}
              onChange={(event) => motion(scene.scene_id,{ ...scene.motion_plan, camera:event.target.value as MotionPlan["camera"] })}>
              <option value="slow_zoom">Slow zoom</option><option value="pan">Pan</option><option value="parallax">Simulated parallax</option></select></label>
            <label>Transition <select aria-label={`Transition for ${scene.title}`} value={scene.motion_plan.transition} disabled={locked || dirty}
              onChange={(event) => motion(scene.scene_id,{ ...scene.motion_plan, transition:event.target.value as MotionPlan["transition"] })}>
              <option value="cross_fade">Cross fade</option><option value="fade_black">Fade to black</option><option value="fade_color">Fade through white</option><option value="motion_blur">Horizontal blur</option></select></label>
            <p>Focus: {scene.motion_plan.focus_x}, {scene.motion_plan.focus_y} / Pacing: {scene.motion_plan.pacing}</p>
            <p>{scene.motion_plan.motion_prompt}</p><p>{scene.motion_plan.animation_instructions}</p><p>{scene.motion_plan.character_movement_prompt}</p>
            <Notice>Camera effects apply to still images. Approved local animation replaces them; motion prompts are planning metadata, not controls supported by SVD. Save order/duration changes before editing motion.</Notice>
          </details>
          <div className="card-actions"><Button variant="secondary" disabled={locked || index === 0} onClick={() => move(index, -1)} aria-label={`Move ${scene.title} up`}>Move up</Button><Button variant="secondary" disabled={locked || index === timeline.scenes.length - 1} onClick={() => move(index, 1)} aria-label={`Move ${scene.title} down`}>Move down</Button></div>
          </details>
        </div>
      </article>)}</div>
      <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/scenes`}>Back to Scenes</Button><div><Button variant="secondary" disabled={locked || !dirty} onClick={() => act("save")}>Save order and durations</Button>
        {!dirty && timeline.ready && <Button href={`/projects/${id}/render`}>Review render estimate</Button>}</div>
      </div>
      {dirty && <Notice>Save timeline changes before generating or rendering. Reordering invalidates the connected narration and audio; regenerate them after saving. Durations cannot truncate narration audio.</Notice>}
    </>}
  </ProjectLayout>;
}
