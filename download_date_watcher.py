#!/usr/bin/env python3
"""Sort new items in the Downloads root into a folder named for today's date.

When a file or folder appears directly in the Downloads root, it is moved into
Downloads/<YYYY>-<MM>-<DD> <Day>, for example Downloads/2026-10-10 Sat. That folder is
created if it does not exist yet. Only the root is watched: anything already
inside a subfolder is left alone.

Usage:
    python3 download_date_watcher.py [download_dir ...]
    Defaults to ~/Downloads if no paths are given. Each folder gets its own
    date subfolders inside it.

Logs one line per move to ~/Library/Logs/download_date_watcher.log and rotates
that file in place, keeping LOGFILE_BACKUP_COUNT rolled copies.
"""

import os
import sys
import time
import shutil
import logging
import threading
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

# strftime pattern for the date folders, e.g. "2026-10-10 Sat". The year-first
# form sorts chronologically in Finder.
DATE_FORMAT = "%Y-%m-%d %a"

# Browsers write partial downloads under these suffixes and rename them when
# finished. Moving one mid-download would break the download, so they are
# skipped until they are renamed to their final name.
TEMP_SUFFIXES = (".crdownload", ".download", ".part", ".partial", ".tmp")

# A new item is moved only once its size stops changing, so a download or an
# unzip that is still writing is not split from its own folder.
STABLE_INTERVAL = 2  # seconds between size checks
STABLE_CHECKS = 2  # consecutive unchanged checks required
MAX_STABLE_CHECKS = 150  # give up waiting after about 5 minutes and move anyway

POLL_SECONDS = 30  # rescan the root this often, in case an event is missed

LOGFILE_PATH = os.path.expanduser("~/Library/Logs/download_date_watcher.log")
LOGFILE_MAX_BYTES = 1 * 1024 * 1024  # roll over at 1 MiB
LOGFILE_BACKUP_COUNT = 5  # keep 5 rolled files, so at most ~6 MiB of history

LOG_FORMAT = logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

log = logging.getLogger(__name__)


def configure_logging(log_path=LOGFILE_PATH):
    """Log to a size-rotated file and to the terminal."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=LOGFILE_MAX_BYTES,
        backupCount=LOGFILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    stream_handler = logging.StreamHandler()
    for handler in (file_handler, stream_handler):
        handler.setFormatter(LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def is_date_folder_name(name):
    """True for names this tool creates, such as 2026-10-10 Sat."""
    try:
        datetime.strptime(name, DATE_FORMAT)
    except ValueError:
        return False
    return True


def is_temp_or_hidden(name):
    """Hidden files such as .DS_Store, and browser partial downloads."""
    return name.startswith(".") or name.lower().endswith(TEMP_SUFFIXES)


def is_wanted(path):
    """Whether a new root entry should be sorted at all."""
    if is_temp_or_hidden(path.name):
        return False
    if path.is_dir() and is_date_folder_name(path.name):  # never sort a date folder into itself
        return False
    return True


def signature(path):
    """A value that changes whenever the file or anything inside the folder changes."""
    if not path.is_dir():
        return path.stat().st_size
    total = 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            count += 1
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass  # vanished between listing and stat
    return (count, total)


def wait_until_stable(path):
    """Return once the item has stopped changing, or after the wait cap."""
    last = None
    unchanged = 0
    for _ in range(MAX_STABLE_CHECKS):
        current = signature(path)
        if current == last:
            unchanged += 1
            if unchanged >= STABLE_CHECKS:
                return
        else:
            last = current
            unchanged = 0
        time.sleep(STABLE_INTERVAL)
    log.warning("still changing after wait cap, moving anyway: %s", path)


def unique_destination(dest):
    """Return dest, or dest with a ' (n)' suffix if that name is already taken."""
    if not os.path.lexists(dest):
        return dest
    if dest.is_dir():
        stem, suffix = dest.name, ""
    else:
        stem, suffix = dest.stem, dest.suffix
    counter = 1
    while True:
        candidate = dest.with_name(f"{stem} ({counter}){suffix}")
        if not os.path.lexists(candidate):
            return candidate
        counter += 1


class DownloadDateHandler(FileSystemEventHandler):
    """Files every new entry that appears in the Downloads root.

    The watcher is non-recursive, and on macOS FSEvents does not report
    directory creation at that level, so per-event paths can't be trusted to
    catch new folders. Instead, any event touching the root (and a periodic
    poll from main) rescans the root's entries. An entry is new when its inode
    was not present at the previous scan. Inodes mean a plain rename of an item
    already in the root is not new, while a browser renaming its temp file to
    the final name is.
    """

    def __init__(self, download_dir):
        super().__init__()
        self.root = Path(os.path.abspath(download_dir))
        self._known = set()
        self._lock = threading.Lock()
        self.scan(initial=True)

    def on_any_event(self, event):
        self.scan()

    def scan(self, initial=False):
        with self._lock:
            try:
                entries = list(os.scandir(self.root))
            except OSError as e:
                log.warning("could not list %s: %s", self.root, e)
                return

            settled = set()
            fresh = []
            for entry in entries:
                # Partial downloads stay out of `settled`, so the rename to the
                # final name shows up as new.
                if is_temp_or_hidden(entry.name):
                    continue
                try:
                    ino = entry.inode()
                except OSError:
                    continue
                settled.add(ino)
                if ino not in self._known:
                    fresh.append(Path(entry.path))
            self._known = settled

        if initial:
            return
        for path in fresh:
            if is_wanted(path):
                threading.Thread(target=self._process, args=(path,), daemon=True).start()

    def _process(self, path):
        try:
            wait_until_stable(path)
            if not os.path.lexists(path):
                return  # moved or removed while we were waiting
            target_dir = self.root / date.today().strftime(DATE_FORMAT)
            target_dir.mkdir(exist_ok=True)
            dest = unique_destination(target_dir / path.name)
            shutil.move(str(path), str(dest))
            log.info("moved    %s -> %s", path, dest)
        except OSError as e:
            log.warning("could not move %s: %s", path, e)


def main():
    configure_logging()

    requested = [os.path.expanduser(d) for d in (sys.argv[1:] or [DEFAULT_DOWNLOAD_DIR])]
    handlers = []
    observer = Observer()
    for download_dir in requested:
        if not os.path.isdir(download_dir):
            log.warning("skipping non-existent directory: %s", download_dir)
            continue
        handler = DownloadDateHandler(download_dir)
        observer.schedule(handler, download_dir, recursive=False)
        handlers.append(handler)
        log.info("watching  %s", download_dir)

    if not handlers:
        log.error("nothing to watch, exiting")
        return 1

    observer.start()

    try:
        ticks = 0
        while True:
            time.sleep(1)
            ticks += 1
            if ticks % POLL_SECONDS == 0:
                for handler in handlers:
                    handler.scan()  # backstop in case the observer misses an event
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
