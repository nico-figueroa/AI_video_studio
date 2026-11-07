export type WorkflowWarning = {
  code: "review_required"; stage: string; confirmation_token: string;
  message: string; consequences: string; required_action: string;
};

let handler: ((warning: WorkflowWarning) => Promise<boolean>) | null = null;
export function setWorkflowConfirmation(value: typeof handler) { handler = value; }
export function confirmWorkflow(warning: WorkflowWarning): Promise<boolean> {
  if (!handler) throw new Error(warning.required_action);
  return handler(warning);
}
