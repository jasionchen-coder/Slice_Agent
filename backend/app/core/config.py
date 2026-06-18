from pathlib import Path
from urllib.parse import urlparse

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "Live Slicing Agent API"
    database_url: str = "sqlite:///./data/app.db"
    storage_root: Path = Path("./storage")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    allowed_video_extensions: set[str] = Field(
        default_factory=lambda: {".mp4", ".mov", ".m4v", ".flv"}
    )
    max_upload_mb: int = 2048
    auto_process: bool = True
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    audio_chunk_seconds: int = 600
    audio_chunk_overlap_seconds: int = 2
    audio_extract_retries: int = 1
    asr_retries: int = 2
    llm_retries: int = 2
    ffmpeg_cut_retries: int = 1
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    asr_provider: str = "mock"
    llm_provider: str = "mock"
    default_language: str = "zh"
    request_timeout_seconds: int = 120

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_asr_model: str = "whisper-large-v3-turbo"
    groq_llm_model: str = "llama-3.3-70b-versatile"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_llm_model: str = "gpt-4.1-mini"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_llm_model: str = "claude-3-5-sonnet-latest"

    ark_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_ARK_API_KEY", "ARK_API_KEY"),
    )
    ark_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        validation_alias=AliasChoices("APP_ARK_BASE_URL", "ARK_BASE_URL"),
    )
    ark_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_ARK_MODEL", "ARK_MODEL"),
    )

    @property
    def sqlite_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// URLs are supported by the local repository")
        return Path(self.database_url.removeprefix("sqlite:///"))

    @property
    def database_backend(self) -> str:
        scheme = urlparse(self.database_url).scheme
        if scheme == "sqlite":
            return "sqlite"
        if scheme in {"postgres", "postgresql"}:
            return "postgresql"
        raise ValueError(f"Unsupported database backend: {scheme}")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
