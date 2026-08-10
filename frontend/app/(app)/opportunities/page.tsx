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

  const filtered = opportunities.filter(
    (o) =>
      !query ||
      o.title.toLowerCase().includes(query.toLowerCase()) ||
      o.provider.toLowerCase().includes(query.toLowerCase())
  );

  const sorted = [...filtered].sort((a, b) => {
    const scoreA = matchMap.get(a.id)?.ranking_score ?? 0;
    const scoreB = matchMap.get(b.id)?.ranking_score ?? 0;
    return scoreB - scoreA;
  });

  if (loading) return <LoadingSpinner />;

  return (
    <>
      <PageHeader
        title="Opportunities"
        subtitle="Scholarships, grants, and fellowships discovered and ranked for your profile."
      />

      <div className="relative mb-8 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ocean-400" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search opportunities..."
          className="pl-10"
        />
      </div>

      {sorted.length === 0 ? (
        <EmptyState
          title="No opportunities found"
          description="Run discovery from the dashboard to find scholarships matched to your profile."
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
