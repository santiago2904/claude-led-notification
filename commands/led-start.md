---
description: Start the led-notify daemon in the background
---

Start the led-notify daemon for this session. The script is `${CLAUDE_PLUGIN_ROOT}/scripts/led.py`. Use `python3`, or `python` on Windows if `python3` isn't available.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" start`. It prints `Already running.`, `running`, or an error such as `No device configured` (then tell the user to run `/led-setup`).
2. Show the last lines of `~/.config/claude-led/led.log`. A `Connected to ...` line means it reached the strip. Repeated `BLE connect failed` usually means the phone app is still connected to the strip or the strip is off. On macOS the first start may show a *"LED Notify" would like to use Bluetooth* prompt that must be allowed.
3. Mention that `/led-autostart` keeps the daemon running across logins on macOS, Linux and Windows.
