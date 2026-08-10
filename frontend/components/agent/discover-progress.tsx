"use client";

import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import type { AgentStep } from "@/lib/types";
import { cn } from "@/lib/utils";

export function DiscoverProgress({
  steps,
  active,
  onClose,
}: {
  steps: AgentStep[];
  active: boolean;
  onClose?: () => void;
}) {
  if (!active && steps.length === 0) return null;

  const statusIcon = (status?: string) => {
    if (status === "completed") return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    if (status === "running") return <Loader2 className="w-4 h-4 text-ocean-500 animate-spin" />;
    if (status === "failed") return <AlertCircle className="w-4 h-4 text-red-500" />;
    return <Circle className="w-4 h-4 text-ocean-300" />;
  };

  return (
    <div className="rounded-2xl border border-ocean-200 bg-white/90 backdrop-blur-sm p-5 animate-slide-up">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display font-semibold text-ocean-900">
          {active ? "Discovering Opportunities..." : "Discovery Complete"}
        </h3>
        {!active && onClose && (
          <button onClick={onClose} className="text-xs text-ocean-500 hover:text-ocean-700">
            Dismiss
          </button>
        )}
      </div>

      {active && (
        <div className="h-1.5 rounded-full bg-ocean-100 mb-5 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-ocean-500 to-gold-400 animate-shimmer"
            style={{
              width: "60%",
              backgroundSize: "200% 100%",
            }}
          />
        </div>
      )}

      <div className="space-y-3">
        {steps.map((step, i) => (
          <div
            key={i}
            className={cn(
              "flex items-start gap-3 p-3 rounded-xl transition-all duration-300",
              step.status === "running" && "bg-ocean-50 border border-ocean-100",
              step.status === "completed" && "opacity-80"
            )}
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <div className="mt-0.5">{statusIcon(step.status)}</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-ocean-900">
                {step.message || step.name || step.agent || step.output || `Step ${i + 1}`}
              </p>
              {step.name && step.message && step.name !== step.message && (
                <p className="text-xs text-ocean-600 mt-0.5 line-clamp-2">{step.name}</p>
              )}
              {step.duration_ms != null && step.status === "completed" && (
                <p className="text-[10px] text-ocean-400 mt-1">{step.duration_ms}ms</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
