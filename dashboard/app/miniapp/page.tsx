"use client";

// GovMind Telegram Mini App — the Telegram counterpart of the original Luffa mini app:
// a DAO Health tab (treasury, proposals, quick actions, demo) with a floating agent chat,
// an Agent tab (the live tool graph), and the message feed.

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { backendUrl } from "@/lib/backend";
import { connectSocket } from "@/lib/socket";
import { useDashboardStore } from "@/lib/store";
import { AgentWorkspace } from "../components/AgentWorkspace";
import { DaoHealth } from "../components/DaoHealth";
import { LiveFeed } from "../components/LiveFeed";

type Tab = "health" | "agent" | "feed";

const SUGGESTIONS = [
  "What is our current burn rate?",
  "How many active proposals do we have?",
  "Who hasn't voted on the latest proposal?",
  "Show me the treasury allocation breakdown",
];

declare global {
  interface Window {
    Telegram?: { WebApp?: { ready: () => void; expand: () => void; HapticFeedback?: { notificationOccurred: (t: string) => void } } };
  }
}

// Buzz the phone when an answer lands. Telegram's SDK throws on clients that don't support it
// (and outside Telegram), so never let that reach React.
function haptic(kind: "success" | "error") {
  try {
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred(kind);
  } catch {}
}

