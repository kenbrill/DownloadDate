-- Starts download_date_watcher.py in the background unless it is already running.
-- install_login_app.sh replaces __PROJECT_DIR__ with the real project path
-- and compiles this into "DownloadDate Watcher.app".

property projectDir : "__PROJECT_DIR__"

on run
	-- The [d] keeps pgrep from matching its own shell command line.
	set startCommand to "cd " & quoted form of projectDir & " && pgrep -f '[d]ownload_date_watcher.py' >/dev/null || nohup ./.venv/bin/python3 download_date_watcher.py >/dev/null 2>&1 &"
	do shell script startCommand
	-- Quit once the watcher is running. Left open, this applet blocks shutdown
	-- and macOS asks you to force quit it. The watcher keeps running after this.
	quit
end run
