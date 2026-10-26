---
description: Stop the led-notify daemon
---

Stop the led-notify daemon. The script is `${CLAUDE_PLUGIN_ROOT}/scripts/led.py`.

1. On macOS, if `~/Library/LaunchAgents/com.claude-led.daemon.plist` exists, the daemon is managed by launchd and would restart on its own. Ask the user whether to stop it just for this session (`launchctl bootout gui/$(id -u)/com.claude-led.daemon`; it comes back at next login) or remove autostart entirely (`/led-autostart remove`).
2. Otherwise run `pkill -f "led.py serve"`. The daemon turns the strip off and removes its socket on exit.
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" status` and confirm it prints `stopped`.
