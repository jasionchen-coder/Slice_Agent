# Live Slicing Agent Backend

FastAPI backend for the live replay clipping MVP.

## What Is Implemented

- Video upload and task creation
- Task status, retry, cancel, and clip list APIs
- SQLite persistence for local development
- Local filesystem storage under `storage/`
- FFprobe video metadata parsing
- FFmpeg audio extraction and video clipping
- Replaceable ASR and LLM integration layer
- Mock ASR and mock LLM providers so the pipeline can run without API keys

## Run Locally

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

The API will create `backend/data/app.db` and `backend/storage/` on startup.

## Useful Environment Variables

```bash
APP_DATABASE_URL=sqlite:///./data/app.db
# or: APP_DATABASE_URL=postgresql://postgres:password@localhost:5432/postgres
APP_STORAGE_ROOT=./storage
APP_MAX_UPLOAD_MB=2048
APP_AUTO_PROCESS=true
APP_CELERY_BROKER_URL=redis://localhost:6379/0
APP_CELERY_RESULT_BACKEND=redis://localhost:6379/1
APP_AUDIO_CHUNK_SECONDS=600
APP_AUDIO_CHUNK_OVERLAP_SECONDS=2
APP_FFMPEG_PATH=ffmpeg
APP_FFPROBE_PATH=ffprobe
APP_ASR_PROVIDER=mock
APP_LLM_PROVIDER=mock
APP_GROQ_API_KEY=
APP_GROQ_ASR_MODEL=whisper-large-v3-turbo
APP_GROQ_LLM_MODEL=llama-3.3-70b-versatile
```

`mock` providers are intentionally basic. They make development and API integration possible before real Whisper/OpenAI/Claude providers are connected.

Copy or edit `.env` directly for local development. `.env.example` is kept as the shareable template.

To use Groq for the real pipeline:

```bash
APP_ASR_PROVIDER=groq
APP_LLM_PROVIDER=groq
APP_GROQ_API_KEY=your_key_here
```

To use Groq ASR and Volcano Engine Ark LLM:

```bash
APP_ASR_PROVIDER=groq
APP_LLM_PROVIDER=ark
APP_GROQ_API_KEY=your_groq_key
ARK_API_KEY=your_ark_key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=your_endpoint_model
```

## Checks

```bash
uv run python -m compileall app
uv run python -m unittest discover -s tests
```

## Real Pipeline API Test

Start the API:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Start Redis and the Celery worker before creating tasks:

```bash
redis-server
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info --pool=solo
```

In another terminal, upload a real video and wait for the full pipeline:

```bash
uv run python scripts/e2e_api_test.py --video D:\path\to\live_replay.mp4 --min-duration 10 --max-duration 180 --max-count 5
```

The script calls the public API only: `POST /api/tasks`, `GET /api/tasks/{task_id}`, and `GET /api/tasks/{task_id}/clips`.
