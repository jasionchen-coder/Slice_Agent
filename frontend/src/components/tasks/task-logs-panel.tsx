"use client";

import { useEffect, useState } from "react";
import { RefreshCwIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getTaskLogs } from "@/lib/api";
import type { TaskLog } from "@/lib/types";

export function TaskLogsPanel({ taskId }: { taskId: string }) {
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await getTaskLogs(taskId);
      setLogs(result.logs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "日志加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [taskId]);

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>处理日志</CardTitle>
          <CardDescription>ASR、LLM、FFmpeg 的阶段日志和重试信息。</CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </CardHeader>
      <CardContent>
        {error ? <Alert tone="destructive" className="mb-3">{error}</Alert> : null}
        <div className="max-h-[360px] overflow-auto rounded-md border">
          {logs.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-muted-foreground">暂无日志。</div>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="grid gap-1 border-b px-3 py-2 text-sm last:border-b-0 md:grid-cols-[150px_110px_minmax(0,1fr)]">
                <div className="text-xs text-muted-foreground">{new Date(log.created_at).toLocaleString()}</div>
                <div className="font-medium">
                  {log.stage}
                  {log.attempt ? <span className="ml-1 text-xs text-muted-foreground">#{log.attempt}</span> : null}
                </div>
                <div className={log.level === "error" ? "text-red-700" : "text-muted-foreground"}>
                  {log.message}
                  {log.error_message ? <span className="ml-2 text-red-700">{log.error_message}</span> : null}
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
