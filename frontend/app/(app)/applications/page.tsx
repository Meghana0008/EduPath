"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { Application } from "@/lib/types";
import { PageHeader, LoadingSpinner, EmptyState } from "@/components/ui/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getStatusColor, formatDate, statusLabel } from "@/lib/utils";

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.applications().then(setApplications).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <>
      <PageHeader
        title="Applications"
        subtitle="Track your scholarship and grant applications from draft to decision."
      />

      {applications.length === 0 ? (
        <EmptyState
          title="No applications yet"
          description="Start an application from any opportunity detail page."
        />
      ) : (
        <div className="space-y-4">
          {applications.map((app) => (
            <Link key={app.id} href={`/applications/${app.id}`}>
              <Card interactive>
                <CardContent className="pt-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <h3 className="font-display text-lg font-semibold text-ocean-950">
                        {app.opportunity?.title || "Application"}
                      </h3>
                      <p className="text-sm text-ocean-600">{app.opportunity?.provider}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge className={`normal-case tracking-normal ${getStatusColor(app.status)}`}>
                        {statusLabel(app.status)}
                      </Badge>
                      {app.opportunity?.deadline && (
                        <span className="text-xs text-ocean-500">
                          Due {formatDate(app.opportunity.deadline)}
                        </span>
                      )}
                      <ArrowRight className="w-4 h-4 text-ocean-400" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
