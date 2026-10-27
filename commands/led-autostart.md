---
description: (macOS) Run the led-notify daemon now and at every login; "/led-autostart remove" undoes it
argument-hint: [remove]
---

Arguments: `$ARGUMENTS`

- If the argument is `remove`, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" autostart remove`.
- Otherwise, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" autostart`.

On Linux the script says autostart is macOS-only. Suggest a systemd user service running `python3 <path>/led.py serve` instead.

After installing:

1. Wait about 5 seconds.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" status` and show the last lines of `~/.config/claude-led/led.log`. A `Connected to ...` line means it works.

Explain to the user:

- **How it runs.** The daemon is a LaunchAgent (`com.claude-led.daemon`). It runs Python inside a small `LED Notify.app` in `~/.config/claude-led/`, so it needs no terminal open. launchd restarts it if it dies.
- **Bluetooth permission.** The first time, macOS may ask *"LED Notify" would like to use Bluetooth*. They must allow it. If they missed the prompt, they can enable it in System Settings → Privacy & Security → Bluetooth.
- **Plugin updates.** The script is copied to `~/.config/claude-led/led.py`. Re-run `/led-autostart` after updating the plugin to pick up the new version.
