# 直播切片 Agent 数据流转说明

本文档基于当前代码实现梳理项目的数据流转。当前默认方案已经调整为“视频留在浏览器本地，前端用 ffmpeg.wasm 提取 MP3，后端只接收音频做 ASR/LLM 分析，前端再用原视频本地切片”。旧的视频直传后端接口仍保留，用作兼容路径。

## 1. 总体架构

```text
用户浏览器
  |
  | 1. 选择视频，本地提取 MP3 / 查看任务 / 本地切片
  v
Next.js 前端
  |
  | 2. 上传 MP3 或 MP3 分片
  v
FastAPI 后端
  |
  | 3. 写任务记录、保存音频、投递异步任务
  v
PostgreSQL + 本地 storage + Redis
  |
  | Celery worker 消费任务
  v
ASR / LLM Pipeline
  |
  | 4. 写文字稿、话题、切片时间方案、日志
  v
前端轮询任务状态，使用本地原视频切 mp4，按需上传保存
```

核心角色：

- 前端：负责本地提取 MP3、本地切 mp4、展示任务进度、展示日志、预览和编辑切片。
- FastAPI：负责接收请求、创建任务、查询任务、切片变更和下载。
- Redis：作为 Celery broker/result backend。
- Celery worker：执行耗时的 ASR/LLM 分析 pipeline。
- PostgreSQL：保存任务、文字稿、话题分析、切片和日志等结构化数据。
- 本地 storage：保存前端上传的音频、ASR/LLM JSON 中间产物，以及用户按需上传保存的最终切片视频。

## 2. 前端到后端的入口流

### 2.1 默认流程：前端提取 MP3 后创建音频任务

用户在前端 `/tasks/create` 页面选择视频文件并填写参数：

- `content_type`
- `min_clip_duration`
- `max_clip_duration`
- `max_clip_count`
- `risk_filter_enabled`

浏览器端处理：

1. 使用 HTML video metadata 读取原视频时长。
2. 使用 `@ffmpeg/ffmpeg` 在浏览器内加载 ffmpeg.wasm。
3. 对 30 分钟以内的视频提取单个 MP3。
4. 对 30 分钟以上的视频按 30 分钟切成多个 MP3 分片。
5. 构造 `audio_manifest`，记录每个 MP3 分片的 `chunk_index`、`start_time`、`end_time`。

前端调用：

```text
POST /api/tasks/audio
Content-Type: multipart/form-data
```

表单字段：

```text
audio_files[]          MP3 文件或多个 MP3 分片
audio_manifest         JSON 数组，记录每段音频的起止时间
original_video_name    原视频文件名
video_duration         原视频时长
content_type
min_clip_duration
max_clip_duration
max_clip_count
risk_filter_enabled
```

对应代码：

- 前端表单：[frontend/src/components/tasks/task-create-form.tsx](../frontend/src/components/tasks/task-create-form.tsx)
- 浏览器 FFmpeg 工具：[frontend/src/lib/browser-ffmpeg.ts](../frontend/src/lib/browser-ffmpeg.ts)
- API client：[frontend/src/lib/api.ts](../frontend/src/lib/api.ts)
- 后端路由：[backend/app/api/routes/tasks.py](../backend/app/api/routes/tasks.py)

后端处理步骤：

1. 校验 `audio_manifest`。
2. 校验 MP3/音频文件格式。
3. 保存音频到 `storage/live-slicing/tasks/{task_id}/audio/chunks/`。
4. 写入 `audio/manifest.json`。
5. 在 `tasks` 表创建任务记录，`video_url = frontend-audio`。
6. 如果 `APP_AUTO_PROCESS=true`，投递 Celery 任务 `process_video_task(task_id)`。
7. 返回 `task_id` 给前端。

### 2.2 兼容流程：直接上传视频创建任务

旧的视频直传接口仍保留：

```text
POST /api/tasks
Content-Type: multipart/form-data
```

对应代码：

- 前端：[frontend/src/components/tasks/task-create-form.tsx](../frontend/src/components/tasks/task-create-form.tsx)
- API client：[frontend/src/lib/api.ts](../frontend/src/lib/api.ts)
- 后端路由：[backend/app/api/routes/tasks.py](../backend/app/api/routes/tasks.py)

该流程会把原视频上传后端，后端使用 FFprobe 读取视频信息，使用 FFmpeg 提取音频和切 mp4。新默认流程不再推荐这个路径，除非明确希望服务器端保存原视频并负责最终切片。

