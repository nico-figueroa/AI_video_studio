"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { API_URL, api, assetUrl, type ProductionVideo, type Project } from "@/services/api";
import { Button, Loading, Notice, PageHeading, ProjectLayout } from "@/components/ui";

export default function VideoPage() {
  const id = Number(useParams<{ projectId: string }>().projectId);
  const [project, setProject] = useState<Project | null>(null);
  const [video, setVideo] = useState<ProductionVideo | null>(null);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const player = useRef<HTMLVideoElement>(null);
  const narrationPlayer = useRef<HTMLAudioElement>(null);
  const [useWav, setUseWav] = useState(false);
  const [position, setPosition] = useState(0);
  const [muted, setMuted] = useState(false);
  useEffect(() => {
    setUseWav(!document.createElement("video").canPlayType('audio/mp4; codecs="mp4a.40.2"'));
  }, []);
  function syncNarration() {
    const element = player.current;
    const audio = narrationPlayer.current;
    if (!element || !audio || !useWav) return;
    if (Math.abs(audio.currentTime - element.currentTime) > 0.3) audio.currentTime = element.currentTime;
    audio.playbackRate = element.playbackRate;
  }
  async function startNarration() {
    const audio = narrationPlayer.current;
    if (!useWav || !audio) return;
    syncNarration();
    try {
      await audio.play();
    } catch (reason) {
      const element = player.current;
      if (reason instanceof DOMException && reason.name === "AbortError"
          && (!element || element.paused || element.seeking || element.readyState < 3)) return;
      player.current?.pause();
      setError(reason instanceof Error ? `Narration playback failed: ${reason.message}` : "Narration could not play. Try downloading the MP4.");
    }
  }
  async function playWithSound(start?: number) {
    const element = player.current;
    if (!element) return;
    setError("");
    try {
      if (start !== undefined) element.currentTime = start;
      element.muted = false;
      if (element.volume === 0) element.volume = 1;
      if (useWav && narrationPlayer.current) {
        narrationPlayer.current.muted = false;
        narrationPlayer.current.volume = element.volume;
      }
      await element.play();
    } catch (reason) {
      narrationPlayer.current?.pause();
      setError(reason instanceof Error ? `Playback failed: ${reason.message}` : "Playback failed. Try downloading the MP4.");
    }
  }
  async function deleteVideos() {
    if (!window.confirm("Delete all exported videos and render checkpoints for this project? Story, images, narration and motion clips will remain.")) return;
    setDeleting(true); setError("");
    try {
      await api.deleteVideos(id);
      setVideo(null); setProject(await api.getProject(id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete videos.");
    } finally { setDeleting(false); }
  }
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const data = await api.getProject(id);
      if (cancelled) return;
      setProject(data);
      if (data.video_url) {
        const result = await api.getVideo(id);
        if (!cancelled) setVideo(result);
      }
    }
    load().catch((reason: Error) => { if (!cancelled) setError(reason.message); });
    return () => { cancelled = true; };
  }, [id]);
  return <ProjectLayout projectId={id} title={project?.title ?? "Your video"}>
    <PageHeading label="07 / YOUR VIDEO" title="Your final cut." description="Play or download your MP4 with AI-generated narration. The latest successful export remains available if a replacement fails." />
    {error && <Notice tone="error">{error}</Notice>}
    {!project && !error && <Loading label="Loading your video..." />}
    {project && !project.video_url && <Notice>No video has been rendered yet.</Notice>}
    {project?.video_url && !video && !error && <Loading label="Loading video metrics..." />}
    {video && <>
      <Notice>Export source: <strong>{video.render_mode.replaceAll("_", " ")}</strong>.
        {video.animated_scene_count > 0
          ? ` ${video.animated_scene_count} model-generated clips; ${video.generated_motion_seconds} seconds of generated motion in total, with final-frame holds for longer narration.`
          : " No model-generated motion clips were used; this is a still-image export."}</Notice>
      <div className="video-player-wrap"><video ref={player} className="video-player" src={assetUrl(video.url)} controls playsInline
        onTimeUpdate={(event) => { setPosition(event.currentTarget.currentTime); if (!event.currentTarget.seeking) syncNarration(); }}
        onPause={() => narrationPlayer.current?.pause()}
        onWaiting={() => narrationPlayer.current?.pause()} onPlaying={() => { setError(""); void startNarration(); }}
        onSeeking={() => narrationPlayer.current?.pause()}
        onSeeked={() => { syncNarration(); if (!player.current?.paused) void startNarration(); }}
        onRateChange={syncNarration} onEnded={() => narrationPlayer.current?.pause()}
        onVolumeChange={(event) => {
          setMuted(event.currentTarget.muted || event.currentTarget.volume === 0);
          if (narrationPlayer.current) {
            narrationPlayer.current.muted = event.currentTarget.muted;
            narrationPlayer.current.volume = event.currentTarget.volume;
          }
        }}
        onError={() => setError("The video could not be played. Try downloading it or render a new version.")} /></div>
      {useWav && video.playback_audio_url && <>
        <audio ref={narrationPlayer} src={assetUrl(video.playback_audio_url)} preload="auto"
          onError={() => { player.current?.pause(); setError("Browser narration audio could not load. Reload or download the MP4."); }} />
        <Notice>This browser cannot decode MP4 AAC audio. Narration plays through a synchronized WAV track; the downloaded MP4 still contains its original audio.</Notice>
      </>}
      {useWav && !video.playback_audio_url && <Notice>This browser cannot decode MP4 AAC audio. Download this legacy video and play it in an external media player.</Notice>}
      <div className="progression-actions"><Button variant="secondary" onClick={() => playWithSound()}>Play with sound</Button></div>
      {muted && <Notice>Player sound is muted. Select Play with sound to enable narration. Also check your system output device and browser/system volume.</Notice>}
      {video.chapters.length > 0 && <section className="video-chapters" aria-label="Exported scene navigation">
        <h2>Scenes in this export</h2>
        <p>Jump to any scene below. Narration determines scene length; a short generated clip holds its final frame until the next scene.</p>
        <div className="chapter-buttons">{video.chapters.map((chapter, index) => <Button key={chapter.scene_id} variant="secondary"
          aria-current={position >= chapter.start_seconds && position < chapter.start_seconds + chapter.duration_seconds ? "true" : undefined}
          onClick={() => playWithSound(chapter.start_seconds)}>
          {index + 1}. {chapter.title} / {chapter.start_seconds}s–{chapter.start_seconds + chapter.duration_seconds}s
        </Button>)}</div>
      </section>}
      <div className="metric-grid">
        <div><span>VIDEO LENGTH</span><b>{video.duration_seconds?.toFixed(1) ?? "Legacy export"} s</b></div>
        <div><span>NARRATION AUDIO</span><b>{video.audio_seconds?.toFixed(1) ?? "-"} s</b></div>
        <div><span>FILE SIZE</span><b>{video.size_bytes == null ? "-" : (video.size_bytes / 1_000_000).toFixed(2)} MB</b></div>
        <div><span>RENDER TIME</span><b>{video.generation_seconds?.toFixed(1) ?? "-"} s</b></div>
        <div><span>LOCAL RENDER COST</span><b>${video.estimated_cost?.toFixed(4) ?? "0.0000"}</b><small>Excludes electricity and hardware</small></div>
        <div><span>RESERVED AI ESTIMATE</span><b>${video.estimated_ai_spend.toFixed(4)}</b><small>Actual provider invoice unavailable</small></div>
      </div>
      <div className="video-actions"><a className="button button-primary" href={`${API_URL}${video.download_url}`}>Download MP4</a><Button variant="secondary" href={`/projects/${id}/timeline`}>Create new version</Button>
        <Button variant="ghost" disabled={deleting} onClick={deleteVideos}>{deleting ? "Deleting..." : "Delete exported videos"}</Button></div>
    </>}
    <div className="workflow-footer"><Button href={`/projects/${id}/render`}>Render status</Button><Button variant="ghost" href="/dashboard">Return to dashboard</Button></div>
  </ProjectLayout>;
}
