"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeftIcon } from "lucide-react";
import { ClipWorkspace } from "@/components/tasks/clip-workspace";
import { cn } from "@/lib/utils";

export default function TaskClipsPage() {
  const params = useParams<{ taskId: string }>();
  const taskId = params.taskId;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">切片审核</h1>
          <p className="text-sm text-muted-foreground">{taskId}</p>
        </div>
        <Link
          href={`/tasks/${taskId}`}
          className={cn("inline-flex h-9 items-center gap-2 rounded-md border bg-background px-3 text-sm font-medium hover:bg-secondary", "[&_svg]:h-4 [&_svg]:w-4")}
        >
          <ArrowLeftIcon data-icon="inline-start" />
          返回任务
        </Link>
      </div>
      <ClipWorkspace taskId={taskId} />
    </div>
  );
}
