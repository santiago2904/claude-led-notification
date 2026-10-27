# led-notify

A [Claude Code](https://code.claude.com) plugin that makes a cheap Bluetooth LED strip react to Claude Code:

| Event | Preset | Default |
| --- | --- | --- |
| You send a prompt (`UserPromptSubmit`) | `thinking` | dim blue (can be set to `off`) |
| Claude finishes (`Stop`) | `done` | red for 3 s, then off |
| Claude needs you (`Notification`) | `attention` | orange for 3 s, then off |

<!-- TODO: add a GIF or photo of the strip in action as docs/demo.gif and uncomment:
![led-notify demo](docs/demo.gif)
-->
> 📷 *Demo GIF coming soon.*

*[Leer en español](#español)*

## How it works

A small daemon (`scripts/led.py serve`) keeps the BLE connection to the controller open and listens on `127.0.0.1:47821` (TCP, so it works the same on macOS, Linux and Windows; change it with `CLAUDE_LED_PORT`). Claude Code hooks send it one-line commands. If the daemon isn't running, the hooks do nothing: they print nothing, exit 0, and give up after 0.5 s, so they can never block or break Claude Code.

The controller's BLE protocol is **not hard-coded for any specific model**. `/led-setup` runs `probe`, which tries the protocols it knows (ELK-BLEDOM, ELK-BLEDOM v2, Triones, SP110E, BJ_LED) and saves the one that lights your strip. If none works, see [CONTRIBUTING.md](CONTRIBUTING.md) to add yours.

## Requirements

- macOS, Linux (BlueZ) or Windows 10+, with Bluetooth LE
- Python 3.9+ available as `python3` (or `python` on Windows)
- On Windows, Claude Code with Git Bash (its default hook shell)
- [bleak](https://github.com/hbldh/bleak): `python3 -m pip install --user bleak`
- A BLE RGB LED controller (see [Tested controllers](#tested-controllers))

## Install

In Claude Code:

```
/plugin marketplace add santiago2904/claude-led-notification
/plugin install led-notify@led-notify
```

## Setup

1. Close the controller's phone app (it holds the only BLE connection).
2. Run `/led-setup`: checks Python and bleak, scans, lets you pick the device, probes the protocol and runs a test.
3. Run `/led-autostart`: the daemon starts now and at every login, with no terminal needed. It uses a LaunchAgent on macOS, a systemd user service on Linux and the Startup folder on Windows. For a one-off, run `/led-start` instead.

| Command | What it does |
| --- | --- |
| `/led-setup` | Guided setup: scan, probe, test |
| `/led-start` | Start the daemon in the background |
| `/led-stop` | Stop the daemon |
| `/led-color <preset> <R G B \| off>` | Change a preset color |
| `/led-autostart [remove]` | Run the daemon now and at every login (macOS, Linux, Windows) |

Plugin commands may also appear namespaced, e.g. `/led-notify:led-setup`.

Config and log live in `~/.config/claude-led/` (`config.json`, `led.log`), so plugin updates never wipe them.

## Customize colors

```
/led-color done 0 255 0          # green flash when finished (keeps the 3 s duration)
/led-color attention 255 0 255   # magenta flash
/led-color thinking off          # no light while thinking
/led-color done flash 0 0 255 5  # full command: blue for 5 s
```

Or edit `~/.config/claude-led/config.json` directly:

```json
{
  "address": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
  "protocol": "ELK-BLEDOM",
  "presets": {
    "thinking": "color 0 0 40",
    "done": "flash 255 0 0 3",
    "attention": "flash 255 120 0 3",
    "off": "off"
  }
}
```

Commands: `color R G B`, `flash R G B SECONDS` (turns off after N seconds; any new command cancels the pending off), `off`. The daemon re-reads presets on every event, so changes apply without a restart.

You can also drive it by hand: `python3 scripts/led.py send "color 255 0 128"`.

## Troubleshooting

**macOS Bluetooth permission.** macOS kills (exit 134, no prompt) any process that uses Bluetooth when the app responsible for it doesn't declare Bluetooth usage. That includes Warp, Terminal.app and launchd. So on macOS, `scan`, `probe`, `test` and `serve` transparently re-run themselves inside a tiny `LED Notify.app` that `led.py` builds in `~/.config/claude-led/` from your Python (python.org or Homebrew framework builds). That makes them work from any terminal and at login. Allow the *"LED Notify" would like to use Bluetooth* prompt, or enable it in *System Settings → Privacy & Security → Bluetooth*. After a Python upgrade the app is rebuilt and macOS may ask again.

**The phone app blocks the connection.** Most controllers accept a single BLE connection. If the phone app (BojiaLED, duoCo Strip, Happy Lighting…) is open or connected in the background, `scan` may not see the device and `probe`/`serve` can't connect. Force-close the app or turn off the phone's Bluetooth.

**The daemon is down / nothing lights up.**
- With `/led-autostart` it restarts after a crash. Inspect it with `launchctl print gui/$(id -u)/com.claude-led.daemon` (macOS) or `systemctl --user status led-notify` (Linux).
- `python3 scripts/led.py status` prints `running` or `stopped`.
- Check `~/.config/claude-led/led.log`. Repeated `BLE connect failed` means the controller is out of range, powered off, or held by another device. The daemon keeps retrying every 5 s.
- `probe` and `test` need the BLE connection too: stop the daemon (`/led-stop`) before running them.
- Another program on port 47821? Set `CLAUDE_LED_PORT` to another port for both the daemon and the hooks.

**Linux.** Bluetooth must be powered on (`bluetoothctl power on`) and BlueZ running.

**Windows.** If `python3` opens the Microsoft Store, the hooks fall back to `python` automatically. Use `python` in the commands above.

**`bleak` not found.** The hooks and the daemon use `python3` from your `PATH`. Install bleak for that interpreter: `python3 -m pip install --user bleak`.

## Other coding agents

The daemon is harness-agnostic. GitHub Copilot CLI (tested), Codex CLI, Gemini CLI, Cursor and OpenCode can drive it too. See [docs/other-harnesses.md](docs/other-harnesses.md).

## Tested controllers

| Controller | BLE name | Protocol | Status |
| --- | --- | --- | --- |
| NBBUFF BJ-5VRGB/TY-C (Shenzhen Bojia Electronic, app *BojiaLED*) | `BJ_LED` | `BJ_LED` | ✅ macOS 15, bleak 3.0.2 |

Got it working on another controller? Open a PR adding a row.

## Development

```
python3 -m unittest discover tests   # uses a fake bleak, no hardware needed
claude plugin validate .
claude --plugin-dir .                # try the plugin locally
```

## License

[MIT](LICENSE)

---

## Español

**led-notify** es un plugin de Claude Code que hace que una tira LED Bluetooth reaccione a Claude Code: azul tenue mientras piensa, rojo 3 s cuando termina y naranja 3 s cuando necesita tu atención.

Un daemon (`led.py serve`) mantiene abierta la conexión BLE y escucha en `127.0.0.1:47821` (TCP, igual en macOS, Linux y Windows). Los hooks le envían comandos; si el daemon no corre, los hooks no hacen nada, no imprimen nada y nunca bloquean Claude Code.

El protocolo del controlador **no está fijado para ningún modelo**: `/led-setup` ejecuta `probe`, que prueba los protocolos conocidos y guarda el que enciende tu tira. El BJ-5VRGB/TY-C (nombre BLE `BJ_LED`) funciona con el protocolo `BJ_LED`; si ninguno funciona, mira [CONTRIBUTING.md](CONTRIBUTING.md).

**Requisitos:** macOS, Linux o Windows 10+, Python 3.9+ y `bleak` (`python3 -m pip install --user bleak`). En Windows, Claude Code con Git Bash.

**Instalación:**

```
/plugin marketplace add santiago2904/claude-led-notification
/plugin install led-notify@led-notify
```

**Configuración:** cierra la app del celular, ejecuta `/led-setup` y luego `/led-autostart` (arranca ahora y en cada inicio de sesión, sin terminal abierta, en macOS, Linux y Windows) o `/led-start`.

**Colores:** `/led-color done 0 255 0`, `/led-color thinking off`, o edita `~/.config/claude-led/config.json`.

**Problemas comunes:**
- *Permiso de Bluetooth (macOS):* los comandos Bluetooth corren dentro de una pequeña `LED Notify.app` que `led.py` crea sola, así que funcionan desde cualquier terminal (Warp incluido). Permite el aviso *"LED Notify" quiere usar Bluetooth*.
- *Otros agentes (Copilot CLI, Codex, Gemini, Cursor, OpenCode):* ver [docs/other-harnesses.md](docs/other-harnesses.md).
- *La app del celular bloquea la conexión:* ciérrala por completo o apaga el Bluetooth del teléfono.
- *Daemon caído:* `python3 scripts/led.py status` y revisa `~/.config/claude-led/led.log`.