后端兼容处理步骤：

1. 校验必须上传本地视频文件。
2. 校验 `min_clip_duration < max_clip_duration`。
3. 调用 `TaskService.create_from_upload()`。
4. 保存原视频到本地 storage。
5. 通过 FFprobe 读取视频基础信息。
6. 在 `tasks` 表创建任务记录。
7. 如果 `APP_AUTO_PROCESS=true`，投递 Celery 任务 `process_video_task(task_id)`。
8. 返回 `task_id` 给前端。

## 3. 文件存储流

所有任务文件都在 `APP_STORAGE_ROOT` 下，默认是：

```text
backend/storage/live-slicing/tasks/{task_id}/
```

典型目录结构：

```text
storage/live-slicing/tasks/{task_id}/
  audio/
    manifest.json
    chunks/
      audio_001.mp3
      audio_002.mp3
  transcript/
    raw_transcript.json
    cleaned_transcript.json
  llm/
    topic_analysis.json
    clip_plan.json
  clips/
    {clip_id}.mp4
```

对应代码：

- [backend/app/services/storage_service.py](../backend/app/services/storage_service.py)

文件用途：

- `audio/manifest.json`：前端上传音频分片的起止时间信息。
- `audio/chunks/`：前端提取并上传的 MP3 音频或音频分片。
- `transcript/raw_transcript.json`：ASR 原始转写结果。
- `transcript/cleaned_transcript.json`：清洗后的文字稿。
- `llm/topic_analysis.json`：LLM 话题分析结果。
- `llm/clip_plan.json`：LLM 生成的切片方案。
- `clips/*.mp4`：用户在前端本地切出 mp4 后，按需上传保存的最终切片视频。

兼容视频直传路径还会出现：

```text
original/source.*
audio/audio.wav
```

其中 `original/source.*` 是后端保存的原视频，`audio/audio.wav` 是服务器端 FFmpeg 提取的音频。

## 4. 数据库表流转

### 4.1 `tasks`

任务主表。创建任务时写入，pipeline 每个阶段都会更新状态。

关键字段：

- `task_id`
- `video_name`
- `original_video_path`
- `video_duration`
- `video_format`
- `video_resolution`
- `content_type`
- `min_clip_duration`
- `max_clip_duration`
- `max_clip_count`
- `risk_filter_enabled`
- `status`
- `progress`
- `current_stage`
- `failed_stage`
- `error_message`

### 4.2 `transcripts`

文字稿主表。在 `cleaning_transcript` 阶段写入。

关键字段：

- `transcript_id`
- `task_id`
- `raw_text`
- `cleaned_text`
- `language`
- `asr_provider`

### 4.3 `transcript_segments`

逐段文字稿。在 `cleaning_transcript` 阶段批量写入。

关键字段：

- `segment_id`
- `task_id`
- `transcript_id`
- `start_time`
- `end_time`
- `speaker`
- `text`
- `cleaned_text`
- `segment_index`

### 4.4 `topic_analysis`

LLM 话题分析结果。在 `analyzing_content` 阶段写入。

关键字段：

- `topic_id`
- `task_id`
- `start_time`
- `end_time`
- `topic_title`
- `summary`
- `content_type`
- `suitable_for_clip`
- `risk_level`
- `score`
- `raw_llm_output`

### 4.5 `clips`

切片候选和成片结果。在 `generating_clips` 阶段创建，在 `cutting_video` 阶段更新文件路径和状态。

关键字段：

- `clip_id`
- `task_id`
- `title`
- `summary`
- `reason`
- `start_time`
- `end_time`
- `duration`
- `score`
- `risk_level`
- `tags`
- `content_type`
- `clip_path`
- `clip_url`
- `status`
- `error_message`

### 4.6 `task_logs`

任务日志表。pipeline 每个关键阶段和重试都会写入。

关键字段：

- `task_id`
- `stage`
- `level`
- `message`
- `attempt`
- `error_message`

前端任务详情页通过：

```text
GET /api/tasks/{task_id}/logs
```

读取日志并展示。

## 5. Celery Pipeline 流转

任务创建后，FastAPI 通过 `QueueService` 投递：

```text
process_video_task(task_id)
```

Celery worker 执行：

```text
VideoPipeline.process(task_id)
```

对应代码：

- [backend/app/workers/video_pipeline.py](../backend/app/workers/video_pipeline.py)
- [backend/app/services/queue_service.py](../backend/app/services/queue_service.py)
- [backend/app/workers/celery_app.py](../backend/app/workers/celery_app.py)

