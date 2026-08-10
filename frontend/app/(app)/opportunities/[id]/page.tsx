"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ExternalLink, ArrowLeft, Sparkles, FileCheck, Plus } from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import type { Opportunity, Match, AnalysisResult } from "@/lib/types";
import { PageHeader, LoadingSpinner } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/input";
import { AnalysisPanel } from "@/components/documents/analysis-panel";
import { ChatAssistant } from "@/components/chat/chat-assistant";
import { formatCurrency, formatDate, getMatchColor } from "@/lib/utils";

export default function OpportunityDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [resumeResult, setResumeResult] = useState<AnalysisResult | null>(null);
  const [sopResult, setSopResult] = useState<AnalysisResult | null>(null);
  const [sopText, setSopText] = useState("");
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [opp, matches] = await Promise.all([
          api.opportunity(id),
          api.matches(),
        ]);
        setOpportunity(opp);
        setMatch(matches.find((m) => m.opportunity_id === id) || null);
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const evaluate = async () => {
    setEvaluating(true);
    try {
      const result = await api.evaluateOpportunity(id);
      setMatch(result);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setEvaluating(false);
    }
  };

  const startApplication = async (confirm = false) => {
    setApplying(true);
    setMessage("");
    try {
      const app = await api.createApplication(id, confirm);
      setMessage(`Application created: ${app.status}`);
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 400) {
        const detail = err.data as { detail?: { confirmation_prompt?: string } };
        const prompt = detail?.detail?.confirmation_prompt;
        if (prompt && confirm === false) {
          if (window.confirm(prompt)) {
            await startApplication(true);
            return;
          }
        }
      }
      setMessage(err instanceof Error ? err.message : "Application failed");
    } finally {
      setApplying(false);
    }
  };

  const analyzeResume = async () => {
    setAnalyzing("resume");
    try {
      const result = await api.analyzeResume({ opportunity_id: id });
      setResumeResult(result);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Resume analysis failed");
    } finally {
      setAnalyzing(null);
    }
  };

  const analyzeSop = async () => {
    if (!sopText.trim()) return;
    setAnalyzing("sop");
    try {
      const result = await api.analyzeSop({
        opportunity_id: id,
        sop_text: sopText,
        generate_improved_draft: true,
      });
      setSopResult(result);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "SOP analysis failed");
    } finally {
      setAnalyzing(null);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!opportunity) return <p className="text-ocean-600">Opportunity not found.</p>;

  const applyUrl = opportunity.application_url || opportunity.official_source_url;

  return (
    <>
      <Link href="/opportunities" className="inline-flex items-center gap-1 text-sm text-ocean-600 hover:text-ocean-800 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to opportunities
      </Link>

      <PageHeader
        title={opportunity.title}
        subtitle={opportunity.provider}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={evaluate} loading={evaluating}>
              <Sparkles className="w-4 h-4" />
              Evaluate Match
            </Button>
            <Button onClick={() => startApplication(false)} loading={applying}>
              <Plus className="w-4 h-4" />
              Start Application
            </Button>
          </div>
        }
      />

      {message && (
        <p className="mb-4 text-sm bg-ocean-50 text-ocean-800 rounded-lg px-4 py-2">{message}</p>
      )}

      <div className="grid lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardContent className="pt-5">
              <p className="text-ocean-700 leading-relaxed">{opportunity.description}</p>
              {opportunity.eligibility_text && (
                <div className="mt-4 pt-4 border-t border-ocean-100">
                  <h4 className="text-sm font-medium text-ocean-800 mb-2">Eligibility</h4>
                  <p className="text-sm text-ocean-600">{opportunity.eligibility_text}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {match && (
            <Card>
              <CardHeader>
                <CardTitle>Match Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid sm:grid-cols-3 gap-4 mb-4">
                  <div className={`p-4 rounded-xl border text-center ${getMatchColor(match.ranking_score)}`}>
                    <span className="font-display text-2xl font-bold">{Math.round(match.ranking_score)}%</span>
                    <span className="block text-xs uppercase mt-1">Overall Match</span>
                  </div>
                  <div className="p-4 rounded-xl border border-ocean-100 bg-ocean-50 text-center">
                    <span className="font-display text-2xl font-bold text-ocean-800">{Math.round(match.eligibility_score)}%</span>
                    <span className="block text-xs uppercase mt-1 text-ocean-500">Eligibility</span>
                  </div>
                  <div className="p-4 rounded-xl border border-sand-200 bg-sand-50 text-center">
                    <span className="font-display text-2xl font-bold text-sand-800">{Math.round(match.application_readiness_score)}%</span>
                    <span className="block text-xs uppercase mt-1 text-sand-600">Readiness</span>
                  </div>
                </div>
                <p className="text-sm text-ocean-700 mb-3">{match.reasoning}</p>
                {match.missing_requirements?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-amber-700 mb-1">Missing Requirements</h4>
                    <ul className="text-sm text-ocean-600 space-y-1">
                      {match.missing_requirements.map((r, i) => (
                        <li key={i}>• {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Document Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button variant="outline" onClick={analyzeResume} loading={analyzing === "resume"}>
                <FileCheck className="w-4 h-4" />
                Analyze Resume
              </Button>
              <div>
                <Label>Statement of Purpose</Label>
                <Textarea
                  value={sopText}
                  onChange={(e) => setSopText(e.target.value)}
                  placeholder="Paste your SOP here for AI analysis..."
                  rows={5}
                />
                <Button
                  className="mt-2"
                  variant="outline"
                  onClick={analyzeSop}
                  loading={analyzing === "sop"}
                  disabled={!sopText.trim()}
                >
                  Analyze SOP
                </Button>
              </div>
            </CardContent>
          </Card>

          {resumeResult && <AnalysisPanel result={resumeResult} title="Resume Analysis" />}
          {sopResult && <AnalysisPanel result={sopResult} title="SOP Analysis" />}
        </div>

        <div className="space-y-4">
          <Card>
            <CardContent className="pt-5 space-y-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="ocean">{opportunity.opportunity_type.replace(/_/g, " ")}</Badge>
                {opportunity.source_verified && <Badge variant="success">Verified Source</Badge>}
              </div>
              {opportunity.amount != null && (
                <div>
                  <span className="text-xs text-ocean-500">Amount</span>
                  <p className="font-display text-xl font-semibold text-ocean-900">
                    {formatCurrency(opportunity.amount, opportunity.currency)}
                  </p>
                </div>
              )}
              {opportunity.deadline && (
                <div>
                  <span className="text-xs text-ocean-500">Deadline</span>
                  <p className="font-medium text-ocean-800">{formatDate(opportunity.deadline)}</p>
                </div>
              )}
              {opportunity.location && (
                <div>
                  <span className="text-xs text-ocean-500">Location</span>
                  <p className="font-medium text-ocean-800">{opportunity.location}</p>
                </div>
              )}
              {opportunity.required_documents?.length > 0 && (
                <div>
                  <span className="text-xs text-ocean-500">Required Documents</span>
                  <ul className="text-sm text-ocean-700 mt-1 space-y-0.5">
                    {opportunity.required_documents.map((d, i) => (
                      <li key={i}>• {typeof d === "string" ? d : JSON.stringify(d)}</li>
                    ))}
                  </ul>
                </div>
              )}
              <a
                href={applyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-gold-500 hover:bg-gold-600 text-white font-medium text-sm transition-colors"
              >
                Official Apply Link
                <ExternalLink className="w-4 h-4" />
              </a>
            </CardContent>
          </Card>
        </div>
      </div>

      <ChatAssistant opportunityId={id} />
    </>
  );
}
