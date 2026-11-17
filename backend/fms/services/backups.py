"""Backups of the hub's database.

- Taken with SQLite's online backup API, so a backup is consistent even while the
  FMS is in use, and checked with `PRAGMA integrity_check` before it is kept.
- Automatic: once a day (checked hourly while the hub runs); the newest 30 are kept.
- Optional second copy in a folder the owner chooses (a USB drive, a Google Drive
  folder...), so a dead laptop disk doesn't take the backups with it.
- Restore keeps the CURRENT owner password and device logins (an old backup would
  otherwise log the owner out), and saves a copy of the current data first.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from alembic.script import ScriptDirectory

from ..db import alembic_config, run_migrations
from ..errors import Invalid, NotFound

log = logging.getLogger("fms.backups")

KEEP = 30
AUTO_EVERY = timedelta(hours=24)
NAME_RE = re.compile(r"^fms-\d{8}-\d{6}(-[a-z-]+)?\.db$")
REQUIRED_TABLES = {"workers", "production_entries", "rates", "worker_types", "alembic_version"}
AUTH_TABLES = ("owner_account", "device_sessions")


@dataclass(frozen=True)
class BackupFile:
    name: str
    path: Path
    size: int
    created_at: datetime
    kind: str  # "auto", "manual" or "before-restore"


def backup_dir(data_dir: Path) -> Path:
    path = data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _kind(name: str) -> str:
    match = NAME_RE.match(name)
    return (match.group(1) or "-auto")[1:] if match else "unknown"


def list_backups(data_dir: Path) -> list[BackupFile]:
    files = []
    for path in backup_dir(data_dir).glob("fms-*.db"):
        if not NAME_RE.match(path.name):
            continue
        stamp = datetime.strptime(path.name[4:19], "%Y%m%d-%H%M%S")
        files.append(BackupFile(path.name, path, path.stat().st_size, stamp, _kind(path.name)))
    return sorted(files, key=lambda f: f.created_at, reverse=True)


def get_backup(data_dir: Path, name: str) -> BackupFile:
    for backup in list_backups(data_dir):
        if backup.name == name:  # only names we created: no path tricks
            return backup
    raise NotFound("Backup not found", name=name)


def _integrity_ok(db_path: Path) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def create_backup(
    db_path: Path, data_dir: Path, kind: str = "auto", copy_dir: str = ""
) -> BackupFile:
    """Copy the live database into backups/ (and the optional extra folder)."""
    folder = backup_dir(data_dir)
    # Always later than the newest backup: two in the same second must not overwrite each
    # other, and a new one must never take an older (already pruned) time and be pruned.
    when = datetime.now().replace(microsecond=0)
    existing = list_backups(data_dir)
    if existing and existing[0].created_at >= when:
        when = existing[0].created_at + timedelta(seconds=1)
    stamp = when.strftime("%Y%m%d-%H%M%S")
    name = f"fms-{stamp}.db" if kind == "auto" else f"fms-{stamp}-{kind}.db"
    final = folder / name
    temp = folder / f".{name}.partial"

    source = sqlite3.connect(db_path)
    target = sqlite3.connect(temp)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    if not _integrity_ok(temp):
        temp.unlink(missing_ok=True)
        raise RuntimeError("The backup failed its integrity check")
    os.replace(temp, final)
    log.info("Backup created: %s", final)

    if copy_dir:
        copy_to_folder(final, copy_dir)
    prune(data_dir)
    return get_backup(data_dir, name)


def copy_to_folder(backup: Path, copy_dir: str) -> None:
    """Best effort: a missing USB drive must never stop the main backup."""
    try:
        target = Path(copy_dir)
        if not target.is_dir():
            raise FileNotFoundError(f"Folder not found: {copy_dir}")
        shutil.copy2(backup, target / backup.name)
        log.info("Backup copied to %s", target)
    except OSError as exc:
        log.warning("Could not copy the backup to %s: %s", copy_dir, exc)


def prune(data_dir: Path, keep: int = KEEP) -> None:
    for old in list_backups(data_dir)[keep:]:
        old.path.unlink(missing_ok=True)


def due(data_dir: Path, now: datetime | None = None) -> bool:
    autos = [b for b in list_backups(data_dir) if b.kind == "auto"]
    return not autos or (now or datetime.now()) - autos[0].created_at >= AUTO_EVERY


# ------------------------------------------------------------------ restore
def remove_with_sidecars(path: Path) -> None:
    """Delete a database file and the -wal/-shm files SQLite may have created next to it."""
    for suffix in ("", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def known_revisions() -> set[str]:
    script = ScriptDirectory.from_config(alembic_config())
    return {rev.revision for rev in script.walk_revisions()}


def check_backup_file(path: Path) -> None:
    """Make sure a file really is a usable FMS backup before restoring it."""
    version = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            tables = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            if "alembic_version" in tables:
                row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                version = row[0] if row else None
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise Invalid("This file isn't an FMS backup", reason="not_a_backup") from exc
    if not tables >= REQUIRED_TABLES:
        raise Invalid("This file isn't an FMS backup", reason="not_a_backup")
    if not ok:
        raise Invalid("This backup is damaged and can't be restored", reason="backup_damaged")
    if version not in known_revisions():
        # Made by a newer FMS (or tampered with): this version can't safely open it.
        raise Invalid(
            "This backup was made by a newer version of FMS. Update FMS on the laptop first.",
            reason="backup_too_new",
            version=version,
        )


def _carry_over_logins(restored: Path, live: Path) -> None:
    """Put the current password and device logins into the restored database."""
    conn = sqlite3.connect(restored)
    try:
        conn.execute("ATTACH DATABASE ? AS live", (str(live),))
        with conn:
            for table in AUTH_TABLES:
                cols = ", ".join(
                    f'"{row[1]}"' for row in conn.execute(f"PRAGMA live.table_info({table})")
                )
                conn.execute(f"DELETE FROM main.{table}")
                conn.execute(f"INSERT INTO main.{table} ({cols}) SELECT {cols} FROM live.{table}")
        conn.execute("DETACH DATABASE live")
    finally:
        conn.close()


def prepare_restore(source: Path, db_path: Path, data_dir: Path) -> Path:
    """Validate a backup and turn it into a ready-to-swap copy (upgraded, logins kept)."""
    staged = data_dir / "restore-staged.db"
    remove_with_sidecars(staged)
    try:
        check_backup_file(source)
        shutil.copy2(source, staged)
        run_migrations(f"sqlite:///{staged.as_posix()}")  # an older backup is upgraded
        _carry_over_logins(staged, db_path)
    except BaseException:
        remove_with_sidecars(staged)
        raise
    finally:
        # Opening the file read-only can still create -wal/-shm next to it.
        for suffix in ("-wal", "-shm"):
            Path(f"{source}{suffix}").unlink(missing_ok=True)
    return staged


def swap_in(staged: Path, db_path: Path) -> None:
    """Replace the live database file. Call only after all connections are closed."""
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    os.replace(staged, db_path)
    log.info("Database restored from backup")


# ------------------------------------------------------------------ schedule
class BackupScheduler:
    """Checks every hour (and shortly after start) whether a daily backup is due."""

    def __init__(
        self, db_path: Path, data_dir: Path, copy_dir: Callable[[], str], every: float = 3600
    ):
        self.db_path, self.data_dir, self.copy_dir, self.every = db_path, data_dir, copy_dir, every
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="fms-backups", daemon=True)
        self.lock = threading.Lock()  # shared with restores
        self.last_error: str | None = None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def tick(self) -> bool:
        """Take the daily backup if it's due. Returns True if one was taken."""
        with self.lock:
            if not due(self.data_dir):
                return False
            try:
                create_backup(self.db_path, self.data_dir, "auto", self.copy_dir())
                self.last_error = None
                return True
            except Exception as exc:  # noqa: BLE001 - keep the scheduler alive, report it
                self.last_error = str(exc)
                log.exception("Automatic backup failed")
                return False

    def _run(self) -> None:
        if self._stop.wait(30):  # let start-up finish first
            return
        while True:
            self.tick()
            if self._stop.wait(self.every):
                return
