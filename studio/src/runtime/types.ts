export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export type RunStatus =
  | "pending"
  | "running"
  | "interrupted"
  | "completed"
  | "failed"
  | "cancelled"
  | "recovery_required";
export interface Assistant {
  assistant_id: string;
  graph_id: string;
  name: string;
  config: { recursion_limit: number };
  created_at: string;
}
export interface Session {
  session_id: string;
  assistant_id: string;
  graph_id: string;
  config: { recursion_limit: number };
  title: string;
  created_at: string;
}
export interface Run {
  run_id: string;
  session_id: string;
  status: RunStatus;
  action: "input" | "resume" | "recover";
  idempotency_key: string;
  created_at: string;
  updated_at: string;
  error: Record<string, Json> | null;
}
export interface RuntimeEvent {
  event_id: number;
  session_id: string;
  run_id: string;
  kind: string;
  created_at: string;
  payload: Json;
  durable: true;
}
export interface StateView {
  values: Record<string, Json>;
  next: string[];
  checkpoint_id: string | null;
  created_at: string | null;
  metadata: Json;
  interrupts: Json[];
}
export interface Comparison {
  left: StateView;
  right: StateView;
  changed_keys: string[];
}
export type Submission =
  | { action: "input"; input: Record<string, Json>; idempotency_key: string }
  | { action: "resume"; resume: Json; idempotency_key: string }
  | { action: "recover"; acknowledge_replay: true; idempotency_key: string };
export const isActive = (run: Run | undefined) =>
  run?.status === "pending" || run?.status === "running";
export function object(value: Json | undefined): Record<string, Json> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}
export function mergeEvents(
  current: RuntimeEvent[],
  incoming: RuntimeEvent[],
): RuntimeEvent[] {
  const events = new Map(current.map((event) => [event.event_id, event]));
  incoming.forEach((event) => events.set(event.event_id, event));
  return [...events.values()].sort((a, b) => a.event_id - b.event_id);
}
