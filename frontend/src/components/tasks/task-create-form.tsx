"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { MusicIcon, UploadIcon } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { createAudioTask } from "@/lib/api";
import { AUDIO_CHUNK_SECONDS, extractMp3Chunks, getVideoDuration } from "@/lib/browser-ffmpeg";
import { formatSeconds } from "@/lib/utils";

export function TaskCreateForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    setProgress(0);
    setSubmitting(true);
    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file");
    const selectedFile = fileInput instanceof HTMLInputElement ? fileInput.files?.[0] : null;
    if (!selectedFile) {
      setError("请选择视频文件");
      setSubmitting(false);
      return;
    }

    try {
      setStatus("正在读取视频信息");
      setProgress(10);
      const duration = await getVideoDuration(selectedFile);
      if (duration <= 0) {
        throw new Error("无法读取视频时长");
      }

      setStatus(duration > AUDIO_CHUNK_SECONDS ? "视频超过 30 分钟，将分段提取 MP3" : "正在提取 MP3");
      setProgress(20);
      const chunks = await extractMp3Chunks(selectedFile, duration, (message) => setStatus(message));

      const audioForm = new FormData();
      audioForm.append("original_video_name", selectedFile.name);
      audioForm.append("video_duration", String(duration));
      audioForm.append("content_type", String(new FormData(form).get("content_type") || "直播回放"));
      audioForm.append("min_clip_duration", String(new FormData(form).get("min_clip_duration") || 30));
      audioForm.append("max_clip_duration", String(new FormData(form).get("max_clip_duration") || 180));
      audioForm.append("max_clip_count", String(new FormData(form).get("max_clip_count") || 10));
      audioForm.append("risk_filter_enabled", new FormData(form).has("risk_filter_enabled") ? "true" : "false");
      audioForm.append(
        "audio_manifest",
        JSON.stringify(
          chunks.map((chunk) => ({
            chunk_index: chunk.chunkIndex,
            start_time: chunk.startTime,
            end_time: chunk.endTime
          }))
        )
      );
      for (const chunk of chunks) {
        audioForm.append("audio_files", chunk.file);
      }

      setStatus(`正在上传 ${chunks.length} 个 MP3 音频文件`);
      setProgress(80);
      const result = await createAudioTask(audioForm);
      setStatus(`音频已上传，原视频时长 ${formatSeconds(duration)}`);
      setProgress(100);
      router.push(`/tasks/${result.task_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务创建失败");
      setStatus("");
      setProgress(0);
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Card>
        <CardHeader>
          <CardTitle>上传直播回放</CardTitle>
          <CardDescription>视频保留在浏览器本地，前端提取 MP3 后上传给后端分析。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <Alert tone="destructive">{error}</Alert> : null}
          {status ? (
            <Alert>
              <div className="flex items-center gap-2">
                <MusicIcon className="h-4 w-4" />
                <span>{status}</span>
              </div>
              <Progress value={progress} className="mt-2" />
            </Alert>
          ) : null}
          <div className="grid gap-2">
            <Label htmlFor="file">视频文件</Label>
            <Input id="file" name="file" type="file" accept="video/*" required />
            <p className="text-xs text-muted-foreground">原视频不会上传到后端；超过 30 分钟会按 30 分钟提取多个 MP3 分片。</p>
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
            {submitting ? "处理中" : "提取 MP3 并创建任务"}
          </Button>
        </CardContent>
      </Card>
    </form>
  );
}
