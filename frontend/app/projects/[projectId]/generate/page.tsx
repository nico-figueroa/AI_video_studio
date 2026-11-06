"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type Estimate, type Job, type Project } from "@/services/api";
import { Button, GenerationDisclosure, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";

export default function GeneratePage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.getProject(id), api.getEstimates(id)])
      .then(([projectData, estimates]) => {
        setProject(projectData);
        if (projectData.selected_plan) setEstimate(estimates[projectData.selected_plan]);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [id]);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setTimeout(() => {
      api.getJob(job.job_id).then((next) => {
        setJob(next);
        if (next.status === "completed") router.push(`/projects/${id}/video`);
        if (next.status === "failed") setError(next.error ?? "Video generation failed.");
      }).catch((reason: Error) => setError(reason.message));
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [job, id, router]);

  async function start() {
    if (!project?.selected_plan) {
      setError("Choose and approve a plan before generating.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const started = await api.startVideo(id, project.selected_plan);
      const initial: Job = { ...started, project_id: id, progress: 0, current_stage: "Queued", error: null, video_url: null };
      setJob(initial);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start video export."); }
    finally { setBusy(false); }
  }

  const steps = ["Story reviewed", "Scene images", "Slideshow export", "MP4 ready"];
  const activeStage = job?.current_stage ?? "Ready when you are";
  return <ProjectLayout projectId={id} title={project?.title ?? "Video generation"}>
    <PageHeading label="05 / GENERATION" title="Your story, coming together." description="A clear view of each generation stage, with no hidden usage. This prototype runs everything locally." />
    {error && <Notice tone="error">{error}</Notice>}
    {!project ? <Loading label="Loading production details…" /> : <>
      <GenerationDisclosure plan={project.selected_plan} estimate={estimate} />
      <div className="generation-panel">
        <div className="generation-status"><span className={`generation-icon ${job?.status === "completed" ? "done" : ""}`}>{job?.status === "completed" ? "✓" : "✳"}</span><div><div className="eyebrow">{job ? job.status.toUpperCase() : "READY TO EXPORT"}</div><h2>{job?.status === "completed" ? "Video ready" : job?.status === "failed" ? "Export needs attention" : job ? "Making your video." : "Everything is in place."}</h2><p>{job?.current_stage ?? "Your selected plan and storyboard will guide the local MP4 export."}</p></div></div>
        {job && <div className="job-progress"><div className="progress-track"><span style={{ width: `${job.progress}%` }} /></div><b>{job.progress}%</b></div>}
        <div className="pipeline">{steps.map((step, index) => <div className={`pipeline-step ${job && job.progress >= [0, 10, 55, 100][index] ? "pipeline-done" : ""}`} key={step}><span>{job && job.progress >= [0, 10, 55, 100][index] ? "✓" : String(index + 1).padStart(2, "0")}</span><b>{step}</b></div>)}</div>
        {project.selected_plan && <div className="generation-receipt"><div><span>APPROVED PLAN</span><b>{project.selected_plan}</b></div><div><span>VIDEO LENGTH</span><b>{project.target_minutes} min target</b></div><div><span>ESTIMATED COST</span><b>${estimate?.estimated_cost.toFixed(2) ?? "—"}</b></div><div><span>ACTUAL PROVIDER COST</span><b>$0.00</b></div></div>}
        {!job && <Button onClick={start} disabled={busy || !project.selected_plan}>{busy ? "Preparing export…" : "Start video generation"} <span>→</span></Button>}
        {job?.status === "completed" && <Button href={`/projects/${id}/video`}>Watch your video <span>→</span></Button>}
      </div>
      <Notice>All costs and GPU minutes on the plan screen are illustrative estimates. This prototype uses local placeholder art and local FFmpeg; actual provider spend is $0.</Notice>
      <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/scenes`}>← Review scenes</Button><span>{activeStage}</span></div>
    </>}
  </ProjectLayout>;
}
