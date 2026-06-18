"use client";

import { useEffect, useState } from "react";
import { RefreshCwIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth } from "@/lib/api";
import { apiBaseUrl } from "@/lib/utils";

export default function SystemPage() {
  const [health, setHealth] = useState<{ status: string; version?: string } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setHealth(await getHealth());
    } catch (err) {
      setError(err instanceof Error ? err.message : "后端连接失败");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">系统状态</h1>
          <p className="text-sm text-muted-foreground">确认前端到后端 API 的连接情况。</p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}>
          <RefreshCwIcon data-icon="inline-start" />
          检查
        </Button>
      </div>
      {error ? <Alert tone="destructive">{error}</Alert> : null}
      <Card>
        <CardHeader>
          <CardTitle>后端 API</CardTitle>
          <CardDescription>{apiBaseUrl()}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-3">
          <div className="rounded-md border px-3 py-2">
            <div className="text-xs text-muted-foreground">连接状态</div>
            <div className="mt-2">
              {health ? <Badge tone="success">{health.status}</Badge> : <Badge tone="destructive">不可用</Badge>}
            </div>
          </div>
          <div className="rounded-md border px-3 py-2">
            <div className="text-xs text-muted-foreground">版本</div>
            <div className="mt-1 font-medium">{health?.version || "未返回"}</div>
          </div>
          <div className="rounded-md border px-3 py-2">
            <div className="text-xs text-muted-foreground">前端配置</div>
            <div className="mt-1 break-all font-medium">NEXT_PUBLIC_API_BASE_URL</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
