"use client";

export function Header({ connected }: { connected: boolean }) {
  return (
    <header className="h-12 flex items-center justify-between px-5 border-b border-[var(--border-dim)] bg-[var(--bg-secondary)] shrink-0">
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded-md bg-[var(--accent-emerald)] flex items-center justify-center text-black font-bold text-xs">
          GM
        </div>
        <span className="text-sm font-semibold tracking-wide text-[var(--text-primary)]">
          GOVMIND
        </span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-dim)] border border-[var(--border-dim)] uppercase tracking-widest">
          Agent Dashboard
        </span>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              connected
                ? "bg-[var(--accent-emerald)] animate-pulse-dot"
                : "bg-[var(--accent-red)]"
            }`}
          />
          <span className="text-[11px] text-[var(--text-dim)]">
            {connected ? "LIVE" : "DISCONNECTED"}
          </span>
        </div>
        <span className="text-[10px] text-[var(--text-dim)]">MetaDAO</span>
      </div>
    </header>
  );
}
