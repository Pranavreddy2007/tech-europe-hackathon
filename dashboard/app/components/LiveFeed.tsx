"use client";

import { useEffect, useRef, useState } from "react";
import { useDashboardStore, WhatsAppMessage } from "@/lib/store";

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function detectMessageType(text: string): { label: string; color: string } {
  const lower = text.toLowerCase();
  if (lower.includes("governance alert") || lower.includes("attack"))
    return { label: "ALERT", color: "bg-red-500/15 text-red-400" };
  if (lower.includes("treasury alert") || lower.includes("burn rate"))
    return { label: "TREASURY", color: "bg-amber-500/15 text-amber-400" };
  if (lower.includes("proposal briefing") || lower.includes("risk rating"))
    return { label: "BRIEFING", color: "bg-blue-500/15 text-blue-400" };
  if (lower.includes("voting reminder") || lower.includes("haven't voted") || lower.includes("nudge"))
    return { label: "NUDGE", color: "bg-purple-500/15 text-purple-400" };
  return { label: "", color: "" };
}

function MessageBubble({ msg }: { msg: WhatsAppMessage }) {
  const isOutgoing = msg.type === "outgoing";
  const [expanded, setExpanded] = useState(false);
  const isLong = msg.text.length > 300;
  const msgType = isOutgoing ? detectMessageType(msg.text) : { label: "", color: "" };

  return (
    <div
      className={`animate-slide-in px-3 py-2.5 ${
        isOutgoing
          ? "border-l-2 border-l-emerald-500/40"
          : msg.channel === "dm"
          ? "border-l-2 border-l-purple-500/40"
          : ""
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1 flex-wrap">
        {isOutgoing ? (
          <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 uppercase tracking-wider">
            GovMind
          </span>
        ) : (
          <>
            <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 uppercase tracking-wider">
              {msg.channel === "dm" ? `${msg.platform ?? "WhatsApp"} In` : msg.platform ?? "Broadcast"}
            </span>
            {msg.senderName && (
              <span className="text-[9px] font-semibold text-[var(--text-secondary)]">{msg.senderName}</span>
            )}
          </>
        )}
        {isOutgoing && msg.channel === "group" && (
          <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300/80 uppercase tracking-wider">
            {msg.platform ?? "Broadcast"}{msg.recipientCount ? ` → ${msg.recipientCount}` : ""}
          </span>
        )}
        {isOutgoing && msg.channel === "dm" && (
          <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-400 uppercase tracking-wider">
            DM
          </span>
        )}
        {msgType.label && (
          <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${msgType.color}`}>
            {msgType.label}
          </span>
        )}
        <span className="text-[9px] text-[var(--text-dim)] ml-auto">
          {formatTime(msg.timestamp)}
        </span>
      </div>
      <p
        className={`text-[11px] leading-relaxed whitespace-pre-wrap ${
          isOutgoing ? "text-emerald-300/80" : "text-[var(--text-secondary)]"
        }`}
      >
        {isLong && !expanded ? msg.text.slice(0, 300) + "..." : msg.text}
      </p>
      {msg.imageUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={msg.imageUrl}
          alt="Chart sent on WhatsApp"
          className="mt-2 rounded-md border border-[var(--border-dim)] w-full bg-white"
        />
      )}
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-[9px] text-cyan-400 hover:text-cyan-300 mt-1 cursor-pointer"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

export function LiveFeed() {
  const messages = useDashboardStore((s) => s.messages);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className="h-full flex flex-col bg-[var(--bg-primary)]">
      <div className="px-4 py-3 border-b border-[var(--border-dim)] shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-[11px] font-semibold text-[var(--text-dim)] uppercase tracking-widest">
              Live Feed
            </h2>
            <p className="text-[10px] text-[var(--text-dim)] mt-0.5">
              {messages.length} messages
            </p>
          </div>
          {messages.length > 0 && (
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin divide-y divide-[var(--border-dim)]/50">
        {messages.length === 0 && (
          <div className="px-4 py-8 text-center">
            <div className="text-[28px] mb-3 opacity-30">📡</div>
            <div className="text-[var(--text-dim)] text-[11px]">
              Waiting for messages...
            </div>
            <div className="text-[var(--text-dim)] text-[9px] mt-1">
              Message GovMind on WhatsApp or trigger an action
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