### 5.1 `extracting_audio`

默认音频任务中，前端已经完成 MP3 提取，后端不会再执行服务器端 FFmpeg 提取音频。pipeline 会读取 `audio/manifest.json`，把前端上传的 MP3 分片转换成内部 `AudioChunk` 列表，并记录日志：

```text
使用前端上传音频，共 N 段
```

兼容视频直传任务中，该阶段仍会执行服务器端音频提取：

1. 读取 `tasks.original_video_path`。
2. 调用 FFmpeg 提取音频。
3. 输出到 `audio/audio.wav`。
4. 按 `APP_AUDIO_CHUNK_SECONDS` 和 `APP_AUDIO_CHUNK_OVERLAP_SECONDS` 切分长音频。
5. 分片输出到 `audio/chunks/`。

### 5.2 `transcribing`

状态更新：

```text
status = transcribing
progress = 40
current_stage = 语音识别中
```

处理：

1. 遍历音频分片。
2. 调用 ASR client，目前可配置 Groq。
3. 每个分片得到若干 `TranscriptSegment`。
4. 按分片起始时间做 offset。
5. 合并分片结果，处理重叠片段。
6. 写入 `transcript/raw_transcript.json`。

### 5.3 `cleaning_transcript`

状态更新：

```text
status = cleaning_transcript
progress = 50
current_stage = 文字清洗中
```

处理：

1. 调用 `TranscriptService.clean_segments()` 清洗文本。
2. 写入 `transcript/cleaned_transcript.json`。
3. 创建 `transcripts` 记录。
4. 批量创建 `transcript_segments` 记录。

### 5.4 `analyzing_content`

状态更新：

```text
status = analyzing_content
progress = 70
current_stage = 内容分析中
```

处理：

1. 调用 LLM client 分析文字稿话题。
2. LLM 返回结构化 topic 列表。
3. 写入 `llm/topic_analysis.json`。
4. 写入 `topic_analysis` 表。

### 5.5 `generating_clips`

状态更新：

```text
status = generating_clips
progress = 80
current_stage = 切片方案生成中
```

处理：

1. 调用 LLM client 根据 topics 生成切片方案。
2. 传入用户参数：
   - `min_clip_duration`
   - `max_clip_duration`
   - `max_clip_count`
   - `risk_filter_enabled`
   - `video_duration`
3. 写入 `llm/clip_plan.json`。
4. 删除该任务旧的 `clips`。
5. 校验候选切片：
   - 起止时间合法
   - 时长在用户配置范围内
   - 标题和摘要存在
   - 分数在 0-100
   - 开启风险过滤时过滤高风险切片
6. 将合法候选写入 `clips` 表。
7. 默认音频任务会把切片状态更新为 `ready_for_local_cut`，表示后端只生成切片时间方案，等待前端本地切 mp4。
8. 兼容视频直传任务保持 `pending`，继续进入服务器端 `cutting_video`。

### 5.6 `cutting_video`

默认音频任务不会进入该阶段，因为后端没有原视频文件。生成切片时间方案后，任务直接进入：

```text
status = completed
progress = 100
current_stage = 切片方案已生成
```

前端在切片审核页重新选择本地原视频，按 `clips.start_time` 和 `clips.end_time` 使用浏览器 FFmpeg 切出 mp4。

兼容视频直传任务才会执行服务器端 `cutting_video`：

状态更新：

```text
status = cutting_video
progress = 95
current_stage = 视频切割中
```

处理：

1. 遍历 `clips` 表中的候选切片。
2. 调用 FFmpeg 按 `start_time` 和 `end_time` 切割原视频。
3. 输出到 `clips/{clip_id}.mp4`。
4. 成功后更新：
   - `status = success`
   - `clip_path`
   - `clip_url = /media/...`
5. 单个切片失败时：
   - 当前切片标记为 `failed`
   - 记录 `error_message`
   - pipeline 继续处理其他切片。

### 5.7 `completed` / `failed` / `cancelled`

全部阶段成功后：

```text
status = completed
progress = 100
current_stage = 处理完成
```

如果用户取消：

```text
status = cancelled
current_stage = 任务已取消
```

如果 pipeline 抛出未处理异常：

```text
status = failed
progress = 0
current_stage = 处理失败
failed_stage = 当前阶段
error_message = 异常信息
```

## 6. 状态流转

任务状态大致如下：

