"use client";

import Link from "next/link";

export default function FakeScholarshipPage() {
  return (
    <div className="min-h-screen bg-[#f4f7fb] text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-700 font-semibold">EduPath Demo Foundation</p>
            <h1 className="font-serif text-2xl mt-1">Ocean AI Research Fellowship</h1>
          </div>
          <span className="rounded-full bg-amber-100 text-amber-800 text-xs font-semibold px-3 py-1">
            FAKE DEMO PAGE
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10 grid lg:grid-cols-[1.4fr_0.8fr] gap-8">
        <section className="space-y-6">
          <div className="rounded-3xl overflow-hidden bg-gradient-to-br from-cyan-800 via-slate-800 to-indigo-900 text-white p-8 min-h-[240px] flex flex-col justify-end">
            <p className="text-cyan-100 text-sm mb-2">Academic Year 2026–27</p>
            <h2 className="text-4xl font-serif leading-tight">Fund your AI research journey</h2>
            <p className="mt-3 text-cyan-50/90 max-w-xl">
              A simulated fellowship webpage used to demonstrate EduPath application tracking,
              email follow-ups, and alerts. Not a real scholarship.
            </p>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            <h3 className="text-xl font-semibold">Overview</h3>
            <p className="text-slate-600 leading-relaxed">
              Selected scholars receive mentorship, research stipend support, and progress reviews.
              In this demo, EduPath watches emails from this “provider” and updates your application
              status automatically.
            </p>
            <ul className="grid sm:grid-cols-2 gap-3 text-sm">
              <li className="rounded-xl bg-slate-50 p-3"><strong>Amount:</strong> ₹2,50,000</li>
              <li className="rounded-xl bg-slate-50 p-3"><strong>Deadline:</strong> ~45 days from today</li>
              <li className="rounded-xl bg-slate-50 p-3"><strong>Level:</strong> Master&apos;s / Research</li>
              <li className="rounded-xl bg-slate-50 p-3"><strong>Field:</strong> AI / Data Science</li>
            </ul>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-3">
            <h3 className="text-xl font-semibold">Eligibility</h3>
            <ul className="list-disc pl-5 text-slate-600 space-y-1">
              <li>Master&apos;s or research student in AI / Data Science / CS</li>
              <li>GPA / CGPA at least 7.0</li>
              <li>Based in India</li>
            </ul>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-3">
            <h3 className="text-xl font-semibold">What happens after you apply (demo)</h3>
            <ol className="list-decimal pl-5 text-slate-600 space-y-2">
              <li>You start the application in EduPath</li>
              <li>Provider emails: received → under review</li>
              <li>Provider asks for additional documents → alert</li>
              <li>Interview invite email → status + notification</li>
            </ol>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm sticky top-6">
            <h3 className="font-semibold text-lg">Apply / Track with EduPath</h3>
            <p className="text-sm text-slate-600 mt-2 mb-4">
              Open EduPath, run the fake scholarship demo, then watch Applications + the bell icon.
            </p>
            <Link
              href="/applications"
              className="block text-center rounded-xl bg-cyan-700 hover:bg-cyan-800 text-white font-medium px-4 py-3 transition"
            >
              Open EduPath Applications
            </Link>
            <Link
              href="/opportunities/demo-local-ocean-fellowship"
              className="mt-3 block text-center rounded-xl border border-slate-300 hover:bg-slate-50 text-slate-800 font-medium px-4 py-3 transition"
            >
              View in Opportunities
            </Link>
            <p className="text-[11px] text-slate-500 mt-4">
              This page is local-only demo content for showcasing alerts. It does not submit to any real foundation.
            </p>
          </div>
        </aside>
      </main>
    </div>
  );
}
