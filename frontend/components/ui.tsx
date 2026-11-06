import Link from "next/link";
import type { ReactNode } from "react";
import type { Estimate, GenerationEstimate, PlanName } from "@/services/api";

export function Button({
  children,
  href,
  variant = "primary",
  className = "",
  ...props
}: {
  children: ReactNode;
  href?: string;
  variant?: "primary" | "secondary" | "ghost";
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const classes = `button button-${variant} ${className}`;
  if (href) return <Link className={classes} href={href}>{children}</Link>;
  return <button className={classes} {...props}>{children}</button>;
}

export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "error" | "success";
}) {
  return <div className={`notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}>{children}</div>;
}

export function Loading({ label = "Loading your studio…" }: { label?: string }) {
  return <div className="loading"><span className="spinner" />{label}</div>;
}

export function ProjectLayout({
  projectId,
  title,
  eyebrow = "YOUR PROJECT",
  children,
}: {
  projectId: number;
  title: string;
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <main className="workspace">
      <header className="workspace-head">
        <Link className="brand" href="/dashboard"><span className="brand-mark">✳</span> Framewise</Link>
        <div className="crumb"><Link href="/dashboard">Projects</Link><span>/</span><span>{title}</span></div>
        <Link className="avatar" href="/dashboard" aria-label="Back to projects">N</Link>
      </header>
      <div className="workspace-body">
        <aside className="project-sidebar">
          <div className="sidebar-project"><div className="eyebrow">{eyebrow}</div><strong>{title || "Untitled project"}</strong></div>
          <nav className="step-nav" aria-label="Project workflow">
            {[
              ["01", "Plan", `/projects/${projectId}/analysis`],
              ["02", "Story", `/projects/${projectId}/story`],
              ["03", "Characters", `/projects/${projectId}/characters`],
              ["04", "Scenes", `/projects/${projectId}/scenes`],
            ].map(([number, label, href]) => (
              <Link className="step-link" href={href} key={number}><span>{number}</span>{label}</Link>
            ))}
            <Link className="step-link" href="/settings/ai"><span>⚙</span>AI settings</Link>
          </nav>
          <div className="sidebar-note"><span className="status-dot" />AI planning studio <small>Estimate before every call</small></div>
        </aside>
        <section className="project-content">{children}</section>
      </div>
    </main>
  );
}

export function PageHeading({
  label,
  title,
  description,
  children,
}: {
  label: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div><div className="eyebrow">{label}</div><h1>{title}</h1><p>{description}</p></div>
      {children}
    </div>
  );
}

export function GenerationEstimateDisclosure({
  estimate,
  title,
}: {
  estimate: GenerationEstimate;
  title: string;
}) {
  return (
    <div className="generation-disclosure estimate-detail">
      <div><span>ESTIMATED COST</span><b>${estimate.estimated_cost.toFixed(4)}</b></div>
      <div><span>ESTIMATED TIME</span><b>~{estimate.estimated_minutes} min</b></div>
      <div><span>ESTIMATED API CALLS</span><b>{estimate.estimated_api_calls}</b></div>
      <div><span>MODEL USAGE</span><b>{estimate.estimated_model_usage}</b></div>
      <p>{title}. {estimate.notes} Provider billing may differ; requests are not sent until you start generation.</p>
    </div>
  );
}

export function GenerationDisclosure({
  plan,
  estimate,
}: {
  plan: PlanName | null;
  estimate: Estimate | null;
}) {
  if (!plan || !estimate) {
    return <Notice tone="error">Choose a production plan on the analysis page before generating assets.</Notice>;
  }
  return (
    <div className="generation-disclosure">
      <div><span>APPROVED PLAN</span><b>{plan}</b></div>
      <div><span>EST. TIME</span><b>~{estimate.estimated_minutes} min</b></div>
      <div><span>EST. PROVIDER COST</span><b>${estimate.estimated_cost.toFixed(2)}*</b></div>
      <div><span>EST. STORAGE</span><b>{estimate.storage_mb} MB</b></div>
      <div><span>EST. GPU USE</span><b>{estimate.gpu_minutes} min</b></div>
      <p>*Phase 1 export estimate only. AI generation costs are estimated separately; actual provider billing is not reported by this app.</p>
    </div>
  );
}
