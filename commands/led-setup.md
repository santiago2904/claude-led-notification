---
description: Interactive setup — find your BLE LED controller, detect its protocol and test it
---

Guide the user through setting up led-notify, one step at a time. The script is `${CLAUDE_PLUGIN_ROOT}/scripts/led.py`. Stop and explain if any step fails.

1. **Python.** Run `python3 --version`. It must be 3.9 or newer.
2. **bleak.** Run `python3 -c "import bleak"`. If it fails, ask the user before installing, then run `python3 -m pip install --user bleak` (on a Homebrew/PEP 668 Python suggest `pipx`/a venv or `python3 -m pip install --user --break-system-packages bleak`, and let the user choose).
3. **Free the controller.** Tell the user to fully close the phone app (BojiaLED, duoCo Strip, Happy Lighting, etc.) and turn off the phone's Bluetooth if needed: most controllers accept only one connection at a time. If the daemon is running (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" status` prints `running`), stop it first with `pkill -f "led.py serve"`.
4. **Scan.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" scan`. On macOS the first run may trigger a Bluetooth permission prompt for the terminal app — tell the user to accept it and re-run. If it exits with code 134 and no output, the terminal app has no Bluetooth permission (Warp and Terminal.app cannot get it): tell the user to run Claude Code from iTerm2 for setup. Show the list and ask the user which device is their LED controller (names like `BJ_LED`, `ELK-BLEDOM`, `Triones`, `SP110E`, `QHM-xxxx` are good hints; the strongest signal is usually the right one).
5. **Probe.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" probe <ADDRESS>`. Before running, tell the user to watch the strip: each candidate protocol is numbered and turns the strip red for 2 seconds. Then ask which number turned the strip red, and run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" probe <ADDRESS> "<PROTOCOL NAME>"` to save it. If nothing matched or nothing lit up, point the user to CONTRIBUTING.md (capturing the phone app's BLE traffic) — do not guess a protocol.
6. **Test.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/led.py" test` and confirm with the user that the strip went red for 2 seconds and then off.
7. Tell the user the config is saved in `~/.config/claude-led/config.json` and that the next step is `/led-start` (or `/led-autostart` on macOS to start it at login).
