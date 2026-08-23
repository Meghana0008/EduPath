"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Mail, RefreshCw } from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import type { Application } from "@/lib/types";
import { PageHeader, LoadingSpinner, EmptyState } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getStatusColor, formatDate, statusLabel } from "@/lib/utils";

export default function ApplicationsPage() {
  const searchParams = useSearchParams();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [emailInfo, setEmailInfo] = useState<Awaited<ReturnType<typeof api.emailStatus>> | null>(null);
  const [proposals, setProposals] = useState<Awaited<ReturnType<typeof api.emailProposals>>>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [autoApply, setAutoApply] = useState(true);
  const [pasteSubject, setPasteSubject] = useState("");
  const [pasteBody, setPasteBody] = useState("");
  const autoSynced = useRef(false);
  const handledOauth = useRef(false);

  const load = async () => {
    try {
      const [apps, status, props] = await Promise.all([
        api.applications(),
        api.emailStatus(),
        api.emailProposals(),
      ]);
      setApplications(apps);
      setEmailInfo(status);
      setProposals(props.filter((p) => p.status !== "dismissed" && p.status !== "applied"));
      setAutoApply(status.auto_apply);
      return status;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      const status = await load();
      if (!status?.connected || autoSynced.current) return;
      autoSynced.current = true;
      try {
        const res = await api.emailSync();
        if (res.message) setMessage(res.message);
        await load();
      } catch {
        /* keep page usable if inbox sync fails */
      }
    })();
  }, []);

  useEffect(() => {
    if (handledOauth.current) return;
    const gmail = searchParams.get("gmail");
    if (!gmail) return;
    handledOauth.current = true;
    const reason = searchParams.get("reason");
    if (gmail === "connected") {
      setMessage(
        searchParams.get("sync") === "error"
          ? `Gmail connected, but first inbox sync had an issue${reason ? `: ${reason}` : "."}`
          : "Gmail connected. Inbox sync started for your tracked applications."
      );
      load();
    } else if (gmail === "error") {
      setMessage(reason || "Gmail connection was cancelled or failed.");
    }
  }, [searchParams]);

  const connectGmail = async () => {
    setBusy("connect");
    setMessage("");
    try {
      if (emailInfo?.connected) {
        // keep auto-apply preference before reconnect flows
        await api.emailGmailPrefs(autoApply);
      }
      const res = await api.emailGmailStart();
      if (!res.authorize_url) throw new Error("No Google login URL returned");
      window.location.href = res.authorize_url;
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not start Gmail connect");
      setBusy(null);
    }
  };

  const sync = async () => {
    setBusy("sync");
    setMessage("");
    try {
      await api.emailGmailPrefs(autoApply);
      const res = await api.emailSync();
      setMessage(
        res.message ||
          `Watched ${res.watched_applications ?? 0} application(s) · matched ${res.matched ?? res.proposals.length} email(s)`
      );
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setBusy(null);
    }
  };

  const ingest = async () => {
    if (!pasteSubject.trim() || !pasteBody.trim()) return;
    setBusy("ingest");
    setMessage("");
    try {
      const res = await api.emailIngest({
        subject: pasteSubject,
        body: pasteBody,
        auto_apply: autoApply,
      });
      if (res.proposal) {
        setMessage(`Matched your application · status: ${String(res.proposal.proposed_status)}.`);
      } else {
        setMessage(res.reason || "No update found for your tracked applications.");
      }
      setPasteSubject("");
      setPasteBody("");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(null);
    }
  };

  const applyProposal = async (id: string) => {
    if (!window.confirm("Apply this email-detected status update to your application?")) return;
    setBusy(id);
    try {
      await api.emailApplyProposal(id, true);
      setMessage("Application status updated from email.");
      await load();
    } catch (err) {
      if (err instanceof ApiClientError) setMessage(err.message);
      else setMessage("Could not apply proposal");
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <LoadingSpinner />;

  const watchedCount = emailInfo?.watched_applications ?? 0;

  return (
    <>
      <PageHeader
        title="Applications"
        subtitle="Start an application, connect Gmail once — the agent tracks only mails for those schemes."
      />

      {message && (
        <p className="mb-4 text-sm bg-ocean-50 text-ocean-800 rounded-lg px-4 py-2">{message}</p>
      )}

      <Card className="mb-8 border-ocean-200 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="w-5 h-5 text-ocean-700" />
            Application email agent
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-ocean-600">
            {emailInfo?.note ||
              "Click Connect Gmail, sign in with Google, and EduPath reads only emails related to schemes you started."}
          </p>
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge variant={emailInfo?.connected ? "success" : "warning"} className="normal-case tracking-normal">
              {emailInfo?.connected ? `Gmail connected: ${emailInfo.email_address}` : "Gmail not connected"}
            </Badge>
            <Badge variant="ocean" className="normal-case tracking-normal">
              Watching {watchedCount} application{watchedCount === 1 ? "" : "s"}
            </Badge>
            {emailInfo?.last_synced_at && (
              <Badge variant="ocean" className="normal-case tracking-normal">
                Last sync: {new Date(emailInfo.last_synced_at).toLocaleString()}
              </Badge>
            )}
            <Badge variant="gold" className="normal-case tracking-normal">
              Pending proposals: {emailInfo?.pending_proposals ?? 0}
            </Badge>
          </div>
          {emailInfo?.watched_titles && emailInfo.watched_titles.length > 0 && (
            <p className="text-xs text-ocean-500">
              Watching: {emailInfo.watched_titles.join(" · ")}
              {(emailInfo.watched_applications || 0) > emailInfo.watched_titles.length ? "…" : ""}
            </p>
          )}
          {watchedCount === 0 && (
            <p className="text-sm text-amber-800 bg-amber-50 rounded-lg px-3 py-2">
              Start at least one application first. The agent ignores inbox mail until you have schemes to watch.
            </p>
          )}

          <label className="flex items-center gap-2 text-sm text-ocean-700">
            <input
              type="checkbox"
              checked={autoApply}
              onChange={(e) => setAutoApply(e.target.checked)}
            />
            Auto-apply status updates from matched emails
          </label>

          <div className="flex flex-wrap gap-2">
            <Button onClick={connectGmail} loading={busy === "connect"}>
              {emailInfo?.connected ? "Reconnect Gmail" : "Connect Gmail"}
            </Button>
            <Button variant="outline" onClick={sync} loading={busy === "sync"} disabled={!emailInfo?.connected}>
              <RefreshCw className="w-4 h-4" />
              Sync inbox now
            </Button>
            <Button
              variant="outline"
              loading={busy === "demo"}
              onClick={async () => {
                setBusy("demo");
                setMessage("");
                try {
                  const res = await api.runFakeScholarshipDemo();
                  setMessage(
                    `${res.message} Final status: ${res.final_status}. Check the bell icon for alerts.`
                  );
                  await load();
                  window.open(res.fake_webpage, "_blank");
                } catch (err) {
                  setMessage(err instanceof Error ? err.message : "Demo failed");
                } finally {
                  setBusy(null);
                }
              }}
            >
              Run fake scholarship alert demo
            </Button>
            {emailInfo?.connected && (
              <Button
                variant="ghost"
                onClick={async () => {
                  await api.emailDisconnect();
                  await load();
                  setMessage("Gmail disconnected.");
                }}
              >
                Disconnect
              </Button>
            )}
          </div>

          {!emailInfo?.gmail_oauth_ready && (
            <p className="text-sm text-amber-900 bg-amber-50 rounded-lg px-3 py-2">
              Server setup needed: add <code className="text-xs">GOOGLE_CLIENT_ID</code> and{" "}
              <code className="text-xs">GOOGLE_CLIENT_SECRET</code> in <code className="text-xs">.env</code>, with
              redirect URI <code className="text-xs">http://localhost:8000/api/email/gmail/callback</code>, then
              restart the API.
            </p>
          )}

          <div className="pt-4 border-t border-ocean-100 space-y-3">
            <h3 className="font-medium text-ocean-900">Optional: paste one email</h3>
            <p className="text-xs text-ocean-500">
              Use this only for a quick test. Normal flow is Connect Gmail → Sync inbox.
            </p>
            <div>
              <Label>Subject</Label>
              <Input value={pasteSubject} onChange={(e) => setPasteSubject(e.target.value)} placeholder="NSP Application Update" />
            </div>
            <div>
              <Label>Body</Label>
              <Textarea
                rows={4}
                value={pasteBody}
                onChange={(e) => setPasteBody(e.target.value)}
                placeholder="Paste the email text about your application status..."
              />
            </div>
            <Button variant="outline" onClick={ingest} loading={busy === "ingest"}>
              Match to my applications
            </Button>
          </div>
        </CardContent>
      </Card>

      {proposals.length > 0 && (
        <div className="mb-8 space-y-3">
          <h2 className="font-display text-xl font-semibold text-ocean-950">Needs confirmation</h2>
          {proposals.map((p) => (
            <Card key={p.notification_id}>
              <CardContent className="pt-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-ocean-900">
                    {p.from_status} → {p.proposed_status}
                  </p>
                  <p className="text-sm text-ocean-600">{p.subject}</p>
                  <p className="text-xs text-ocean-500 mt-1 line-clamp-2">{p.snippet}</p>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => applyProposal(p.notification_id)} loading={busy === p.notification_id}>
                    Confirm
                  </Button>
                  <Button
                    variant="outline"
                    onClick={async () => {
                      await api.emailDismissProposal(p.notification_id);
                      await load();
                    }}
                  >
                    Dismiss
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {applications.length === 0 ? (
        <EmptyState
          title="No applications yet"
          description="Start an application from an opportunity page. Then connect Gmail — the agent watches only those schemes."
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
                      {app.status !== "NOT_STARTED" && (
                        <Badge variant="ocean" className="normal-case tracking-normal">
                          Agent watching
                        </Badge>
                      )}
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
