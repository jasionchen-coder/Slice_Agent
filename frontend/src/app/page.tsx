"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PlusIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { TaskHistoryTable } from "@/components/tasks/task-history-table";
import { listTasks } from "@/lib/api";
import type { Task } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function HomePage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await listTasks();
      setTasks(result.tasks);
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务列表加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">直播切片工作台</h1>
          <p className="text-sm text-muted-foreground">上传视频、跟踪处理进度，并进入切片审核。</p>
        </div>
        <Link
          href="/tasks/create"
          className={cn("inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90", "[&_svg]:h-4 [&_svg]:w-4")}
        >
          <PlusIcon data-icon="inline-start" />
          新建任务
        </Link>
      </div>
      {error ? <Alert tone="destructive">{error}</Alert> : null}
      <TaskHistoryTable tasks={tasks} loading={loading} onRefresh={load} />
    </div>
  );
}
