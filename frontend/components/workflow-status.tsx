"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api, type QualityReport } from "@/services/api";

export function WorkflowStatus({ projectId }: { projectId: number }) {
  const path = usePathname();
  const [report, setReport] = useState<QualityReport | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    async function refresh() {
      try { const next = await api.getQuality(projectId); if (active) { setReport(next); setError(""); } }
      catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "Could not read review status."); }
    }
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [projectId,path]);
  return <aside className="workflow-status" aria-label="Project readiness">
    <Link href="/docs">Studio guide</Link> / Current page: {path.split("/").pop()}
    {error && <p role="alert">{error}</p>}
    {report && <><p>Stage: {report.stage} / Readiness: <strong>{report.score}%</strong> (local checks)</p>
      <div className="review-badges">{report.reviews.map((review) => <Link key={review.stage} href={`/projects/${projectId}/${review.stage === "animations" ? "render" : review.stage}`}>
        {review.stage}: {review.approved}/{review.total} approved
      </Link>)}</div>
      <details><summary>{report.blockers.length ? `${report.blockers.length} incomplete items / required actions` : "All production requirements are complete"}</summary>
        <ul>{report.blockers.map((item) => <li key={item}>{item}</li>)}</ul>
        {report.reviews.filter((item) => item.approved<item.total || item.total===0).map((item) => <p key={item.stage}>{item.required_action}</p>)}
        <p>{report.explanation}</p><ul>{Object.entries(report.dimensions).map(([name,value]) => <li key={name}>{name.replaceAll("_"," ")}: {value}%</li>)}</ul>
      </details>
    </>}
  </aside>;
}
