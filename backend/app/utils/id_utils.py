from datetime import UTC, datetime
from uuid import uuid4


def new_task_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"task_{stamp}_{uuid4().hex[:8]}"


def new_entity_id(prefix: str, index: int | None = None) -> str:
    if index is None:
        return f"{prefix}_{uuid4().hex[:10]}"
    return f"{prefix}_{index + 1:03d}_{uuid4().hex[:6]}"

