---
description: Stop the led-notify daemon
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" stop` (use `python` on Windows if `python3` isn't available). The daemon turns the strip off and exits, and the command prints `stopped`.

If autostart is installed, the daemon stays stopped until the next login or `/led-start`. To disable autostart entirely, use `/led-autostart remove`.
