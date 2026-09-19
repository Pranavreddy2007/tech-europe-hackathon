"use client";

import { io, Socket } from "socket.io-client";
import { useDashboardStore, getStepId } from "./store";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

let socket: Socket | null = null;
let currentRunId: string | null = null;

export function connectSocket() {
  if (socket?.connected) return;

  const store = useDashboardStore.getState();
  socket = io(BACKEND_URL, { transports: ["websocket", "polling"] });

  socket.on("connect", () => {
    useDashboardStore.getState().setConnected(true);
  });

  socket.on("disconnect", () => {
    useDashboardStore.getState().setConnected(false);
  });

  socket.on("agent:start", (data: { trigger: string; timestamp: string }) => {
    currentRunId = useDashboardStore.getState().startRun(data.trigger);
  });

  socket.on(
    "agent:tool-start",
    (data: { tool: string; input: Record<string, unknown>; timestamp: string }) => {
      if (!currentRunId) return;
      const desc = describeToolCall(data.tool, data.input);
      useDashboardStore.getState().addStep(currentRunId, {
        id: getStepId(),
        tool: data.tool,
        input: data.input,
        status: "running",
        description: desc,
        timestamp: data.timestamp,
      });
    }
  );

  socket.on(
    "agent:tool-result",
    (data: { tool: string; result: unknown; timestamp: string }) => {
      if (!currentRunId) return;
      useDashboardStore.getState().completeStep(currentRunId, data.tool, data.result);
    }
  );

  socket.on(
    "agent:complete",
    (data: { response: string; steps: unknown[]; timestamp: string }) => {
      if (!currentRunId) return;
      useDashboardStore.getState().completeRun(currentRunId, data.response);
      currentRunId = null;
    }
  );

  socket.on("agent:error", (data: { error: string; timestamp: string }) => {
    if (!currentRunId) return;
    useDashboardStore.getState().errorRun(currentRunId, data.error);
    currentRunId = null;
  });

  socket.on(
    "whatsapp:message-received",
    (data: { type: string; text: string; senderUid?: string; timestamp: string }) => {
      useDashboardStore.getState().addMessage({
        id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        type: "incoming",
        channel: data.type as "dm" | "group",
        text: data.text,
        senderUid: data.senderUid,
        timestamp: data.timestamp,
      });
    }
  );

  socket.on(
    "whatsapp:message-sent",
    (data: { type: string; text: string; recipientUid?: string; timestamp: string }) => {
      useDashboardStore.getState().addMessage({
        id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        type: "outgoing",
        channel: data.type as "dm" | "group",
        text: data.text,
        recipientUid: data.recipientUid,
        timestamp: data.timestamp,
      });
    }
  );
}

export function disconnectSocket() {
  socket?.disconnect();
  socket = null;
}

function describeToolCall(name: string, input: Record<string, unknown>): string {
  const map: Record<string, string> = {
    get_active_proposals: "Fetching active proposals",
    get_proposal_detail: `Analysing proposal #${input.proposal_number ?? ""}`,
    get_voting_status: `Checking votes on proposal #${input.proposal_number ?? ""}`,
    get_member_vote_history: `Reviewing member voting history`,
    get_treasury_summary: "Querying treasury balances",
    get_treasury_transactions: "Scanning treasury transactions",
    get_token_transfers: "Scanning token transfer activity",
    get_wallet_profile: `Profiling wallet ${String(input.address ?? "").slice(0, 10)}...`,
    query_data: "Running database query",
    send_group_message: "Broadcasting on WhatsApp",
    send_direct_message: "Sending WhatsApp message",
    generate_chart: `Generating ${input.chart_type ?? ""} chart`,
    get_knowledge: `Checking knowledge: "${input.term ?? ""}"`,
    store_knowledge: `Storing correction: "${input.term ?? ""}"`,
    log_action: "Logging action to audit trail",
  };
  return map[name] || `Calling ${name}`;
}
