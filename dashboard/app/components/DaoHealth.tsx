"use client";

import { useEffect, useState } from "react";
import { backendUrl } from "@/lib/backend";
import { useDashboardStore } from "@/lib/store";

interface TreasurySummary {
  total_balance_eds: number;
  total_balance_usd: number;
  monthly_burn_rate_eds: number;
  runway_months: number;
  allocations: { token: string; balance: number; percentage: number }[];
  concentration_risk: { risk_level: string; details: string };
}

interface ProposalSummary {
  proposal_number: number;
  title: string;
  requested_amount: number;
  votes_for: number;
  votes_against: number;
  total_eligible_voters: number;
  total_votes: number;
}


function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-dim)] bg-[var(--bg-card)] p-3">
      <p className="text-[9px] text-[var(--text-dim)] uppercase tracking-wider">
        {label}
      </p>
      <p className="text-lg font-bold mt-0.5" style={{ color }}>
        {value}
      </p>
      {sub && (
        <p className="text-[9px] text-[var(--text-dim)] mt-0.5">{sub}</p>
      )}
    </div>
  );
}

function AllocationBar({
  token,
  pct,
  color,
}: {
  token: string;
  pct: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] text-[var(--text-secondary)] w-10 shrink-0">
        {token}
      </span>
      <div className="flex-1 h-2 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-[9px] text-[var(--text-dim)] w-8 text-right">
        {pct}%
      </span>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    LOW: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    MEDIUM: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    HIGH: "bg-red-500/15 text-red-400 border-red-500/30",
  };
  return (
    <span
      className={`text-[9px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wider ${
        colors[level] || colors.MEDIUM
      }`}
    >
      {level}
    </span>
  );
}

function ProposalCard({ p }: { p: ProposalSummary }) {
  const pct = p.total_eligible_voters
    ? Math.round((p.total_votes / p.total_eligible_voters) * 100)
    : 0;
  const forPct =
    p.total_votes > 0 ? Math.round((p.votes_for / p.total_votes) * 100) : 0;

  return (
    <div className="rounded-lg border border-[var(--border-dim)] bg-[var(--bg-card)] p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold text-[var(--text-primary)] truncate">
            #{p.proposal_number} {p.title}
          </p>
          <p className="text-[9px] text-[var(--text-dim)] mt-0.5">
            {p.requested_amount} EDS requested
          </p>
        </div>
      </div>
      <div className="mt-2 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[9px] text-[var(--text-dim)]">
            Participation
          </span>
          <span
            className={`text-[9px] font-semibold ${
              pct < 20 ? "text-red-400" : pct < 40 ? "text-amber-400" : "text-emerald-400"
            }`}
          >
            {pct}% ({p.total_votes}/{p.total_eligible_voters})
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              backgroundColor:
                pct < 20
                  ? "var(--accent-red)"
                  : pct < 40
                  ? "var(--accent-amber)"
                  : "var(--accent-emerald)",
            }}
          />
        </div>
        <div className="flex gap-3 text-[9px]">
          <span className="text-emerald-400">
            {p.votes_for} for ({forPct}%)
          </span>
          <span className="text-red-400">
            {p.votes_against} against ({100 - forPct}%)
          </span>
        </div>
      </div>
    </div>
  );
}

