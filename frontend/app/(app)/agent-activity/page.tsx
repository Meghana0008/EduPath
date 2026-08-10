"use client";

import { useEffect, useState } from "react";
import { Bot, RefreshCw, Power } from "lucide-react";
import { api } from "@/lib/api";
import type { AgentRun } from "@/lib/types";
import { PageHeader, LoadingSpinner, EmptyState } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { AgentRunCard } from "@/components/agent/agent-run-card";
import { DiscoverProgress } from "@/components/agent/discover-progress";
import type { AgentStep } from "@/lib/types";

export default function AgentActivityPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [discoverSteps, setDiscoverSteps] = useState<AgentStep[]>([]);
  const [activating, setActivating] = useState(false);

  const load = async () => {
    try {
      const data = await api.agentRuns();
      setRuns(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  const runDiscover = async () => {
    setDiscovering(true);
    setDiscoverSteps([]);
    try {
      const res = await api.discover(false);
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

  const activate = async () => {
    setActivating(true);
    try {
      await api.activateAgent();
    } catch {
      /* ignore */
    } finally {
      setActivating(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  const runningCount = runs.filter((r) => r.status === "running").length;
  const completedCount = runs.filter((r) => r.status === "completed").length;

  return (
    <>
      <PageHeader
        title="Agent Activity"
        subtitle="Monitor AI agent workflows — discovery, ranking, eligibility, and document analysis."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={load}>
              <RefreshCw className="w-4 h-4" />
              Refresh
            </Button>
            <Button variant="outline" onClick={activate} loading={activating}>
              <Power className="w-4 h-4" />
              Activate Agent
            </Button>
            <Button onClick={runDiscover} loading={discovering}>
              <Bot className="w-4 h-4" />
              Run Discovery
            </Button>
          </div>
        }
      />

      <div className="grid sm:grid-cols-3 gap-4 mb-8">
        <div className="p-5 rounded-2xl bg-white/70 border border-ocean-100">
          <p className="text-xs uppercase tracking-wider text-ocean-500 mb-1">Total Runs</p>
          <p className="font-display text-3xl font-semibold text-ocean-900">{runs.length}</p>
        </div>
        <div className="p-5 rounded-2xl bg-ocean-50 border border-ocean-100">
          <p className="text-xs uppercase tracking-wider text-ocean-500 mb-1">Running</p>
          <p className="font-display text-3xl font-semibold text-ocean-700">{runningCount}</p>
        </div>
        <div className="p-5 rounded-2xl bg-emerald-50 border border-emerald-100">
          <p className="text-xs uppercase tracking-wider text-emerald-600 mb-1">Completed</p>
          <p className="font-display text-3xl font-semibold text-emerald-700">{completedCount}</p>
        </div>
      </div>

      {(discovering || discoverSteps.length > 0) && (
        <div className="mb-8">
          <DiscoverProgress steps={discoverSteps} active={discovering} />
        </div>
      )}

      {runs.length === 0 ? (
        <EmptyState
          title="No agent runs yet"
          description="Run discovery to see agent workflows in action."
          action={
            <Button onClick={runDiscover} loading={discovering}>
              <Bot className="w-4 h-4" />
              Run Discovery
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {runs.map((run) => (
            <AgentRunCard key={run.id} run={run} />
          ))}
        </div>
      )}
    </>
  );
}
