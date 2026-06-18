from __future__ import annotations

import argparse
from collections import deque
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


BACKEND_LOG_NAMES = (
    "uvicorn.err.log",
    "uvicorn.out.log",
    "celery.err.log",
    "celery.out.log",
)


def tcp_open(host: str, port: int, timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
            capture_output=True,
            text=True,
            check=False,
        )
        return f'"{pid}"' in result.stdout or f",{pid}," in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def pid_listening_on_port(port: int) -> int | None:
    if os.name != "nt":
        return None
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address, state, pid_text = parts[1], parts[3].upper(), parts[4]
        if state != "LISTENING":
            continue
        if not local_address.rsplit(":", 1)[-1] == str(port):
            continue
        try:
            return int(pid_text)
        except ValueError:
            return None
    return None


def stop_process_tree(pid: int, name: str) -> None:
    if not is_pid_running(pid):
        return
    print(f"Stopping {name} pid {pid} ...")
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        return
    try:
        os.kill(pid, 15)
    except OSError:
        pass


def load_latest_pids(log_root: Path) -> dict[str, int | str]:
    latest = log_root / "latest_backend_pids.json"
    if not latest.exists():
        return {}
    try:
        return json.loads(latest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def process_flags(visible: bool) -> int:
    if os.name != "nt":
        return 0
    flags = subprocess.CREATE_NEW_PROCESS_GROUP
    if visible:
        return flags | subprocess.CREATE_NEW_CONSOLE
    return flags | subprocess.CREATE_NO_WINDOW


def start_process(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    visible: bool,
) -> subprocess.Popen[bytes]:
    print(f"Starting {name}: {' '.join(command)}")
    stdout = stdout_path.open("ab")
    stderr = stderr_path.open("ab")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=stdout,
        stderr=stderr,
        creationflags=process_flags(visible),
    )
    print(f"{name} pid: {process.pid}")
    return process


