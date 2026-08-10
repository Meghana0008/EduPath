"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import type { Application } from "@/lib/types";
import { PageHeader, LoadingSpinner } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApplicationTimeline, StatusProgressBar } from "@/components/applications/application-timeline";
import { getStatusColor, statusLabel, formatDateTime } from "@/lib/utils";

const STATUS_OPTIONS = [
  "DRAFT",
  "SUBMITTED",
  "UNDER_REVIEW",
  "DOCUMENT_VERIFICATION",
  "INTERVIEW",
  "APPROVED",
  "REJECTED",
  "WITHDRAWN",
];

export default function ApplicationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [application, setApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState("");
  const [updating, setUpdating] = useState(false);
  const [message, setMessage] = useState("");

  const load = async () => {
    try {
      const app = await api.application(id);
      setApplication(app);
      setNotes(app.notes || "");
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const updateStatus = async (status: string) => {
    setUpdating(true);
    setMessage("");
    try {
      const updated = await api.updateApplication(id, { status, confirm: true });
      setApplication(updated);
      setMessage(`Status updated to ${statusLabel(status)}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Update failed");
    } finally {
      setUpdating(false);
    }
  };

  const saveNotes = async () => {
    setUpdating(true);
    try {
      const updated = await api.updateApplication(id, { notes });
      setApplication(updated);
      setMessage("Notes saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed");
    } finally {
      setUpdating(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!application) return <p className="text-ocean-600">Application not found.</p>;

  return (
    <>
      <Link href="/applications" className="inline-flex items-center gap-1 text-sm text-ocean-600 hover:text-ocean-800 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to applications
      </Link>

      <PageHeader
        title={application.opportunity?.title || "Application"}
        subtitle={application.opportunity?.provider}
      />

      {message && (
        <p className="mb-4 text-sm bg-ocean-50 text-ocean-800 rounded-lg px-4 py-2">{message}</p>
      )}

      <div className="mb-6">
        <Badge className={`normal-case tracking-normal text-sm px-3 py-1 ${getStatusColor(application.status)}`}>
          {statusLabel(application.status)}
        </Badge>
      </div>

      <div className="mb-8 overflow-x-auto">
        <StatusProgressBar currentStatus={application.status} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ApplicationTimeline timeline={application.timeline} />
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Update Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {STATUS_OPTIONS.filter((s) => s !== application.status).map((status) => (
                  <Button
                    key={status}
                    variant="outline"
                    size="sm"
                    onClick={() => updateStatus(status)}
                    disabled={updating}
                  >
                    {statusLabel(status)}
                  </Button>
                ))}
              </div>
              {application.last_status_update && (
                <p className="text-xs text-ocean-500 mt-3">
                  Last updated: {formatDateTime(application.last_status_update)}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add notes about this application..."
                rows={4}
              />
              <Button className="mt-3" onClick={saveNotes} loading={updating} size="sm">
                Save Notes
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
