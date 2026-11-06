"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type GenerationEstimates, type Story } from "@/services/api";
import { Button, GenerationEstimateDisclosure, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";

export default function StoryPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const router = useRouter();
  const [story, setStory] = useState<Story | null>(null);
  const [estimates, setEstimates] = useState<GenerationEstimates | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([api.getStory(id), api.getGenerationEstimates(id)])
      .then(([storyData, estimateData]) => {
        setStory(storyData);
        setEstimates(estimateData);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [id]);

  function updateScene(index: number, description: string) {
    if (!story) return;
    const scenes = story.scenes.map((scene, i) => i === index ? { ...scene, description } : scene);
    setStory({ ...story, scenes });
  }

  async function save(continueNext = false) {
    if (!story) return;
    setBusy(true);
    setError("");
    try {
      await api.saveStory(id, story);
      setStory(await api.getStory(id));
      setSaved(true);
      if (continueNext) router.push(`/projects/${id}/characters`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save your story.");
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    if (!window.confirm("Regenerate the story bible? Unsaved edits and generated project artwork will be cleared.")) return;
    setBusy(true);
    setError("");
    try {
      await api.regenerateStory(id);
      router.push(`/projects/${id}/analysis`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not regenerate the story.");
      setBusy(false);
    }
  }

  return <ProjectLayout projectId={id} title={story?.title ?? "Project"}>
    {!story ? error ? <Notice tone="error">{error}</Notice> : <Loading label="Writing your story bible…" /> : <>
      <PageHeading label="02 / STORY REVIEW" title="The story is yours to shape." description="Review the story bible and scene beats. Edit any detail before moving on to characters." />
      {estimates && <GenerationEstimateDisclosure estimate={estimates.planning} title="This estimate applies if you regenerate the story, character bible, and scene plan." />}
      {error && <Notice tone="error">{error}</Notice>}{saved && <Notice tone="success">Story bible saved.</Notice>}
      <div className="editor-panel">
        <label className="field-label" htmlFor="story-title">STORY TITLE</label>
        <input id="story-title" className="text-input title-input" value={story.title} onChange={(event) => setStory({ ...story, title: event.target.value })} />
        <label className="field-label" htmlFor="story-genre">GENRE</label>
        <input id="story-genre" className="text-input" value={story.genre} onChange={(event) => setStory({ ...story, genre: event.target.value })} />
        <label className="field-label" htmlFor="story-audience">TARGET AUDIENCE</label>
        <input id="story-audience" className="text-input" value={story.target_audience} onChange={(event) => setStory({ ...story, target_audience: event.target.value })} />
        <label className="field-label" htmlFor="story-summary">THE STORY</label>
        <textarea id="story-summary" className="text-input summary-input" value={story.summary} onChange={(event) => setStory({ ...story, summary: event.target.value })} />
        <div className="eyebrow">THREE ACT STRUCTURE</div>
        <div className="act-grid">{Object.entries(story.three_act_structure).map(([act, detail]) => <article key={act}>
          <label className="field-label" htmlFor={`story-act-${act}`}>{act.replaceAll("_", " ").toUpperCase()}</label>
          <textarea
            id={`story-act-${act}`}
            className="text-input"
            aria-label={`${act.replaceAll("_", " ")} details`}
            value={detail}
            onChange={(event) => setStory({
              ...story,
              three_act_structure: { ...story.three_act_structure, [act]: event.target.value },
            })}
          />
        </article>)}</div>
      </div>
      <div className="section-title"><div><div className="eyebrow">THE PEOPLE IN YOUR STORY</div><h2>Character bible</h2></div><span>{story.characters.length} characters</span></div>
      <div className="character-mini-grid">{story.characters.map((character, index) => <div className="character-mini" key={character.id}><div className={`character-monogram monogram-${index}`}>{character.name.slice(0, 1)}</div><div><input aria-label="Character name" className="inline-edit" value={character.name} onChange={(event) => setStory({ ...story, characters: story.characters.map((item) => item.id === character.id ? { ...item, name: event.target.value } : item) })} /><textarea aria-label={`Description for ${character.name}`} value={character.description} onChange={(event) => setStory({ ...story, characters: story.characters.map((item) => item.id === character.id ? { ...item, description: event.target.value } : item) })} /></div></div>)}</div>
      <div className="section-title"><div><div className="eyebrow">THE STORYBOARD</div><h2>Scene breakdown</h2></div><span>{story.scenes.length} scenes</span></div>
      <div className="story-scenes">{story.scenes.map((scene, index) => <div className="story-scene" key={scene.id}><div className="scene-number">{String(scene.scene_number).padStart(2, "0")}</div><div><input aria-label={`Title for scene ${scene.scene_number}`} className="inline-edit" value={scene.title} onChange={(event) => setStory({ ...story, scenes: story.scenes.map((item, i) => i === index ? { ...item, title: event.target.value } : item) })} /><textarea aria-label={`Description for ${scene.title}`} value={scene.description} onChange={(event) => updateScene(index, event.target.value)} /></div></div>)}</div>
      <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/analysis`}>← Back to plan</Button><div><Button variant="secondary" disabled={busy} onClick={regenerate}>Regenerate story</Button><Button variant="secondary" disabled={busy} onClick={() => save()}>{busy ? "Saving…" : "Save changes"}</Button><Button disabled={busy} onClick={() => save(true)}>Continue to characters <span>→</span></Button></div></div>
    </>}
  </ProjectLayout>;
}