// Minimal formatting for agent answers: **bold** / *bold*, and drop markdown heading hashes.
function Formatted({ text }: { text: string }) {
  const clean = text.replace(/^#{1,6}\s*/gm, "");
  return (
    <>
      {clean.split(/(\*\*[^*]+\*\*|\*[^*\n]+\*)/g).map((part, i) =>
        /^\*{1,2}[^*]/.test(part) && /\*$/.test(part) ? (
          <strong key={i} className="text-[var(--text-primary)]">{part.replace(/^\*+|\*+$/g, "")}</strong>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

interface ChatMsg {
  id: number;
  role: "user" | "agent" | "error";
  text: string;
}

function FloatingChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const pendingRun = useRef<string | null>(null);
  const counter = useRef(0);
  const bottom = useRef<HTMLDivElement>(null);
  const runs = useDashboardStore((s) => s.runs);
  const activeRunId = useDashboardStore((s) => s.activeRunId);

  const liveRun = busy ? runs.find((r) => r.id === activeRunId) : undefined;

  // When the run we started finishes, show its answer in the chat (like the original floating chat).
  useEffect(() => {
    if (!busy) return;
    if (!pendingRun.current && activeRunId) pendingRun.current = activeRunId;
    const run = runs.find((r) => r.id === pendingRun.current);
    if (run && run.status !== "running") {
      counter.current += 1;
      setMessages((m) => [
        ...m,
        { id: counter.current, role: run.status === "error" ? "error" : "agent", text: run.response || "Done." },
      ]);
      haptic(run.status === "error" ? "error" : "success");
      pendingRun.current = null;
      setBusy(false);
    }
  }, [runs, activeRunId, busy]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, liveRun?.steps.length]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    counter.current += 1;
    setMessages((m) => [...m, { id: counter.current, role: "user", text: q }]);
    setInput("");
    setBusy(true);
    pendingRun.current = null;
    try {
      const res = await fetch(`${backendUrl()}/trigger/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error();
    } catch {
      counter.current += 1;
      setMessages((m) => [...m, { id: counter.current, role: "error", text: "Failed to reach GovMind. Check your connection." }]);
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed right-4 bottom-20 w-14 h-14 rounded-full bg-emerald-500 text-black text-2xl shadow-lg shadow-emerald-500/30 z-40 cursor-pointer"
        aria-label="Ask GovMind"
      >
        💬
      </button>
    );
  }

  return (
    <div className="fixed inset-x-0 bottom-0 top-16 z-50 flex flex-col bg-[var(--bg-secondary)] border-t border-[var(--border-dim)] rounded-t-2xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-dim)]">
        <span className="text-[12px] font-semibold text-[var(--text-primary)]">Ask GovMind</span>
        <button onClick={() => setOpen(false)} className="text-[var(--text-dim)] text-lg px-2 cursor-pointer">✕</button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-[11px] text-[var(--text-dim)]">Ask anything about the DAO:</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="block w-full text-left text-[11px] px-3 py-2 rounded-lg border border-[var(--border-dim)] bg-[var(--bg-card)] text-[var(--text-secondary)] cursor-pointer"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`text-[11px] leading-relaxed whitespace-pre-wrap rounded-lg px-3 py-2 max-w-[90%] ${
              m.role === "user"
                ? "ml-auto bg-emerald-500/15 text-emerald-200"
                : m.role === "error"
                ? "bg-red-500/10 text-red-300"
                : "bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-dim)]"
            }`}
          >
            {m.role === "agent" ? <Formatted text={m.text} /> : m.text}
          </div>
        ))}
        {liveRun && (
          <div className="rounded-lg border border-[var(--border-dim)] bg-[var(--bg-card)] px-3 py-2 space-y-1">
            {liveRun.steps.map((st) => (
              <div key={st.id} className="flex items-center gap-2 text-[10px] text-[var(--text-dim)]">
                <span className={st.status === "running" ? "text-amber-400 animate-pulse" : "text-emerald-400"}>
                  {st.status === "running" ? "●" : "✓"}
                </span>
                {st.description}
              </div>
            ))}
            {liveRun.steps.length === 0 && <div className="text-[10px] text-[var(--text-dim)] animate-pulse">Thinking…</div>}
          </div>
        )}
        <div ref={bottom} />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 p-3 border-t border-[var(--border-dim)]"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={busy ? "GovMind is working…" : "Ask about proposals, votes, treasury…"}
          disabled={busy}
          className="flex-1 text-[12px] px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-dim)] text-[var(--text-primary)] outline-none"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="px-4 rounded-lg bg-emerald-500 text-black text-[12px] font-semibold disabled:opacity-40 cursor-pointer"
        >
          Send
        </button>
      </form>
    </div>
  );
}

export default function MiniApp() {
  const [tab, setTab] = useState<Tab>("health");
  const connected = useDashboardStore((s) => s.connected);
  const running = useDashboardStore((s) => s.runs.some((r) => r.status === "running"));

  useEffect(() => {
    connectSocket();
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: "health", label: "DAO Health" },
    { id: "agent", label: running ? "Agent ●" : "Agent" },
    { id: "feed", label: "Feed" },
  ];

  return (
    <div className="h-full flex flex-col bg-[var(--bg-primary)]">
      <Script
        src="https://telegram.org/js/telegram-web-app.js"
        strategy="afterInteractive"
        onLoad={() => {
          window.Telegram?.WebApp?.ready();
          window.Telegram?.WebApp?.expand();
        }}
      />
      <header className="h-12 flex items-center justify-between px-4 border-b border-[var(--border-dim)] bg-[var(--bg-secondary)] shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-[var(--accent-emerald)] flex items-center justify-center text-black font-bold text-xs">
            GM
          </div>
          <span className="text-sm font-semibold tracking-wide text-[var(--text-primary)]">GOVMIND</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? "bg-[var(--accent-emerald)] animate-pulse-dot" : "bg-[var(--accent-red)]"}`} />
          <span className="text-[10px] text-[var(--text-dim)]">{connected ? "LIVE" : "OFFLINE"}</span>
        </div>
      </header>

      <main className="flex-1 min-h-0 overflow-hidden">
        {/* Keep all tabs mounted so the graph keeps animating while you look at another tab. */}
        <div className={tab === "health" ? "h-full" : "hidden"}><DaoHealth /></div>
        <div className={tab === "agent" ? "h-full" : "hidden"}><AgentWorkspace /></div>
        <div className={tab === "feed" ? "h-full" : "hidden"}><LiveFeed /></div>
      </main>

      <nav className="h-14 shrink-0 grid grid-cols-3 border-t border-[var(--border-dim)] bg-[var(--bg-secondary)]">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`text-[11px] font-semibold cursor-pointer ${tab === t.id ? "text-emerald-400" : "text-[var(--text-dim)]"}`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "health" && <FloatingChat />}
    </div>
  );
}
