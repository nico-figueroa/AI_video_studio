"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  api,
  assetUrl,
  type Character,
  type GenerationEstimates,
  type Project,
} from "@/services/api";
import {
  Button,
  GenerationEstimateDisclosure,
  Loading,
  Notice,
  PageHeading,
  ProjectLayout,
} from "@/components/ui";
import { StageGeneration } from "@/components/stage-generation";

export default function CharactersPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [estimates, setEstimates] = useState<GenerationEstimates | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [stageBusy, setStageBusy] = useState(true);
  const refreshStage = useCallback(async () => {
    const [items, data] = await Promise.all([api.getCharacters(id), api.getProject(id)]);
    setCharacters(items); setProject(data);
  }, [id]);
  const [scores, setScores] = useState<Record<string, number>>({});
  useEffect(() => {
    api.getQuality(id).then((report) => setScores(report.character_scores)).catch((reason: Error) => setError(reason.message));
  }, [id, characters]);
  const refresh = useCallback(() => api.getCharacters(id).then(setCharacters), [id]);

  useEffect(() => {
    Promise.all([refresh(), api.getProject(id), api.getGenerationEstimates(id)])
      .then(([, projectData, estimateData]) => {
        setProject(projectData);
        setEstimates(estimateData);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [id, refresh]);

  async function portrait(character: Character) {
    if (!window.confirm("Regenerate this portrait using the displayed per-image estimate? It will need approval again.")) return;
    setBusyId(character.id);
    setError("");
    let generationError = "";
    try {
      await api.createPortrait(character.id);
    } catch (reason) {
      generationError = reason instanceof Error ? reason.message : "Could not generate portrait.";
    } finally {
      const [charactersResult, projectResult] = await Promise.allSettled([
        api.getCharacters(id),
        api.getProject(id),
      ]);
      if (charactersResult.status === "fulfilled") setCharacters(charactersResult.value);
      if (projectResult.status === "fulfilled") setProject(projectResult.value);

      const refreshError = [charactersResult, projectResult]
        .find((result) => result.status === "rejected");
      const refreshMessage = refreshError?.status === "rejected"
        ? refreshError.reason instanceof Error ? refreshError.reason.message : "Could not refresh project data."
        : "";
      const errors = [generationError, refreshMessage].filter(Boolean);
      if (errors.length) setError(errors.join(" "));
      setBusyId(null);
    }
  }

  async function approve(character: Character) {
    setBusyId(character.id);
    setError("");
    try {
      const updated = await api.approveCharacter(
        character.id,
        !character.approved,
        character.image_path,
      );
      setCharacters((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update character."); }
    finally { setBusyId(null); }
  }

  const remainingBudget = project ? Math.max(0, project.max_budget - project.estimated_spend) : 0;
  const overBudget = estimates ? estimates.character_portrait.estimated_cost > remainingBudget : false;
  const overWait = project && estimates
    ? estimates.character_portrait.estimated_minutes > project.max_wait_minutes
    : false;

  return <ProjectLayout projectId={id} title="Character review">
    <PageHeading label="03 / CHARACTER BIBLE" title="Meet the people in your story." description="All missing portraits generate automatically with the approved stage budget. Preview and approve each result, or explicitly regenerate it." />
    <StageGeneration projectId={id} stage="characters" onComplete={refreshStage} onActive={setStageBusy} />
    {error && <Notice tone="error">{error}</Notice>}
    {loading ? <Loading label="Loading character bible and estimates…" /> : !estimates || !project ? <>
      <Button variant="secondary" onClick={() => window.location.reload()}>Retry loading characters</Button>
    </> : <>
      <GenerationEstimateDisclosure
        estimate={estimates.character_portrait}
        title="Estimate per character portrait. Starting a portrait reserves this amount against your project budget."
      />
      {overBudget && <Notice tone="error">A portrait estimate exceeds your remaining ${remainingBudget.toFixed(2)} project budget.</Notice>}
      {overWait && <Notice tone="error">A portrait estimate exceeds your project wait limit.</Notice>}
      {characters.length === 0 && <Notice>Generate the Story Bible from the planning page before reviewing characters.</Notice>}
      <div className="character-grid">{characters.map((character, index) => <article className="character-card" key={character.id}>
        <div className={`character-art character-art-${index}`} style={character.image_path ? { backgroundImage: `url("${assetUrl(character.image_path)}")` } : undefined}>
          {!character.image_path && <span>{character.name.slice(0, 1)}</span>}
          <small>{character.approved ? "✓ APPROVED" : "CHARACTER STUDY"}</small>
        </div>
        <div className="character-details">
          <h3>{character.name}</h3>
          <details className="card-details"><summary>Character details and review</summary><dl className="character-facts">
            <dt>Role</dt><dd>{character.role || "Not specified"}</dd>
            <dt>Personality</dt><dd>{character.personality || "Not specified"}</dd>
            <dt>Description</dt><dd>{character.description}</dd>
            <dt>Appearance</dt><dd>{character.appearance || "Not specified"}</dd>
            <dt>Motivations</dt><dd>{character.motivations || "Not specified"}</dd>
            <dt>Relationships</dt><dd>{character.relationships || "Not specified"}</dd>
            <dt>Portrait prompt</dt><dd>{character.portrait_prompt || "Uses the character description"}</dd>
            <dt>Clothing / age</dt><dd>{character.clothing || "Not specified"} / {character.age || "Not specified"}</dd>
            <dt>Distinctive traits</dt><dd>{character.distinctive_traits || "Not specified"}</dd>
            <dt>Facial features</dt><dd>{character.facial_features || "Not specified"}</dd>
            <dt>Negative prompt</dt><dd>{character.negative_prompt || "Not specified"}</dd>
            <dt>Consistency coverage</dt><dd>{scores[character.id] ?? 0}% / {character.reference_image_paths.length} retained references. Local identity-field/reference coverage, not measured visual similarity.</dd>
          </dl>
          <div className="card-actions">
            {character.image_path && <Button variant="secondary" disabled={stageBusy || overBudget || overWait || busyId !== null} onClick={() => portrait(character)}>
              {busyId === character.id ? "Generating portrait…" : "Regenerate portrait"}
            </Button>}
            <Button
              variant={character.approved ? "ghost" : "primary"}
              disabled={stageBusy || busyId !== null || !character.image_path}
              onClick={() => approve(character)}
            >
              {character.approved ? "✓ Approved" : "Approve"}
            </Button>
          </div>
          </details>
          {busyId === character.id && <Loading label="Waiting for portrait image…" />}
        </div>
      </article>)}</div>
    </>}
    <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/story`}>← Story bible</Button>
      {characters.length > 0 && characters.every((item) => item.approved) && !stageBusy
        ? <Button href={`/projects/${id}/scenes`}>Continue to Scenes <span>→</span></Button>
        : <Notice>Approve all portraits before continuing to scene generation.</Notice>}</div>
  </ProjectLayout>;
}
