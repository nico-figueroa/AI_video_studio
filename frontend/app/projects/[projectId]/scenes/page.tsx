"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  api,
  assetUrl,
  type GenerationEstimates,
  type Project,
  type Scene,
} from "@/services/api";
import {
  Button,
  GenerationEstimateDisclosure,
  Loading,
  Notice,
  PageHeading,
  ProjectLayout,
} from "@/components/ui";
import { StageGeneration } from "@/components/stage-generation";

export default function ScenesPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [estimates, setEstimates] = useState<GenerationEstimates | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [stageBusy, setStageBusy] = useState(true);
  const refreshStage = useCallback(async () => {
    const [items, data] = await Promise.all([api.getScenes(id), api.getProject(id)]);
    setScenes(items); setProject(data);
  }, [id]);
  const refresh = useCallback(() => api.getScenes(id).then(setScenes), [id]);

  useEffect(() => {
    Promise.all([refresh(), api.getProject(id), api.getGenerationEstimates(id)])
      .then(([, projectData, estimateData]) => {
        setProject(projectData);
        setEstimates(estimateData);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [id, refresh]);

  async function makeImage(scene: Scene) {
    if (!window.confirm("Regenerate this scene image using the displayed per-image estimate? It will need approval again.")) return;
    setBusyId(scene.id);
    setError("");
    let generationError = "";
    try {
      await api.generateScene(scene.id, Boolean(scene.image_path));
    } catch (reason) {
      generationError = reason instanceof Error ? reason.message : "Could not generate scene image.";
    } finally {
      const [scenesResult, projectResult] = await Promise.allSettled([
        api.getScenes(id),
        api.getProject(id),
      ]);
      if (scenesResult.status === "fulfilled") setScenes(scenesResult.value);
      if (projectResult.status === "fulfilled") setProject(projectResult.value);

      const refreshError = [scenesResult, projectResult]
        .find((result) => result.status === "rejected");
      const refreshMessage = refreshError?.status === "rejected"
        ? refreshError.reason instanceof Error ? refreshError.reason.message : "Could not refresh project data."
        : "";
      const errors = [generationError, refreshMessage].filter(Boolean);
      if (errors.length) setError(errors.join(" "));
      setBusyId(null);
    }
  }

  async function approve(scene: Scene) {
    setBusyId(scene.id);
    setError("");
    try {
      const updated = await api.approveScene(scene.id, !scene.approved, scene.image_path);
      setScenes((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update scene."); }
    finally { setBusyId(null); }
  }

  const generated = scenes.filter((scene) => scene.image_path).length;
  const remainingBudget = project ? Math.max(0, project.max_budget - project.estimated_spend) : 0;
  const overBudget = estimates ? estimates.scene_image.estimated_cost > remainingBudget : false;
  const overWait = project && estimates
    ? estimates.scene_image.estimated_minutes > project.max_wait_minutes
    : false;
  return <ProjectLayout projectId={id} title="Scene plan">
    <PageHeading label="04 / SCENE PLAN" title="Review your generated storyboard." description="All missing scene images generate automatically with approved character references and the stage budget. Approve each result or explicitly regenerate it." />
    <StageGeneration projectId={id} stage="scenes" onComplete={refreshStage} onActive={setStageBusy} />
    {error && <Notice tone="error">{error}</Notice>}
    {loading ? <Loading label="Loading scene plan and estimates…" /> : !estimates || !project ? <>
      <Button variant="secondary" onClick={() => window.location.reload()}>Retry loading scenes</Button>
    </> : <>
      <GenerationEstimateDisclosure
        estimate={estimates.scene_image}
        title="Estimate per scene image. Starting a request reserves this amount against your project budget."
      />
      {overBudget && <Notice tone="error">A scene image estimate exceeds your remaining ${remainingBudget.toFixed(2)} project budget.</Notice>}
      {overWait && <Notice tone="error">A scene image estimate exceeds your project wait limit.</Notice>}
      <div className="scene-progress">
        <div><span>STORYBOARD PROGRESS</span><b>{generated} <small>/ {scenes.length} images</small></b></div>
        <div className="progress-track"><span style={{ width: `${scenes.length ? generated / scenes.length * 100 : 0}%` }} /></div>
      </div>
      {scenes.length === 0 && <Notice>Generate the Story Bible from the planning page before reviewing scenes.</Notice>}
      <div className="scene-grid">{scenes.map((scene, index) => <article className="scene-card" key={scene.id}>
        <div className={`scene-art scene-art-${index % 5}`} style={scene.image_path ? { backgroundImage: `url("${assetUrl(scene.image_path)}")` } : undefined}>
          {!scene.image_path && <><div className="scene-placeholder-orb" /><span>FRAME {String(scene.scene_number).padStart(2, "0")}</span><small>AWAITING IMAGE</small></>}
          {scene.approved && <b className="approved-ribbon">✓ APPROVED</b>}
        </div>
        <div className="scene-card-body">
          <h3>{scene.scene_number}. {scene.title}</h3>
          <details className="card-details"><summary>Scene details and review</summary><p>Beat {scene.beat_number} / Estimated duration: {scene.estimated_duration} seconds</p>
          <p>{scene.description}</p>
          <dl className="scene-facts">
            <dt>Visual description</dt><dd>{scene.visual_description}</dd>
            <dt>Image prompt</dt><dd>{scene.image_prompt}</dd>
          </dl>
          <div className="card-actions">
            {scene.image_path && <Button variant="secondary" disabled={stageBusy || overBudget || overWait || busyId !== null} onClick={() => makeImage(scene)}>
              {busyId === scene.id ? "Generating image…" : "Regenerate image"}
            </Button>}
            {scene.image_path && <Button variant={scene.approved ? "ghost" : "primary"} disabled={stageBusy || busyId !== null} onClick={() => approve(scene)}>
              {scene.approved ? "✓ Approved" : "Approve"}
            </Button>}
          </div>
          </details>
          {busyId === scene.id && <Loading label="Waiting for scene image…" />}
        </div>
      </article>)}</div>
      <Notice>{generated} of {scenes.length} scene images generated. Image prompts and estimated duration remain editable in the story bible workflow.</Notice>
    </>}
    <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/characters`}>← Characters</Button><Button variant="secondary" href={`/projects/${id}/story`}>Edit story bible</Button>
      {scenes.length > 0 && scenes.every((item) => item.approved) && !stageBusy
        ? <Button href={`/projects/${id}/timeline`}>Continue to narration and timeline</Button>
        : <Notice>Approve all scene images before continuing to Timeline.</Notice>}</div>
  </ProjectLayout>;
}
