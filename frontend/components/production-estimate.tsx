import type { ProductionEstimate } from "@/services/api";

export function ProductionEstimateDisclosure({ estimate, title }: {
  estimate: ProductionEstimate; title: string;
}) {
  return <section aria-label={title} className="generation-disclosure estimate-detail">
    <h3>{title}</h3>
    <div><span>ESTIMATED COST</span><b>${estimate.estimated_cost.toFixed(4)}</b></div>
    <div><span>ESTIMATED RUNTIME</span><b>{Math.ceil(estimate.estimated_runtime_seconds)} seconds</b></div>
    <div><span>ESTIMATED STORAGE</span><b>{estimate.estimated_storage_mb.toFixed(2)} MB</b></div>
    <div><span>ESTIMATED AUDIO DURATION</span><b>{estimate.estimated_audio_seconds.toFixed(1)} seconds</b></div>
    <div><span>ESTIMATED VIDEO LENGTH</span><b>{estimate.estimated_video_seconds.toFixed(1)} seconds</b></div>
    <div><span>MODEL / API CALLS</span><b>{estimate.model_usage} / {estimate.estimated_api_calls}</b></div>
    <details><summary>Estimate details and limitations</summary><p>{estimate.notes}</p></details>
  </section>;
}
