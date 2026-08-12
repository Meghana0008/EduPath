"use client";

import Link from "next/link";
import { ExternalLink, Calendar, MapPin, ShieldCheck } from "lucide-react";
import type { Opportunity, Match } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatCurrency, formatDate, getMatchColor } from "@/lib/utils";

export function OpportunityCard({
  opportunity,
  match,
}: {
  opportunity: Opportunity;
  match?: Match;
}) {
  const score = match?.ranking_score;
  const readiness = match?.application_readiness_score;
  const applyUrl = opportunity.application_url || opportunity.official_source_url;

  return (
    <Link href={`/opportunities/${opportunity.id}`}>
      <Card interactive className="h-full group">
        <CardContent className="pt-5">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="min-w-0 flex-1">
              <h3 className="font-display text-lg font-semibold text-ocean-950 group-hover:text-ocean-700 transition-colors line-clamp-2">
                {opportunity.title}
              </h3>
              <p className="text-sm text-ocean-600 mt-1">{opportunity.provider}</p>
            </div>
            {score != null && (
              <div
                className={cn(
                  "shrink-0 px-3 py-1.5 rounded-xl border text-center",
                  getMatchColor(score)
                )}
              >
                <span className="block text-lg font-display font-bold">{Math.round(score)}%</span>
                <span className="text-[9px] uppercase tracking-wider">Match</span>
              </div>
            )}
          </div>

          <p className="text-sm text-ocean-600 line-clamp-2 mb-4">{opportunity.description}</p>

          <div className="flex flex-wrap gap-2 mb-4">
            <Badge variant="ocean">{opportunity.opportunity_type.replace(/_/g, " ")}</Badge>
            {opportunity.source_verified && (
              <Badge variant="success" className="normal-case tracking-normal">
                <ShieldCheck className="w-3 h-3 mr-1" />
                Verified
              </Badge>
            )}
            <Badge variant="gold" className="normal-case tracking-normal">
              {opportunity.location || "India"}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs text-ocean-600 mb-4">
            {opportunity.amount != null ? (
              <div>
                <span className="text-ocean-400 block">Amount</span>
                <span className="font-medium text-ocean-800">
                  {formatCurrency(opportunity.amount, opportunity.currency)}
                </span>
              </div>
            ) : (
              <div>
                <span className="text-ocean-400 block">Funding</span>
                <span className="font-medium text-ocean-800">See official portal</span>
              </div>
            )}
            {readiness != null && (
              <div>
                <span className="text-ocean-400 block">Readiness</span>
                <span className="font-medium text-ocean-800">{Math.round(readiness)}%</span>
              </div>
            )}
            {opportunity.deadline && (
              <div className="flex items-center gap-1">
                <Calendar className="w-3 h-3 text-ocean-400" />
                <span>{formatDate(opportunity.deadline)}</span>
              </div>
            )}
            {opportunity.location && (
              <div className="flex items-center gap-1">
                <MapPin className="w-3 h-3 text-ocean-400" />
                <span className="truncate">{opportunity.location}</span>
              </div>
            )}
          </div>

          <button
            onClick={(e) => {
              e.preventDefault();
              window.open(applyUrl, "_blank", "noopener,noreferrer");
            }}
            className="flex items-center gap-1.5 text-xs font-medium text-gold-600 hover:text-gold-500 transition-colors"
          >
            Apply on official portal
            <ExternalLink className="w-3 h-3" />
          </button>
        </CardContent>
      </Card>
    </Link>
  );
}
