import { Badge } from "@/components/ui/badge";
import type { Clip, TaskStatus } from "@/lib/types";

const statusText: Record<TaskStatus, string> = {
  pending: "排队中",
  uploaded: "已上传",
  extracting_audio: "提取音频",
  transcribing: "ASR 转写",
  cleaning_transcript: "清洗文本",
  analyzing_content: "内容分析",
  generating_clips: "生成方案",
  cutting_video: "视频切片",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消"
};

export function taskStatusLabel(status: TaskStatus | string) {
  return statusText[status as TaskStatus] || status;
}

export function StatusBadge({ status }: { status: TaskStatus | string }) {
  if (status === "completed") return <Badge tone="success">{taskStatusLabel(status)}</Badge>;
  if (status === "failed") return <Badge tone="destructive">{taskStatusLabel(status)}</Badge>;
  if (status === "cancelled") return <Badge tone="outline">{taskStatusLabel(status)}</Badge>;
  if (["pending", "uploaded"].includes(status)) return <Badge tone="secondary">{taskStatusLabel(status)}</Badge>;
  return <Badge tone="warning">{taskStatusLabel(status)}</Badge>;
}

export function ClipRiskBadge({ riskLevel }: { riskLevel: Clip["risk_level"] }) {
  if (!riskLevel) return <Badge tone="secondary">未评估</Badge>;
  if (riskLevel === "low") return <Badge tone="success">低风险</Badge>;
  if (riskLevel === "medium") return <Badge tone="warning">中风险</Badge>;
  if (riskLevel === "high") return <Badge tone="destructive">高风险</Badge>;
  return <Badge tone="outline">{riskLevel}</Badge>;
}
