export type TaskStatus =
  | "pending"
  | "uploaded"
  | "extracting_audio"
  | "transcribing"
  | "cleaning_transcript"
  | "analyzing_content"
  | "generating_clips"
  | "cutting_video"
  | "completed"
  | "failed"
  | "cancelled";

export type Task = {
  task_id: string;
  video_name: string;
  video_url?: string | null;
  video_duration?: number | null;
  video_size?: number | null;
  video_format?: string | null;
  video_resolution?: string | null;
  content_type?: string | null;
  min_clip_duration: number;
  max_clip_duration: number;
  max_clip_count: number;
  risk_filter_enabled: boolean;
  status: TaskStatus;
  progress: number;
  current_stage?: string | null;
  failed_stage?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type Clip = {
  clip_id: string;
  task_id: string;
  title?: string | null;
  summary?: string | null;
  reason?: string | null;
  start_time: number;
  end_time: number;
  duration: number;
  score?: number | null;
  risk_level?: "low" | "medium" | "high" | string | null;
  tags: string[];
  content_type?: string | null;
  clip_url?: string | null;
  status?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskLog = {
  id: number;
  task_id: string;
  stage: string;
  level: string;
  message: string;
  attempt?: number | null;
  error_message?: string | null;
  created_at: string;
};

