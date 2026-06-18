from typing import Any

from app.db import db_connection
from app.repositories.base import decode_json_list, encode_json, row_to_dict


class ClipRepository:
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = data.copy()
        payload["tags"] = encode_json(payload.get("tags", []))
        fields = list(payload.keys())
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields)
        values = [payload[field] for field in fields]
        with db_connection() as conn:
            conn.execute(f"INSERT INTO clips ({columns}) VALUES ({placeholders})", values)
            row = conn.execute(
                "SELECT * FROM clips WHERE clip_id = ?",
                (payload["clip_id"],),
            ).fetchone()
        created = self._deserialize(row_to_dict(row))
        if created is None:
            raise RuntimeError("Clip was not created")
        return created

    def get(self, clip_id: str) -> dict[str, Any] | None:
        with db_connection() as conn:
            row = conn.execute("SELECT * FROM clips WHERE clip_id = ?", (clip_id,)).fetchone()
        return self._deserialize(row_to_dict(row))

    def list_by_task(self, task_id: str) -> list[dict[str, Any]]:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM clips WHERE task_id = ? ORDER BY score DESC, start_time ASC",
                (task_id,),
            ).fetchall()
        return [self._deserialize(dict(row)) for row in rows]

    def update(self, clip_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = data.copy()
        if "tags" in payload:
            payload["tags"] = encode_json(payload["tags"])
        if not payload:
            return self.get(clip_id)
        assignments = ", ".join(f"{field} = ?" for field in payload)
        values = [*payload.values(), clip_id]
        with db_connection() as conn:
            conn.execute(
                f"UPDATE clips SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE clip_id = ?",
                values,
            )
            row = conn.execute("SELECT * FROM clips WHERE clip_id = ?", (clip_id,)).fetchone()
        return self._deserialize(row_to_dict(row))

    def delete_by_task(self, task_id: str) -> None:
        with db_connection() as conn:
            conn.execute("DELETE FROM clips WHERE task_id = ?", (task_id,))

    def _deserialize(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        row["tags"] = decode_json_list(row.get("tags"))
        return row

