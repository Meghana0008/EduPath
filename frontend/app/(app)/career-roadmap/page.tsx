"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Map, Compass } from "lucide-react";
import { api } from "@/lib/api";
import type { CareerRoadmap } from "@/lib/types";
import { PageHeader, LoadingSpinner } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function CareerRoadmapPage() {
  const [roadmap, setRoadmap] = useState<CareerRoadmap | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.careerRoadmap().then(setRoadmap).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (!roadmap) return <p className="text-ocean-600">Unable to generate roadmap. Complete your profile first.</p>;

  return (
    <>
      <PageHeader
        title="Career Roadmap"
        subtitle="AI-generated path aligned with your goals and available opportunities."
      />

      <Card className="mb-8 bg-gradient-to-br from-ocean-700 to-ocean-800 text-white border-0">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
              <Map className="w-6 h-6" />
            </div>
            <div>
              <h2 className="font-display text-2xl font-semibold mb-2">{roadmap.career_goal}</h2>
              <p className="text-ocean-100 leading-relaxed">{roadmap.summary}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="relative">
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gradient-to-b from-ocean-400 via-gold-400 to-sand-300 hidden sm:block" />

        <div className="space-y-8">
          {roadmap.years.map((year, i) => (
            <div key={i} className="relative sm:pl-16 animate-slide-up" style={{ animationDelay: `${i * 100}ms` }}>
              <div className="hidden sm:flex absolute left-4 top-6 w-5 h-5 rounded-full bg-ocean-700 border-4 border-sand-50 items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-gold-400" />
              </div>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <Badge variant="gold" className="normal-case tracking-normal">
                      Year {year.year}
                    </Badge>
                    <CardTitle>{year.title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid sm:grid-cols-2 gap-6">
                    <div>
                      <h4 className="text-sm font-medium text-ocean-800 mb-2">Milestones</h4>
                      <ul className="space-y-2">
                        {(year.milestones || []).map((m, j) => (
                          <li key={j} className="text-sm text-ocean-700 flex gap-2">
                            <span className="text-gold-500 shrink-0">◆</span>
                            {m}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-ocean-800 mb-2">Skills to Develop</h4>
                      <div className="flex flex-wrap gap-2">
                        {(year.skills_to_develop || []).map((s, j) => (
                          <Badge key={j} variant="ocean" className="normal-case tracking-normal">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          ))}
        </div>
      </div>

      {roadmap.linked_opportunity_ids?.length > 0 && (
        <div className="mt-10">
          <h3 className="font-display text-lg font-semibold text-ocean-900 mb-4 flex items-center gap-2">
            <Compass className="w-5 h-5" />
            Linked Opportunities
          </h3>
          <div className="flex flex-wrap gap-2">
            {roadmap.linked_opportunity_ids.map((id) => (
              <Link key={id} href={`/opportunities/${id}`}>
                <Badge variant="default" className="normal-case tracking-normal cursor-pointer hover:bg-ocean-50">
                  {id}
                </Badge>
              </Link>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
