from typing import Any

from app.db import db_connection
from app.repositories.base import encode_json, row_to_dict


class TranscriptRepository:
    def create_transcript(self, data: dict[str, Any]) -> dict[str, Any]:
        fields = list(data.keys())
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields)
        values = [data[field] for field in fields]
        with db_connection() as conn:
            conn.execute(f"INSERT INTO transcripts ({columns}) VALUES ({placeholders})", values)
            row = conn.execute(
                "SELECT * FROM transcripts WHERE transcript_id = ?",
                (data["transcript_id"],),
            ).fetchone()
        created = row_to_dict(row)
        if created is None:
            raise RuntimeError("Transcript was not created")
        return created

    def create_segments(self, segments: list[dict[str, Any]]) -> None:
        if not segments:
            return
        fields = list(segments[0].keys())
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields)
        values = [[segment[field] for field in fields] for segment in segments]
        with db_connection() as conn:
            conn.executemany(
                f"INSERT INTO transcript_segments ({columns}) VALUES ({placeholders})",
                values,
            )

    def create_topics(self, topics: list[dict[str, Any]]) -> None:
        if not topics:
            return
        payloads = []
        for topic in topics:
            payload = topic.copy()
            payload["raw_llm_output"] = encode_json(payload.get("raw_llm_output", {}))
            payload["suitable_for_clip"] = bool(payload.get("suitable_for_clip", True))
            payloads.append(payload)
        fields = list(payloads[0].keys())
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields)
        values = [[payload[field] for field in fields] for payload in payloads]
        with db_connection() as conn:
            conn.executemany(
                f"INSERT INTO topic_analysis ({columns}) VALUES ({placeholders})",
                values,
            )
