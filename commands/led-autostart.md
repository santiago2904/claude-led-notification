---
description: Run the led-notify daemon now and at every login (macOS, Linux, Windows); "/led-autostart remove" undoes it
argument-hint: [remove]
---

Arguments: `$ARGUMENTS`. Use `python3`, or `python` on Windows if `python3` isn't available.

- If the argument is `remove`, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" autostart remove`.
- Otherwise, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" autostart`.

After installing:

1. Wait about 5 seconds.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" status` and show the last lines of `~/.config/claude-led/led.log`. A `Connected to ...` line means it works.

Explain to the user what was installed:

- **macOS:** a LaunchAgent (`~/Library/LaunchAgents/com.claude-led.daemon.plist`). It runs Python inside a small `LED Notify.app` in `~/.config/claude-led/`, so no terminal is needed. The first time, macOS may ask *"LED Notify" would like to use Bluetooth*; they must allow it.
- **Linux:** a systemd user service (`~/.config/systemd/user/led-notify.service`). Check it with `systemctl --user status led-notify`.
- **Windows:** `led-notify.cmd` in the Startup folder, which runs the daemon with `pythonw` (no console window).

On every platform, the daemon restarts only after a crash, so `/led-stop` still works.

The script is copied to `~/.config/claude-led/led.py`. Re-run `/led-autostart` after updating the plugin to pick up the new version.
