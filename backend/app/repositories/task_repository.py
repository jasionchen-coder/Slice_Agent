from typing import Any

from app.db import db_connection
from app.repositories.base import row_to_dict


class TaskRepository:
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        fields = list(data.keys())
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields)
        values = [data[field] for field in fields]
        with db_connection() as conn:
            conn.execute(
                f"INSERT INTO tasks ({columns}) VALUES ({placeholders})",
                values,
            )
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (data["task_id"],),
            ).fetchone()
        created = row_to_dict(row)
        if created is None:
            raise RuntimeError("Task was not created")
        return created

    def get(self, task_id: str) -> dict[str, Any] | None:
        with db_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return row_to_dict(row)

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def update(self, task_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if not data:
            return self.get(task_id)
        assignments = ", ".join(f"{field} = ?" for field in data)
        values = [*data.values(), task_id]
        with db_connection() as conn:
            conn.execute(
                f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                values,
            )
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return row_to_dict(row)

    def update_status(
        self,
        task_id: str,
        *,
        status: str,
        progress: int,
        current_stage: str | None = None,
        failed_stage: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        return self.update(
            task_id,
            {
                "status": status,
                "progress": progress,
                "current_stage": current_stage,
                "failed_stage": failed_stage,
                "error_message": error_message,
            },
        )

