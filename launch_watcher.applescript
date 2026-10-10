-- Starts download_date_watcher.py in the background unless it is already running.
-- Compiled into "DownloadDate Watcher.app" by install_login_app.sh.

property projectDir : "/Users/kbrill/theVault/PythonProjects/DownloadDate"

on run
	-- The [d] keeps pgrep from matching its own shell command line.
	set startCommand to "cd " & quoted form of projectDir & " && pgrep -f '[d]ownload_date_watcher.py' >/dev/null || nohup ./.venv/bin/python3 download_date_watcher.py >/dev/null 2>&1 &"
	do shell script startCommand
end run
