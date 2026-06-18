from collections.abc import Callable
from time import sleep
from typing import TypeVar


T = TypeVar("T")


def run_with_retries(
    operation: Callable[[], T],
    *,
    retries: int,
    on_retry: Callable[[int, Exception], None] | None = None,
    retry_delay_seconds: float = 1.0,
) -> T:
    attempt = 1
    max_attempts = retries + 1
    while True:
        try:
            return operation()
        except Exception as exc:
            if attempt >= max_attempts:
                raise
            if on_retry is not None:
                on_retry(attempt, exc)
            sleep(retry_delay_seconds)
            attempt += 1
