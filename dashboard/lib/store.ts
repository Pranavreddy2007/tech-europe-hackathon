import { create } from "zustand";

export interface ToolStep {
  id: string;
  tool: string;
  input: Record<string, unknown>;
  result?: unknown;
  status: "running" | "complete" | "error";
  description: string;
  timestamp: string;
}

export interface AgentRun {
  id: string;
  trigger: string;
  steps: ToolStep[];
  response?: string;
  status: "running" | "complete" | "error";
  startedAt: string;
  completedAt?: string;
}

export interface WhatsAppMessage {
  id: string;
  type: "incoming" | "outgoing";
  channel: "dm" | "group";
  text: string;
  senderUid?: string;
  recipientUid?: string;
  timestamp: string;
}

interface DashboardState {
  runs: AgentRun[];
  activeRunId: string | null;
  messages: WhatsAppMessage[];
  connected: boolean;

  setConnected: (v: boolean) => void;
  addMessage: (msg: WhatsAppMessage) => void;

  startRun: (trigger: string) => string;
  addStep: (runId: string, step: ToolStep) => void;
  completeStep: (runId: string, toolName: string, result: unknown) => void;
  completeRun: (runId: string, response: string) => void;
  errorRun: (runId: string, error: string) => void;
}

let runCounter = 0;
let stepCounter = 0;

export const useDashboardStore = create<DashboardState>((set, get) => ({
  runs: [],
  activeRunId: null,
  messages: [],
  connected: false,

  setConnected: (v) => set({ connected: v }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages.slice(-100), msg] })),

  startRun: (trigger) => {
    const id = `run-${++runCounter}`;
    const run: AgentRun = {
      id,
      trigger,
      steps: [],
      status: "running",
      startedAt: new Date().toISOString(),
    };
    set((s) => ({
      runs: [...s.runs.slice(-20), run],
      activeRunId: id,
    }));
    return id;
  },

  addStep: (runId, step) =>
    set((s) => ({
      runs: s.runs.map((r) =>
        r.id === runId ? { ...r, steps: [...r.steps, step] } : r
      ),
    })),

  completeStep: (runId, toolName, result) =>
    set((s) => ({
      runs: s.runs.map((r) =>
        r.id === runId
          ? {
              ...r,
              steps: r.steps.map((st) =>
                st.tool === toolName && st.status === "running"
                  ? { ...st, status: "complete" as const, result }
                  : st
              ),
            }
          : r
      ),
    })),

  completeRun: (runId, response) =>
    set((s) => ({
      runs: s.runs.map((r) =>
        r.id === runId
          ? {
              ...r,
              status: "complete" as const,
              response,
              completedAt: new Date().toISOString(),
            }
          : r
      ),
    })),

  errorRun: (runId, error) =>
    set((s) => ({
      runs: s.runs.map((r) =>
        r.id === runId
          ? {
              ...r,
              status: "error" as const,
              response: error,
              completedAt: new Date().toISOString(),
            }
          : r
      ),
    })),
}));

export function getStepId() {
  return `step-${++stepCounter}`;
}
