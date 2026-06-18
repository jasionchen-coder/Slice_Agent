"use client";

import Link from "next/link";
import { ExternalLinkIcon, RefreshCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/tasks/status-badge";
import { TaskProgress } from "@/components/tasks/task-progress";
import type { Task } from "@/lib/types";
import { cn, formatSeconds } from "@/lib/utils";

export function TaskHistoryTable({
  tasks,
  loading,
  onRefresh
}: {
  tasks: Task[];
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="rounded-md border bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h1 className="text-base font-semibold">任务队列</h1>
          <p className="text-sm text-muted-foreground">查看上传、处理进度和历史切片结果。</p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="bg-secondary/60 text-left text-xs text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">视频</th>
              <th className="px-4 py-3 font-medium">状态</th>
              <th className="px-4 py-3 font-medium">进度</th>
              <th className="px-4 py-3 font-medium">参数</th>
              <th className="px-4 py-3 font-medium">创建时间</th>
              <th className="px-4 py-3 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.length === 0 ? (
              <tr>
                <td className="px-4 py-8 text-center text-muted-foreground" colSpan={6}>
                  还没有任务。
                </td>
              </tr>
            ) : (
              tasks.map((task) => (
                <tr key={task.task_id} className="border-t">
                  <td className="max-w-[260px] px-4 py-3">
                    <div className="truncate font-medium">{task.video_name}</div>
                    <div className="text-xs text-muted-foreground">{formatSeconds(task.video_duration)}</div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={task.status} />
                  </td>
                  <td className="w-[230px] px-4 py-3">
                    <TaskProgress task={task} />
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {task.min_clip_duration}-{task.max_clip_duration}s / {task.max_clip_count} 条
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{new Date(task.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={task.status === "completed" ? `/tasks/${task.task_id}/clips` : `/tasks/${task.task_id}`}
                      className={cn(
                        "inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-background px-3 text-sm font-medium hover:bg-secondary",
                        "[&_svg]:h-4 [&_svg]:w-4"
                      )}
                    >
                      <ExternalLinkIcon data-icon="inline-start" />
                      打开
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
