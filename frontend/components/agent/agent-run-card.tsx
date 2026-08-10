"use client";

import { cn, formatDateTime } from "@/lib/utils";
import type { AgentRun } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Bot, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";

function statusBadge(status: string) {
  if (status === "completed") return { variant: "success" as const, icon: CheckCircle2 };
  if (status === "running") return { variant: "ocean" as const, icon: Loader2 };
  if (status === "failed") return { variant: "warning" as const, icon: XCircle };
  return { variant: "default" as const, icon: Clock };
}

export function AgentRunCard({ run }: { run: AgentRun }) {
  const { variant, icon: Icon } = statusBadge(run.status);

  return (
    <Card className="animate-slide-up">
      <CardContent className="pt-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-ocean-100 flex items-center justify-center">
              <Bot className="w-5 h-5 text-ocean-700" />
            </div>
            <div>
              <h3 className="font-medium text-ocean-900">{run.agent_name}</h3>
              <p className="text-xs text-ocean-500">{run.run_type.replace(/_/g, " ")}</p>
            </div>
          </div>
          <Badge variant={variant} className="normal-case tracking-normal flex items-center gap-1">
            <Icon className={cn("w-3 h-3", run.status === "running" && "animate-spin")} />
            {run.status}
          </Badge>
        </div>

        {run.input_summary && (
          <p className="text-xs text-ocean-500 mb-1">
            <span className="font-medium">Input:</span> {run.input_summary}
          </p>
        )}
        {run.output_summary && (
          <p className="text-sm text-ocean-700 mb-3">{run.output_summary}</p>
        )}

        <div className="flex items-center gap-4 text-xs text-ocean-400 mb-3">
          <span>Started {formatDateTime(run.started_at)}</span>
          {run.completed_at && <span>Completed {formatDateTime(run.completed_at)}</span>}
        </div>

        {run.steps?.length > 0 && (
          <div className="border-t border-ocean-100 pt-3 space-y-2">
            {run.steps.map((step, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-xs p-2 rounded-lg bg-ocean-50/50"
              >
                <span className="text-ocean-400 font-mono shrink-0">{i + 1}.</span>
                <div>
                  <span className="font-medium text-ocean-800">
                    {step.name || step.agent || "Step"}
                  </span>
                  {(step.message || step.output) && (
                    <p className="text-ocean-600 mt-0.5">{step.message || step.output}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
