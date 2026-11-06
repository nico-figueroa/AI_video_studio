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

export default function CharactersPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [estimates, setEstimates] = useState<GenerationEstimates | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
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
      const updated = await api.approveCharacter(character.id, !character.approved);
      setCharacters((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update character."); }
    finally { setBusyId(null); }
  }

  const remainingBudget = project ? Math.max(0, project.max_budget - project.estimated_spend) : 0;
  const overBudget = estimates ? estimates.character_portrait.estimated_cost > remainingBudget : false;

  return <ProjectLayout projectId={id} title="Character review">
    <PageHeading label="03 / CHARACTER BIBLE" title="Meet the people in your story." description="Review each character bible and generate portraits individually. The estimate below applies to one image request." />
    {error && <Notice tone="error">{error}</Notice>}
    {loading || !estimates || !project ? <Loading label="Loading character bible and estimates…" /> : <>
      <GenerationEstimateDisclosure
        estimate={estimates.character_portrait}
        title="Estimate per character portrait. Starting a portrait reserves this amount against your project budget."
      />
      {overBudget && <Notice tone="error">A portrait estimate exceeds your remaining ${remainingBudget.toFixed(2)} project budget.</Notice>}
      {characters.length === 0 && <Notice>Generate the Story Bible from the planning page before reviewing characters.</Notice>}
      <div className="character-grid">{characters.map((character, index) => <article className="character-card" key={character.id}>
        <div className={`character-art character-art-${index}`} style={character.image_path ? { backgroundImage: `url("${assetUrl(character.image_path)}")` } : undefined}>
          {!character.image_path && <span>{character.name.slice(0, 1)}</span>}
          <small>{character.approved ? "✓ APPROVED" : "CHARACTER STUDY"}</small>
        </div>
        <div className="character-details">
          <div className="eyebrow">CHARACTER {String(index + 1).padStart(2, "0")} · {character.role || "ROLE"}</div>
          <h3>{character.name}</h3>
          <dl className="character-facts">
            <dt>Personality</dt><dd>{character.personality || character.description}</dd>
            <dt>Appearance</dt><dd>{character.appearance || "Not specified"}</dd>
            <dt>Motivations</dt><dd>{character.motivations || "Not specified"}</dd>
            <dt>Relationships</dt><dd>{character.relationships || "Not specified"}</dd>
            <dt>Portrait prompt</dt><dd>{character.portrait_prompt || "Uses the character description"}</dd>
          </dl>
          <div className="card-actions">
            <Button variant="secondary" disabled={overBudget || busyId === character.id} onClick={() => portrait(character)}>
              {busyId === character.id ? "Generating portrait…" : character.image_path ? "Regenerate portrait" : "Generate portrait"}
            </Button>
            <Button variant={character.approved ? "ghost" : "primary"} disabled={busyId === character.id} onClick={() => approve(character)}>
              {character.approved ? "✓ Approved" : "Approve"}
            </Button>
          </div>
          {busyId === character.id && <Loading label="Waiting for portrait image…" />}
        </div>
      </article>)}</div>
    </>}
    <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/story`}>← Story bible</Button><Button href={`/projects/${id}/scenes`}>Review scenes <span>→</span></Button></div>
  </ProjectLayout>;
}
