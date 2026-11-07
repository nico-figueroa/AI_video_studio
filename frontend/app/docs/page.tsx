import Link from "next/link";

export default function DocsPage() {
  return <main className="docs-page">
    <header className="workspace-head"><Link className="brand" href="/docs">Framewise / Studio guide</Link>
      <nav aria-label="Studio navigation"><Link href="/dashboard">Projects</Link> / <Link href="/projects/new">New project</Link> / <Link href="/settings/ai">AI settings</Link></nav></header>
    <section className="create-wrap">
      <div className="eyebrow">TRANSPARENCY FIRST</div><h1>Your story, one reviewed stage at a time.</h1>
      <p>AI Video Studio turns ideas and supplied assets into a narrated, downloadable MP4. You stay in control of content, review, and estimated spending.</p>
      <details className="collapsible-section"><summary>Workflow and generation stages</summary>
      <ol>
        <li>Create a project and set budget, wait limit, and target duration in seconds. Optionally import a full story, scenes, narration, character definitions, described images, or audio.</li>
        <li>Review the missing-asset planning estimate. Supplied content is preserved; only missing bibles or plans are generated. Audio transcription is a separate approved call.</li>
        <li>On Plan, approve the bounded automatic artwork/local-motion estimate once. Generate planning, then advance to Story and explicitly approve it. Enter Characters to generate all missing portraits automatically; preview and approve their references.</li>
        <li>After character approval, enter Scenes to generate all missing scene images automatically. Approve scenes before generating the connected narration arc and speech. Regeneration is an explicit choice, not an automatic repeat.</li>
        <li>Arrange the timeline, inspect pacing, camera focus, transitions, narration, and audio. Reordering invalidates generated narration so bridges can be recomposed.</li>
        <li>Enter Render to generate all missing local clips sequentially under the approved budget. Preview/approve every clip, then approve final export estimates, render locally, and download the MP4. Still-image-only export must be selected explicitly.</li>
      </ol>
      </details><details className="collapsible-section"><summary>Requirements and safeguards</summary>
      <p>Configure a provider key in the backend environment, start PostgreSQL and the backend, and keep local media available. Rendering requires scene images, current narration, and audio. Missing files and budget/wait limits cannot be bypassed.</p>
      <p>The project header shows your current stage, review coverage, incomplete assets, and required actions. Skipping a review requires an explicit confirmation; it never silently approves content.</p>
      <p>Edit the original prompt on Plan and confirm a complete restart to clear prior content, inputs and videos while retaining recorded spending. Delete whole projects from Dashboard, or exported videos/checkpoints only from Your video. These actions are blocked during active work.</p>
      </details><details className="collapsible-section"><summary>Cost philosophy</summary>
      <p>Estimates appear before paid calls. Estimated spending is reserved before requests, including requests that later fail; it is not an invoice. Transcription, images, text, and speech may incur provider charges. Local FFmpeg rendering has no provider fee, but uses your computer and storage. Runtime estimates are not promises.</p>
      </details><details className="collapsible-section"><summary>Quality and limitations</summary>
      <p>Character bibles, approved portrait references, story history, and connected narration improve consistency but cannot guarantee visual identity or narrative correctness. Readiness scores measure local reference/context coverage, asset availability, and approvals, not a visual or semantic AI assessment.</p>
      <p>Camera effects include slow zoom, pan, simulated two-plane parallax, crossfades, fades through black/white, and horizontal-blur transitions. Local Stable Video Diffusion generates experimental 2-second, 512x288 motion clips on an NVIDIA GPU. Preview and approve every clip on Render; local-motion exports cannot silently use still images. SVD cannot obey text-directed gestures, walking or camera prompts; identity and visible character motion are not guaranteed. Short clips hold their last frame rather than loop. This deployment is for authorized non-commercial use only. No lip sync, voice cloning, music generation or cloud GPU orchestration is included.</p>
      <p>Import TXT, MD, DOCX, text PDFs, JSON, YAML and CSV alongside images/audio. Scanned PDFs require external OCR. Structured documents use the input schema, not arbitrary schemas. Uploaded audio is retained; scene splits use separately approved word-timestamp transcription. Text classification is heuristic and can be corrected before import. Images require descriptions; the app does not infer a story from filenames.</p>
      </details><h2>Navigate your production</h2>
      <p><Link className="button button-primary" href="/projects/new">Create a project</Link> <Link className="button button-secondary" href="/dashboard">Open projects</Link></p>
      <p>Select any project from the dashboard to access its plan, story, characters, scenes, timeline, render, and video routes. Each project sidebar links to all seven stages.</p>
      <p><Link href="/settings/ai">Configure AI models and default limits</Link></p>
    </section>
  </main>;
}
