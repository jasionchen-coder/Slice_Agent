from typing import Any


class QueueDispatchError(RuntimeError):
    pass


class QueueService:
    def submit(self, task: Any, *args, **kwargs) -> None:
        delay = getattr(task, "delay", None)
        if delay is None:
            raise QueueDispatchError("QueueService requires a Celery task with .delay()")
        try:
            delay(*args, **kwargs)
        except Exception as exc:
            raise QueueDispatchError(f"Failed to enqueue Celery task: {exc}") from exc
