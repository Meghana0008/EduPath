"use client";

import { useState } from "react";
import { GraduationCap, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

export default function LoginPage() {
  const { login, register, loading } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(name, email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
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
            Create your profile, upload documents, and let EduPath search official portals like NSP, UGC, AICTE, INSPIRE, and more — with real application links.
          </p>
          <div className="mt-12 flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-gold-400" />
            <span className="text-ocean-200 text-sm">Agentic matching · Official sources only</span>
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
              {mode === "login" ? "Welcome back" : "Get started"}
            </h2>
            <p className="text-sm text-ocean-600 mb-6">
              {mode === "login"
                ? "Sign in to continue tracking Indian scholarships"
                : "Create an account — next we will ask for your profile and documents"}
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === "register" && (
                <div>
                  <Label htmlFor="name">Full name</Label>
                  <Input
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    placeholder="Your full name"
                  />
                </div>
              )}
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
              <div>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="At least 6 characters"
                />
              </div>

              {error && (
                <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
              )}

              <Button type="submit" className="w-full" loading={submitting}>
                {mode === "login" ? "Sign in" : "Create account & continue"}
              </Button>
            </form>

            <div className="mt-6 pt-6 border-t border-ocean-100">
              <button
                type="button"
                onClick={() => {
                  setMode(mode === "login" ? "register" : "login");
                  setError("");
                }}
                className="w-full text-sm text-ocean-700 font-medium"
              >
                {mode === "login" ? "Need an account? Register" : "Already have an account? Sign in"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
