import { FFmpeg } from "@ffmpeg/ffmpeg";
import { fetchFile, toBlobURL } from "@ffmpeg/util";
import type { Clip } from "@/lib/types";

const FFMPEG_CORE_VERSION = "0.12.10";
const CORE_BASE_URL = `https://unpkg.com/@ffmpeg/core@${FFMPEG_CORE_VERSION}/dist/umd`;
export const AUDIO_CHUNK_SECONDS = 30 * 60;

let ffmpegPromise: Promise<FFmpeg> | null = null;

export type AudioChunkUpload = {
  file: File;
  chunkIndex: number;
  startTime: number;
  endTime: number;
};

export type LocalCutResult = {
  clipId: string;
  title: string;
  file: File;
  url: string;
};

export async function loadBrowserFFmpeg(onStatus?: (message: string) => void) {
  if (ffmpegPromise) return ffmpegPromise;

  ffmpegPromise = (async () => {
    onStatus?.("正在加载浏览器 FFmpeg");
    const ffmpeg = new FFmpeg();
    await ffmpeg.load({
      coreURL: await toBlobURL(`${CORE_BASE_URL}/ffmpeg-core.js`, "text/javascript"),
      wasmURL: await toBlobURL(`${CORE_BASE_URL}/ffmpeg-core.wasm`, "application/wasm")
    });
    return ffmpeg;
  })();

  return ffmpegPromise;
}

export async function getVideoDuration(file: File): Promise<number> {
  const video = document.createElement("video");
  video.preload = "metadata";
  video.muted = true;
  const url = URL.createObjectURL(file);

  try {
    video.src = url;
    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error("无法读取视频时长"));
    });
    return Number.isFinite(video.duration) ? video.duration : 0;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function extractMp3Chunks(
  videoFile: File,
  duration: number,
  onStatus?: (message: string) => void
): Promise<AudioChunkUpload[]> {
  const ffmpeg = await loadBrowserFFmpeg(onStatus);
  const inputName = safeFileName(videoFile.name || "source.mp4");
  await replaceFile(ffmpeg, inputName, await fetchFile(videoFile));

  const chunks: AudioChunkUpload[] = [];
  const totalChunks = Math.max(1, Math.ceil(duration / AUDIO_CHUNK_SECONDS));

  for (let index = 0; index < totalChunks; index += 1) {
    const start = index * AUDIO_CHUNK_SECONDS;
    const end = Math.min(start + AUDIO_CHUNK_SECONDS, duration);
    const outputName = `audio_${String(index + 1).padStart(3, "0")}.mp3`;
    onStatus?.(`正在提取音频 ${index + 1}/${totalChunks}`);
    await deleteIfExists(ffmpeg, outputName);
    await ffmpeg.exec([
      "-ss",
      start.toFixed(3),
      "-t",
      Math.max(end - start, 0.01).toFixed(3),
      "-i",
      inputName,
      "-vn",
      "-ac",
      "1",
      "-ar",
      "16000",
      "-b:a",
      "64k",
      outputName
    ]);

    const data = await ffmpeg.readFile(outputName);
    const bytes = data instanceof Uint8Array ? data : new TextEncoder().encode(data);
    chunks.push({
      file: new File([toArrayBuffer(bytes)], outputName, { type: "audio/mpeg" }),
      chunkIndex: index,
      startTime: start,
      endTime: end
    });
    await deleteIfExists(ffmpeg, outputName);
  }

  await deleteIfExists(ffmpeg, inputName);
  return chunks;
}

export async function cutLocalClip(videoFile: File, clip: Clip, onStatus?: (message: string) => void): Promise<LocalCutResult> {
  const ffmpeg = await loadBrowserFFmpeg(onStatus);
  const inputName = safeFileName(videoFile.name || "source.mp4");
  const outputName = `${clip.clip_id}.mp4`;
  await replaceFile(ffmpeg, inputName, await fetchFile(videoFile));
  await deleteIfExists(ffmpeg, outputName);
  onStatus?.(`正在本地切片：${clip.title || clip.clip_id}`);
  await ffmpeg.exec([
    "-ss",
    clip.start_time.toFixed(3),
    "-to",
    clip.end_time.toFixed(3),
    "-i",
    inputName,
    "-c",
    "copy",
    "-avoid_negative_ts",
    "make_zero",
    outputName
  ]);
  const data = await ffmpeg.readFile(outputName);
  const bytes = data instanceof Uint8Array ? data : new TextEncoder().encode(data);
  await deleteIfExists(ffmpeg, outputName);
  await deleteIfExists(ffmpeg, inputName);

  const title = clip.title?.trim() || clip.clip_id;
  const file = new File([toArrayBuffer(bytes)], `${safeFileName(title)}.mp4`, { type: "video/mp4" });
  return {
    clipId: clip.clip_id,
    title,
    file,
    url: URL.createObjectURL(file)
  };
}

async function replaceFile(ffmpeg: FFmpeg, path: string, data: Uint8Array) {
  await deleteIfExists(ffmpeg, path);
  await ffmpeg.writeFile(path, data);
}

async function deleteIfExists(ffmpeg: FFmpeg, path: string) {
  try {
    await ffmpeg.deleteFile(path);
  } catch {
    // File may not exist in the in-memory FS.
  }
}

function safeFileName(value: string) {
  const cleaned = value.replace(/[\\/:*?"<>|]+/g, "_").trim();
  return cleaned || "output";
}

function toArrayBuffer(bytes: Uint8Array) {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}
