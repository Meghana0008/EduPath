"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, FileUp, UserRound, ExternalLink } from "lucide-react";

type Action = { type: string; title: string; detail: string; href?: string };
type BucketItem = {
  opportunity_id?: string;
  title?: string;
  ranking_score?: number;
  application_url?: string;
  missing_documents?: string[];
  eligibility_status?: string;
};

export function NextActionsPanel({
  tip,
  actions,
  buckets,
}: {
  tip?: string;
  actions: Action[];
  buckets?: {
    apply_now?: BucketItem[];
    need_documents?: BucketItem[];
    not_eligible?: BucketItem[];
  };
}) {
  const iconFor = (type: string) => {
    if (type === "upload" || type === "prepare") return <FileUp className="w-4 h-4" />;
    if (type === "profile" || type === "apply_suggestions") return <UserRound className="w-4 h-4" />;
    if (type === "apply") return <ExternalLink className="w-4 h-4" />;
    return <CheckCircle2 className="w-4 h-4" />;
  };

  return (
    <div className="space-y-6 mb-10">
      {tip && (
        <p className="text-sm text-ocean-700 bg-ocean-50 border border-ocean-100 rounded-xl px-4 py-3">
          {tip}
        </p>
      )}

      {actions.length > 0 && (
        <div>
          <h2 className="font-display text-xl font-semibold text-ocean-950 mb-3">What to do next</h2>
          <div className="grid md:grid-cols-2 gap-3">
            {actions.map((a, i) => (
              <Link
                key={i}
                href={a.href || "/dashboard"}
                className="rounded-2xl border border-ocean-100 bg-white/80 p-4 hover:border-ocean-300 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 text-ocean-700">{iconFor(a.type)}</div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ocean-950">{a.title}</p>
                    <p className="text-xs text-ocean-600 mt-1">{a.detail}</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-ocean-400 shrink-0" />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        <Bucket
          title="Ready to apply"
          subtitle="Eligible + docs mostly ready"
          items={buckets?.apply_now || []}
          tone="emerald"
        />
        <Bucket
          title="Need documents"
          subtitle="Good match — finish vault first"
          items={buckets?.need_documents || []}
          tone="gold"
        />
        <Bucket
          title="Not eligible"
          subtitle="Usually category/income/degree"
          items={buckets?.not_eligible || []}
          tone="ocean"
        />
      </div>
    </div>
  );
}

function Bucket({
  title,
  subtitle,
  items,
  tone,
}: {
  title: string;
  subtitle: string;
  items: BucketItem[];
  tone: "emerald" | "gold" | "ocean";
}) {
  const border =
    tone === "emerald"
      ? "border-emerald-200 bg-emerald-50/50"
      : tone === "gold"
        ? "border-gold-400/30 bg-sand-50"
        : "border-ocean-100 bg-white/70";

  return (
    <div className={`rounded-2xl border p-4 ${border}`}>
      <h3 className="font-display font-semibold text-ocean-950">{title}</h3>
      <p className="text-xs text-ocean-600 mb-3">{subtitle}</p>
      {items.length === 0 ? (
        <p className="text-xs text-ocean-500">None right now</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 4).map((item, idx) => (
            <li key={idx}>
              <Link
                href={`/opportunities/${item.opportunity_id}`}
                className="text-sm text-ocean-800 hover:text-ocean-600 font-medium line-clamp-2"
              >
                {item.title}
              </Link>
              {item.missing_documents && item.missing_documents.length > 0 && (
                <p className="text-[11px] text-ocean-500 mt-0.5">
                  Missing: {item.missing_documents.slice(0, 3).join(", ")}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
