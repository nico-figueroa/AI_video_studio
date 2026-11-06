export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type PlanName = "economy" | "balanced" | "premium";
export type ProjectSummary = {
  id: number;
  title: string;
  status: string;
  target_minutes: number;
  selected_plan: PlanName | null;
  created_at: string;
  estimated_cost: number | null;
};
export type Project = ProjectSummary & {
  prompt: string;
  max_budget: number;
  max_wait_minutes: number;
  video_url: string | null;
};
export type Character = {
  id: number;
  name: string;
  description: string;
  image_path: string | null;
  approved: boolean;
};
export type Scene = {
  id: number;
  scene_number: number;
  title: string;
  description: string;
  image_path: string | null;
  status: string;
  approved: boolean;
};
export type Story = {
  title: string;
  summary: string;
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
};
export type Metrics = {
  estimated_cost: number;
  actual_cost: number;
  estimated_time: number;
  actual_time: number | null;
  total_images: number;
  video_length_seconds: number | null;
};

export function assetUrl(path: string | null): string {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new Error("Could not reach the API. Start the backend at http://localhost:8000.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = body?.detail;
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

export const api = {
  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (input: {
    prompt: string;
    target_minutes: number;
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
  selectPlan: (id: number, plan: PlanName) => request<{ selected_plan: PlanName }>(
    `/projects/${id}/select-plan`,
    { method: "POST", body: JSON.stringify({ plan }) },
  ),
  getStory: (id: number) => request<Story>(`/projects/${id}/story`),
  regenerateStory: (id: number) => request<{ status: string }>(
    `/projects/${id}/story/regenerate`,
    { method: "POST" },
  ),
  saveStory: (id: number, story: Story) => request<{ updated: boolean }>(
    `/projects/${id}/story`,
    { method: "PUT", body: JSON.stringify(story) },
  ),
  getCharacters: (id: number) => request<Character[]>(`/projects/${id}/characters`),
  createPortrait: (id: number) => request<{ status: string }>(
    `/characters/${id}/portrait`,
    { method: "POST" },
  ),
  approveCharacter: (id: number, approved: boolean) => request<Character>(
    `/characters/${id}`,
    { method: "PUT", body: JSON.stringify({ approved }) },
  ),
  getScenes: (id: number) => request<Scene[]>(`/projects/${id}/scenes`),
  generateScene: (id: number, regenerate = false) => request<{ status: string }>(
    `/scenes/${id}/${regenerate ? "regenerate" : "generate"}`,
    { method: "POST" },
  ),
  approveScene: (id: number, approved: boolean) => request<Scene>(
    `/scenes/${id}`,
    { method: "PUT", body: JSON.stringify({ approved }) },
  ),
  startVideo: (id: number, plan: PlanName) => request<{ job_id: string; status: string }>(
    `/projects/${id}/video`,
    { method: "POST", body: JSON.stringify({ plan }) },
  ),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  getActiveJob: (id: number) => request<Job | null>(`/projects/${id}/active-job`),
  getMetrics: (id: number) => request<Metrics>(`/projects/${id}/metrics`),
};
