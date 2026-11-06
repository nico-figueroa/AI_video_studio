"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type Estimate, type Estimates, type PlanName, type Project } from "@/services/api";
import { Button, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";

const labels: Record<PlanName, string> = { economy: "Economy", balanced: "Balanced", premium: "Premium" };

export default function AnalysisPage() {
  const params = useParams<{ projectId: string }>();
  const id = Number(params.projectId);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [estimates, setEstimates] = useState<Estimates | null>(null);
  const [selected, setSelected] = useState<PlanName | null>(null);
  const [busy, setBusy] = useState<PlanName | "analysis" | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.getProject(id), api.getEstimates(id)])
      .then(([projectData, estimateData]) => {
        setProject(projectData);
        setEstimates(estimateData);
        setSelected(projectData.selected_plan);
      })
      .catch(async (reason: Error) => {
        if (reason.message.includes("Analyze the project")) {
          try {
            await api.analyze(id);
            const [projectData, estimateData] = await Promise.all([api.getProject(id), api.getEstimates(id)]);
            setProject(projectData);
            setEstimates(estimateData);
          } catch (failure) {
            setError(failure instanceof Error ? failure.message : "Could not analyze the project.");
          }
        } else setError(reason.message);
      });
  }, [id]);

  async function choose(plan: PlanName) {
    setBusy(plan);
    setError("");
    try {
      await api.selectPlan(id, plan);
      setSelected(plan);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not select this plan.");
    } finally {
      setBusy(null);
    }
  }

  async function continueToStory() {
    if (!selected) return;
    setBusy(selected);
    try {
      await api.selectPlan(id, selected);
      router.push(`/projects/${id}/story`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not continue.");
      setBusy(null);
    }
  }

  if (!project || !estimates) return <ProjectLayout projectId={id} title={project?.title ?? "Project"}>{error ? <Notice tone="error">{error}</Notice> : <Loading label="Preparing your production plan…" />}</ProjectLayout>;
  const plans: PlanName[] = ["economy", "balanced", "premium"];
  return (
    <ProjectLayout projectId={id} title={project.title}>
      <PageHeading label="01 / PRODUCTION PLAN" title="A clear plan, before the first frame." description="Review the story and choose a quality tier. Nothing generates until you approve a plan." />
      {error && <Notice tone="error">{error}</Notice>}
      <div className="analysis-summary"><div className="summary-poster"><span>STORY IDEA</span><strong>{project.title}</strong><i>✳</i></div><div className="summary-copy"><span className="eyebrow">YOUR IDEA</span><p>{project.prompt}</p><div className="summary-meta"><span><b>{project.target_minutes} min</b> target video</span><i /><span><b>{Math.min(8, Math.max(4, project.target_minutes * 2))}</b> storyboard scenes</span></div></div></div>
      <div className="plan-intro"><div><div className="eyebrow">YOUR OPTIONS</div><h2>Pick your production style.</h2></div><span>Estimates shown before approval</span></div>
      <div className="plan-grid">
        {plans.map((name) => {
          const item: Estimate = estimates[name];
          const overBudget = item.estimated_cost > project.max_budget;
          const overTime = item.estimated_minutes > project.max_wait_minutes;
          const unavailable = overBudget || overTime;
          return (
            <article key={name} className={`plan-card ${name === "balanced" ? "plan-featured" : ""} ${selected === name ? "plan-selected" : ""}`}>
              {name === "balanced" && <div className="plan-badge">MOST POPULAR</div>}
              <div className="plan-name">{labels[name]}</div><div className="plan-price">${item.estimated_cost.toFixed(2)}<small> illustrative</small></div>
              <p>{name === "economy" ? "A lighter touch, with less render time." : name === "balanced" ? "A thoughtful balance of detail and speed." : "A richer look with extra processing time."}</p>
              <div className="plan-stats"><div><span>TIME</span><b>~{item.estimated_minutes} min</b></div><div><span>RESOLUTION</span><b>{item.resolution}</b></div><div><span>QUALITY SCORE</span><b>{item.quality_score}<small> / 100</small></b></div></div>
              <div className="plan-resource"><span>Storage</span><b>{item.storage_mb} MB</b><i /> <span>GPU estimate</span><b>{item.gpu_minutes} min</b></div>
              {unavailable && <div className="limit-warning">{overBudget ? "Over budget cap" : ""}{overBudget && overTime ? " · " : ""}{overTime ? "Over wait cap" : ""}</div>}
              <Button variant={selected === name ? "primary" : "secondary"} disabled={unavailable || busy !== null} onClick={() => choose(name)}>{busy === name ? "Saving…" : selected === name ? "✓ Selected" : "Choose plan"}</Button>
            </article>
          );
        })}
      </div>
      <Notice>Illustrative provider-equivalent estimates only. This local prototype uses placeholder artwork and charges $0. Estimates are capped by your {`$${project.max_budget.toFixed(2)}`} budget and {project.max_wait_minutes}-minute wait limit.</Notice>
      <div className="workflow-footer"><span>Nothing is generated until you approve.</span><Button onClick={continueToStory} disabled={!selected || busy !== null}>Review your story <span>→</span></Button></div>
    </ProjectLayout>
  );
}
