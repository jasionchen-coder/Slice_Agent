"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { DownloadIcon, RefreshCwIcon, RotateCcwIcon, SaveIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ClipRiskBadge } from "@/components/tasks/status-badge";
import { clipDownloadUrl, getTaskClips, regenerateClip, updateClip } from "@/lib/api";
import type { Clip } from "@/lib/types";
import { absoluteMediaUrl, cn, formatSeconds } from "@/lib/utils";

type Draft = Pick<Clip, "title" | "summary" | "start_time" | "end_time">;

export function ClipWorkspace({ taskId }: { taskId: string }) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [activeId, setActiveId] = useState("");
  const [draft, setDraft] = useState<Draft>({ title: "", summary: "", start_time: 0, end_time: 0 });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const activeClip = useMemo(() => clips.find((clip) => clip.clip_id === activeId) || clips[0], [clips, activeId]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await getTaskClips(taskId);
      setClips(result.clips);
      if (!activeId && result.clips[0]) setActiveId(result.clips[0].clip_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "切片加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [taskId]);

  useEffect(() => {
    if (!activeClip) return;
    setDraft({
      title: activeClip.title || "",
      summary: activeClip.summary || "",
      start_time: activeClip.start_time,
      end_time: activeClip.end_time
    });
    setMessage("");
    setError("");
  }, [activeClip?.clip_id]);

  async function save() {
    if (!activeClip) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await updateClip(activeClip.clip_id, draft);
      setMessage("切片信息已保存。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function regenerate() {
    if (!activeClip) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await regenerateClip(activeClip.clip_id);
      setMessage("已提交重新切片任务。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "重新生成失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
      <Card>
        <CardHeader className="flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>候选切片</CardTitle>
            <CardDescription>按分数、风险和状态快速筛选。</CardDescription>
          </div>
          <Button variant="outline" size="icon" onClick={load} disabled={loading} aria-label="刷新切片">
            <RefreshCwIcon />
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {clips.length === 0 ? (
            <div className="rounded-md border px-3 py-8 text-center text-sm text-muted-foreground">暂无切片结果。</div>
          ) : (
            clips.map((clip, index) => (
              <button
                key={clip.clip_id}
                className={`w-full rounded-md border px-3 py-3 text-left transition-colors hover:bg-secondary ${
                  activeClip?.clip_id === clip.clip_id ? "border-primary bg-secondary" : "bg-background"
                }`}
                onClick={() => setActiveId(clip.clip_id)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-medium">{clip.title || `切片 ${index + 1}`}</span>
                  {clip.score !== null && clip.score !== undefined ? <Badge tone="outline">{clip.score.toFixed(1)}</Badge> : null}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatSeconds(clip.start_time)}-{formatSeconds(clip.end_time)}</span>
                  <ClipRiskBadge riskLevel={clip.risk_level} />
                  {clip.status ? <Badge tone="secondary">{clip.status}</Badge> : null}
                </div>
              </button>
            ))
          )}
        </CardContent>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>预览与审核</CardTitle>
            <CardDescription>确认成片效果后可编辑元信息、下载或重新生成。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error ? <Alert tone="destructive">{error}</Alert> : null}
            {message ? <Alert>{message}</Alert> : null}
            {activeClip?.clip_url ? (
              <video className="aspect-video w-full rounded-md" src={absoluteMediaUrl(activeClip.clip_url)} controls />
            ) : (
              <div className="flex aspect-video items-center justify-center rounded-md border bg-secondary text-sm text-muted-foreground">
                当前切片还没有可预览的视频文件。
              </div>
            )}
            {activeClip ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="grid gap-2 md:col-span-2">
                  <Label htmlFor="title">标题</Label>
                  <Input id="title" value={draft.title || ""} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="start_time">开始秒数</Label>
                  <Input
                    id="start_time"
                    type="number"
                    value={draft.start_time}
                    onChange={(event) => setDraft({ ...draft, start_time: Number(event.target.value) })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="end_time">结束秒数</Label>
                  <Input
                    id="end_time"
                    type="number"
                    value={draft.end_time}
                    onChange={(event) => setDraft({ ...draft, end_time: Number(event.target.value) })}
                  />
                </div>
                <div className="grid gap-2 md:col-span-2">
                  <Label htmlFor="summary">摘要</Label>
                  <Textarea id="summary" value={draft.summary || ""} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} />
                </div>
              </div>
            ) : null}
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" onClick={regenerate} disabled={!activeClip || saving}>
                <RotateCcwIcon data-icon="inline-start" />
                重新生成
              </Button>
              {activeClip ? (
                <Link
                  href={clipDownloadUrl(activeClip.clip_id)}
                  className={cn(
                    "inline-flex h-10 items-center justify-center gap-2 rounded-md border bg-background px-4 py-2 text-sm font-medium hover:bg-secondary",
                    saving && "pointer-events-none opacity-50",
                    "[&_svg]:h-4 [&_svg]:w-4"
                  )}
                >
                  <DownloadIcon data-icon="inline-start" />
                  下载
                </Link>
              ) : null}
              <Button onClick={save} disabled={!activeClip || saving}>
                <SaveIcon data-icon="inline-start" />
                保存
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
