"""One log file per play, kept for three days.

Files are opened for append. Nothing is truncated on startup. A file whose
mtime is older than three days is removed the next time a play starts.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR_NAME = "logs"
KEEP_DAYS = 3
PLAY_PREFIX = "play-"


def start_play_log(
    log_dir: Path | None = None,
    now: datetime | None = None,
    keep_days: int = KEEP_DAYS,
) -> Path:
    """Open this play's log and delete play logs older than keep_days."""
    directory = Path(log_dir) if log_dir is not None else _default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    moment = now or datetime.now()
    removed = cleanup_old_logs(directory, moment - timedelta(days=keep_days))

    path = directory / f"{PLAY_PREFIX}{moment.strftime('%Y%m%d-%H%M%S')}.log"
    handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    named = logging.getLogger("GameLogicLogger")
    named.setLevel(logging.DEBUG)
    named.propagate = True

    logging.info("Play log %s (removed %s log(s) older than %s days)", path, removed, keep_days)
    (directory / "LATEST").write_text(f"{path}\n", encoding="utf-8")
    return path


def cleanup_old_logs(log_dir: Path, older_than: datetime) -> int:
    """Delete play-*.log files last modified before older_than. Returns the count."""
    if not log_dir.is_dir():
        return 0
    cutoff = older_than.timestamp()
    removed = 0
    for path in log_dir.glob(f"{PLAY_PREFIX}*.log"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def _default_log_dir() -> Path:
    """Return the log directory path.
    
    Priority:
    1. FUNGI_LOG_DIR environment variable if set
    2. ./logs in the current working directory
    
    This ensures logs are written to the working directory, not the package directory.
    """
    env_log_dir = os.environ.get("FUNGI_LOG_DIR")
    if env_log_dir:
        return Path(env_log_dir)
    return Path.cwd() / LOG_DIR_NAME
