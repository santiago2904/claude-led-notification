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

A small daemon (`scripts/led.py serve`) keeps the BLE connection to the controller open and listens on a Unix socket. Claude Code hooks send one-line commands to that socket. If the daemon isn't running, the hooks do nothing: they print nothing, exit 0, and give up after 0.5 s, so they can never block or break Claude Code.

The controller's BLE protocol is **not hard-coded for any specific model**. `/led-setup` runs `probe`, which tries the protocols it knows (ELK-BLEDOM, ELK-BLEDOM v2, Triones, SP110E, BJ_LED) and saves the one that lights your strip. If none works, see [CONTRIBUTING.md](CONTRIBUTING.md) to add yours.

## Requirements

- macOS or Linux (BlueZ) with Bluetooth LE
- Python 3.9+ available as `python3`
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
3. Run `/led-start` to start the daemon. On macOS you can use `/led-autostart` instead to start it at login.

| Command | What it does |
| --- | --- |
| `/led-setup` | Guided setup: scan, probe, test |
| `/led-start` | Start the daemon in the background |
| `/led-stop` | Stop the daemon |
| `/led-color <preset> <R G B \| off>` | Change a preset color |
| `/led-autostart [remove]` | (macOS) Start at login via a LaunchAgent |

Plugin commands may also appear namespaced, e.g. `/led-notify:led-setup`.

Config, socket and log live in `~/.config/claude-led/` (`config.json`, `led.sock`, `led.log`), so plugin updates never wipe them.

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

**macOS Bluetooth permission / `led.py` exits with code 134.** macOS attributes Bluetooth access to the terminal app that launched Python, and kills the process (SIGABRT, exit 134, no prompt) if that app doesn't declare Bluetooth usage. **Warp and Terminal.app don't; iTerm2 does.** Run `/led-setup`, `/led-start` and the daemon from Claude Code inside iTerm2 (or another terminal that shows a Bluetooth prompt) and accept the prompt, or enable it in *System Settings → Privacy & Security → Bluetooth*. Once the daemon runs, the hooks work from any terminal, since they only talk to the Unix socket. `/led-autostart` is untested: under launchd the Python binary itself needs the permission, and Homebrew's Python doesn't declare it either.

**The phone app blocks the connection.** Most controllers accept a single BLE connection. If the phone app (BojiaLED, duoCo Strip, Happy Lighting…) is open or connected in the background, `scan` may not see the device and `probe`/`serve` can't connect. Force-close the app or turn off the phone's Bluetooth.

**The daemon is down / nothing lights up.**
- `python3 scripts/led.py status` prints `running` or `stopped`.
- Check `~/.config/claude-led/led.log`. Repeated `BLE connect failed` means the controller is out of range, powered off, or held by another device. The daemon keeps retrying every 5 s.
- `probe` and `test` need the BLE connection too: stop the daemon (`/led-stop`) before running them.
- A stale `led.sock` is removed automatically when the daemon starts.

**`bleak` not found.** The hooks and the daemon use `python3` from your `PATH`. Install bleak for that interpreter: `python3 -m pip install --user bleak`.

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

Un daemon (`led.py serve`) mantiene abierta la conexión BLE y escucha en un Unix socket. Los hooks le envían comandos; si el daemon no corre, los hooks no hacen nada, no imprimen nada y nunca bloquean Claude Code.

El protocolo del controlador **no está fijado para ningún modelo**: `/led-setup` ejecuta `probe`, que prueba los protocolos conocidos y guarda el que enciende tu tira. El BJ-5VRGB/TY-C (nombre BLE `BJ_LED`) funciona con el protocolo `BJ_LED`; si ninguno funciona, mira [CONTRIBUTING.md](CONTRIBUTING.md).

**Requisitos:** macOS o Linux, Python 3.9+ y `bleak` (`python3 -m pip install --user bleak`).

**Instalación:**

```
/plugin marketplace add santiago2904/claude-led-notification
/plugin install led-notify@led-notify
```

**Configuración:** cierra la app del celular, ejecuta `/led-setup` y luego `/led-start` (o `/led-autostart` en macOS para arrancar al iniciar sesión).

**Colores:** `/led-color done 0 255 0`, `/led-color thinking off`, o edita `~/.config/claude-led/config.json`.

**Problemas comunes:**
- *Permiso de Bluetooth (macOS) / código de salida 134:* macOS mata el proceso si la terminal no declara uso de Bluetooth. **Warp y Terminal.app no lo declaran; iTerm2 sí.** Haz el setup y arranca el daemon desde iTerm2. Después los hooks funcionan desde cualquier terminal.
- *La app del celular bloquea la conexión:* ciérrala por completo o apaga el Bluetooth del teléfono.
- *Daemon caído:* `python3 scripts/led.py status` y revisa `~/.config/claude-led/led.log`.
