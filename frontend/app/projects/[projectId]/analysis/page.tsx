"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  type GenerationEstimates,
  type Project,
  type Story,
} from "@/services/api";
import {
  Button,
  GenerationEstimateDisclosure,
  Loading,
  Notice,
  PageHeading,
  ProjectLayout,
} from "@/components/ui";

export default function AnalysisPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [story, setStory] = useState<Story | null>(null);
  const [generationEstimates, setGenerationEstimates] = useState<GenerationEstimates | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.getProject(id), api.getGenerationEstimates(id)])
      .then(async ([projectData, estimateData]) => {
        setProject(projectData);
        setGenerationEstimates(estimateData);
        if (projectData.status !== "created") setStory(await api.getStory(id));
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function generatePlanning() {
    setBusy(true);
    setError("");
    try {
      await api.analyze(id);
      const [projectData, storyData, estimateData] = await Promise.all([
        api.getProject(id),
        api.getStory(id),
        api.getGenerationEstimates(id),
      ]);
      setProject(projectData);
      setStory(storyData);
      setGenerationEstimates(estimateData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not generate the story bible.");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !project || !generationEstimates) {
    return (
      <ProjectLayout projectId={id} title={project?.title ?? "Project"}>
        {error ? <Notice tone="error">{error}</Notice> : <Loading label="Preparing your planning estimate…" />}
      </ProjectLayout>
    );
  }

  const isPlanned = story !== null;
  const remainingBudget = Math.max(0, project.max_budget - project.estimated_spend);
  const exceedsBudget = generationEstimates.planning.estimated_cost > remainingBudget;

  return (
    <ProjectLayout projectId={id} title={project.title}>
      <PageHeading
        label="01 / STORY PLANNING"
        title="Know the estimate before the first prompt."
        description="Review the model, estimated cost, duration, and call count. Story, character, and scene generation starts only when you choose to run it."
      />
      {error && <Notice tone="error">{error}</Notice>}
      <div className="analysis-summary">
        <div className="summary-poster"><span>STORY IDEA</span><strong>{project.title}</strong><i>✳</i></div>
        <div className="summary-copy">
          <span className="eyebrow">YOUR IDEA</span>
          <p>{project.prompt}</p>
          <div className="summary-meta">
            <span><b>{project.target_minutes} min</b> target story</span><i />
            <span><b>${remainingBudget.toFixed(2)}</b> estimated budget remaining</span>
          </div>
        </div>
      </div>

      {!isPlanned ? (
        <section className="planning-start">
          <div className="section-title"><div><div className="eyebrow">THREE STRUCTURED OUTPUTS</div><h2>Story, character, and scene bibles</h2></div></div>
          <GenerationEstimateDisclosure
            estimate={generationEstimates.planning}
            title="Covers story generation, one character-bible call, and one scene-plan call."
          />
          <div className="planning-cost-breakdown">
            {[generationEstimates.story, generationEstimates.characters, generationEstimates.scenes].map((estimate) => (
              <div key={estimate.operation}>
                <span>{estimate.operation.replaceAll("_", " ")}</span>
                <b>${estimate.estimated_cost.toFixed(4)} · ~{estimate.estimated_minutes} min · {estimate.estimated_api_calls} call</b>
                <small>{estimate.estimated_model_usage}</small>
              </div>
            ))}
          </div>
          {exceedsBudget && <Notice tone="error">This planning estimate exceeds the remaining project budget. Update the budget in AI settings or increase it on a new project.</Notice>}
          <div className="workflow-footer">
            <span>Estimated spend is reserved before provider calls.</span>
            <Button onClick={generatePlanning} disabled={busy || exceedsBudget}>
              {busy ? "Generating story, characters, and scenes…" : "Generate Story Bible"}
            </Button>
          </div>
          {busy && <Loading label="Waiting for structured AI planning responses…" />}
        </section>
      ) : (
        <>
          <section className="editor-panel">
            <div className="eyebrow">STORY BIBLE</div>
            <h2>{story.title}</h2>
            <p>{story.summary}</p>
            <div className="summary-meta"><span><b>{story.genre || "Unspecified"}</b> genre</span><i /><span><b>{story.target_audience || "Unspecified"}</b> target audience</span></div>
            <div className="section-title"><div><div className="eyebrow">THREE ACT STRUCTURE</div></div></div>
            <div className="act-grid">
              {Object.entries(story.three_act_structure).map(([act, detail]) => (
                <article key={act}><span>{act.replaceAll("_", " ").toUpperCase()}</span><p>{detail}</p></article>
              ))}
            </div>
          </section>
          <div className="planning-summary">
            <div><span>CHARACTERS</span><b>{story.characters.length}</b></div>
            <div><span>PLANNED SCENES</span><b>{story.scenes.length}</b></div>
            <div><span>ALL PORTRAITS + SCENE IMAGES</span><b>${generationEstimates.all_images.estimated_cost.toFixed(4)}</b></div>
            <div><span>EST. IMAGE API CALLS</span><b>{generationEstimates.all_images.estimated_api_calls}</b></div>
          </div>
          <Notice>Image estimates are separate from planning. Each portrait or scene image shows its own estimate before you start generation. Estimates do not guarantee provider billing.</Notice>
          <div className="workflow-footer">
            <Button variant="secondary" onClick={() => router.push(`/projects/${id}/story`)}>Review story bible</Button>
            <div>
              <Button variant="secondary" onClick={() => router.push(`/projects/${id}/characters`)}>Character bible</Button>
              <Button onClick={() => router.push(`/projects/${id}/scenes`)}>Scene plan <span>→</span></Button>
            </div>
          </div>
        </>
      )}
    </ProjectLayout>
  );
}
