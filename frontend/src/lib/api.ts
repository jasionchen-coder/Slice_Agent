import { apiBaseUrl } from "@/lib/utils";
import type { Clip, Task, TaskLog } from "@/lib/types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store"
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep status text.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function listTasks() {
  return request<{ tasks: Task[] }>("/api/tasks");
}

export function getTask(taskId: string) {
  return request<Task>(`/api/tasks/${taskId}`);
}

export function getTaskClips(taskId: string) {
  return request<{ task_id: string; clips: Clip[] }>(`/api/tasks/${taskId}/clips`);
}

export function getTaskLogs(taskId: string) {
  return request<{ task_id: string; logs: TaskLog[] }>(`/api/tasks/${taskId}/logs`);
}

export function cancelTask(taskId: string) {
  return request<Task>(`/api/tasks/${taskId}/cancel`, { method: "POST" });
}

export function retryTask(taskId: string) {
  return request<Task>(`/api/tasks/${taskId}/retry`, { method: "POST" });
}

export async function createTask(formData: FormData) {
  const response = await fetch(`${apiBaseUrl()}/api/tasks`, {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || response.statusText);
  }
  return response.json() as Promise<{ task_id: string; status: string; message: string }>;
}

export function updateClip(clipId: string, payload: Partial<Pick<Clip, "title" | "summary" | "start_time" | "end_time">>) {
  return request<{ clip_id: string; status?: string; message: string }>(`/api/clips/${clipId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function regenerateClip(clipId: string) {
  return request<{ clip_id: string; status?: string; message: string }>(`/api/clips/${clipId}/regenerate`, {
    method: "POST"
  });
}

export function clipDownloadUrl(clipId: string) {
  return `${apiBaseUrl()}/api/clips/${clipId}/download`;
}

export function getHealth() {
  return request<{ status: string; version?: string }>("/health");
}
