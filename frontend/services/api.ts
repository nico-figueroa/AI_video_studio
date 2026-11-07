import { confirmWorkflow, type WorkflowWarning } from "@/services/workflow-confirmation";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type MotionPlan = {
  camera: "slow_zoom" | "pan" | "parallax"; focus_x: number; focus_y: number;
  transition: "cross_fade" | "fade_black" | "fade_color" | "motion_blur";
  color: "black" | "white"; pacing: "reflective" | "balanced" | "urgent";
  animation_instructions: string; motion_prompt: string; character_movement_prompt: string;
  execution: "camera_effects_only";
};
export type QualityReport = {
  score: number; dimensions: Record<string, number>; explanation: string; blockers: string[];
  reviews: { stage: string; approved: number; total: number; required_action: string }[];
  story_revision: string; stage: string;
  character_scores: Record<string, number>;
};
export type InputBundle = {
  text: string; text_kind: "auto" | "text_story" | "scene_descriptions" | "narration_script" | "character_definitions";
  title: string; scenes: { title: string; description: string; duration_seconds: number }[];
  characters: { name: string; role: string; appearance: string; personality: string; motivations: string; relationships: string; portrait_prompt: string }[];
  images: { name: string; content_base64: string; description: string }[];
  audio: { name: string; content_base64: string; description: string } | null;
  documents?: { name: string; content_base64: string; description: string }[];
};
export type InputClassification = { kinds: string[]; workflow: string[]; preserved: string[]; limitations: string[]; needs_transcription: boolean };
export type InputState = { classification: InputClassification; manifest: { text?: string; text_kind?: string; transcript?: string; transcript_words?: { word:string; start:number; end:number }[]; preserve_narration?: boolean; audio_seconds?: number; supplied_scenes?: boolean } };

