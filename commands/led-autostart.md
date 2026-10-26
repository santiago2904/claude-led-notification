---
description: (macOS) Start the led-notify daemon at login with a LaunchAgent; "/led-autostart remove" undoes it
argument-hint: [remove]
---

Manage the led-notify LaunchAgent on macOS. Arguments: `$ARGUMENTS`. If `uname` is not `Darwin`, tell the user this command is macOS-only (on Linux suggest a systemd user service running `python3 ~/.config/claude-led/led.py serve`) and stop.

Paths: label `com.claude-led.daemon`, plist `~/Library/LaunchAgents/com.claude-led.daemon.plist`.

## If the argument is `remove`

Run `launchctl bootout gui/$(id -u)/com.claude-led.daemon` (ignore "not loaded" errors), delete the plist and `~/.config/claude-led/led.py`, and confirm with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" status`.

## Otherwise, install

1. Check `~/.config/claude-led/config.json` exists with an `address`; if not, tell the user to run `/led-setup` first.
2. Copy the script to a stable path, because the plugin directory changes on every update: `cp "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" ~/.config/claude-led/led.py`. Tell the user to re-run `/led-autostart` after updating the plugin.
3. Find the absolute Python path (launchd does not use your shell PATH): `python3 -c "import sys; print(sys.executable)"`. Verify bleak with that exact binary: `<PYTHON> -c "import bleak"`.
4. Stop a manually started daemon: `pkill -f "led.py serve"`.
5. Write `~/Library/LaunchAgents/com.claude-led.daemon.plist`, replacing `<PYTHON>` and `<HOME>` with absolute paths:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.claude-led.daemon</string>
     <key>ProgramArguments</key>
     <array>
       <string><PYTHON></string>
       <string><HOME>/.config/claude-led/led.py</string>
       <string>serve</string>
     </array>
     <key>RunAtLoad</key><true/>
     <key>KeepAlive</key><true/>
     <key>ThrottleInterval</key><integer>30</integer>
     <key>StandardOutPath</key><string><HOME>/.config/claude-led/led.log</string>
     <key>StandardErrorPath</key><string><HOME>/.config/claude-led/led.log</string>
   </dict>
   </plist>
   ```
6. Load it: `launchctl bootout gui/$(id -u)/com.claude-led.daemon 2>/dev/null; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claude-led.daemon.plist`.
7. Wait about 5 seconds, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" status` and show the last lines of `~/.config/claude-led/led.log`.

## Bluetooth permission

Explain this to the user: when started from a terminal, macOS attributes Bluetooth access to the terminal app. Under launchd there is no terminal, so macOS asks for (or silently denies) permission for the Python binary itself. If the log shows no `Connected to ...` line, Bluetooth errors, or the process keeps restarting:

- Open **System Settings → Privacy & Security → Bluetooth** and allow the Python entry if it appears, or add it with **+** (in the file dialog press ⌘⇧G and paste the path from step 3; for Homebrew/python.org framework builds you may need the `Python.app` inside the framework's `Resources` folder).
- Then restart it: `launchctl kickstart -k gui/$(id -u)/com.claude-led.daemon`.
- If it still fails, fall back to `/led-autostart remove` and `/led-start` from a terminal that already has Bluetooth permission.
