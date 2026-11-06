"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type AISettings } from "@/services/api";
import { Button, Loading, Notice } from "@/components/ui";

export default function AISettingsPage() {
  const [settings, setSettings] = useState<AISettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSettings(await api.getAISettings());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load AI settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      setSettings(await api.saveAISettings({
        provider: settings.provider,
        model: settings.model,
        image_model: settings.image_model,
        default_budget: settings.default_budget,
        default_wait_minutes: settings.default_wait_minutes,
      }));
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save AI settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="form-page">
      <header className="workspace-head">
        <Link className="brand" href="/dashboard"><span className="brand-mark">✳</span> Framewise</Link>
        <div className="crumb"><Link href="/dashboard">Projects</Link><span>/</span><span>AI settings</span></div>
        <Link className="avatar" href="/dashboard" aria-label="Back to projects">N</Link>
      </header>
      <div className="create-wrap">
        <Link href="/dashboard" className="back-link">← &nbsp;Back to studio</Link>
        <div className="eyebrow">PROVIDER CONFIGURATION</div>
        <h1>Make every call <em>visible.</em></h1>
        <p className="form-intro">Choose the provider and model defaults used for story planning and image generation. Your API key stays in the server environment and is never stored in the database.</p>
        {error && <Notice tone="error">{error}</Notice>}
        {saved && <Notice tone="success">AI settings saved.</Notice>}
        {loading ? <Loading label="Loading AI settings…" /> : !settings ? (
          <Button variant="secondary" onClick={loadSettings}>Retry loading AI settings</Button>
        ) : (
          <form className="create-form" onSubmit={save}>
            <label htmlFor="provider">Provider<span>AVAILABLE IN PHASE 2</span>
              <select id="provider" className="text-input" value={settings.provider} onChange={(event) => setSettings({ ...settings, provider: event.target.value as "openai" })}>
                <option value="openai">OpenAI</option>
              </select>
            </label>
            <label htmlFor="model">Text model<span>STORY, CHARACTER, AND SCENE GENERATION</span>
              <input id="model" className="text-input" required maxLength={120} value={settings.model} onChange={(event) => setSettings({ ...settings, model: event.target.value })} />
            </label>
            <label htmlFor="image-model">Image model<span>PORTRAITS AND SCENE IMAGES</span>
              <input id="image-model" className="text-input" required maxLength={120} value={settings.image_model} onChange={(event) => setSettings({ ...settings, image_model: event.target.value })} />
            </label>
            <div className="form-grid">
              <label htmlFor="default-budget">Default budget<span>USD</span>
                <input id="default-budget" type="number" min={0} max={1000} step={0.25} value={settings.default_budget} onChange={(event) => setSettings({ ...settings, default_budget: Number(event.target.value) })} />
              </label>
              <label htmlFor="default-wait">Default wait time<span>MINUTES</span>
                <input id="default-wait" type="number" min={1} max={1440} value={settings.default_wait_minutes} onChange={(event) => setSettings({ ...settings, default_wait_minutes: Number(event.target.value) })} />
              </label>
            </div>
            <Notice tone={settings.api_key_configured ? "success" : "error"}>
              {settings.api_key_configured
                ? "OPENAI_API_KEY is configured on the backend."
                : "OPENAI_API_KEY is not configured. Add it to the backend .env before starting generation."}
            </Notice>
            <Notice>Cost and duration estimates are planning figures, not provider quotes. Confirm current model pricing with your provider. Saving settings never starts a generation request.</Notice>
            <div className="form-actions"><span>Settings are stored in PostgreSQL.</span><Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save AI settings"}</Button></div>
          </form>
        )}
      </div>
    </main>
  );
}