export type PlanName = "economy" | "balanced" | "premium";
export type ProjectSummary = {
  id: number;
  title: string;
  status: string;
  target_minutes: number;
  target_seconds: number;
  selected_plan: PlanName | null;
  created_at: string;
  estimated_cost: number | null;
};
export type Project = ProjectSummary & {
  prompt: string;
  max_budget: number;
  max_wait_minutes: number;
  estimated_spend: number;
  video_url: string | null;
  render_mode: RenderMode;
};
export type Character = {
  id: number;
  name: string;
  description: string;
  role: string;
  personality: string;
  appearance: string;
  motivations: string;
  relationships: string;
  portrait_prompt: string;
  image_path: string | null;
  approved: boolean;
  clothing: string; age: string; distinctive_traits: string; negative_prompt: string;
  reference_image_paths: string[];
  facial_features: string;
};
export type Scene = {
  id: number;
  scene_number: number;
  title: string;
  description: string;
  visual_description: string;
  image_prompt: string;
  estimated_duration: number;
  image_path: string | null;
  status: string;
  approved: boolean;
  beat_number: number;
};
export type Story = {
  title: string;
  summary: string;
  genre: string;
  target_audience: string;
  three_act_structure: Record<string, string>;
  characters: Character[];
  scenes: Scene[];
};
export type Estimate = {
  plan_name: PlanName;
  estimated_cost: number;
  estimated_minutes: number;
  resolution: string;
  quality_score: number;
  storage_mb: number;
  gpu_minutes: number;
};
export type GenerationEstimate = {
  operation: string;
  estimated_cost: number;
  estimated_minutes: number;
  estimated_model_usage: string;
  estimated_api_calls: number;
  notes: string;
};
export type GenerationEstimates = {
  planning: GenerationEstimate;
  story: GenerationEstimate;
  characters: GenerationEstimate;
  scenes: GenerationEstimate;
  character_portrait: GenerationEstimate;
  scene_image: GenerationEstimate;
  all_images: GenerationEstimate;
};
export type AISettings = {
  provider: "openai";
  model: string;
  image_model: string;
  default_budget: number;
  default_wait_minutes: number;
  api_key_configured: boolean;
};
export type Estimates = {
  economy: Estimate;
  balanced: Estimate;
  premium: Estimate;
  simulated: boolean;
  actual_provider_cost: number;
};
export type Job = {
  job_id: string;
  project_id: number;
  status: string;
  progress: number;
  current_stage: string;
  error: string | null;
  video_url: string | null;
  operation: string;
};
export type RenderMode = "local_animation" | "still_images";
export type GenerationStage = "characters" | "scenes" | "animations";
export type AutomaticGenerationState = {
  estimate: ProductionEstimate; approved: boolean; render_mode: RenderMode;
  characters: number; scenes: number; max_animation_seconds: number;
};
export type StageGenerationState = { job: Job | null; missing: number };
export type Metrics = {
  estimated_cost: number;
  actual_cost: number;
  estimated_ai_spend: number;
  actual_provider_cost: number | null;
  estimated_time: number;
  actual_time: number | null;
  total_images: number;
  video_length_seconds: number | null;
};
export type ProductionEstimate = {
  estimate_id: string;
  estimated_cost: number;
  estimated_runtime_seconds: number;
  estimated_storage_mb: number;
  estimated_audio_seconds: number;
  estimated_video_seconds: number;
  estimated_api_calls: number;
  model_usage: string;
  notes: string;
};
export type Narration = {
  items: {
    scene_id: number; text: string; recommended_seconds: number;
    audio_url: string | null; audio_seconds: number | null; stale: boolean;
  }[];
  narration_estimate: ProductionEstimate;
  audio_estimate: ProductionEstimate;
};
export type TimelineScene = {
  scene_id: number; order: number; title: string; image_url: string | null;
  narration: string | null; audio_url: string | null; audio_seconds: number | null;
  duration_seconds: number; ready: boolean;
  motion_plan: MotionPlan;
  animation_url: string | null; animation_issue: string | null;
};
export type AnimationJob = {
  job_id: string; scene_id: number; status: string; progress: number;
  error: string | null; clip_url: string | null; approved: boolean; stale: boolean;
  metadata: Record<string, unknown>;
};
export type AnimationState = { estimate: ProductionEstimate; job: AnimationJob | null };
export type FilmPlan = {
  narrative: { source: string; beats: {
    number: number; title: string; purpose: string; timeline_progression: string;
    character_introductions: string[]; transition: string; scene_ids: number[];
  }[] };
  scenes: { scene_id: number; beat_number: number; bridge: {
    previous: { title: string } | null; current: { title: string }; next: { title: string } | null;
    instructions: string;
  }; camera_motion_transition_animation_plan: MotionPlan; animation_capability: string }[];
};
export type Timeline = {
  project_id: number; revision: string; scenes: TimelineScene[];
  duration_seconds: number; ready: boolean;
};
export type RenderStatus = {
  job_id: string; project_id: number; status: string; progress: number;
  current_stage: string; error: string | null; completed_scenes: number[];
  video_url: string | null;
  elapsed_seconds: number; estimated_remaining_seconds: number | null;
};
export type ProductionVideo = {
  url: string; download_url: string; duration_seconds: number | null;
  audio_seconds: number | null; size_bytes: number | null;
  generation_seconds: number | null; estimated_cost: number | null;
  estimated_ai_spend: number; actual_provider_cost: number | null;
  render_job_id: string | null;
  render_mode: string; animated_scene_count: number; generated_motion_seconds: number;
  chapters: { scene_id: number; title: string; start_seconds: number; duration_seconds: number; generated_motion_seconds: number }[];
  playback_audio_url: string | null;
};

