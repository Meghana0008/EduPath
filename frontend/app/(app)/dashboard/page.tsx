"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Bot, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { DashboardStats, Match } from "@/lib/types";
import { PageHeader, StatPill, LoadingSpinner } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { ChatAssistant } from "@/components/chat/chat-assistant";
import { DiscoverProgress } from "@/components/agent/discover-progress";
import type { AgentStep } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [discoverSteps, setDiscoverSteps] = useState<AgentStep[]>([]);
  const [showDiscover, setShowDiscover] = useState(false);

  const load = async () => {
    try {
      const [dash, matchData] = await Promise.all([api.dashboard(), api.matches()]);
      setStats(dash);
      setMatches(matchData.slice(0, 3));
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runDiscover = async (simulateNew = false) => {
    setDiscovering(true);
    setShowDiscover(true);
    setDiscoverSteps([]);
    try {
      const res = await api.discover(simulateNew);
      setDiscoverSteps(res.steps || []);
      await load();
    } catch (err) {
      setDiscoverSteps([
        { name: "Discovery failed", status: "failed", message: err instanceof Error ? err.message : "Error" },
      ]);
    } finally {
      setDiscovering(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <>
      <PageHeader
        title={`Good day, ${stats?.student_name || "Scholar"}`}
        subtitle="EduPath is searching official Indian scholarship portals and ranking matches for you."
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => runDiscover(false)} loading={discovering}>
              <Search className="w-4 h-4" />
              Find India Scholarships
            </Button>
          </div>
        }
      />

      <div className="mb-6">
        <Badge variant="ocean" className="normal-case tracking-normal">
          Focus: {stats?.country_focus || "India"} · Official source links only
        </Badge>
      </div>

      {showDiscover && (
        <div className="mb-8">
          <DiscoverProgress
            steps={discoverSteps}
            active={discovering}
            onClose={() => setShowDiscover(false)}
          />
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-10">
        <div className="col-span-1 p-4 rounded-2xl bg-white/60 border border-ocean-100">
          <StatPill label="Found" value={stats?.opportunities_found ?? 0} accent="ocean" />
        </div>
        <div className="col-span-1 p-4 rounded-2xl bg-white/60 border border-ocean-100">
          <StatPill label="Strong Matches" value={stats?.strong_matches ?? 0} accent="gold" />
        </div>
        <div className="col-span-1 p-4 rounded-2xl bg-white/60 border border-ocean-100">
          <StatPill label="Applications" value={stats?.applications ?? 0} />
        </div>
        <div className="col-span-1 p-4 rounded-2xl bg-white/60 border border-ocean-100">
          <StatPill label="Under Review" value={stats?.under_review ?? 0} />
        </div>
        <div className="col-span-1 p-4 rounded-2xl bg-white/60 border border-ocean-100">
          <StatPill label="Approved" value={stats?.approved ?? 0} accent="emerald" />
        </div>
        <div className="col-span-2 lg:col-span-1 p-4 rounded-2xl bg-gradient-to-br from-ocean-700 to-ocean-800 text-white">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider opacity-80">Agent</span>
          </div>
          <p className="font-display text-lg font-semibold">
            {stats?.agent_active ? "Active" : "Inactive"}
          </p>
          {stats?.last_scan && (
            <p className="text-xs opacity-70 mt-1">Last scan: {formatDateTime(stats.last_scan)}</p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h2 className="font-display text-xl font-semibold text-ocean-950">Top Matches</h2>
        <Link
          href="/opportunities"
          className="text-sm text-ocean-600 hover:text-ocean-800 flex items-center gap-1 transition-colors"
        >
          View all <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      {matches.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ocean-200 p-12 text-center">
          <p className="text-ocean-600 mb-4">No matches yet. Run discovery to find opportunities.</p>
          <Button onClick={() => runDiscover(false)} loading={discovering}>
            <Search className="w-4 h-4" />
            Find Opportunities
          </Button>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {matches.map((m) =>
            m.opportunity ? (
              <OpportunityCard key={m.id} opportunity={m.opportunity} match={m} />
            ) : null
          )}
        </div>
      )}

      <div className="mt-8 flex justify-center">
        <Link href="/agent-activity">
          <Button variant="outline">
            <Bot className="w-4 h-4" />
            View Agent Activity
          </Button>
        </Link>
      </div>

      <ChatAssistant />
    </>
  );
}
