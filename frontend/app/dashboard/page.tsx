"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type ProjectSummary } from "@/services/api";
import { Button, Loading, Notice } from "@/components/ui";

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<number | null>(null);
  async function deleteProject(project: ProjectSummary) {
    if (!window.confirm(`Delete "${project.title}" and all its videos, inputs and generated assets? This cannot be undone.`)) return;
    setDeleting(project.id); setError("");
    try {
      await api.deleteProject(project.id);
      setProjects((items) => items.filter((item) => item.id !== project.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete project.");
    } finally { setDeleting(null); }
  }

  useEffect(() => {
    api.listProjects().then(setProjects).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, []);

  return (
    <main className="dashboard">
      <header className="workspace-head">
        <Link className="brand" href="/"><span className="brand-mark">✳</span> Framewise</Link>
        <Link className="nav-link" href="/settings/ai">AI settings <span>↗</span></Link>
        <span className="dashboard-tag"><span className="status-dot" /> CREATOR STUDIO</span>
        <Link className="avatar" href="/">N</Link>
      </header>
      <div className="dashboard-main">
        <div className="dashboard-welcome">
          <div><div className="eyebrow">YOUR CREATIVE WORKSPACE</div><h1>Good ideas start <em>somewhere.</em></h1><p>Pick up a project or give a new story its first frame.</p></div>
          <Button href="/projects/new">＋ New project</Button>
        </div>
        <div className="dashboard-callout">
          <span className="callout-icon">✳</span><div><strong>Clarity comes standard.</strong><p>See your estimated cost, time, storage, and quality before any generation starts.</p></div><span className="callout-arrow">↗</span>
        </div>
        <div className="section-title"><div><div className="eyebrow">YOUR LIBRARY</div><h2>Recent projects</h2></div><span>{projects.length} {projects.length === 1 ? "project" : "projects"}</span></div>
        {error && <Notice tone="error">{error}</Notice>}
        {loading ? <Loading label="Loading your projects…" /> : projects.length === 0 ? (
          <div className="empty-state"><div className="empty-symbol">✳</div><h3>Your next story starts here.</h3><p>Create a project and turn a simple idea into a reviewed storyboard and video.</p><Button href="/projects/new">Create a project <span>→</span></Button></div>
        ) : (
          <div className="project-table">
            <div className="table-head"><span>PROJECT</span><span>STATUS</span><span>LENGTH</span><span>EST. COST</span><span>CREATED</span></div>
            {projects.map((project) => (
              <div className="project-row-wrap" key={project.id}><Link className="project-row" href={`/projects/${project.id}/${project.status === "completed" ? "video" : "analysis"}`}>
                <span className="project-name"><span className="mini-art">✳</span><b>{project.title}</b></span>
                <span><i className={`project-status status-${project.status.replaceAll("_", "-")}`} />{project.status.replaceAll("_", " ")}</span>
                <span>{project.target_seconds} s</span><span>{project.estimated_cost === null ? "—" : `$${project.estimated_cost.toFixed(2)}`}</span>
                <span>{new Date(project.created_at).toLocaleDateString()}</span>
              </Link><Button variant="ghost" disabled={deleting !== null} onClick={() => deleteProject(project)}>
                {deleting === project.id ? "Deleting..." : "Delete project"}</Button></div>
            ))}
          </div>
        )}
        <footer className="dashboard-footer">POSTGRESQL PROJECT STORAGE <i /> AI CALLS REQUIRE YOUR OPENAI API KEY</footer>
      </div>
    </main>
  );
}