export function assetUrl(path: string | null): string {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit, reviewedStages: string[] = []): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.body) headers.set("Content-Type","application/json");
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new Error("Could not reach the API. Start the backend at http://localhost:8000.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = body?.detail;
    if (response.status === 409 && isWorkflowWarning(detail) && !reviewedStages.includes(detail.stage) && reviewedStages.length < 3) {
      if (!await confirmWorkflow(detail)) throw new Error("Generation cancelled. Review the required stage before continuing.");
      const headers = new Headers(init?.headers);
      headers.set("X-Workflow-Override",[headers.get("X-Workflow-Override"),detail.confirmation_token].filter(Boolean).join(","));
      return request<T>(path, { ...init, headers }, [...reviewedStages,detail.stage]);
    }
    if (typeof detail === "string") throw new Error(detail);
    if (Array.isArray(detail)) {
      const messages = detail.map((item: { loc?: (string | number)[]; msg?: string }) =>
        `${item.loc?.filter((part) => part !== "body").join(".") || "Request"}: ${item.msg ?? "Invalid value"}`,
      );
      throw new Error(messages.join("; "));
    }
    throw new Error(`Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

function isWorkflowWarning(value: unknown): value is WorkflowWarning {
  return typeof value === "object" && value !== null && "code" in value && value.code === "review_required"
    && "stage" in value && typeof value.stage === "string"
    && "confirmation_token" in value && typeof value.confirmation_token === "string"
    && "message" in value && typeof value.message === "string"
    && "consequences" in value && typeof value.consequences === "string"
    && "required_action" in value && typeof value.required_action === "string";
}

export const api = {
  getAutomaticGeneration: (id: number, mode: RenderMode = "local_animation") =>
    request<AutomaticGenerationState>(`/projects/${id}/automatic-generation?mode=${mode}`),
  approveAutomaticGeneration: (id: number, estimateId: string, mode: RenderMode) =>
    request<AutomaticGenerationState>(`/projects/${id}/automatic-generation`, {
      method:"POST", body:JSON.stringify({ approved:true, estimate_id:estimateId, render_mode:mode }),
    }),
  getStageGeneration: (id: number, stage: GenerationStage) =>
    request<StageGenerationState>(`/projects/${id}/generation/${stage}`),
  startStageGeneration: (id: number, stage: GenerationStage, retry = false) =>
    request<StageGenerationState>(`/projects/${id}/generation/${stage}`, {
      method:"POST", body:JSON.stringify({ retry }),
    }),
  deleteProject: (id: number) => request<{ status: string }>(`/projects/${id}`, {
    method:"DELETE", body:JSON.stringify({ approved:true }),
  }),
  deleteVideos: (id: number) => request<{ status: string }>(`/projects/${id}/video`, {
    method:"DELETE", body:JSON.stringify({ approved:true }),
  }),
  restartProject: (id: number, input: {
    expected_prompt: string; prompt: string; target_seconds: number; max_budget: number; max_wait_minutes: number;
  }) => request<{ status: string }>(`/projects/${id}/prompt`, {
    method:"PUT", body:JSON.stringify({ ...input, approved:true }),
  }),
  getQuality: (id: number) => request<QualityReport>(`/projects/${id}/quality`),
  approveStory: (id: number, revision: string, approved: boolean) => request<QualityReport>(`/projects/${id}/story/approval`, {
    method: "POST", body: JSON.stringify({ approved, revision }),
  }),
  saveMotion: (id: number, sceneId: number, revision: string, plan: MotionPlan) => request<QualityReport>(`/projects/${id}/scenes/${sceneId}/motion`, {
    method: "PUT", body: JSON.stringify({ revision, plan }),
  }),
  classifyInputs: (bundle: InputBundle) => request<InputClassification>("/inputs/classify", { method:"POST",body:JSON.stringify(bundle) }),
  importInputs: (id: number, bundle: InputBundle) => request<InputState>(`/projects/${id}/inputs`, { method:"POST",body:JSON.stringify(bundle) }),
  getInputs: (id: number) => request<InputState | null>(`/projects/${id}/inputs`),
  getTranscriptionEstimate: (id: number) => request<ProductionEstimate>(`/projects/${id}/inputs/transcription-estimate`),
  transcribe: (id: number, estimateId: string) => request<InputState>(`/projects/${id}/inputs/transcribe`, {
    method:"POST",body:JSON.stringify({ approved:true, estimate_id:estimateId }),
  }),
  getNarration: (id: number) => request<Narration>(`/projects/${id}/narration`),
  generateNarration: (id: number, estimateId: string, regenerate: boolean) =>
    request<Narration>(`/projects/${id}/narration`, {
      method: "POST", body: JSON.stringify({ approved: true, estimate_id: estimateId, regenerate }),
    }),
  generateAudio: (id: number, estimateId: string) =>
    request<Narration>(`/projects/${id}/narration/audio`, {
      method: "POST", body: JSON.stringify({ approved: true, estimate_id: estimateId }),
    }),
  getTimeline: (id: number) => request<Timeline>(`/projects/${id}/timeline`),
  getFilmPlan: (id: number) => request<FilmPlan>(`/projects/${id}/film-plan`),
  getAnimation: (id: number, scene: number) => request<AnimationState>(`/projects/${id}/scenes/${scene}/animation`),
  startAnimation: (id: number, scene: number, estimateId: string) => request<AnimationJob>(
    `/projects/${id}/scenes/${scene}/animation`, {
      method:"POST", body:JSON.stringify({ approved:true, estimate_id:estimateId }),
    }),
  reviewAnimation: (id: number, scene: number, jobId: string, approved: boolean) => request<AnimationJob>(
    `/projects/${id}/scenes/${scene}/animation/approval`, {
      method:"PUT", body:JSON.stringify({ job_id:jobId, approved }),
    }),
  saveTimeline: (id: number, timeline: Timeline) => request<Timeline>(`/projects/${id}/timeline`, {
    method: "PUT", body: JSON.stringify({
      revision: timeline.revision,
      scenes: timeline.scenes.map(({ scene_id, duration_seconds }) => ({ scene_id, duration_seconds })),
    }),
  }),
  getRenderEstimate: (id: number, mode: RenderMode = "local_animation") =>
    request<ProductionEstimate>(`/projects/${id}/render/estimate?mode=${mode}`),
  getRenderStatus: (id: number) => request<RenderStatus | null>(`/projects/${id}/render/status`),
  startRender: (id: number, estimateId: string, mode: RenderMode, resumeJobId?: string) =>
    request<RenderStatus>(`/projects/${id}/render`, {
      method: "POST", body: JSON.stringify({
        approved: true, estimate_id: estimateId, mode, resume_job_id: resumeJobId,
      }),
    }),
  getVideo: (id: number) => request<ProductionVideo>(`/projects/${id}/video`),
  getAISettings: () => request<AISettings>("/settings/ai"),
  saveAISettings: (settings: Omit<AISettings, "api_key_configured">) =>
    request<AISettings>("/settings/ai", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (input: {
    prompt: string;
    target_seconds: number;
    max_budget: number;
    max_wait_minutes: number;
  }) => request<{ project_id: number; status: string }>("/projects", {
    method: "POST",
    body: JSON.stringify(input),
  }),
  analyze: (id: number, refresh = false) => request<{ status: string }>(
    `/projects/${id}/analyze${refresh ? "?refresh=true" : ""}`,
    { method: "POST" },
  ),
  getProject: (id: number) => request<Project>(`/projects/${id}`),
  getEstimates: (id: number) => request<Estimates>(`/projects/${id}/estimates`),
  getGenerationEstimates: (id: number) =>
    request<GenerationEstimates>(`/projects/${id}/generation-estimates`),
  selectPlan: (id: number, plan: PlanName) => request<{ selected_plan: PlanName }>(
    `/projects/${id}/select-plan`,
    { method: "POST", body: JSON.stringify({ plan }) },
  ),
  getStory: (id: number) => request<Story>(`/projects/${id}/story`),
  regenerateStory: (id: number) => request<{ status: string }>(
    `/projects/${id}/story/regenerate`,
    { method: "POST" },
  ),
  saveStory: (id: number, story: Story) => request<{ updated: boolean; revision: string }>(
    `/projects/${id}/story`,
    { method: "PUT", body: JSON.stringify(story) },
  ),
  getCharacters: (id: number) => request<Character[]>(`/projects/${id}/characters`),
  createPortrait: (id: number) => request<{ status: string }>(
    `/characters/${id}/portrait`,
    { method: "POST" },
  ),
  approveCharacter: (id: number, approved: boolean, expectedImagePath: string | null) => request<Character>(
    `/characters/${id}`,
    { method: "PUT", body: JSON.stringify({ approved, expected_image_path: expectedImagePath }) },
  ),
  getScenes: (id: number) => request<Scene[]>(`/projects/${id}/scenes`),
  generateScene: (id: number, regenerate = false) => request<{ status: string }>(
    `/scenes/${id}/${regenerate ? "regenerate" : "generate"}`,
    { method: "POST" },
  ),
  approveScene: (id: number, approved: boolean, expectedImagePath: string | null) => request<Scene>(
    `/scenes/${id}`,
    { method: "PUT", body: JSON.stringify({ approved, expected_image_path: expectedImagePath }) },
  ),
  startVideo: (id: number, plan: PlanName) => request<{ job_id: string; status: string }>(
    `/projects/${id}/video`,
    { method: "POST", body: JSON.stringify({ plan }) },
  ),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  getActiveJob: (id: number) => request<Job | null>(`/projects/${id}/active-job`),
  getMetrics: (id: number) => request<Metrics>(`/projects/${id}/metrics`),
};
