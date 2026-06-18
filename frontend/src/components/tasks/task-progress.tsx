import { Progress } from "@/components/ui/progress";
import { StatusBadge, taskStatusLabel } from "@/components/tasks/status-badge";
import type { Task } from "@/lib/types";

export function TaskProgress({ task }: { task: Task }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{task.current_stage || taskStatusLabel(task.status)}</div>
          <div className="mt-1 text-xs text-muted-foreground">进度 {Math.round(task.progress)}%</div>
        </div>
        <StatusBadge status={task.status} />
      </div>
      <Progress value={task.progress} />
      {task.error_message ? <p className="text-sm text-red-700">{task.error_message}</p> : null}
    </div>
  );
}
