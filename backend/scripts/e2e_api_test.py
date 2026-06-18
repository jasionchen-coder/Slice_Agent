import argparse
import sys
import time
from pathlib import Path

import httpx


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an end-to-end API test with a real video.")
    parser.add_argument("--video", required=True, help="Path to the local video file to upload.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--content-type", default="other", help="Live content type.")
    parser.add_argument("--min-duration", type=int, default=10, help="Minimum clip duration in seconds.")
    parser.add_argument("--max-duration", type=int, default=180, help="Maximum clip duration in seconds.")
    parser.add_argument("--max-count", type=int, default=5, help="Maximum number of generated clips.")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="Polling interval in seconds.")
    parser.add_argument("--timeout", type=int, default=1800, help="Max wait time in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Video file not found: {video_path}", file=sys.stderr)
        return 2

    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        health = client.get("/health")
        health.raise_for_status()
        print("health_ok")

        with video_path.open("rb") as video_file:
            response = client.post(
                "/api/tasks",
                data={
                    "content_type": args.content_type,
                    "min_clip_duration": str(args.min_duration),
                    "max_clip_duration": str(args.max_duration),
                    "max_clip_count": str(args.max_count),
                    "risk_filter_enabled": "true",
                },
                files={"file": (video_path.name, video_file, "video/mp4")},
            )
        response.raise_for_status()
        task_id = response.json()["task_id"]
        print(f"task_created {task_id}")

        deadline = time.monotonic() + args.timeout
        task = {}
        while time.monotonic() < deadline:
            task_response = client.get(f"/api/tasks/{task_id}")
            task_response.raise_for_status()
            task = task_response.json()
            print(
                "task_status "
                f"{task['status']} progress={task['progress']} "
                f"stage={task.get('current_stage') or ''}"
            )
            if task["status"] in TERMINAL_STATUSES:
                break
            time.sleep(args.poll_interval)
        else:
            print(f"Timed out waiting for task {task_id}", file=sys.stderr)
            return 3

        if task["status"] != "completed":
            print(
                f"task_failed status={task['status']} "
                f"stage={task.get('failed_stage')} error={task.get('error_message')}",
                file=sys.stderr,
            )
            logs_response = client.get(f"/api/tasks/{task_id}/logs")
            if logs_response.status_code == 200:
                for log in logs_response.json().get("logs", [])[-20:]:
                    print(
                        "task_log "
                        f"{log.get('level')} stage={log.get('stage')} "
                        f"attempt={log.get('attempt')} message={log.get('message')} "
                        f"error={log.get('error_message')}",
                        file=sys.stderr,
                    )
            return 4

        clips_response = client.get(f"/api/tasks/{task_id}/clips")
        clips_response.raise_for_status()
        clips = clips_response.json()["clips"]
        print(f"clips_count {len(clips)}")
        for clip in clips:
            print(
                "clip "
                f"{clip['clip_id']} status={clip['status']} "
                f"score={clip.get('score')} duration={clip['duration']:.2f} "
                f"url={clip.get('clip_url')}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
