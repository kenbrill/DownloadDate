# DownloadDate

A macOS background daemon that keeps `~/Downloads` tidy by filing each new item
under a folder named for the day it arrived.

When a file or folder lands in the Downloads root, it is moved into a folder
named like `2026-10-10 Sat` (`<YYYY>-<MM>-<DD> <Day>`), so folders sort by date. The folder is created the first
time something arrives on a given day. Everything after that goes into the same
folder.

## What it does

```
~/Downloads/report.pdf          ← new file appears in the root
~/Downloads/2026-10-10 Sat/report.pdf  ← moved here
```

- Only the Downloads root is watched. Items already inside a subfolder are never
  touched.
- Partial downloads (`.crdownload`, `.download`, `.part`, `.partial`, `.tmp`) are
  skipped. The item is moved once the browser renames it to its final name.
- An item is moved only after its size stops changing, so a download or unzip
  still in progress is not split from its own folder.
- Hidden files such as `.DS_Store` are left alone.
- If a file with the same name is already in the day's folder, the new one is
  saved as `name (1).ext`, `name (2).ext`, and so on. Nothing is overwritten.

## Requirements

- macOS
- Python 3
- [`watchdog`](https://pypi.org/project/watchdog/) (`install_login_app.sh` installs this for you)

## Install

```bash
./install_login_app.sh
```

This creates a `.venv`, installs `watchdog` into it, builds
`~/Applications/DownloadDate Watcher.app`, and adds that app to Login Items.
The app starts the watcher in the background, and only if it isn't already
running.

The first time the watcher reads `~/Downloads`, macOS asks whether the app may
access Downloads. Open `~/Applications/DownloadDate Watcher.app` once and click
**Allow**. Until you do, the log shows `could not list ... Operation not permitted`.

## Usage

Run the watcher directly. With no arguments it watches `~/Downloads`. Pass one
or more folders to watch those instead:

```bash
python3 download_date_watcher.py                       # ~/Downloads
python3 download_date_watcher.py ~/Downloads ~/Desktop # several roots
```

Each folder is sorted independently. Items in `~/Desktop` go into
`~/Desktop/<date folder>/`, not into `~/Downloads`. Folders that don't exist
are skipped with a warning.

## Configuration

Edit the constants at the top of `download_date_watcher.py`:

| Constant | Default | Purpose |
| --- | --- | --- |
| `DEFAULT_DOWNLOAD_DIR` | `~/Downloads` | Folder watched when no path is given |
| `DATE_FORMAT` | `%Y-%m-%d %a` | Strftime pattern for day folder names |
| `TEMP_SUFFIXES` | `.crdownload`, `.download`, `.part`, `.partial`, `.tmp` | Partial-download names that are skipped |
| `STABLE_INTERVAL` / `STABLE_CHECKS` | `2` s / `2` | How long an item must hold still before it is moved |
| `MAX_STABLE_CHECKS` | `150` | Stops waiting after about 5 minutes and moves the item anyway |
| `LOGFILE_PATH` | `~/Library/Logs/download_date_watcher.log` | Where events are logged |

## Logs

Each move is one line:

```
2026-10-10 09:14:02  moved    /Users/you/Downloads/report.pdf -> /Users/you/Downloads/2026-10-10 Sat/report.pdf
```

The log rotates at 1 MiB and keeps five rolled copies. 

## Uninstall

Remove the app from System Settings → General → Login Items, then delete
`~/Applications/DownloadDate Watcher.app` and stop the running watcher:

```bash
pkill -f download_date_watcher.py
```

Files that were already moved stay where they are. The log files in
`~/Library/Logs/` are left in place.

## Notes

- Only items that arrive after the watcher starts are moved. Existing loose
  files in the root are not swept.
- Renaming an item that is already in the root does not move it. A browser
  finishing a download is the exception, because it renames the temp file to
  its final name.
