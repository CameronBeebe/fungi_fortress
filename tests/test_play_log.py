"""Play logs append, and files older than three days are removed."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from fungi_fortress.play_log import cleanup_old_logs, start_play_log


def test_old_play_logs_are_removed_and_new_ones_append(tmp_path: Path):
    import os

    old = tmp_path / "play-20000101-000000.log"
    recent = tmp_path / "play-20990101-000000.log"
    old.write_text("old\n", encoding="utf-8")
    recent.write_text("recent\n", encoding="utf-8")
    ancient = datetime(2000, 1, 2).timestamp()
    fresh = datetime(2099, 1, 2).timestamp()
    os.utime(old, (ancient, ancient))
    os.utime(recent, (fresh, fresh))

    removed = cleanup_old_logs(tmp_path, datetime(2000, 1, 5))
    assert removed == 1
    assert not old.exists()
    assert recent.read_text(encoding="utf-8") == "recent\n"

    moment = datetime(2026, 9, 28, 18, 30, 0)
    path = start_play_log(tmp_path, now=moment, keep_days=3)
    try:
        logging.getLogger("GameLogicLogger").info("dwarf took move")
        for handler in logging.getLogger().handlers:
            handler.flush()
        text = path.read_text(encoding="utf-8")
        assert "dwarf took move" in text
        with path.open("a", encoding="utf-8") as handle:
            handle.write("still here\n")
        assert "still here" in path.read_text(encoding="utf-8")
        assert (tmp_path / "LATEST").read_text(encoding="utf-8").strip() == str(path)
    finally:
        root = logging.getLogger()
        for handler in list(root.handlers):
            if isinstance(handler, logging.FileHandler) and str(tmp_path) in getattr(handler, "baseFilename", ""):
                handler.close()
                root.removeHandler(handler)
