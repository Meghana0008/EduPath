"use client";

import { useEffect, useState, useRef } from "react";
import { Upload, Trash2, FileText, Sparkles } from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import type { Document, Opportunity, AnalysisResult } from "@/lib/types";
import { PageHeader, LoadingSpinner, EmptyState } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { AnalysisPanel } from "@/components/documents/analysis-panel";
import { formatDateTime } from "@/lib/utils";

const DOC_TYPES = [
  "aadhaar",
  "resume",
  "transcript",
  "income_certificate",
  "bank_passbook",
  "passport_photo",
  "caste_certificate",
  "community_certificate",
  "disability_certificate",
  "passport",
  "id",
  "gate_scorecard",
  "recommendation_letter",
  "statement_of_purpose",
  "bonafide_certificate",
  "research_proposal",
  "other",
];

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [docType, setDocType] = useState("resume");
  const [selectedOpp, setSelectedOpp] = useState("");
  const [sopText, setSopText] = useState("");
  const [resumeResult, setResumeResult] = useState<AnalysisResult | null>(null);
  const [sopResult, setSopResult] = useState<AnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      const [docs, opps] = await Promise.all([api.documents(), api.opportunities()]);
      setDocuments(docs);
      setOpportunities(opps);
      if (opps.length && !selectedOpp) setSelectedOpp(opps[0].id);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const upload = async (file: File) => {
    setUploading(true);
    setMessage("");
    try {
      await api.uploadDocument(docType, file);
      await load();
      setMessage("Document uploaded successfully");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Delete this document from your vault?")) return;
    try {
      await api.deleteDocument(id, true);
      await load();
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 400) {
        setMessage("Confirmation required to delete");
      } else {
        setMessage(err instanceof Error ? err.message : "Delete failed");
      }
    }
  };

  const analyzeResume = async (documentId?: string) => {
    if (!selectedOpp) return;
    setAnalyzing("resume");
    try {
      const result = await api.analyzeResume({
        opportunity_id: selectedOpp,
        document_id: documentId,
      });
      setResumeResult(result);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(null);
    }
  };

  const analyzeSop = async () => {
    if (!selectedOpp || !sopText.trim()) return;
    setAnalyzing("sop");
    try {
      const result = await api.analyzeSop({
        opportunity_id: selectedOpp,
        sop_text: sopText,
        generate_improved_draft: true,
      });
      setSopResult(result);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(null);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <>
      <PageHeader
        title="Document Vault"
        subtitle="Every upload is checked against your profile — name, college, degree, category, and state must match yours."
        action={
          <Button onClick={() => fileRef.current?.click()} loading={uploading}>
            <Upload className="w-4 h-4" />
            Upload Document
          </Button>
        }
      />

      <input
        ref={fileRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.txt,.md"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload(file);
          e.target.value = "";
        }}
      />

      {message && (
        <p className="mb-4 text-sm bg-ocean-50 text-ocean-800 rounded-lg px-4 py-2">{message}</p>
      )}

      <p className="mb-4 text-sm text-ocean-700/80">
        Upload only your own files. Aadhaar, caste/income certificates, transcripts, resumes, and bank
        documents that belong to someone else are rejected.
      </p>

      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div>
          <Label>Document Type</Label>
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="h-10 rounded-xl border border-ocean-200 bg-white/80 px-3 text-sm"
          >
            {DOC_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {documents.length === 0 ? (
        <EmptyState
          title="No documents uploaded"
          description="Upload your own resume, transcripts, and certificates — they must match your profile fields."
          action={
            <Button onClick={() => fileRef.current?.click()}>
              <Upload className="w-4 h-4" />
              Upload First Document
            </Button>
          }
        />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
          {documents.map((doc) => (
            <Card key={doc.id}>
              <CardContent className="pt-5">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-ocean-100 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-ocean-700" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ocean-900 truncate">{doc.file_name}</p>
                    <Badge variant="ocean" className="normal-case tracking-normal mt-1">
                      {doc.document_type.replace(/_/g, " ")}
                    </Badge>
                    <p className="text-xs text-ocean-500 mt-2">{formatDateTime(doc.uploaded_at)}</p>
                  </div>
                  <button
                    onClick={() => remove(doc.id)}
                    className="p-1.5 text-ocean-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {doc.document_type === "resume" && selectedOpp && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 w-full"
                    onClick={() => analyzeResume(doc.id)}
                    loading={analyzing === "resume"}
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Analyze for Opportunity
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>AI Document Analyzer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Target Opportunity</Label>
            <select
              value={selectedOpp}
              onChange={(e) => setSelectedOpp(e.target.value)}
              className="w-full h-10 rounded-xl border border-ocean-200 bg-white/80 px-3 text-sm"
            >
              {opportunities.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title}
                </option>
              ))}
            </select>
          </div>
          <Button variant="outline" onClick={() => analyzeResume()} loading={analyzing === "resume"}>
            <Sparkles className="w-4 h-4" />
            Analyze Resume
          </Button>
          <div>
            <Label>Statement of Purpose</Label>
            <Textarea
              value={sopText}
              onChange={(e) => setSopText(e.target.value)}
              placeholder="Paste your SOP for AI analysis..."
              rows={6}
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
    </>
  );
}
