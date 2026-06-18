import json
from typing import Any


def row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def decode_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
