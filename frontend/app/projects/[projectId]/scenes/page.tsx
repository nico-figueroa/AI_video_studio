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

export default function ScenesPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [estimates, setEstimates] = useState<GenerationEstimates | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
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
      const updated = await api.approveScene(scene.id, !scene.approved);
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
    <PageHeading label="04 / SCENE PLAN" title="Plan each frame before creating it." description="Review the visual plan and image prompt, then generate or regenerate each scene image with its own visible estimate." />
    {error && <Notice tone="error">{error}</Notice>}
    {loading || !estimates || !project ? <Loading label="Loading scene plan and estimates…" /> : <>
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
          <div className="scene-topline"><span>SCENE {String(scene.scene_number).padStart(2, "0")} · ~{scene.estimated_duration}s</span><i className={scene.image_path ? "dot-ready" : "dot-pending"} /></div>
          <h3>{scene.title}</h3>
          <p>{scene.description}</p>
          <dl className="scene-facts">
            <dt>Visual description</dt><dd>{scene.visual_description}</dd>
            <dt>Image prompt</dt><dd>{scene.image_prompt}</dd>
          </dl>
          <div className="card-actions">
            <Button variant="secondary" disabled={overBudget || overWait || busyId !== null} onClick={() => makeImage(scene)}>
              {busyId === scene.id ? "Generating image…" : scene.image_path ? "Regenerate image" : "Generate image"}
            </Button>
            {scene.image_path && <Button variant={scene.approved ? "ghost" : "primary"} disabled={busyId !== null} onClick={() => approve(scene)}>
              {scene.approved ? "✓ Approved" : "Approve"}
            </Button>}
          </div>
          {busyId === scene.id && <Loading label="Waiting for scene image…" />}
        </div>
      </article>)}</div>
      <Notice>{generated} of {scenes.length} scene images generated. Image prompts and estimated duration remain editable in the story bible workflow.</Notice>
    </>}
    <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/characters`}>← Characters</Button><Button variant="secondary" href={`/projects/${id}/story`}>Edit story bible</Button></div>
  </ProjectLayout>;
}
