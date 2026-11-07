"use client";

import { useEffect, useRef, useState } from "react";
import { setWorkflowConfirmation, type WorkflowWarning } from "@/services/workflow-confirmation";

export function WorkflowConfirmation() {
  const [warning, setWarning] = useState<WorkflowWarning | null>(null);
  const pending = useRef<((value: boolean) => void) | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    setWorkflowConfirmation((next) => {
      pending.current?.(false);
      setWarning(next);
      return new Promise((resolve) => { pending.current = resolve; });
    });
    return () => { setWorkflowConfirmation(null); pending.current?.(false); };
  }, []);
  useEffect(() => { if (warning && !dialog.current?.open) dialog.current?.showModal(); }, [warning]);
  function finish(approved: boolean) {
    dialog.current?.close(); pending.current?.(approved); pending.current = null; setWarning(null);
  }
  return <dialog ref={dialog} className="workflow-dialog" aria-labelledby="review-warning" onCancel={(event) => { event.preventDefault(); finish(false); }}>
    {warning && <><h2 id="review-warning">Skipped review: {warning.stage}</h2><p>{warning.message}</p><p><strong>Potential consequences:</strong> {warning.consequences}</p><p><strong>Required action:</strong> {warning.required_action}</p>
      <div className="card-actions"><button className="button button-secondary" autoFocus onClick={() => finish(false)}>Cancel</button><button className="button button-primary" onClick={() => finish(true)}>Continue Anyway</button></div>
    </>}
  </dialog>;
}
