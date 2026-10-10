#!/usr/bin/env python3
"""One-time sort of items already in the Downloads root into date folders.

Each item goes into a folder named for the day it was added to Downloads
(Finder's "Date Added"), the same format the watcher uses. Items without that
value fall back to their modification date.

Runs as a dry run unless --apply is given, so you can review the plan first.

Usage:
    python3 sort_existing.py [download_dir]          # show the plan
    python3 sort_existing.py [download_dir] --apply  # move the items
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from download_date_watcher import DATE_FORMAT, DEFAULT_DOWNLOAD_DIR, is_date_folder_name, is_temp_or_hidden, unique_destination


def date_added(path):
    """The local date the item was added to Downloads, or None if macOS has no record."""
    try:
        out = subprocess.run(
            ["mdls", "-raw", "-name", "kMDItemDateAdded", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not out or out == "(null)":
        return None
    try:
        added = datetime.strptime(out, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None
    return added.astimezone().date()


def item_date(path):
    """Date Added if macOS recorded it, otherwise the modification date."""
    added = date_added(path)
    if added:
        return added
    return datetime.fromtimestamp(os.lstat(path).st_mtime).date()


def main():
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply = "--apply" in sys.argv[1:]
    root = Path(os.path.abspath(os.path.expanduser(args[0] if args else DEFAULT_DOWNLOAD_DIR)))

    moves = []
    for entry in sorted(root.iterdir()):
        if is_temp_or_hidden(entry.name):
            continue
        if entry.is_dir() and is_date_folder_name(entry.name):
            continue  # already a date folder
        folder = item_date(entry).strftime(DATE_FORMAT)
        dest = unique_destination(root / folder / entry.name)
        moves.append((entry, dest))

    for src, dest in moves:
        print(f"{src.name}  ->  {dest.parent.name}/{dest.name}")
    print(f"\n{len(moves)} item(s) {'moved' if apply else 'would be moved'}.")

    if not apply:
        print("Dry run only. Re-run with --apply to move them.")
        return 0

    for src, dest in moves:
        dest.parent.mkdir(exist_ok=True)
        shutil.move(str(src), str(dest))
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
