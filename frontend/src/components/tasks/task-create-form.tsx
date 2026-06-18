"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { UploadIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { createTask } from "@/lib/api";

export function TaskCreateForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const form = event.currentTarget;
    const formData = new FormData(form);
    if (!formData.has("risk_filter_enabled")) {
      formData.append("risk_filter_enabled", "false");
    }
    try {
      const result = await createTask(formData);
      router.push(`/tasks/${result.task_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务创建失败");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Card>
        <CardHeader>
          <CardTitle>上传直播回放</CardTitle>
          <CardDescription>提交后端会自动进入音频提取、ASR、内容分析和 FFmpeg 切片流程。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <Alert tone="destructive">{error}</Alert> : null}
          <div className="grid gap-2">
            <Label htmlFor="file">视频文件</Label>
            <Input id="file" name="file" type="file" accept="video/*" required />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="content_type">内容类型</Label>
            <Select id="content_type" name="content_type" defaultValue="直播回放">
              <option value="直播回放">直播回放</option>
              <option value="知识分享">知识分享</option>
              <option value="电商带货">电商带货</option>
              <option value="访谈对话">访谈对话</option>
              <option value="游戏实况">游戏实况</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>切片参数</CardTitle>
          <CardDescription>控制候选短视频的时长和数量。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="min_clip_duration">最短秒数</Label>
              <Input id="min_clip_duration" name="min_clip_duration" type="number" min={5} defaultValue={30} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="max_clip_duration">最长秒数</Label>
              <Input id="max_clip_duration" name="max_clip_duration" type="number" min={10} defaultValue={180} />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="max_clip_count">最多切片数</Label>
            <Input id="max_clip_count" name="max_clip_count" type="number" min={1} max={50} defaultValue={10} />
          </div>
          <label className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
            <span className="text-sm font-medium">风险过滤</span>
            <input name="risk_filter_enabled" type="checkbox" value="true" defaultChecked className="h-4 w-4 accent-primary" />
          </label>
          <Button className="w-full" disabled={submitting}>
            <UploadIcon data-icon="inline-start" />
            {submitting ? "提交中" : "创建任务"}
          </Button>
        </CardContent>
      </Card>
    </form>
  );
}
