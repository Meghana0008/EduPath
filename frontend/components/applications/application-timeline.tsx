"use client";

import type { TimelineEntry } from "@/lib/types";
import { cn, formatDateTime, getStatusColor, statusLabel } from "@/lib/utils";
import { CheckCircle2, Circle } from "lucide-react";

const STATUS_ORDER = [
  "NOT_STARTED",
  "DRAFT",
  "SUBMITTED",
  "UNDER_REVIEW",
  "DOCUMENT_VERIFICATION",
  "INTERVIEW",
  "APPROVED",
  "DISBURSED",
  "REJECTED",
  "WITHDRAWN",
];

export function ApplicationTimeline({ timeline }: { timeline: TimelineEntry[] }) {
  if (!timeline?.length) {
    return (
      <p className="text-sm text-ocean-500 py-4">No timeline events yet.</p>
    );
  }

  const sorted = [...timeline].sort(
    (a, b) => new Date(a.at).getTime() - new Date(b.at).getTime()
  );

  return (
    <div className="relative pl-6">
      <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-gradient-to-b from-ocean-300 via-ocean-200 to-sand-200" />
      <div className="space-y-6">
        {sorted.map((entry, i) => {
          const isLast = i === sorted.length - 1;
          return (
            <div key={i} className="relative animate-slide-up" style={{ animationDelay: `${i * 60}ms` }}>
              <div
                className={cn(
                  "absolute -left-6 top-0.5 w-6 h-6 rounded-full flex items-center justify-center",
                  isLast ? "bg-ocean-700" : "bg-white border-2 border-ocean-300"
                )}
              >
                {isLast ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                ) : (
                  <Circle className="w-2 h-2 text-ocean-400 fill-ocean-400" />
                )}
              </div>
              <div className="pb-1">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span
                    className={cn(
                      "text-xs font-medium px-2 py-0.5 rounded-full",
                      getStatusColor(entry.status)
                    )}
                  >
                    {statusLabel(entry.status)}
                  </span>
                  <span className="text-xs text-ocean-400">{formatDateTime(entry.at)}</span>
                </div>
                {entry.note && (
                  <p className="text-sm text-ocean-700">{entry.note}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function StatusProgressBar({ currentStatus }: { currentStatus: string }) {
  const currentIdx = STATUS_ORDER.indexOf(currentStatus);
  const progressSteps = STATUS_ORDER.filter((s) => !["REJECTED", "WITHDRAWN", "NOT_STARTED"].includes(s));

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-2">
      {progressSteps.map((status, i) => {
        const idx = STATUS_ORDER.indexOf(status);
        const done = currentIdx >= idx;
        const active = currentStatus === status;
        return (
          <div key={status} className="flex items-center shrink-0">
            <div
              className={cn(
                "px-2 py-1 rounded-lg text-[10px] font-medium uppercase tracking-wide whitespace-nowrap transition-all duration-300",
                done ? "bg-ocean-100 text-ocean-800" : "bg-gray-50 text-gray-400",
                active && "ring-2 ring-ocean-500 ring-offset-1"
              )}
            >
              {status.replace(/_/g, " ")}
            </div>
            {i < progressSteps.length - 1 && (
              <div
                className={cn(
                  "w-4 h-0.5 mx-0.5",
                  done ? "bg-ocean-400" : "bg-gray-200"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
