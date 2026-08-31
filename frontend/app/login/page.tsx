"use client";

import { useState } from "react";
import { GraduationCap, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

export default function LoginPage() {
  const { requestCode, verifyCode, loading } = useAuth();
  const [step, setStep] = useState<"email" | "code">("email");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const sendCode = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setError("");
    setInfo("");
    setDevCode(null);
    setSubmitting(true);
    try {
      const res = await requestCode(email.trim(), name.trim() || undefined);
      if (res.needs_name) {
        setError("New account — please enter your full name, then continue.");
        return;
      }
      if (!res.ok) {
        setError(res.message || "Could not send confirmation code");
        return;
      }
      setInfo(res.message || "We emailed you a code. Enter it below.");
      // Only show on-screen code in true offline demo (never when email was sent)
      if (res.dev_code && res.email_sent === false) setDevCode(res.dev_code);
      else setDevCode(null);
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send code");
    } finally {
      setSubmitting(false);
    }
  };

  const confirmCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await verifyCode(email.trim(), code.trim(), name.trim() || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid confirmation code");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return null;

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-ocean-800 via-ocean-700 to-ocean-900">
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 80%, rgba(196,146,46,0.3) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.1) 0%, transparent 40%)",
          }}
        />
        <div className="relative z-10 flex flex-col justify-center px-16">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center mb-8">
            <GraduationCap className="w-8 h-8 text-white" />
          </div>
          <h1 className="font-display text-5xl font-semibold text-white leading-tight mb-6">
            India scholarships, discovered for you
          </h1>
          <p className="text-ocean-200 text-lg max-w-md leading-relaxed">
            Automatic email login for every student: we send a code, you enter it, you&apos;re in. No password.
          </p>
          <div className="mt-12 flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-gold-400" />
            <span className="text-ocean-200 text-sm">Email code login · Official sources only</span>
          </div>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-ocean-gradient bg-grid-pattern bg-grid">
        <div className="w-full max-w-md animate-slide-up">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-ocean-700 flex items-center justify-center">
              <GraduationCap className="w-5 h-5 text-white" />
            </div>
            <span className="font-display text-2xl font-semibold text-ocean-950">EduPath AI</span>
          </div>

          <div className="rounded-2xl border border-ocean-100 bg-white/80 backdrop-blur-sm p-8 shadow-xl shadow-ocean-900/5">
            <h2 className="font-display text-2xl font-semibold text-ocean-950 mb-1">
              {step === "email" ? "Sign in or create account" : "Enter your code"}
            </h2>
            <p className="text-sm text-ocean-600 mb-6">
              {step === "email"
                ? "1) Enter email → 2) We send a code automatically → 3) Enter code to log in."
                : `Code sent to ${email}. Enter it to finish login.`}
            </p>

            {step === "email" ? (
              <form onSubmit={sendCode} className="space-y-4">
                <div>
                  <Label htmlFor="name">Full name</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    placeholder="Your full name"
                  />
                  <p className="mt-1 text-xs text-ocean-500">Needed for first-time signup; returning users can use the same name.</p>
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="you@email.com"
                  />
                </div>

                {info && (
                  <p className="text-sm text-ocean-700 bg-ocean-50 rounded-lg px-3 py-2">{info}</p>
                )}
                {error && (
                  <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
                )}

                <Button type="submit" className="w-full" loading={submitting}>
                  Continue — send my code
                </Button>
              </form>
            ) : (
              <form onSubmit={confirmCode} className="space-y-4">
                <div>
                  <Label htmlFor="code">Confirmation code</Label>
                  <Input
                    id="code"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    required
                    placeholder="6-digit code"
                    autoFocus
                    className="tracking-[0.3em] text-center text-lg font-semibold"
                  />
                </div>

                {devCode && (
                  <p className="text-sm text-amber-900 bg-amber-50 rounded-lg px-3 py-2">
                    Offline demo only (email not configured): your code is <strong>{devCode}</strong>
                  </p>
                )}
                {info && !devCode && (
                  <p className="text-sm text-ocean-700 bg-ocean-50 rounded-lg px-3 py-2">{info}</p>
                )}
                {!devCode && (
                  <p className="text-xs text-ocean-500">
                    Open the email we just sent, copy the 6-digit code, and enter it here. Check spam if you do not see it.
                  </p>
                )}
                {error && (
                  <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
                )}

                <Button type="submit" className="w-full" loading={submitting}>
                  Verify & log in
                </Button>
                <button
                  type="button"
                  className="w-full text-sm text-ocean-700 font-medium"
                  onClick={() => {
                    setStep("email");
                    setCode("");
                    setError("");
                    setDevCode(null);
                  }}
                >
                  Use a different email
                </button>
                <button
                  type="button"
                  className="w-full text-sm text-ocean-500"
                  disabled={submitting}
                  onClick={() => sendCode()}
                >
                  Resend code
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