```text
uploaded
  -> extracting_audio
  -> transcribing
  -> cleaning_transcript
  -> analyzing_content
  -> generating_clips
  -> cutting_video
  -> completed
```

异常分支：

```text
任意阶段 -> failed
任意阶段用户取消 -> cancelled
failed 后用户重试 -> pending -> 重新投递 process_video_task
```

前端展示状态时会轮询：

```text
GET /api/tasks/{task_id}
GET /api/tasks/{task_id}/logs
```

## 7. 前端页面消费数据流

### 7.1 首页任务队列

页面：

```text
/
```

调用：

```text
GET /api/tasks
```

展示：

- 视频名称
- 状态
- 进度
- 切片参数
- 创建时间
- 打开任务详情或切片审核入口

### 7.2 创建任务页

页面：

```text
/tasks/create
```

调用：

```text
POST /api/tasks
```

成功后跳转：

```text
/tasks/{task_id}
```

### 7.3 任务详情页

页面：

```text
/tasks/{task_id}
```

调用：

```text
GET /api/tasks/{task_id}
GET /api/tasks/{task_id}/logs
POST /api/tasks/{task_id}/cancel
POST /api/tasks/{task_id}/retry
```

展示：

- 当前状态
- 进度条
- 任务参数
- 失败原因
- 阶段日志
- 完成后进入切片审核

### 7.4 切片审核页

页面：

```text
/tasks/{task_id}/clips
```

调用：

```text
GET /api/tasks/{task_id}/clips
PATCH /api/clips/{clip_id}
POST /api/clips/{clip_id}/regenerate
POST /api/clips/{clip_id}/upload
GET /api/clips/{clip_id}/download
```

展示和操作：

- 候选切片列表
- 本地切片视频预览
- 标题、摘要、起止时间编辑
- 选择本地原视频后按时间点切当前或全部切片
- 下载本地切片文件
- 按需上传本地切片到后端保存

如果用户修改 `start_time` 或 `end_time`：

1. 后端更新 `clips` 表。
2. 默认音频任务设置 `status = ready_for_local_cut`，等待前端重新本地切片。
3. 兼容视频直传任务设置 `status = pending` 并投递 `regenerate_clip_task(clip_id)`，由服务器端 FFmpeg 重新切割。

## 8. 切片重新生成流

入口：

```text
PATCH /api/clips/{clip_id}
POST /api/clips/{clip_id}/regenerate
```

触发条件：

- 用户点击重新生成。
- 用户修改切片起止时间。

处理：

默认音频任务：

1. 查询 `clips` 表获得切片信息。
2. 查询关联 `tasks` 表，识别 `video_url = frontend-audio`。
3. 将切片状态改为 `ready_for_local_cut`。
4. 前端重新选择本地原视频并用浏览器 FFmpeg 切片。
5. 用户按需调用 `POST /api/clips/{clip_id}/upload` 上传保存最终 mp4。
6. 后端更新 `clip_path`、`clip_url` 和 `status = success`。

兼容视频直传任务：

1. 查询 `clips` 表获得切片信息。
2. 查询关联 `tasks` 表获得后端原视频路径。
3. 将切片状态改为 `pending`。
4. Celery 执行 `regenerate_clip_task`。
5. 调用 `ClipService.regenerate_clip()`。
6. FFmpeg 重新输出 `clips/{clip_id}.mp4`。
7. 更新 `clip_path`、`clip_url` 和 `status`。

## 9. 重试和错误日志流

pipeline 对关键外部调用使用 `run_with_retries()`：

- 音频提取，兼容视频直传任务
- ASR
- LLM
- FFmpeg 切片，兼容视频直传任务

重试时会写入 `task_logs`：

```text
level = warning
stage = 当前阶段
attempt = 第几次重试
error_message = 异常信息
```

最终失败时：

1. 写入 `task_logs`：

```text
level = error
message = 任务处理失败
error_message = 异常信息
```

2. 更新 `tasks`：

```text
status = failed
failed_stage = 当前阶段
error_message = 异常信息
```

前端任务详情页会展示这些错误和日志。

## 10. 运行时配置影响的数据流

主要环境变量：

```text
APP_DATABASE_URL
APP_STORAGE_ROOT
APP_AUTO_PROCESS
APP_CELERY_BROKER_URL
APP_CELERY_RESULT_BACKEND
APP_AUDIO_CHUNK_SECONDS
APP_AUDIO_CHUNK_OVERLAP_SECONDS
APP_ASR_PROVIDER
APP_LLM_PROVIDER
APP_GROQ_API_KEY
APP_GROQ_BASE_URL
APP_GROQ_ASR_MODEL
APP_FFMPEG_PATH
APP_FFPROBE_PATH
```

