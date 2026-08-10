import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  subtitle,
  action,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8", className)}>
      <div className="animate-slide-up">
        <h1 className="font-display text-3xl sm:text-4xl font-semibold text-ocean-950 tracking-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-2 text-ocean-600 text-sm sm:text-base max-w-2xl">{subtitle}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function StatPill({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: "ocean" | "gold" | "emerald";
}) {
  const accents = {
    ocean: "from-ocean-600 to-ocean-700",
    gold: "from-gold-500 to-sand-600",
    emerald: "from-emerald-500 to-emerald-600",
  };
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wider text-ocean-500 font-medium">{label}</span>
      <span
        className={cn(
          "font-display text-2xl sm:text-3xl font-semibold bg-gradient-to-r bg-clip-text text-transparent",
          accents[accent || "ocean"]
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center animate-fade-in">
      <div className="w-16 h-16 rounded-2xl bg-ocean-50 border border-ocean-100 flex items-center justify-center mb-4">
        <div className="w-8 h-8 rounded-full bg-ocean-200/50" />
      </div>
      <h3 className="font-display text-xl text-ocean-900 mb-2">{title}</h3>
      <p className="text-ocean-600 text-sm max-w-md mb-6">{description}</p>
      {action}
    </div>
  );
}

export function LoadingSpinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center justify-center py-20", className)}>
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-ocean-300 border-t-ocean-700" />
    </div>
  );
}
