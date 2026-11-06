"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, assetUrl, type Character, type Estimate, type PlanName } from "@/services/api";
import { Button, GenerationDisclosure, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";

export default function CharactersPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<PlanName | null>(null);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const refresh = useCallback(() => api.getCharacters(id).then(setCharacters), [id]);

  useEffect(() => {
    Promise.all([refresh(), api.getProject(id), api.getEstimates(id)])
      .then(([, project, estimates]) => {
        const plan = project.selected_plan;
        setSelectedPlan(plan);
        setEstimate(plan ? estimates[plan] : null);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [id, refresh]);

  async function portrait(character: Character) {
    setBusyId(character.id);
    setError("");
    try { await api.createPortrait(character.id); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not generate portrait."); }
    finally { setBusyId(null); }
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

  return <ProjectLayout projectId={id} title="Character review">
    <PageHeading label="03 / CHARACTER REVIEW" title="Meet the people in your story." description="Character portraits are local placeholders in this prototype. Approve the cast or regenerate a reference image." />
    {error && <Notice tone="error">{error}</Notice>}
    {loading ? <Loading label="Loading character bible…" /> : <div className="character-grid">
      <GenerationDisclosure plan={selectedPlan} estimate={estimate} />
      {characters.map((character, index) => <article className="character-card" key={character.id}>
        <div className={`character-art character-art-${index}`} style={character.image_path ? { backgroundImage: `url("${assetUrl(character.image_path)}")` } : undefined}>
          {!character.image_path && <span>{character.name.slice(0, 1)}</span>}
          <small>{character.approved ? "✓ APPROVED" : "CHARACTER STUDY"}</small>
        </div>
        <div className="character-details"><div className="eyebrow">CHARACTER {String(index + 1).padStart(2, "0")}</div><h3>{character.name}</h3><p>{character.description}</p>
          <div className="card-actions"><Button variant="secondary" disabled={!selectedPlan || busyId === character.id} onClick={() => portrait(character)}>{busyId === character.id ? "Working…" : character.image_path ? "Regenerate portrait" : "Generate portrait"}</Button><Button variant={character.approved ? "ghost" : "primary"} disabled={busyId === character.id} onClick={() => approve(character)}>{character.approved ? "✓ Approved" : "Approve"}</Button></div>
        </div>
      </article>)}
    </div>}
    <Notice>Artwork is generated locally by a replaceable placeholder provider. It does not call an image model.</Notice>
    <div className="workflow-footer"><Button variant="ghost" href={`/projects/${id}/story`}>← Story bible</Button><Button href={`/projects/${id}/scenes`}>Review scenes <span>→</span></Button></div>
  </ProjectLayout>;
}
