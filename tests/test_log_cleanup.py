"""Tests for log cleanup — retention, file deletion, error handling."""

import os
import time
from pathlib import Path

import pytest

from proxmox_discord_notifier.config import Settings
from proxmox_discord_notifier.log_cleanup import cleanup_old_logs

# ── helpers ─────────────────────────────────────────────────────────


def _touch(path: Path, days_old: int = 0):
    """Create an empty file and set its mtime to `days_old` days ago."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("mock log content")
    old_time = time.time() - (days_old * 86400)
    os.utime(str(path), (old_time, old_time))


# ── tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retention_disabled_zero_days(tmp_path):
    """log_retention_days=0 → nothing deleted, returns 0."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _touch(log_dir / "old.log", days_old=100)

    settings = Settings(
        log_directory=log_dir,
        log_retention_days=0,
    )
    import proxmox_discord_notifier.log_cleanup as lc
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lc, "settings", settings)
        deleted = await cleanup_old_logs()
        assert deleted == 0
    assert (log_dir / "old.log").exists()


@pytest.mark.asyncio
async def test_cleanup_deletes_old_files(tmp_path):
    """Files older than retention are deleted; recent ones survive."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _touch(log_dir / "old.log", days_old=60)
    _touch(log_dir / "recent.log", days_old=5)

    settings = Settings(
        log_directory=log_dir,
        log_retention_days=30,
    )
    import proxmox_discord_notifier.log_cleanup as lc
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lc, "settings", settings)
        deleted = await cleanup_old_logs()
        assert deleted == 1
    assert not (log_dir / "old.log").exists()
    assert (log_dir / "recent.log").exists()


@pytest.mark.asyncio
async def test_cleanup_nonexistent_directory(tmp_path):
    """When log_directory doesn't exist, returns 0 gracefully."""
    missing = tmp_path / "does_not_exist"
    settings = Settings(
        log_directory=missing,
        log_retention_days=30,
    )
    import proxmox_discord_notifier.log_cleanup as lc
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lc, "settings", settings)
        deleted = await cleanup_old_logs()
        assert deleted == 0


@pytest.mark.asyncio
async def test_cleanup_skips_non_log_files(tmp_path):
    """Only *.log files are considered for deletion."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _touch(log_dir / "old.log", days_old=60)
    _touch(log_dir / "readme.txt", days_old=60)

    settings = Settings(
        log_directory=log_dir,
        log_retention_days=30,
    )
    import proxmox_discord_notifier.log_cleanup as lc
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lc, "settings", settings)
        deleted = await cleanup_old_logs()
        assert deleted == 1
    assert not (log_dir / "old.log").exists()
    assert (log_dir / "readme.txt").exists()


@pytest.mark.asyncio
async def test_cleanup_permission_error_handled(tmp_path):
    """When unlink fails (OSError), the file is skipped and counts as not deleted."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _touch(log_dir / "old.log", days_old=60)
    _touch(log_dir / "old2.log", days_old=60)

    original_unlink = Path.unlink

    def failing_unlink(self, *args, **kwargs):
        if self.name == "old.log":
            raise OSError("Permission denied")
        return original_unlink(self, *args, **kwargs)

    settings = Settings(
        log_directory=log_dir,
        log_retention_days=30,
    )
    import proxmox_discord_notifier.log_cleanup as lc
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lc, "settings", settings)
        mp.setattr(Path, "unlink", failing_unlink)
        deleted = await cleanup_old_logs()
        assert deleted == 1  # only old2.log was deleted
    # old.log survived the OSError
    assert (log_dir / "old.log").exists()
    assert not (log_dir / "old2.log").exists()
