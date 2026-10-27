---
description: Start the led-notify daemon in the background
---

Start the led-notify daemon for this session. The script is `${CLAUDE_PLUGIN_ROOT}/scripts/led.py`. On macOS, mention that `/led-autostart` is usually better: it keeps the daemon running across logins and restarts it if it dies.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" status`. If it prints `running`, tell the user the daemon is already running and stop here.
2. If `~/.config/claude-led/config.json` does not exist or has no `address`, tell the user to run `/led-setup` first and stop here.
3. Start it detached, appending to the log:
   ```
   mkdir -p ~/.config/claude-led && nohup python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" serve >> ~/.config/claude-led/led.log 2>&1 < /dev/null & disown
   ```
4. Wait about 3 seconds, run `status` again and show the last lines of `~/.config/claude-led/led.log`. A `Connected to ...` line means it works. If the log shows repeated `BLE connect failed`, remind the user to close the phone app. On macOS the first start may show a *"LED Notify" would like to use Bluetooth* prompt that must be allowed.
