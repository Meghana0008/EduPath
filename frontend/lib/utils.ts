import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(date: string | null | undefined): string {
  if (!date) return "—";
  return new Date(date).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatCurrency(amount: number | null | undefined, currency = "INR"): string {
  if (amount == null) return "—";
  const locale = currency === "INR" ? "en-IN" : "en-US";
  return new Intl.NumberFormat(locale, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

export function getMatchColor(score: number): string {
  if (score >= 85) return "text-emerald-600 bg-emerald-50 border-emerald-200";
  if (score >= 70) return "text-ocean-700 bg-ocean-50 border-ocean-200";
  if (score >= 50) return "text-sand-700 bg-sand-100 border-sand-300";
  return "text-gray-600 bg-gray-50 border-gray-200";
}

export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    DRAFT: "bg-gray-100 text-gray-700",
    SUBMITTED: "bg-ocean-100 text-ocean-800",
    UNDER_REVIEW: "bg-amber-100 text-amber-800",
    DOCUMENT_VERIFICATION: "bg-purple-100 text-purple-800",
    INTERVIEW: "bg-indigo-100 text-indigo-800",
    APPROVED: "bg-emerald-100 text-emerald-800",
    DISBURSED: "bg-emerald-200 text-emerald-900",
    REJECTED: "bg-red-100 text-red-800",
    WITHDRAWN: "bg-gray-100 text-gray-600",
  };
  return map[status] || "bg-gray-100 text-gray-700";
}

export function statusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