def wait_health(url: str, seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except URLError:
            pass
        except TimeoutError:
            pass
        time.sleep(1)
    return False


def celery_worker_ready(uv: str, backend_root: Path) -> bool:
    command = [
        uv,
        "run",
        "celery",
        "-A",
        "app.workers.celery_app.celery_app",
        "inspect",
        "ping",
        "--timeout=1",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(backend_root),
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "pong" in result.stdout.lower()


def latest_existing_logs(log_root: Path, names: tuple[str, ...]) -> list[Path]:
    found: dict[str, Path] = {}
    if not log_root.exists():
        return []
    for directory in sorted((path for path in log_root.iterdir() if path.is_dir()), reverse=True):
        for name in names:
            path = directory / name
            if name not in found and path.exists():
                found[name] = path
        if len(found) == len(names):
            break
    return list(found.values())


def print_recent_lines(path: Path, line_count: int) -> None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as file:
            lines = deque(file, maxlen=line_count)
    except OSError:
        return
    for line in lines:
        print(f"[{path.name}] {line}", end="")


def follow_logs(paths: list[Path], tail_lines: int) -> bool:
    unique_paths = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)

    if not unique_paths:
        print("No backend log files were found to follow.")
        return False

    print("")
    print("Streaming backend logs. Press Ctrl+C to stop watching logs; services will keep running.")
    print("")

    for path in unique_paths:
        if path.exists() and path.stat().st_size > 0:
            print(f"--- recent {path.name}: {path} ---")
            print_recent_lines(path, tail_lines)

    open_files = []
    try:
        for path in unique_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            file = path.open("r", encoding="utf-8", errors="replace")
            file.seek(0, os.SEEK_END)
            open_files.append((path, file))

        while True:
            printed = False
            for path, file in open_files:
                line = file.readline()
                while line:
                    print(f"[{path.name}] {line}", end="")
                    printed = True
                    line = file.readline()
            if not printed:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("")
        print("Stopping backend services ...")
        return True
    finally:
        for _, file in open_files:
            file.close()
    return False


def shutdown_celery(uv: str, backend_root: Path) -> None:
    print("Stopping Celery workers ...")
    subprocess.run(
        [
            uv,
            "run",
            "celery",
            "-A",
            "app.workers.celery_app.celery_app",
            "control",
            "shutdown",
            "--timeout=3",
        ],
        cwd=str(backend_root),
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )


def stop_backend_services(
    *,
    started: dict[str, int | str],
    uv: str,
    backend_root: Path,
    api_port: int,
    redis_port: int,
    no_redis: bool,
) -> None:
    api_pid = started.get("api")
    if isinstance(api_pid, int):
        stop_process_tree(api_pid, "FastAPI")
    else:
        detected_api_pid = pid_listening_on_port(api_port)
        if detected_api_pid:
            stop_process_tree(detected_api_pid, "FastAPI")

    celery_pid = started.get("celery")
    if isinstance(celery_pid, int):
        stop_process_tree(celery_pid, "Celery worker")
    elif celery_worker_ready(uv, backend_root):
        shutdown_celery(uv, backend_root)

    if not no_redis:
        redis_pid = started.get("redis")
        if isinstance(redis_pid, int):
            stop_process_tree(redis_pid, "Redis")
        else:
            detected_redis_pid = pid_listening_on_port(redis_port)
            if detected_redis_pid:
                stop_process_tree(detected_redis_pid, "Redis")

    print("Backend services stopped.")


def stop_existing_api_and_worker(*, uv: str, backend_root: Path, api_port: int) -> None:
    api_pid = pid_listening_on_port(api_port)
    if api_pid:
        stop_process_tree(api_pid, "FastAPI")
    if celery_worker_ready(uv, backend_root):
        shutdown_celery(uv, backend_root)
        time.sleep(2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the live clipping backend services.")
    parser.add_argument("--api-host", default="127.0.0.1", help="FastAPI bind host.")
    parser.add_argument("--api-port", type=int, default=8000, help="FastAPI bind port.")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port.")
    parser.add_argument("--no-redis", action="store_true", help="Do not start Redis even if it is not listening.")
    parser.add_argument("--visible", action="store_true", help="Open visible process windows on Windows.")
    parser.add_argument("--health-timeout", type=int, default=30, help="Seconds to wait for /health.")
    parser.add_argument("--no-follow", action="store_true", help="Start services and exit without streaming logs.")
    parser.add_argument("--keep-running", action="store_true", help="When watching logs, Ctrl+C exits without stopping services.")
    parser.add_argument("--restart", action="store_true", help="Stop existing FastAPI and Celery worker before starting.")
    parser.add_argument("--tail-lines", type=int, default=80, help="Recent log lines to print before following logs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    backend_root = script_dir.parent
    log_root = backend_root / "logs"
    run_dir = log_root / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Backend root: {backend_root}")
    print(f"Logs: {run_dir}")
    follow_paths = [run_dir / name for name in BACKEND_LOG_NAMES]

    uv = shutil.which("uv")
    if not uv:
        print("ERROR: uv was not found in PATH.", file=sys.stderr)
        return 1

    if args.restart:
        stop_existing_api_and_worker(uv=uv, backend_root=backend_root, api_port=args.api_port)

    started: dict[str, int | str] = {}
    latest_pids = load_latest_pids(log_root)

    if args.no_redis:
        started["redis"] = "skipped"
    elif tcp_open("127.0.0.1", args.redis_port):
        print(f"Redis is already listening on 127.0.0.1:{args.redis_port}")
        started["redis"] = "already-running"
    else:
        redis = shutil.which("redis-server")
        if not redis:
            print("WARNING: redis-server was not found in PATH. Start Redis manually or use --no-redis.")
            started["redis"] = "not-found"
        else:
            process = start_process(
                name="Redis",
                command=[redis, "--port", str(args.redis_port)],
                cwd=backend_root,
                stdout_path=run_dir / "redis.out.log",
                stderr_path=run_dir / "redis.err.log",
                visible=args.visible,
            )
            started["redis"] = process.pid
            time.sleep(1)

    previous_celery = latest_pids.get("celery")
    if celery_worker_ready(uv, backend_root):
        print("Celery worker is already responding to inspect ping")
        started["celery"] = "already-running"
    elif isinstance(previous_celery, int) and is_pid_running(previous_celery):
        print(f"Celery worker is already running with pid {previous_celery}")
        started["celery"] = "already-running"
    else:
        process = start_process(
            name="Celery worker",
            command=[
                uv,
                "run",
                "celery",
                "-A",
                "app.workers.celery_app.celery_app",
                "worker",
                "--loglevel=info",
                "--pool=solo",
            ],
            cwd=backend_root,
            stdout_path=run_dir / "celery.out.log",
            stderr_path=run_dir / "celery.err.log",
            visible=args.visible,
        )
        started["celery"] = process.pid

    if tcp_open(args.api_host, args.api_port):
        print(f"FastAPI is already listening on {args.api_host}:{args.api_port}")
        started["api"] = "already-running"
    else:
        process = start_process(
            name="FastAPI",
            command=[
                uv,
                "run",
                "uvicorn",
                "app.main:app",
                "--reload",
                "--host",
                args.api_host,
                "--port",
                str(args.api_port),
            ],
            cwd=backend_root,
            stdout_path=run_dir / "uvicorn.out.log",
            stderr_path=run_dir / "uvicorn.err.log",
            visible=args.visible,
        )
        started["api"] = process.pid

    pids_path = run_dir / "pids.json"
    pids_path.write_text(json.dumps(started, ensure_ascii=False, indent=2), encoding="utf-8")
    (log_root / "latest_backend_pids.json").write_text(
        json.dumps(started, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    health_url = f"http://{args.api_host}:{args.api_port}/health"
    print(f"Waiting for FastAPI health check: {health_url}")
    if wait_health(health_url, args.health_timeout):
        print(f"Backend is ready: {health_url}")
        print(f"API docs: http://{args.api_host}:{args.api_port}/docs")
        print(f"PID file: {pids_path}")
        if not args.no_follow:
            existing_logs = [path for path in follow_paths if path.exists()]
            previous_logs = latest_existing_logs(log_root, BACKEND_LOG_NAMES)
            interrupted = follow_logs(existing_logs + previous_logs, args.tail_lines)
            if interrupted and not args.keep_running:
                stop_backend_services(
                    started=started,
                    uv=uv,
                    backend_root=backend_root,
                    api_port=args.api_port,
                    redis_port=args.redis_port,
                    no_redis=args.no_redis,
                )
            elif interrupted:
                print("Stopped watching logs. Backend services are still running.")
        return 0

    print(f"WARNING: FastAPI did not pass health check. Check logs under {run_dir}", file=sys.stderr)
    print(f"PID file: {pids_path}")
    if not args.no_follow:
        interrupted = follow_logs(follow_paths + latest_existing_logs(log_root, BACKEND_LOG_NAMES), args.tail_lines)
        if interrupted and not args.keep_running:
            stop_backend_services(
                started=started,
                uv=uv,
                backend_root=backend_root,
                api_port=args.api_port,
                redis_port=args.redis_port,
                no_redis=args.no_redis,
            )
        elif interrupted:
            print("Stopped watching logs. Backend services are still running.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
