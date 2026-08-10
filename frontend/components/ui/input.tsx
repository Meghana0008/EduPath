import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-xl border border-ocean-200/80 bg-white/80 px-3 py-2 text-sm",
        "placeholder:text-ocean-400 focus:outline-none focus:ring-2 focus:ring-ocean-500/30 focus:border-ocean-400",
        "transition-colors duration-200",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export const Label = ({
  className,
  children,
  htmlFor,
}: {
  className?: string;
  children: React.ReactNode;
  htmlFor?: string;
}) => (
  <label
    htmlFor={htmlFor}
    className={cn("block text-sm font-medium text-ocean-800 mb-1.5", className)}
  >
    {children}
  </label>
);
