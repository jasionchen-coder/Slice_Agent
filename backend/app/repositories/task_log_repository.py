from typing import Any

from app.db import db_connection


class TaskLogRepository:
    def create(
        self,
        *,
        task_id: str,
        stage: str,
        level: str,
        message: str,
        attempt: int | None = None,
        error_message: str | None = None,
    ) -> None:
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO task_logs (task_id, stage, level, message, attempt, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, stage, level, message, attempt, error_message),
            )

    def list_by_task(self, task_id: str) -> list[dict[str, Any]]:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM task_logs WHERE task_id = ? ORDER BY created_at ASC, id ASC",
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]
