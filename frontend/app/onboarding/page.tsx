"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, FileUp, UserRound, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const DOC_TYPES = [
  { value: "aadhaar", label: "Aadhaar" },
  { value: "resume", label: "Resume / CV" },
  { value: "transcript", label: "Marksheet / Transcript" },
  { value: "income_certificate", label: "Income Certificate" },
  { value: "bank_passbook", label: "Bank Passbook" },
  { value: "passport_photo", label: "Passport Photo" },
  { value: "caste_certificate", label: "Caste / Community Certificate" },
  { value: "statement_of_purpose", label: "Statement of Purpose" },
  { value: "other", label: "Other" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading, refreshOnboarding } = useAuth();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [docsCount, setDocsCount] = useState(0);
  const [docType, setDocType] = useState("aadhaar");
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({
    degree: "",
    field_of_study: "",
    education_level: "bachelors",
    institution: "",
    gpa: "",
    country: "India",
    state: "",
    city: "",
    category: "",
    gender: "",
    skills: "",
    interests: "",
    career_goals: "",
    family_income: "",
  });

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    api.documents().then((d) => setDocsCount(d.length)).catch(() => undefined);
    api.getProfile().then((p) => {
      setForm((prev) => ({
        ...prev,
        degree: p.degree || "",
        field_of_study: p.field_of_study || "",
        education_level: p.education_level || "bachelors",
        institution: p.institution || "",
        gpa: p.gpa != null ? String(p.gpa) : "",
        country: p.country || "India",
        state: p.state || "",
        city: p.city || "",
        category: p.category || "",
        gender: String((p.additional_profile_data as { gender?: string } | undefined)?.gender || ""),
        skills: (p.skills || []).join(", "),
        interests: (p.interests || []).join(", "),
        career_goals: (p.career_goals || []).join(", "),
      }));
    }).catch(() => undefined);
  }, []);

  const saveProfile = async () => {
    setError("");
    setBusy(true);
    try {
      await api.updateProfile({
        degree: form.degree,
        field_of_study: form.field_of_study,
        education_level: form.education_level,
        institution: form.institution,
        gpa: form.gpa ? Number(form.gpa) : undefined,
        country: form.country || "India",
        state: form.state,
        city: form.city,
        category: form.category || undefined,
        family_income: form.family_income ? Number(form.family_income) : undefined,
        skills: form.skills.split(",").map((s) => s.trim()).filter(Boolean),
        interests: form.interests.split(",").map((s) => s.trim()).filter(Boolean),
        career_goals: form.career_goals.split(",").map((s) => s.trim()).filter(Boolean),
        additional_profile_data: form.gender ? { gender: form.gender } : {},
        agent_active: true,
      } as never);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile");
    } finally {
      setBusy(false);
    }
  };

  const uploadDoc = async () => {
    if (!file) {
      setError("Choose a file to upload");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await api.uploadDocument(docType, file);
      const docs = await api.documents();
      setDocsCount(docs.length);
      setFile(null);
      if (docType === "resume") {
        setError("");
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Upload failed — every document must match your profile (name, college, category, state)."
      );
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    setError("");
    setBusy(true);
    try {
      await api.completeOnboarding();
      await refreshOnboarding();
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finish onboarding");
    } finally {
      setBusy(false);
    }
  };

  if (loading || !user) return null;

  return (
    <div className="min-h-screen bg-ocean-gradient bg-grid-pattern bg-grid px-4 py-10">
      <div className="max-w-2xl mx-auto animate-slide-up">
        <div className="mb-8">
          <Badge variant="gold" className="normal-case tracking-normal mb-3">
            India Scholarship Setup
          </Badge>
          <h1 className="font-display text-3xl font-semibold text-ocean-950">
            Welcome, {user.name.split(" ")[0]}
          </h1>
          <p className="text-ocean-600 mt-2">
            Complete these steps so EduPath can search official Indian scholarship portals for you.
          </p>
        </div>

        <div className="flex gap-2 mb-8">
          {[
            { n: 1, label: "Profile", icon: UserRound },
            { n: 2, label: "Documents", icon: FileUp },
            { n: 3, label: "Find scholarships", icon: Search },
          ].map(({ n, label, icon: Icon }) => (
            <div
              key={n}
              className={`flex-1 rounded-xl border px-3 py-3 text-sm ${
                step === n
                  ? "border-ocean-600 bg-white shadow-sm"
                  : step > n
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-ocean-100 bg-white/50"
              }`}
            >
              <div className="flex items-center gap-2 font-medium text-ocean-900">
                {step > n ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <Icon className="w-4 h-4" />}
                {label}
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-2xl border border-ocean-100 bg-white/90 backdrop-blur p-6 shadow-xl shadow-ocean-900/5">
          {step === 1 && (
            <div className="space-y-4">
              <h2 className="font-display text-xl font-semibold text-ocean-950">Your academic profile</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <Label>Degree</Label>
                  <Input value={form.degree} onChange={(e) => setForm({ ...form, degree: e.target.value })} placeholder="B.Tech / M.Sc / etc." required />
                </div>
                <div>
                  <Label>Education level</Label>
                  <select
                    className="w-full rounded-xl border border-ocean-200 px-3 py-2 text-sm"
                    value={form.education_level}
                    onChange={(e) => setForm({ ...form, education_level: e.target.value })}
                  >
                    <option value="school">School</option>
                    <option value="diploma">Diploma</option>
                    <option value="bachelors">Bachelor&apos;s</option>
                    <option value="masters">Master&apos;s</option>
                    <option value="phd">PhD</option>
                  </select>
                </div>
                <div>
                  <Label>Field of study</Label>
                  <Input value={form.field_of_study} onChange={(e) => setForm({ ...form, field_of_study: e.target.value })} placeholder="Computer Science" />
                </div>
                <div>
                  <Label>Institution</Label>
                  <Input value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} placeholder="College / University" />
                </div>
                <div>
                  <Label>GPA / Percentage</Label>
                  <Input value={form.gpa} onChange={(e) => setForm({ ...form, gpa: e.target.value })} placeholder="8.2 or 82" />
                </div>
                <div>
                  <Label>Category (optional)</Label>
                  <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="General / OBC / SC / ST / EWS" />
                </div>
                <div>
                  <Label>Gender (for schemes like Pragati)</Label>
                  <select
                    className="w-full rounded-xl border border-ocean-200 bg-white px-3 py-2 text-sm"
                    value={form.gender}
                    onChange={(e) => setForm({ ...form, gender: e.target.value })}
                  >
                    <option value="">Select</option>
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <Label>Country</Label>
                  <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
                </div>
                <div>
                  <Label>State (important for state scholarships)</Label>
                  <Input value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} placeholder="Gujarat" />
                </div>
                <div>
                  <Label>City</Label>
                  <Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
                </div>
                <div>
                  <Label>Family income (INR / year, optional)</Label>
                  <Input value={form.family_income} onChange={(e) => setForm({ ...form, family_income: e.target.value })} placeholder="500000" />
                </div>
              </div>
              <div>
                <Label>Skills (comma separated)</Label>
                <Input value={form.skills} onChange={(e) => setForm({ ...form, skills: e.target.value })} placeholder="Python, SQL, ML" />
              </div>
              <div>
                <Label>Interests</Label>
                <Input value={form.interests} onChange={(e) => setForm({ ...form, interests: e.target.value })} placeholder="AI, Research" />
              </div>
              <div>
                <Label>Career goals</Label>
                <Input value={form.career_goals} onChange={(e) => setForm({ ...form, career_goals: e.target.value })} placeholder="AI Researcher" />
              </div>
              <Button onClick={saveProfile} loading={busy} className="w-full">
                Save profile & continue
              </Button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h2 className="font-display text-xl font-semibold text-ocean-950">Upload your documents</h2>
              <p className="text-sm text-ocean-600">
                Indian schemes usually need Aadhaar, marksheets, income certificate, and bank details.
                Upload what you have now — you can add more later.
              </p>
              <p className="text-sm font-medium text-ocean-800">Documents uploaded: {docsCount}</p>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <Label>Document type</Label>
                  <select
                    className="w-full rounded-xl border border-ocean-200 px-3 py-2 text-sm"
                    value={docType}
                    onChange={(e) => setDocType(e.target.value)}
                  >
                    {DOC_TYPES.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label>File (PDF / DOCX / TXT)</Label>
                  <Input type="file" accept=".pdf,.docx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={uploadDoc} loading={busy} variant="outline">Upload document</Button>
                <Button onClick={() => setStep(3)} disabled={docsCount < 1}>
                  Continue
                </Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h2 className="font-display text-xl font-semibold text-ocean-950">Find scholarships for you</h2>
              <p className="text-sm text-ocean-600">
                EduPath will scan trusted Indian sources (NSP, UGC, AICTE, INSPIRE, PMRF, foundations)
                and rank schemes against your profile. Every card links to the official apply page.
              </p>
              <Button onClick={finish} loading={busy} className="w-full">
                Start discovery & go to dashboard
              </Button>
            </div>
          )}

          {error && <p className="mt-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
        </div>
      </div>
    </div>
  );
}
