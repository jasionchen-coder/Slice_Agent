import * as React from "react";
import { cn } from "@/lib/utils";

type BadgeTone = "default" | "secondary" | "success" | "warning" | "destructive" | "outline";

const toneClasses: Record<BadgeTone, string> = {
  default: "bg-primary text-primary-foreground",
  secondary: "bg-secondary text-secondary-foreground",
  success: "bg-emerald-100 text-emerald-800",
  warning: "bg-amber-100 text-amber-900",
  destructive: "bg-red-100 text-red-800",
  outline: "border bg-background text-foreground"
};

export function Badge({
  className,
  tone = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 shrink-0 items-center rounded-md border border-transparent px-2 text-xs font-medium",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
