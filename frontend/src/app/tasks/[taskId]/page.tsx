"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { BanIcon, ClapperboardIcon, RefreshCwIcon, RotateCwIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/tasks/status-badge";
import { TaskLogsPanel } from "@/components/tasks/task-logs-panel";
import { TaskProgress } from "@/components/tasks/task-progress";
import { cancelTask, getTask, retryTask } from "@/lib/api";
import type { Task } from "@/lib/types";
import { cn, formatSeconds } from "@/lib/utils";

const terminalStatuses = new Set(["completed", "failed", "cancelled"]);

export default function TaskDetailPage() {
  const params = useParams<{ taskId: string }>();
  const taskId = params.taskId;
  const [task, setTask] = useState<Task | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setTask(await getTask(taskId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(() => {
      if (!task || !terminalStatuses.has(task.status)) load();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [taskId, task?.status]);

  async function runAction(action: "cancel" | "retry") {
    setActing(true);
    setError("");
    try {
      const next = action === "cancel" ? await cancelTask(taskId) : await retryTask(taskId);
      setTask(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setActing(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold">{task?.video_name || "任务详情"}</h1>
          <p className="text-sm text-muted-foreground">{taskId}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCwIcon data-icon="inline-start" />
            刷新
          </Button>
          <Button variant="outline" onClick={() => runAction("retry")} disabled={acting}>
            <RotateCwIcon data-icon="inline-start" />
            重试
          </Button>
          <Button variant="destructive" onClick={() => runAction("cancel")} disabled={acting || task?.status === "completed"}>
            <BanIcon data-icon="inline-start" />
            取消
          </Button>
        </div>
      </div>
      {error ? <Alert tone="destructive">{error}</Alert> : null}
      {task ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Card>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div>
                <CardTitle>处理进度</CardTitle>
                <CardDescription>自动轮询后端任务状态。</CardDescription>
              </div>
              <StatusBadge status={task.status} />
            </CardHeader>
            <CardContent className="space-y-5">
              <TaskProgress task={task} />
              <div className="grid gap-3 text-sm md:grid-cols-3">
                <Info label="时长" value={formatSeconds(task.video_duration)} />
                <Info label="内容类型" value={task.content_type || "未设置"} />
                <Info label="切片约束" value={`${task.min_clip_duration}-${task.max_clip_duration}s / ${task.max_clip_count} 条`} />
              </div>
              <div className="flex justify-end">
                <Link
                  href={`/tasks/${task.task_id}/clips`}
                  className={cn(
                    "inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90",
                    task.status !== "completed" && "pointer-events-none opacity-50",
                    "[&_svg]:h-4 [&_svg]:w-4"
                  )}
                >
                  <ClapperboardIcon data-icon="inline-start" />
                  查看切片
                </Link>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>任务参数</CardTitle>
              <CardDescription>当前任务的生成约束。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <Info label="文件格式" value={task.video_format || "待解析"} />
              <Info label="分辨率" value={task.video_resolution || "待解析"} />
              <Info label="风险过滤" value={task.risk_filter_enabled ? "开启" : "关闭"} />
              <Info label="更新时间" value={new Date(task.updated_at).toLocaleString()} />
            </CardContent>
          </Card>
        </div>
      ) : null}
      <TaskLogsPanel taskId={taskId} />
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 break-words font-medium">{value}</div>
    </div>
  );
}
