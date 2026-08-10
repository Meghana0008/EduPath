import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "demo" | "success" | "warning" | "ocean" | "gold";

const variants: Record<BadgeVariant, string> = {
  default: "bg-ocean-50 text-ocean-700 border-ocean-200",
  demo: "bg-gold-400/20 text-gold-600 border-gold-400/40 animate-pulse-soft",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  ocean: "bg-ocean-100 text-ocean-800 border-ocean-200",
  gold: "bg-sand-100 text-sand-800 border-sand-300",
};

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-wide uppercase",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