前端环境变量：

```text
NEXT_PUBLIC_API_BASE_URL
```

当前默认前端通过：

```text
http://127.0.0.1:8000
```

访问后端。

## 11. 一次完整任务的数据写入顺序

```text
1. 用户在前端选择视频
2. 浏览器 ffmpeg.wasm 提取 MP3
3. 如果视频超过 30 分钟，浏览器按 30 分钟切出多个 MP3
4. 前端上传 MP3 和 audio_manifest
5. storage 写 audio/chunks/*.mp3 和 audio/manifest.json
6. tasks 插入任务记录，status=uploaded，video_url=frontend-audio
7. Redis 收到 Celery task_id
8. Celery worker 开始 process_video_task
9. pipeline 读取 audio_manifest，跳过服务器端音频提取
10. tasks 更新 transcribing
11. ASR 返回 segments
12. storage 写 transcript/raw_transcript.json
13. tasks 更新 cleaning_transcript
14. storage 写 transcript/cleaned_transcript.json
15. transcripts 插入文字稿主记录
16. transcript_segments 批量插入文字稿片段
17. tasks 更新 analyzing_content
18. LLM 返回 topics
19. storage 写 llm/topic_analysis.json
20. topic_analysis 批量插入话题分析
21. tasks 更新 generating_clips
22. LLM 返回 clip candidates
23. storage 写 llm/clip_plan.json
24. clips 插入候选切片并标记 ready_for_local_cut
25. tasks 更新 completed
26. 前端读取 clips
27. 用户在切片页重新选择原视频
28. 前端浏览器 FFmpeg 按 start_time/end_time 切出 mp4
29. 用户下载本地切片，或上传保存到后端
30. 后端保存 clips/{clip_id}.mp4 并更新 clip_url
```

兼容视频直传任务的数据写入顺序：

```text
1. 用户上传视频到后端
2. storage 写 original/source.*
3. tasks 插入任务记录，status=uploaded
4. Redis 收到 Celery task_id
5. Celery worker 开始 process_video_task
6. tasks 更新 extracting_audio
7. storage 写 audio/audio.wav 和 audio/chunks/*
8. tasks 更新 transcribing
9. ASR 返回 segments
10. storage 写 transcript/raw_transcript.json
11. tasks 更新 cleaning_transcript
12. storage 写 transcript/cleaned_transcript.json
13. transcripts 插入文字稿主记录
14. transcript_segments 批量插入文字稿片段
15. tasks 更新 analyzing_content
16. LLM 返回 topics
17. storage 写 llm/topic_analysis.json
18. topic_analysis 批量插入话题分析
19. tasks 更新 generating_clips
20. LLM 返回 clip candidates
21. storage 写 llm/clip_plan.json
22. clips 插入候选切片
23. tasks 更新 cutting_video
24. FFmpeg 输出 clips/{clip_id}.mp4
25. clips 更新 clip_path、clip_url、status
26. tasks 更新 completed
27. 前端读取 clips 并播放 /media/... 视频
```

## 12. 当前实现边界

当前代码已经具备：

- 浏览器端 ffmpeg.wasm 提取 MP3。
- 超过 30 分钟的视频按 30 分钟提取多个 MP3 分片上传。
- 后端音频任务接口 `POST /api/tasks/audio`。
- 后端基于前端上传音频直接 ASR/LLM 分析。
- 前端基于后端返回的切片时间点，用本地原视频切出 mp4。
- 本地切片下载和按需上传保存。
- 兼容旧的视频直传后端流程。
- PostgreSQL 持久化。
- Redis + Celery 异步任务。
- 长音频切分和 ASR 分片合并。
- ASR/LLM/FFmpeg 重试和日志记录。
- LLM 结构化结果校验。
- 前端任务创建、进度查看、日志查看、切片审核、下载。

当前仍属于后续增强的点：

- 视频 URL 导入目前接口会提示 P1 后续支持。
- 多用户/权限体系尚未接入。
- 对象存储 MinIO/S3 尚未接入，目前使用本地文件系统。
- 更细粒度的 Celery worker 生命周期管理可以继续增强。
- 浏览器 ffmpeg.wasm 首次加载需要下载 wasm 资源，首次处理会比较慢。
