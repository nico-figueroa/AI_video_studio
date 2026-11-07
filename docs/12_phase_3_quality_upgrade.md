# Phase 3 Quality Upgrade

This document records the completed baseline. The subsequent
[local animation and narrative extension](./13_local_animation_extension.md)
supersedes its deferred-only animation and equal-time audio boundaries.

## Mission and boundary

Improve consistency, coherence, review safety and transparency in the existing MP4 workflow. This is not Phase 4. Do not execute character animation, lip sync, voice cloning, generated motion/music, cloud GPU orchestration or RunPod.

## Implementation plan and delivered surfaces

1. **Persistence:** Apply `0003_quality` on top of existing Phase 2/3 migrations. Store story approval, import provenance, narration arc, review override audit, character identity/reference memory, scene generation context/motion instructions, and spoken transition metadata.
2. **Continuity:** Reconstruct story/character memory from PostgreSQL; include it in every artwork request. Copy approved portraits to immutable reference files and pass up to six available reference images through the provider interface. Missing references are explicit errors, not silent unconditioned generation.
3. **Review dependencies:** Guard portrait, scene artwork, narration/audio and final-render reviews with structured state-bound warnings. Require a real Cancel/Continue Anyway dialog. Never equate saving/navigation with approval. Keep technical readiness and cost limits non-bypassable.
4. **Adaptive inputs:** Classify and let users correct text types, import existing content without replacement, preserve full stories/scripts/characters/scenes/described images/audio, and estimate/generate missing planning assets only. Transcribe audio through `AIProvider` only after a separate current estimate approval. Keep original audio and use normalized local audio for narration.
5. **Narration:** Compose a single validated opening/development/resolution arc and ordered scene bridges from complete context. Speak each bridge once. Make whole-project source changes stale; restore imported scripts locally rather than paraphrasing them.
6. **Motion:** Persist tone-driven camera/focus/pacing/transitions and future animation/movement instructions. Execute zoom/pan, simulated two-plane parallax, crossfade, black/white fade and horizontal blur through FFmpeg. Use outgoing visual handles so transition overlaps never shorten narration.
7. **Animation contract only:** Declare `AnimationProvider.generate_motion_plan`, `animate_character` and `animate_scene`. Future adapters may support OpenAI video, Runway, LTX Video, Wan or Mochi; no adapter/execution is included.
8. **Quality:** Measure local identity-field/reference coverage, narration revision/bridge coverage, scene context coverage, asset completeness and approval coverage. Expose project readiness, per-character scores, review counts, missing content and actionable blockers. Never label this as a visual identity or semantic judgment.
9. **UX:** Make `/docs` the default entry, with product/workflow/stages/requirements/limitations/cost guide and navigation. Provide input import, explicit story approval, visible memory/coverage, motion controls and global review status. Rotate 20 unique humorous messages per workflow using locale-keyed shuffled catalogues.
10. **Verification:** Use deterministic provider fixtures, actual media encode/decode, isolated PostgreSQL migrations/production, frontend typecheck/build, catalogue/shuffle tests, and browser confirmation/cancellation/mobile checks. Do not invoke paid APIs automatically.

## Acceptance and verification

```powershell
$env:STUDIO_TEST_POSTGRES="1"
python -m pytest tests
Remove-Item Env:\STUDIO_TEST_POSTGRES
Set-Location frontend
npm run typecheck
npm test
npm run build
```

Backend coverage includes review cancellation/no-spend, stale tokens, explicit audited override, immutable references/context conditioning, full-arc staleness and malformed provider results, mixed classification/correction, preserved inputs/missing-only calls, approved transcription/original audio reuse, malformed uploads/rollback, and decoded transition color/duration. Existing production/recovery/concurrency and legacy compatibility tests remain in use.

Browser checks use fake API responses, not paid generation: `/` redirects to `/docs`; project approval/readiness is visible; Cancel sends no paid retry; Continue Anyway sends exactly one state-bound retry; long operations rotate messages; mobile project review stays within the viewport.

## Honest limitations and operational safeguards

- Reference conditioning improves consistency but does not guarantee identity. Human review of real provider output is still required; no paid visual scoring or unsupported accuracy claims.
- Initial Phase 2 planning creates draft bibles. Explicit artwork/narration review safeguards apply before production assets; drafting itself does not approve those bibles.
- Text detection is heuristic and user-correctable. Images require descriptions; no image-understanding claim. Imports are bounded to 12 items, 20 MB/file, 40 MB total, audio 10 minutes and text/transcript 6000 characters.
- Script/audio without scenes uses one source segment; multiple supplied scenes split source words/audio in equal ranges, not semantic alignment. Timing must be reviewed. Source audio is retained.
- Parallax is a two-plane image simulation, not reconstructed depth. Horizontal blur is a transition, not generated object movement.
- Runtime/storage/cost are planning estimates, not quotes. Image reference input can affect billing; configure image estimate rates conservatively. Attempted paid failures retain reservations. Local rendering excludes hardware/electricity costs.
- Use one backend process per database. Startup marks interrupted jobs/paid operations failed; retries and resumes require explicit actions. Back up PostgreSQL and local media together. No automatic media garbage collection.
- Reordering invalidates narration and story approval. Motion-only changes require a fresh render estimate but no paid text/speech calls. Published earlier videos stay available until a replacement is validated.

See [architecture](./03_system_architecture.md), [database](./04_database_design.md), [API contracts](./07_api_contracts.md), and [workflow](./11_user_workflow.md).
## Image prompt budgeting

Artwork conditioning keeps the complete scene/portrait composition prompt, character identity fields,
approved reference images, story arc and prior/current/upcoming continuity. Duplicate character bibles
and scene-history copies are omitted from image prompts only; stored memories remain unchanged.
Image context uses compact Unicode JSON within a 30,000-character budget. Oversized supporting
fields become explicitly marked excerpts, with a backend warning; every character and event entry
remains represented. OpenAI validates the final 32,000-character limit including its reference-image
instructions before any image request. If the composition itself cannot fit, shorten it before an
explicit retry. Failed batches never retry paid generation automatically and retain completed assets.
