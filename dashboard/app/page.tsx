"use client";

import { useEffect } from "react";
import { connectSocket } from "@/lib/socket";
import { useDashboardStore } from "@/lib/store";
import { Header } from "./components/Header";
import { LiveFeed } from "./components/LiveFeed";
import { AgentWorkspace } from "./components/AgentWorkspace";
import { DaoHealth } from "./components/DaoHealth";

export default function Home() {
  const connected = useDashboardStore((s) => s.connected);

  useEffect(() => {
    connectSocket();
  }, []);

  return (
    <div className="h-full flex flex-col">
      <Header connected={connected} />
      <main className="flex-1 flex gap-0 overflow-hidden">
        <div className="w-[280px] min-w-[280px] border-r border-[var(--border-dim)]">
          <LiveFeed />
        </div>
        <div className="flex-1 min-w-0">
          <AgentWorkspace />
        </div>
        <div className="w-[320px] min-w-[320px] border-l border-[var(--border-dim)]">
          <DaoHealth />
        </div>
      </main>
    </div>
  );
}
