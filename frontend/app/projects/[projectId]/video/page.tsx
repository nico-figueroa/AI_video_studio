"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API_URL, api, assetUrl, type Metrics, type Project } from "@/services/api";
import { Button, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";

export default function VideoPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [project, setProject] = useState<Project | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.getProject(id), api.getMetrics(id)])
      .then(([projectData, metricsData]) => { setProject(projectData); setMetrics(metricsData); })
      .catch((reason: Error) => setError(reason.message));
  }, [id]);

  if (error) return <ProjectLayout projectId={id} title="Your video"><Notice tone="error">{error}</Notice><Button href={`/projects/${id}/generate`}>Back to generation</Button></ProjectLayout>;
  if (!project || !metrics) return <ProjectLayout projectId={id} title="Your video"><Loading label="Preparing your video…" /></ProjectLayout>;
  if (!project.video_url) return <ProjectLayout projectId={id} title={project.title}><PageHeading label="06 / YOUR VIDEO" title="Your final cut is one step away." description="Start the local slideshow export to create your MP4." /><Button href={`/projects/${id}/generate`}>Go to generation <span>→</span></Button></ProjectLayout>;

  return <ProjectLayout projectId={id} title={project.title}>
    <PageHeading label="06 / YOUR VIDEO" title="A story brought to life." description="Your slideshow MP4 is ready. Watch it here or save a copy to your device." />
    <div className="video-player-wrap"><video className="video-player" src={assetUrl(project.video_url)} controls playsInline /><div className="video-label"><span>✳</span> {project.title}</div></div>
    <div className="metric-grid"><div><span>ESTIMATED COST</span><b>${metrics.estimated_cost.toFixed(2)}</b><small>Illustrative only</small></div><div><span>ACTUAL PROVIDER COST</span><b>$0.00</b><small>Local generation</small></div><div><span>VIDEO LENGTH</span><b>{metrics.video_length_seconds ? `${Math.floor(metrics.video_length_seconds / 60)}:${String(metrics.video_length_seconds % 60).padStart(2, "0")}` : "—"}</b><small>Slideshow export</small></div><div><span>SCENE IMAGES</span><b>{metrics.total_images}</b><small>Local placeholders</small></div></div>
    <div className="video-actions"><a className="button button-primary" href={`${API_URL}/api/v1/projects/${id}/video/download`}>Download MP4 <span>↓</span></a><Button variant="secondary" href={`/projects/${id}/generate`}>Create new version</Button><Button variant="ghost" href="/dashboard">Return to dashboard</Button></div>
    <Notice>Video, image, and storage files are saved in this local prototype’s backend/storage folder.</Notice>
  </ProjectLayout>;
}
