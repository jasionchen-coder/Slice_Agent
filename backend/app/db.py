import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT UNIQUE NOT NULL,
  user_id TEXT,
  video_name TEXT NOT NULL,
  video_url TEXT,
  original_video_path TEXT,
  video_duration REAL,
  video_size INTEGER,
  video_format TEXT,
  video_resolution TEXT,
  content_type TEXT,
  min_clip_duration INTEGER DEFAULT 30,
  max_clip_duration INTEGER DEFAULT 180,
  max_clip_count INTEGER DEFAULT 10,
  risk_filter_enabled INTEGER DEFAULT 1,
  status TEXT NOT NULL,
  progress INTEGER DEFAULT 0,
  current_stage TEXT,
  failed_stage TEXT,
  error_message TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  transcript_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  raw_text TEXT,
  cleaned_text TEXT,
  language TEXT,
  asr_provider TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcript_segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  segment_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  transcript_id TEXT NOT NULL,
  start_time REAL NOT NULL,
  end_time REAL NOT NULL,
  speaker TEXT,
  text TEXT NOT NULL,
  cleaned_text TEXT,
  segment_index INTEGER NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topic_analysis (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  start_time REAL NOT NULL,
  end_time REAL NOT NULL,
  topic_title TEXT,
  summary TEXT,
  content_type TEXT,
  suitable_for_clip INTEGER,
  risk_level TEXT,
  score INTEGER,
  raw_llm_output TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  clip_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  title TEXT,
  summary TEXT,
  reason TEXT,
  start_time REAL NOT NULL,
  end_time REAL NOT NULL,
  duration REAL NOT NULL,
  score INTEGER,
  risk_level TEXT,
  tags TEXT,
  content_type TEXT,
  clip_path TEXT,
  clip_url TEXT,
  status TEXT,
  error_message TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  attempt INTEGER,
  error_message TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id BIGSERIAL PRIMARY KEY,
  task_id TEXT UNIQUE NOT NULL,
  user_id TEXT,
  video_name TEXT NOT NULL,
  video_url TEXT,
  original_video_path TEXT,
  video_duration DOUBLE PRECISION,
  video_size BIGINT,
  video_format TEXT,
  video_resolution TEXT,
  content_type TEXT,
  min_clip_duration INTEGER DEFAULT 30,
  max_clip_duration INTEGER DEFAULT 180,
  max_clip_count INTEGER DEFAULT 10,
  risk_filter_enabled BOOLEAN DEFAULT TRUE,
  status TEXT NOT NULL,
  progress INTEGER DEFAULT 0,
  current_stage TEXT,
  failed_stage TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
  id BIGSERIAL PRIMARY KEY,
  transcript_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  raw_text TEXT,
  cleaned_text TEXT,
  language TEXT,
  asr_provider TEXT,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcript_segments (
  id BIGSERIAL PRIMARY KEY,
  segment_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  transcript_id TEXT NOT NULL,
  start_time DOUBLE PRECISION NOT NULL,
  end_time DOUBLE PRECISION NOT NULL,
  speaker TEXT,
  text TEXT NOT NULL,
  cleaned_text TEXT,
  segment_index INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topic_analysis (
  id BIGSERIAL PRIMARY KEY,
  topic_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  start_time DOUBLE PRECISION NOT NULL,
  end_time DOUBLE PRECISION NOT NULL,
  topic_title TEXT,
  summary TEXT,
  content_type TEXT,
  suitable_for_clip BOOLEAN,
  risk_level TEXT,
  score INTEGER,
  raw_llm_output TEXT,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clips (
  id BIGSERIAL PRIMARY KEY,
  clip_id TEXT UNIQUE NOT NULL,
  task_id TEXT NOT NULL,
  title TEXT,
  summary TEXT,
  reason TEXT,
  start_time DOUBLE PRECISION NOT NULL,
  end_time DOUBLE PRECISION NOT NULL,
  duration DOUBLE PRECISION NOT NULL,
  score INTEGER,
  risk_level TEXT,
  tags TEXT,
  content_type TEXT,
  clip_path TEXT,
  clip_url TEXT,
  status TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_logs (
  id BIGSERIAL PRIMARY KEY,
  task_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  attempt INTEGER,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""


class DatabaseConnection:
    def __init__(self, conn: Any, backend: str) -> None:
        self.conn = conn
        self.backend = backend

    def execute(self, query: str, params: Any = None) -> Any:
        return self.conn.execute(self._query(query), self._params(params))

    def executemany(self, query: str, params: Any) -> Any:
        translated_query = self._query(query)
        if self.backend == "postgresql":
            with self.conn.cursor() as cursor:
                return cursor.executemany(translated_query, params)
        return self.conn.executemany(translated_query, params)

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _query(self, query: str) -> str:
        if self.backend == "postgresql":
            return query.replace("?", "%s")
        return query

    def _params(self, params: Any) -> Any:
        if params is None:
            return ()
        return params


def init_db() -> None:
    if settings.database_backend == "sqlite":
        settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(settings.sqlite_path) as conn:
            conn.executescript(SQLITE_SCHEMA)
        return

    with psycopg.connect(settings.database_url) as conn:
        for statement in _split_sql(POSTGRES_SCHEMA):
            conn.execute(statement)
        conn.commit()


@contextmanager
def db_connection() -> Iterator[DatabaseConnection]:
    if settings.database_backend == "sqlite":
        conn = sqlite3.connect(settings.sqlite_path)
        conn.row_factory = sqlite3.Row
        wrapped = DatabaseConnection(conn, "sqlite")
    else:
        conn = psycopg.connect(settings.database_url, row_factory=dict_row)
        wrapped = DatabaseConnection(conn, "postgresql")

    try:
        yield wrapped
        wrapped.commit()
    finally:
        wrapped.close()


def _split_sql(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]
