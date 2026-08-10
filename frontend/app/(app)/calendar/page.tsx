"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Calendar as CalendarIcon, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import type { CalendarEvent } from "@/lib/types";
import { PageHeader, LoadingSpinner, EmptyState } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate } from "@/lib/utils";

const EVENT_COLORS: Record<string, string> = {
  deadline: "border-l-red-500 bg-red-50/50",
  opening: "border-l-emerald-500 bg-emerald-50/50",
  interview: "border-l-indigo-500 bg-indigo-50/50",
};

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.calendar().then(setEvents).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const grouped = events.reduce<Record<string, CalendarEvent[]>>((acc, e) => {
    const month = new Date(e.date).toLocaleDateString("en-US", { month: "long", year: "numeric" });
    if (!acc[month]) acc[month] = [];
    acc[month].push(e);
    return acc;
  }, {});

  if (loading) return <LoadingSpinner />;

  return (
    <>
      <PageHeader
        title="Deadline Calendar"
        subtitle="Application deadlines, opening dates, and interview milestones in one view."
      />

      {events.length === 0 ? (
        <EmptyState
          title="No upcoming events"
          description="Run discovery and evaluate opportunities to populate your calendar."
        />
      ) : (
        <div className="space-y-8">
          {Object.entries(grouped).map(([month, monthEvents]) => (
            <div key={month} className="animate-slide-up">
              <h2 className="font-display text-lg font-semibold text-ocean-900 mb-4 flex items-center gap-2">
                <CalendarIcon className="w-5 h-5 text-ocean-600" />
                {month}
              </h2>
              <div className="space-y-3">
                {monthEvents.map((event) => (
                  <div
                    key={event.id}
                    className={cn(
                      "flex items-start gap-4 p-4 rounded-xl border border-ocean-100 border-l-4 bg-white/70",
                      EVENT_COLORS[event.event_type] || "border-l-ocean-400"
                    )}
                  >
                    <div className="shrink-0 text-center min-w-[60px]">
                      <span className="block text-2xl font-display font-bold text-ocean-800">
                        {new Date(event.date).getDate()}
                      </span>
                      <span className="text-xs text-ocean-500 uppercase">
                        {new Date(event.date).toLocaleDateString("en-US", { weekday: "short" })}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <h3 className="font-medium text-ocean-900">{event.title}</h3>
                        <Badge variant={event.priority === "high" ? "warning" : "default"} className="normal-case tracking-normal text-[10px]">
                          {event.event_type}
                        </Badge>
                        {event.priority === "high" && (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                        )}
                      </div>
                      {event.description && (
                        <p className="text-sm text-ocean-600">{event.description}</p>
                      )}
                      {event.opportunity_id && (
                        <Link
                          href={`/opportunities/${event.opportunity_id}`}
                          className="text-xs text-ocean-500 hover:text-ocean-700 mt-1 inline-block"
                        >
                          View opportunity →
                        </Link>
                      )}
                    </div>
                    <span className="text-xs text-ocean-400 shrink-0">{formatDate(event.date)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