export function DaoHealth() {
  const [treasury, setTreasury] = useState<TreasurySummary | null>(null);
  const [proposals, setProposals] = useState<ProposalSummary[]>([]);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${backendUrl()}/api/health`);
        if (res.ok) {
          const data = await res.json();
          setTreasury(data.treasury);
          setProposals(data.proposals);
        }
      } catch {}
    }
    fetchData();
    const id = setInterval(fetchData, 30000);
    window.addEventListener(REFRESH_EVENT, fetchData);
    return () => {
      clearInterval(id);
      window.removeEventListener(REFRESH_EVENT, fetchData);
    };
  }, []);

  const allocationColors = ["var(--accent-emerald)", "var(--accent-cyan)", "var(--accent-blue)", "var(--accent-amber)"];

  return (
    <div className="h-full flex flex-col bg-[var(--bg-primary)]">
      <div className="px-4 py-3 border-b border-[var(--border-dim)] shrink-0">
        <h2 className="text-[11px] font-semibold text-[var(--text-dim)] uppercase tracking-widest">
          DAO Health
        </h2>
        <p className="text-[10px] text-[var(--text-dim)] mt-0.5">MetaDAO</p>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-3">
        {treasury ? (
          <>
            <div className="grid grid-cols-2 gap-2">
              <StatCard
                label="Treasury"
                value={`${treasury.total_balance_eds} EDS`}
                sub={`$${treasury.total_balance_usd.toLocaleString()}`}
                color="var(--accent-emerald)"
              />
              <StatCard
                label="Runway"
                value={`${treasury.runway_months} mo`}
                sub={`${treasury.monthly_burn_rate_eds} EDS/mo burn`}
                color={
                  treasury.runway_months < 4
                    ? "var(--accent-red)"
                    : treasury.runway_months < 6
                    ? "var(--accent-amber)"
                    : "var(--accent-emerald)"
                }
              />
            </div>

            <div className="rounded-lg border border-[var(--border-dim)] bg-[var(--bg-card)] p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[9px] text-[var(--text-dim)] uppercase tracking-wider">
                  Allocation
                </span>
                <RiskBadge level={treasury.concentration_risk.risk_level} />
              </div>
              {treasury.allocations.map((a, i) => (
                <AllocationBar
                  key={a.token}
                  token={a.token}
                  pct={a.percentage}
                  color={allocationColors[i % allocationColors.length]}
                />
              ))}
              <p className="text-[8px] text-[var(--text-dim)] leading-relaxed">
                {treasury.concentration_risk.details}
              </p>
            </div>
          </>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <StatCard
              label="Treasury"
              value="142.3 EDS"
              sub="$284,600"
              color="var(--accent-emerald)"
            />
            <StatCard
              label="Runway"
              value="6.2 mo"
              sub="23.1 EDS/mo burn"
              color="var(--accent-emerald)"
            />
          </div>
        )}

        <div className="space-y-2">
          <span className="text-[9px] text-[var(--text-dim)] uppercase tracking-wider">
            Active Proposals
          </span>
          {proposals.length > 0 ? (
            proposals.map((p) => <ProposalCard key={p.proposal_number} p={p} />)
          ) : (
            <>
              <ProposalCard
                p={{
                  proposal_number: 48,
                  title: "Fund Marketing Sprint Q2",
                  requested_amount: 45,
                  votes_for: 5,
                  votes_against: 3,
                  total_eligible_voters: 47,
                  total_votes: 8,
                }}
              />
              <ProposalCard
                p={{
                  proposal_number: 49,
                  title: "Strategic Partnership Fund Transfer",
                  requested_amount: 80,
                  votes_for: 3,
                  votes_against: 2,
                  total_eligible_voters: 47,
                  total_votes: 5,
                }}
              />
            </>
          )}
        </div>

        <QuickActions />
      </div>
    </div>
  );
}

const REFRESH_EVENT = "govmind:refresh";

type Trigger = { label: string; endpoint: string; body?: Record<string, unknown> };

const ALICE = { from: "447700900001", name: "Alice Chen" };
const BOB = { from: "447700900002", name: "Bob Martinez" };

// The 2-minute demo: each step waits for the agent to finish before the next starts.
const DEMO_STEPS: Trigger[] = [
  { label: "Alice asks GovMind", endpoint: "whatsapp-demo", body: { ...ALICE, text: "Hey GovMind, is proposal 49 safe to vote for?" } },
  { label: "Attacker submits proposal", endpoint: "submit-proposal" },
  { label: "Attack scan", endpoint: "attack-check" },
  { label: "Bob asks for a chart", endpoint: "whatsapp-demo", body: { ...BOB, text: "What's our treasury runway? Send me a chart." } },
];

const ACTIONS: (Trigger & { color: string })[] = [
  { label: "Alice asks: Is #49 safe?", endpoint: "whatsapp-demo", body: DEMO_STEPS[0].body, color: "hover:border-emerald-500/50 hover:text-emerald-400" },
  { label: "Bob asks: Runway chart", endpoint: "whatsapp-demo", body: DEMO_STEPS[3].body, color: "hover:border-emerald-500/50 hover:text-emerald-400" },
  { label: "🚨 Attacker submits proposal", endpoint: "submit-proposal", color: "hover:border-red-500/50 hover:text-red-400" },
  { label: "Proposal #49", endpoint: "new-proposal", body: { proposal_number: 49 }, color: "hover:border-blue-500/50 hover:text-blue-400" },
  { label: "Proposal #48", endpoint: "new-proposal", body: { proposal_number: 48 }, color: "hover:border-blue-500/50 hover:text-blue-400" },
  { label: "Vote Check", endpoint: "vote-check", color: "hover:border-purple-500/50 hover:text-purple-400" },
  { label: "Treasury Check", endpoint: "treasury-check", color: "hover:border-amber-500/50 hover:text-amber-400" },
  { label: "Attack Scan", endpoint: "attack-check", color: "hover:border-red-500/50 hover:text-red-400" },
];

async function fire(t: Trigger) {
  try {
    await fetch(`${backendUrl()}/trigger/${t.endpoint}`, {
      method: "POST",
      headers: t.body ? { "Content-Type": "application/json" } : {},
      body: t.body ? JSON.stringify(t.body) : undefined,
    });
  } finally {
    window.dispatchEvent(new Event(REFRESH_EVENT));
  }
}

function QuickActions() {
  const [busy, setBusy] = useState(false);
  const [demoStep, setDemoStep] = useState<number | null>(null);
  const clearAll = useDashboardStore((s) => s.clearAll);

  async function run(t: Trigger) {
    setBusy(true);
    try {
      await fire(t);
    } finally {
      setBusy(false);
    }
  }

  async function runDemo() {
    setBusy(true);
    try {
      for (let i = 0; i < DEMO_STEPS.length; i++) {
        setDemoStep(i);
        await fire(DEMO_STEPS[i]);
        await new Promise((r) => setTimeout(r, 1500)); // let the final graph state land on screen
      }
    } finally {
      setDemoStep(null);
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    try {
      await fetch(`${backendUrl()}/trigger/reset-demo`, { method: "POST" });
      clearAll();
      window.dispatchEvent(new Event(REFRESH_EVENT));
    } finally {
      setBusy(false);
    }
  }

  const base =
    "text-[9px] py-1.5 px-2 rounded-md border border-[var(--border-dim)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <div className="rounded-lg border border-[var(--border-dim)] bg-[var(--bg-card)] p-3">
      <span className="text-[9px] text-[var(--text-dim)] uppercase tracking-wider">Quick Actions</span>
      <div className="grid grid-cols-2 gap-1.5 mt-2">
        {ACTIONS.map((action) => (
          <button key={action.label} disabled={busy} onClick={() => run(action)} className={`${base} ${action.color}`}>
            {action.label}
          </button>
        ))}
        <button disabled={busy} onClick={reset} className={`${base} hover:border-zinc-400/50 hover:text-zinc-300`}>
          Reset Demo
        </button>
        <button
          disabled={busy}
          onClick={runDemo}
          className="col-span-2 text-[9px] py-2 px-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors cursor-pointer font-semibold disabled:cursor-not-allowed"
        >
          {demoStep === null
            ? "Run Full Demo Sequence"
            : `Demo ${demoStep + 1}/${DEMO_STEPS.length}: ${DEMO_STEPS[demoStep].label}...`}
        </button>
      </div>
    </div>
  );
}
