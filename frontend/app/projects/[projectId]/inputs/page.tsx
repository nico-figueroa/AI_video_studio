"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type InputBundle, type InputClassification, type InputState, type ProductionEstimate } from "@/services/api";
import { Button, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";
import { ProductionEstimateDisclosure } from "@/components/production-estimate";

async function filePayload(file: File) {
  if (file.size > 20_000_000) throw new Error("Each file must be at most 20 MB.");
  const content = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === "string" ? resolve(reader.result.split(",")[1]) : reject(new Error("Could not read file."));
    reader.onerror = () => reject(new Error("Could not read file."));
    reader.readAsDataURL(file);
  });
  return { name:file.name,content_base64:content,description:"" };
}

export default function InputsPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [bundle, setBundle] = useState<InputBundle>({ title:"Imported story",text:"",text_kind:"auto",scenes:[],characters:[],images:[],audio:null });
  const [characters, setCharacters] = useState("");
  const [scenes, setScenes] = useState("");
  const [classification, setClassification] = useState<InputClassification | null>(null);
  const [state, setState] = useState<InputState | null>(null);
  const [estimate, setEstimate] = useState<ProductionEstimate | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api.getInputs(id).then(setState).catch((reason: Error) => setError(reason.message)); }, [id]);
  function change(next: InputBundle) { setBundle(next); setClassification(null); }
  function supplied(): InputBundle {
    return {
      ...bundle,
      scenes:scenes.split(/\n\s*\n/).filter((part) => part.trim()).map((part,index) => ({ title:`Scene ${index+1}`,description:part,duration_seconds:15 })),
      characters:characters.split(/\n\s*\n/).filter((part) => part.trim()).map((part) => ({
        name:part.split("\n")[0],role:"Supplied character",appearance:part,personality:"",motivations:"",relationships:"",portrait_prompt:part,
      })),
    };
  }
  async function files(files: FileList | null, audio = false, documents = false) {
    if (!files) return;
    setBusy("Reading supplied files"); setError("");
    try {
      if (files.length>12 || Array.from(files).reduce((sum,file) => sum+file.size,0)>40_000_000) throw new Error("Upload at most 12 files and 40 MB in total.");
      const payloads = await Promise.all(Array.from(files).map(filePayload));
      change(documents ? { ...bundle,documents:payloads } : audio ? { ...bundle,audio:payloads[0] } : { ...bundle,images:payloads });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not read files."); }
    finally { setBusy(""); }
  }
  async function act(importing = false) {
    setBusy(importing ? "Preserving supplied inputs" : "Classifying supplied inputs"); setError("");
    try {
      const payload = supplied();
      if (importing) setState(await api.importInputs(id,payload));
      else setClassification(await api.classifyInputs(payload));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Input request failed."); }
    finally { setBusy(""); }
  }
  async function transcribe() {
    if (!estimate || !approved) return;
    setBusy("Transcribing uploaded narration audio"); setError("");
    try { setState(await api.transcribe(id,estimate.estimate_id)); setApproved(false); setEstimate(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Transcription failed."); }
    finally { setBusy(""); }
  }
  return <ProjectLayout projectId={id} title="Supplied inputs">
    <PageHeading label="ADAPTIVE WORKFLOW" title="Start with what you already have." description="Classification and import are local and free. Review the detected types before preserving your supplied content. Only missing assets are generated later." />
    {error && <Notice tone="error">{error}</Notice>}
    {busy && <Loading label={busy} workflow={busy.includes("Transcrib") ? "narration" : "story"} />}
    {state ? <section className="editor-panel">
      <h2>Preserved inputs: {state.classification.kinds.join(", ")}</h2>
      <details className="card-details"><summary>Preserved source text</summary><p>{state.manifest.transcript || state.manifest.text}</p></details>
      {state.classification.limitations.map((item) => <p key={item}>{item}</p>)}
      {state.manifest.audio_seconds && !state.manifest.transcript_words ? <>
        <Button disabled={Boolean(busy)} onClick={() => api.getTranscriptionEstimate(id).then(setEstimate).catch((reason: Error) => setError(reason.message))}>Review transcription estimate</Button>
        {estimate && <><ProductionEstimateDisclosure estimate={estimate} title="Uploaded audio transcription" />
          <label className="production-approval"><input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} /> I approve this transcription estimate.</label>
          <div className="progression-actions"><Button disabled={!approved || Boolean(busy)} onClick={transcribe}>Transcribe supplied audio</Button></div></>}
      </> : <div className="progression-actions"><Button href={`/projects/${id}/analysis`}>Review missing-asset planning estimate</Button></div>}
      <Notice>Supplied story/scripts remain intact. Imported characters and images require review. Original audio is preserved and scene boundaries use approved transcription timestamps.</Notice>
    </section> : <section className="editor-panel">
      <label className="field-label">Project title<input className="text-input" value={bundle.title} onChange={(event) => change({ ...bundle,title:event.target.value })} /></label>
      <label className="field-label">Text type<select value={bundle.text_kind} onChange={(event) => change({ ...bundle,text_kind:event.target.value as InputBundle["text_kind"] })}>
        <option value="auto">Detect automatically (review below)</option><option value="text_story">Full story - preserve verbatim</option>
        <option value="scene_descriptions">Scene descriptions</option><option value="narration_script">Narration script - preserve words</option><option value="character_definitions">Character definitions</option>
      </select></label>
      <textarea className="text-input" aria-label="Supplied text" maxLength={6000} rows={8} value={bundle.text} onChange={(event) => change({ ...bundle,text:event.target.value })} />
      <label className="field-label">Story / scene / character documents
        <input type="file" accept=".txt,.md,.docx,.pdf,.json,.yaml,.yml,.csv" multiple
          disabled={Boolean(busy)} onChange={(event) => files(event.target.files,false,true)} />
      </label>
      {bundle.documents?.map((document,index) => <p key={index}>{document.name}</p>)}
      <details className="collapsible-section"><summary>Additional scenes and characters</summary><label className="field-label">Additional scenes (one paragraph per scene)<textarea className="text-input" value={scenes} onChange={(event) => { setScenes(event.target.value); setClassification(null); }} /></label>
      <label className="field-label">Additional characters (name on first line; description below; blank line between characters)<textarea className="text-input" value={characters} onChange={(event) => { setCharacters(event.target.value); setClassification(null); }} /></label></details>
      <label className="field-label">Images, in scene order (max 12)<input type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={Boolean(busy)} onChange={(event) => files(event.target.files)} /></label>
      {bundle.images.map((image,index) => <label className="field-label" key={index}>{image.name} - required description<input className="text-input" value={image.description} onChange={(event) => change({ ...bundle,images:bundle.images.map((item,other) => other===index ? { ...item,description:event.target.value } : item) })} /></label>)}
      <label className="field-label">Narration audio (max 20 MB / 10 minutes)<input type="file" accept=".wav,.mp3,.m4a,.flac,.ogg" disabled={Boolean(busy)} onChange={(event) => files(event.target.files,true)} /></label>
      <Notice>At most 40 MB total raw uploads. Captions, not filenames, describe images. Audio requires separately approved timestamp transcription, including when paired with a supplied script.</Notice>
      <Button disabled={Boolean(busy)} onClick={() => act()}>Detect and preview workflow</Button>
      {classification && <><h3>Detected: {classification.kinds.join(", ")}</h3>
        <ol>{classification.workflow.map((item) => <li key={item}>{item}</li>)}</ol>
        <p>Preserved: {classification.preserved.join(", ")}</p><ul>{classification.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        <div className="progression-actions"><Button disabled={Boolean(busy)} onClick={() => act(true)}>Confirm types and import</Button></div></>}
    </section>}
  </ProjectLayout>;
}
