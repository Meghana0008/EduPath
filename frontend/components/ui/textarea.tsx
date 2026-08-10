import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[100px] w-full rounded-xl border border-ocean-200/80 bg-white/80 px-3 py-2 text-sm",
        "placeholder:text-ocean-400 focus:outline-none focus:ring-2 focus:ring-ocean-500/30 focus:border-ocean-400",
        "transition-colors duration-200 resize-y",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";
