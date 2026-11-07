"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, assetUrl, type ProductionEstimate, type Project, type RenderStatus, type Timeline, type QualityReport, type FilmPlan, type RenderMode } from "@/services/api";
import { Button, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";
import { ProductionEstimateDisclosure } from "@/components/production-estimate";
import { StageGeneration } from "@/components/stage-generation";
import { SceneAnimation } from "@/components/scene-animation";

export default function RenderPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [project, setProject] = useState<Project | null>(null);
  const [estimate, setEstimate] = useState<ProductionEstimate | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [job, setJob] = useState<RenderStatus | null>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [film, setFilm] = useState<FilmPlan | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<RenderMode | null>(null);
  const [stageBusy, setStageBusy] = useState(false);
  const refresh = useCallback(async () => {
    const projectData = await api.getProject(id);
    const selected = mode ?? projectData.render_mode;
    const [estimateData, jobData, timelineData, qualityData, filmData] = await Promise.all([
      api.getRenderEstimate(id, selected), api.getRenderStatus(id), api.getTimeline(id), api.getQuality(id), api.getFilmPlan(id),
    ]);
    setMode(selected);
    setProject(projectData); setEstimate(estimateData); setJob(jobData); setTimeline(timelineData); setApproved(false);
    setQuality(qualityData);
    setFilm(filmData);
  }, [id, mode]);
  useEffect(() => { refresh().catch((reason: Error) => setError(reason.message)); }, [refresh]);
  const active = job?.status === "queued" || job?.status === "running";
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api.getRenderStatus(id);
        if (cancelled) return;
        if (!next) throw new Error("Render status is unavailable.");
        setJob(next); setError("");
        if (!["queued", "running"].includes(next.status)) return;
      } catch (reason) {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "Could not read render progress.");
      }
      timer = setTimeout(poll, 1200);
    }
    timer = setTimeout(poll, 500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [active, id]);

  async function start(resume = false) {
    if (!estimate || !approved || !mode) return;
    setBusy(true); setError("");
    try { setJob(await api.startRender(id, estimate.estimate_id, mode, resume ? job?.job_id : undefined)); setApproved(false); }
    catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start render.");
      try { await refresh(); } catch { setError((message) => `${message} Could not refresh the estimate; reload before retrying.`); }
    } finally { setBusy(false); }
  }
  return <ProjectLayout projectId={id} title={project?.title ?? "Render"}>
    <PageHeading label="06 / RENDER" title="Approve the final export." description="Review the film plan, approved motion clips or still-image camera effects, transitions and original narration." />
    {error && <Notice tone="error">{error}</Notice>}
    {!project || !estimate || !timeline || !quality || !film || !mode ? <><Loading /><Button variant="secondary" onClick={() => { setError(""); refresh().catch((reason: Error) => setError(reason.message)); }}>Retry loading</Button></> : <>
      <label className="render-source">Final video source <select aria-label="Final video source" value={mode} disabled={active || stageBusy || busy}
        onChange={(event) => { setApproved(false); setMode(event.target.value === "still_images" ? "still_images" : "local_animation"); }}>
        <option value="local_animation">Actual local model motion — every scene must be approved</option>
        <option value="still_images">Still-image camera effects — do not call the local model</option>
      </select></label>
      {mode === "local_animation" ? <>
        <Notice>Non-commercial local SVD: 2 seconds of generated motion per scene; longer scenes hold the final frame.</Notice>
        <details className="collapsible-section"><summary>Local generation workflow and limitations</summary><p>The approved automatic GPU stage generates all missing scene clips in sequence. Preview and approve them below before export.
          Each clip has only 2 seconds of model-generated motion; longer scenes hold the final frame. Powered by Stability AI, non-commercial only.</p></details>
        {!active && <StageGeneration projectId={id} stage="animations" onComplete={refresh} onActive={setStageBusy} />}
        {timeline.scenes.map((scene) => <section key={scene.scene_id}>
          <h3>{scene.order}. {scene.title}</h3>
          {scene.image_url && <img className="review-scene-image" src={assetUrl(scene.image_url)} alt={scene.title} />}
          <p>{scene.animation_url ? "Current model-generated motion selected." : "A current approved model clip is required."}</p>
          <SceneAnimation projectId={id} sceneId={scene.scene_id} disabled={active || stageBusy || busy}
            onReview={refresh} pollActive={stageBusy} batch />
        </section>)}
      </> : <Notice>This explicitly selected mode uses still images and FFmpeg camera motion. The local video model will not be called.</Notice>}
      <details className="collapsible-section"><summary>Readiness score: {quality.score}% / quality details</summary><p>{quality.explanation} Review the global status for incomplete content and approval requirements before starting.</p></details>
      <ProductionEstimateDisclosure estimate={estimate} title="Render estimate" />
      <details><summary>Film / camera / motion / transition / animation plan</summary>
        <p>Narrative source: {film.narrative.source}</p>
        {film.narrative.beats.map((beat) => <section key={beat.number}>
          <h3>Beat {beat.number}: {beat.title}</h3><p>{beat.purpose}</p>
          <p>{beat.timeline_progression} / Scenes: {beat.scene_ids.length}</p>
          <p>{beat.transition}</p>
        </section>)}
        {film.scenes.map((scene) => <section key={scene.scene_id}>
          <h3>{scene.bridge.current.title}</h3>
          <p>{scene.bridge.previous?.title ?? "Opening"} / {scene.bridge.current.title} / {scene.bridge.next?.title ?? "Ending"}</p>
          <p>Camera: {scene.camera_motion_transition_animation_plan.camera}; pacing: {scene.camera_motion_transition_animation_plan.pacing}; transition: {scene.camera_motion_transition_animation_plan.transition}</p>
          <p>{scene.animation_capability}</p>
        </section>)}
      </details>
      {!timeline.ready && <Notice tone="error">The timeline is not ready. Approve images, generate current narration/audio and resolve selected clip problems first.</Notice>}
      {mode === "local_animation" && timeline.scenes.some((scene) => !scene.animation_url) &&
        <Notice tone="error">Final export is blocked until EVERY scene has a current approved local model clip. No automatic still-image fallback is allowed.</Notice>}
      <Notice>Cumulative reserved AI estimate: ${project.estimated_spend.toFixed(4)}. Actual provider invoices are unavailable. Storage estimate includes resumable segments and temporary output.</Notice>
      {job && <section className="generation-panel" aria-live="polite">
        <h2>{job.current_stage}</h2><p>{job.status} / {job.completed_scenes.length} scenes checkpointed</p>
        <div className="render-progress"><progress value={job.progress} max={100} aria-label="Render progress" /><b>{job.progress.toFixed(1)}%</b></div>
        <p>Elapsed: {Math.ceil(job.elapsed_seconds)} seconds.
          {active && (job.estimated_remaining_seconds == null ? " Estimating time remaining..." :
            ` Estimated time remaining: ${Math.ceil(job.estimated_remaining_seconds)} seconds (approximate; updates from actual encoding progress).`)}
        </p>
        {job.error && <Notice tone="error">{job.error}</Notice>}
        {job.status === "completed" && <div className="progression-actions"><Button href={`/projects/${id}/video`}>Watch and download MP4</Button></div>}
      </section>}
      {!active && <>
        <label className="production-approval"><input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} /> I approve the displayed cost, runtime, storage, audio duration, and video length estimates.</label>
        <div className="progression-actions">
          {job?.status === "failed" && <Button variant="secondary" disabled={!approved || busy || stageBusy || !timeline.ready || (mode === "local_animation" && timeline.scenes.some((scene) => !scene.animation_url))} onClick={() => start(true)}>Resume failed render</Button>}
          <Button disabled={!approved || busy || stageBusy || !timeline.ready || (mode === "local_animation" && timeline.scenes.some((scene) => !scene.animation_url))} onClick={() => start()}>Start new render</Button>
        </div>
      </>}
      {busy && <Loading label="Queueing render..." />}
      {active && <Loading label={job?.current_stage ?? "Rendering video..."} workflow="render" />}
      <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/timeline`}>Review timeline</Button></div>
    </>}
  </ProjectLayout>;
}
