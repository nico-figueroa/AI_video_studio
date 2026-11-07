"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { LoadingMessageService, loadingMessages, type LoadingWorkflow } from "@/services/loading-message-service";

export function Loading({ label = "Loading your studio...", workflow, locale = "en" }: {
  label?: string; workflow?: LoadingWorkflow; locale?: string;
}) {
  const path = usePathname();
  const inferred: LoadingWorkflow = workflow ?? (
    /portrait|character/.test(label.toLowerCase()) ? "characters" :
    /scene|image/.test(label.toLowerCase()) ? "scenes" :
    /narrat|speech|audio|transcrib/.test(label.toLowerCase()) ? "narration" :
    /render|export|video/.test(label.toLowerCase()) || path.includes("/render") ? "render" : "story"
  );
  const [message, setMessage] = useState("");
  useEffect(() => {
    const catalogue = loadingMessages[locale] ?? loadingMessages.en;
    const service = new LoadingMessageService(catalogue[inferred]);
    setMessage(service.next());
    const timer = setInterval(() => setMessage(service.next()), 4500);
    return () => clearInterval(timer);
  }, [inferred, locale]);
  return <div className="loading" role="status" aria-live="polite"><span className="loading-wheel" aria-hidden="true" /><div><strong>{label}</strong><p>{message}</p></div></div>;
}
