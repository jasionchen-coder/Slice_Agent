import * as React from "react";
import { cn } from "@/lib/utils";

export function Alert({
  className,
  tone = "default",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { tone?: "default" | "destructive" }) {
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-sm",
        tone === "destructive" ? "border-red-200 bg-red-50 text-red-800" : "bg-card",
        className
      )}
      {...props}
    />
  );
}
