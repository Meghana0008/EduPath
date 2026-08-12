"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import type { Match, Opportunity } from "@/lib/types";
import { PageHeader, LoadingSpinner, EmptyState } from "@/components/ui/page-header";
import { Input } from "@/components/ui/input";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [showNotEligible, setShowNotEligible] = useState(false);

  useEffect(() => {
    Promise.all([api.opportunities(), api.matches()])
      .then(([opps, matchData]) => {
        setOpportunities(opps);
        setMatches(matchData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const matchMap = new Map(matches.map((m) => [m.opportunity_id, m]));

  const filtered = opportunities.filter((o) => {
    const m = matchMap.get(o.id);
    if (!showNotEligible && m?.eligibility_status === "NOT_ELIGIBLE") return false;
    if (!query) return true;
    const q = query.toLowerCase();
    return o.title.toLowerCase().includes(q) || o.provider.toLowerCase().includes(q);
  });

  const sorted = [...filtered].sort((a, b) => {
    const ma = matchMap.get(a.id);
    const mb = matchMap.get(b.id);
    const statusRank = (s?: string) =>
      s === "ELIGIBLE" ? 3 : s === "PARTIALLY_ELIGIBLE" ? 2 : s === "UNKNOWN" ? 1 : 0;
    const sr = statusRank(mb?.eligibility_status) - statusRank(ma?.eligibility_status);
    if (sr !== 0) return sr;
    return (mb?.ranking_score ?? 0) - (ma?.ranking_score ?? 0);
  });

  if (loading) return <LoadingSpinner />;

  const eligibleCount = opportunities.filter(
    (o) => matchMap.get(o.id)?.eligibility_status !== "NOT_ELIGIBLE"
  ).length;

  return (
    <>
      <PageHeader
        title="Opportunities"
        subtitle="Live Indian scholarships ranked for YOUR profile — expired schemes and clear mismatches are hidden by default."
      />

      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ocean-400" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search opportunities..."
            className="pl-10"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-ocean-700">
          <input
            type="checkbox"
            checked={showNotEligible}
            onChange={(e) => setShowNotEligible(e.target.checked)}
          />
          Show not-eligible ({opportunities.length - eligibleCount})
        </label>
      </div>
      <p className="text-xs text-ocean-500 mb-6">
        Showing {sorted.length} of {opportunities.length} open schemes · complete profile + correct resume for better matches.
      </p>

      {sorted.length === 0 ? (
        <EmptyState
          title="No matching opportunities"
          description="Update your profile (college, degree, category, state) and re-run discovery. Wrong resumes are rejected automatically."
        />
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {sorted.map((opp) => (
            <OpportunityCard
              key={opp.id}
              opportunity={opp}
              match={matchMap.get(opp.id)}
            />
          ))}
        </div>
      )}
    </>
  );
}
