---
description: Change a preset color, e.g. /led-color done 0 255 0
argument-hint: <thinking|done|attention> <R G B | off | color R G B | flash R G B SECONDS>
---

Change a led-notify preset. Arguments: `$ARGUMENTS`

Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" preset $ARGUMENTS
```

- `R G B` keeps the preset's type: `done` and `attention` stay flashes with the same duration, `thinking` stays a steady color.
- `off` disables the preset (for example `/led-color thinking off`).
- A full command (`color R G B` or `flash R G B SECONDS`) replaces the preset as-is.

If no arguments were given, show the current presets from `~/.config/claude-led/config.json` (defaults: thinking `color 0 0 40`, done `flash 255 0 0 3`, attention `flash 255 120 0 3`) and the usage above. Report the new value. The daemon reads presets on every event, so no restart is needed.
