"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, assetUrl, type Estimate, type PlanName, type Scene } from "@/services/api";
import { Button, GenerationDisclosure, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";

export default function ScenesPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<PlanName | null>(null);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const refresh = useCallback(() => api.getScenes(id).then(setScenes), [id]);

  useEffect(() => {
    Promise.all([refresh(), api.getProject(id), api.getEstimates(id)])
      .then(([, project, estimates]) => {
        const plan = project.selected_plan;
        setSelectedPlan(plan);
        setEstimate(plan ? estimates[plan] : null);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [id, refresh]);

  async function makeImage(scene: Scene) {
    setBusyId(scene.id);
    setError("");
    try {
      await api.generateScene(scene.id, Boolean(scene.image_path));
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not generate scene image."); }
    finally { setBusyId(null); }
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
  return <ProjectLayout projectId={id} title="Scene review">
    <PageHeading label="04 / SCENE REVIEW" title="One frame at a time." description="Generate and review the storyboard images. You can regenerate any frame before creating the final video." />
    {error && <Notice tone="error">{error}</Notice>}
    {loading ? <Loading label="Loading storyboard…" /> : <>
      <GenerationDisclosure plan={selectedPlan} estimate={estimate} />
      <div className="scene-progress"><div><span>STORYBOARD PROGRESS</span><b>{generated} <small>/ {scenes.length} images</small></b></div><div className="progress-track"><span style={{ width: `${scenes.length ? generated / scenes.length * 100 : 0}%` }} /></div></div>
      <div className="scene-grid">{scenes.map((scene, index) => <article className="scene-card" key={scene.id}>
        <div className={`scene-art scene-art-${index % 5}`} style={scene.image_path ? { backgroundImage: `url("${assetUrl(scene.image_path)}")` } : undefined}>
          {!scene.image_path && <><div className="scene-placeholder-orb" /><span>FRAME {String(scene.scene_number).padStart(2, "0")}</span><small>AWAITING ARTWORK</small></>}
          {scene.approved && <b className="approved-ribbon">✓ APPROVED</b>}
        </div>
        <div className="scene-card-body"><div className="scene-topline"><span>SCENE {String(scene.scene_number).padStart(2, "0")}</span><i className={scene.image_path ? "dot-ready" : "dot-pending"} /></div><h3>{scene.title}</h3><p>{scene.description}</p>
          <div className="card-actions"><Button variant="secondary" disabled={!selectedPlan || busyId === scene.id} onClick={() => makeImage(scene)}>{busyId === scene.id ? "Creating…" : scene.image_path ? "Regenerate image" : "Generate image"}</Button>{scene.image_path && <Button variant={scene.approved ? "ghost" : "primary"} disabled={busyId === scene.id} onClick={() => approve(scene)}>{scene.approved ? "✓ Approved" : "Approve"}</Button>}</div>
        </div>
      </article>)}</div>
      <Notice>Generating these mock images is local and free. You may create the video without approving every frame; only generated images are used.</Notice>
      <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/characters`}>← Characters</Button><Button href={`/projects/${id}/generate`}>Continue to video <span>→</span></Button></div>
    </>}
  </ProjectLayout>;
}
