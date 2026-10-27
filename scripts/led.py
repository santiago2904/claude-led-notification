#!/usr/bin/env python3
"""led-notify: make a Bluetooth LED strip react to Claude Code.

Usage:
  led.py scan                      list nearby BLE devices
  led.py probe ADDR [PROTOCOL]     try known protocols and save the one that works
  led.py serve                     daemon: keep the BLE connection open, listen on 127.0.0.1
  led.py start | stop              run the daemon in the background / stop it
  led.py send PRESET|COMMAND       used by hooks: silent, 0.5 s timeout, never fails
  led.py status                    is the daemon running?
  led.py preset NAME VALUE...      change a preset in config.json
  led.py test                      red for 2 s, then off
  led.py autostart [remove]        run the daemon at login (macOS, Linux, Windows)

Commands: "color R G B", "flash R G B SECONDS", "off".
Presets:  thinking, done, attention, off (editable in config.json).

Config and log live in ~/.config/claude-led/ (override with CLAUDE_LED_HOME), so
updating the plugin never wipes them. The daemon listens on 127.0.0.1:47821
(override with CLAUDE_LED_PORT); TCP rather than a Unix socket so Windows works too.
"""
import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

HOME = os.path.expanduser(os.environ.get("CLAUDE_LED_HOME", "~/.config/claude-led"))
CONFIG = os.path.join(HOME, "config.json")
LOG = os.path.join(HOME, "led.log")
ADDR = ("127.0.0.1", int(os.environ.get("CLAUDE_LED_PORT", "47821")))
WINDOWS = sys.platform == "win32"
# Linux: systemd user service. Windows: a script in the Startup folder.
UNIT = os.path.expanduser("~/.config/systemd/user/led-notify.service")
STARTUP = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup\led-notify.cmd")
UNIT_TEXT = """[Unit]
Description=led-notify: LED strip notifications for coding agents
After=bluetooth.target

[Service]
ExecStart="%(exe)s" "%(script)s" serve
Restart=on-failure
RestartSec=10
StandardOutput=append:%(log)s
StandardError=append:%(log)s

[Install]
WantedBy=default.target
"""

# macOS only: see build_app().
APP = os.path.join(HOME, "LED Notify.app")
APP_EXE = os.path.join(APP, "Contents", "MacOS", "led-notify")
LABEL = "com.claude-led.daemon"
AGENT = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % LABEL)
INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>com.github.santiago2904.led-notify</string>
  <key>CFBundleName</key><string>LED Notify</string>
  <key>CFBundleExecutable</key><string>led-notify</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSUIElement</key><true/>
  <key>NSBluetoothAlwaysUsageDescription</key><string>LED Notify controls your LED strip over Bluetooth.</string>
</dict>
</plist>
"""
AGENT_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>%(label)s</string>
  <key>ProgramArguments</key>
  <array><string>%(exe)s</string><string>%(script)s</string><string>serve</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>%(log)s</string>
  <key>StandardErrorPath</key><string>%(log)s</string>
</dict>
</plist>
"""

# Each protocol: the GATT characteristic to write to and hex frame templates.
# To add one, see CONTRIBUTING.md.
PROTOCOLS = {
    "ELK-BLEDOM": {
        "char": "0000fff3-0000-1000-8000-00805f9b34fb",
        "on": "7e0004f00001ff00ef",
        "off": "7e0004000000ff00ef",
        "color": "7e000503{r:02x}{g:02x}{b:02x}00ef",
    },
    "ELK-BLEDOM v2": {
        "char": "0000fff3-0000-1000-8000-00805f9b34fb",
        "on": "7e0404f00001ff00ef",
        "off": "7e0404000000ff00ef",
        "color": "7e070503{r:02x}{g:02x}{b:02x}10ef",
    },
    "Triones": {
        "char": "0000ffd9-0000-1000-8000-00805f9b34fb",
        "on": "cc2333",
        "off": "cc2433",
        "color": "56{r:02x}{g:02x}{b:02x}00f0aa",
    },
    "SP110E": {
        "char": "0000ffe1-0000-1000-8000-00805f9b34fb",
        "on": "000000aa",
        "off": "000000ab",
        "color": "{r:02x}{g:02x}{b:02x}1e",
    },
    # BJ_LED (BojiaLED app, e.g. NBBUFF BJ-5VRGB/TY-C). ee02 accepts the same frames.
    "BJ_LED": {
        "char": "0000ee01-0000-1000-8000-00805f9b34fb",
        "on": "6996020101",
        "off": "6996020100",
        "color": "69960502{r:02x}{g:02x}{b:02x}",
    },
}

DEFAULT_PRESETS = {
    "thinking": "color 0 0 40",
    "done": "flash 255 0 0 3",
    "attention": "flash 255 120 0 3",
    "off": "off",
}


def log(*args):
    print(*args, flush=True)


def load_config():
    try:
        with open(CONFIG) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg["presets"] = {**DEFAULT_PRESETS, **cfg.get("presets", {})}
    return cfg


def save_config(cfg):
    os.makedirs(HOME, exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def frame(protocol, kind, rgb=(0, 0, 0)):
    r, g, b = rgb
    return bytes.fromhex(PROTOCOLS[protocol][kind].format(r=r, g=g, b=b))


def parse(cmd, presets):
    """Resolve a preset or raw command into (kind, rgb, seconds). Raises ValueError."""
    words = presets.get(cmd.strip(), cmd).split()
    if words == ["off"]:
        return "off", None, None
    if len(words) == 4 and words[0] == "color":
        return "color", rgb(words[1:4]), None
    if len(words) == 5 and words[0] == "flash":
        secs = float(words[4])
        if secs <= 0:
            raise ValueError("flash seconds must be > 0")
        return "flash", rgb(words[1:4]), secs
    raise ValueError("unknown command: %r" % cmd)


def rgb(values):
    out = tuple(int(v) for v in values)
    if any(not 0 <= v <= 255 for v in out):
        raise ValueError("RGB values must be 0-255")
    return out


def daemon_running():
    try:
        with socket.create_connection(ADDR, timeout=0.5) as s:
            s.sendall(b"ping\n")
            return s.recv(16).startswith(b"ok")
    except OSError:
        return False


def send(cmd):
    with socket.create_connection(ADDR, timeout=0.5) as s:
        s.sendall(cmd.encode() + b"\n")


def wait_for(running):
    for _ in range(50):
        if daemon_running() == running:
            return True
        time.sleep(0.2)
    return False


def start():
    if daemon_running():
        log("Already running.")
        return 0
    if not load_config().get("address"):
        log("No device configured. Run /led-setup first.")
        return 1
    os.makedirs(HOME, exist_ok=True)
    script = os.path.abspath(__file__)
    if sys.platform == "darwin" and build_app():
        via_app(["serve"])
    else:
        exe, flags = sys.executable, {"start_new_session": True}
        if WINDOWS:
            # pythonw: no console window. DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP.
            exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            exe = exe if os.path.exists(exe) else sys.executable
            flags = {"creationflags": 0x00000008 | 0x00000200}
        with open(LOG, "a") as out:
            subprocess.Popen([exe, script, "serve"], stdin=subprocess.DEVNULL, stdout=out, stderr=out, **flags)
    if wait_for(True):
        log("running")
        return 0
    log("Not running. See", LOG)
    return 1


def stop():
    try:
        send("quit")
    except OSError:
        log("stopped")
        return 0
    if wait_for(False):
        log("stopped")
        return 0
    log("Still running. See", LOG)
    return 1


def build_app():
    """macOS kills (exit 134, no prompt) any process that touches Bluetooth when the app
    responsible for it doesn't declare Bluetooth usage: Warp, Terminal.app, launchd.
    So run Python from a tiny "LED Notify.app" that does declare it. Launched through
    `open` or launchd, the app is its own responsible process and gets its own permission."""
    src = os.path.realpath(os.path.join(sys.base_prefix, "Resources/Python.app/Contents/MacOS/Python"))
    if not os.path.exists(src):
        return False  # not a framework build (python.org and Homebrew are)
    stamp = os.path.join(HOME, "app-source")
    try:
        with open(stamp) as f:
            if f.read() == src and os.path.exists(APP_EXE):
                return True
    except OSError:
        pass
    # Rebuilt only when Python changes, since macOS may ask for the permission again.
    shutil.rmtree(APP, ignore_errors=True)
    os.makedirs(os.path.dirname(APP_EXE))
    shutil.copy(src, APP_EXE)
    with open(os.path.join(APP, "Contents", "Info.plist"), "w") as f:
        f.write(INFO_PLIST)
    subprocess.run(["codesign", "--force", "--sign", "-", APP], check=True, capture_output=True)
    with open(stamp, "w") as f:
        f.write(src)
    return True


def in_app():
    return os.path.realpath(sys.executable) == os.path.realpath(APP_EXE)


def via_app(args):
    """Re-run `led.py ARGS` inside LED Notify.app and relay its output and exit code."""
    script = os.path.abspath(__file__)
    if args[0] == "serve":
        subprocess.run(["open", "-n", "-a", APP, "--stdout", LOG, "--stderr", LOG, "--args", script, "serve"])
        return 0
    out, rc = os.path.join(HOME, "app.out"), os.path.join(HOME, "app.rc")
    for path in (out, rc):
        if os.path.exists(path):
            os.remove(path)
    subprocess.run(["open", "-n", "-W", "-a", APP, "--stdout", out, "--stderr", out, "--args", script] + args,
                   capture_output=True)
    # `open -W` can return early when the app exits fast; the app writes app.rc last.
    for _ in range(600):
        if os.path.exists(rc):
            break
        time.sleep(0.1)
    if os.path.exists(out):
        with open(out) as f:
            sys.stdout.write(f.read())
    if not os.path.exists(rc):
        log("LED Notify.app did not finish. Check System Settings > Privacy & Security > Bluetooth.")
        return 1
    with open(rc) as f:
        return int(f.read())


def autostart(remove=False):
    """Run the daemon at login: LaunchAgent (macOS), systemd user service (Linux),
    Startup folder script (Windows). Each restarts it only after a crash, so `stop` sticks."""
    script = os.path.join(HOME, "led.py")
    if sys.platform == "darwin":
        subprocess.run(["launchctl", "bootout", "gui/%d/%s" % (os.getuid(), LABEL)], capture_output=True)
        entry = AGENT
    elif WINDOWS:
        entry = STARTUP
    else:
        if remove and os.path.exists(UNIT):
            subprocess.run(["systemctl", "--user", "disable", "--now", "led-notify"], capture_output=True)
        entry = UNIT
    if remove:
        stop()
        for path in (entry, script):
            if os.path.exists(path):
                os.remove(path)
        log("Autostart removed.")
        return 0

    if not load_config().get("address"):
        log("No device configured. Run /led-setup first.")
        return 1
    if sys.platform == "darwin" and not build_app():
        log("Needs a framework build of Python (python.org or Homebrew).")
        return 1
    stop()
    # Stable copy: the plugin directory changes on every update.
    os.makedirs(HOME, exist_ok=True)
    shutil.copy(os.path.abspath(__file__), script)
    os.makedirs(os.path.dirname(entry), exist_ok=True)
    if sys.platform == "darwin":
        with open(entry, "w") as f:
            f.write(AGENT_PLIST % {"label": LABEL, "exe": APP_EXE, "script": script, "log": LOG})
        subprocess.run(["launchctl", "bootstrap", "gui/%d" % os.getuid(), entry], check=True)
    elif WINDOWS:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        with open(entry, "w") as f:
            f.write('@start "" "%s" "%s" serve\n' % (pythonw if os.path.exists(pythonw) else sys.executable, script))
        start()
    else:
        with open(entry, "w") as f:
            f.write(UNIT_TEXT % {"exe": sys.executable, "script": script, "log": LOG})
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "led-notify"], check=True)
    log("Autostart installed (%s): the daemon runs now and at every login." % entry)
    return 0


async def scan():
    from bleak import BleakScanner

    found = await BleakScanner.discover(timeout=8, return_adv=True)
    rows = sorted(found.items(), key=lambda kv: kv[1][1].rssi, reverse=True)
    for addr, (dev, adv) in rows:
        log("%-40s %5d dBm  %s" % (addr, adv.rssi, dev.name or adv.local_name or "?"))
    if not rows:
        log("No devices found. Is Bluetooth on and the phone app closed?")


async def probe(addr, only=None):
    from bleak import BleakClient

    if only and only not in PROTOCOLS:
        log("Unknown protocol %r. Known: %s" % (only, ", ".join(PROTOCOLS)))
        return 1
    async with BleakClient(addr, timeout=15) as client:
        chars = {c.uuid: c for s in client.services for c in s.characteristics}
        candidates = [n for n, p in PROTOCOLS.items() if p["char"] in chars and only in (None, n)]
        if not candidates:
            log("No known protocol matches this device. Writable characteristics:")
            for c in chars.values():
                if "write" in c.properties or "write-without-response" in c.properties:
                    log("  %s  %s" % (c.uuid, ",".join(c.properties)))
            log("See CONTRIBUTING.md to add a new protocol.")
            return 1
        interactive = sys.stdin.isatty() and not only
        for i, name in enumerate(candidates, 1):
            log("[%d] %s: the strip should turn RED for 2 s..." % (i, name))
            char = PROTOCOLS[name]["char"]
            for kind, color in (("on", (0, 0, 0)), ("color", (255, 0, 0))):
                await client.write_gatt_char(char, frame(name, kind, color), response=False)
            await asyncio.sleep(2)
            await client.write_gatt_char(char, frame(name, "off"), response=False)
            await asyncio.sleep(1)
            if only or (interactive and input("Did it turn red? [y/N] ").strip().lower() in ("y", "s", "yes", "si", "sí")):
                cfg = load_config()
                cfg.update(address=addr, protocol=name)
                save_config(cfg)
                log("Saved %s / %s to %s" % (addr, name, CONFIG))
                return 0
        if not interactive:
            log('Run again with the one that lit up: led.py probe %s "PROTOCOL"' % addr)
        else:
            log("None worked. See CONTRIBUTING.md to add a new protocol.")
        return 1


async def serve():
    from bleak import BleakClient

    cfg = load_config()
    if cfg.get("protocol") not in PROTOCOLS or not cfg.get("address"):
        log("No device configured in %s. Run /led-setup first." % CONFIG)
        return 1
    if daemon_running():
        log("Daemon already running.")
        return 0
    if sys.stdout is None:  # pythonw (Windows Startup folder) has no console
        os.makedirs(HOME, exist_ok=True)
        sys.stdout = sys.stderr = open(LOG, "a")

    protocol = cfg["protocol"]
    char = PROTOCOLS[protocol]["char"]
    client = BleakClient(cfg["address"])
    lock = asyncio.Lock()
    pending_off = None
    stopping = asyncio.Event()

    async def write(kind, color=(0, 0, 0)):
        async with lock:
            if not client.is_connected:
                log("BLE not connected, dropped:", kind)
                return
            await client.write_gatt_char(char, frame(protocol, kind, color), response=False)

    async def off_after(secs):
        await asyncio.sleep(secs)
        await write("off")

    async def apply(cmd):
        nonlocal pending_off
        # Re-read presets each time so /led-color applies without a restart.
        kind, color, secs = parse(cmd, load_config()["presets"])
        if pending_off:
            pending_off.cancel()
            pending_off = None
        if kind == "off":
            await write("off")
            return
        await write("on")
        await write("color", color)
        if kind == "flash":
            pending_off = asyncio.ensure_future(off_after(secs))

    async def handle(reader, writer):
        try:
            cmd = (await asyncio.wait_for(reader.readline(), 1)).decode().strip()
            if cmd == "ping":
                writer.write(b"ok\n")
                await writer.drain()
            elif cmd == "quit":
                stopping.set()
            elif cmd:
                await apply(cmd)
        except Exception as e:
            log("error:", e)
        finally:
            writer.close()

    async def keep_connected():
        while not stopping.is_set():
            if not client.is_connected:
                try:
                    await client.connect(timeout=10)
                    log("Connected to", cfg["address"], "(%s)" % protocol)
                except Exception as e:
                    log("BLE connect failed, retrying in 5 s:", e)
            try:
                await asyncio.wait_for(stopping.wait(), 5)
            except asyncio.TimeoutError:
                pass

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except (NotImplementedError, AttributeError):
            pass  # Windows: use `led.py stop`
    server = await asyncio.start_server(handle, *ADDR)
    log("Listening on %s:%d" % ADDR)
    ble = asyncio.ensure_future(keep_connected())
    try:
        await stopping.wait()
    finally:
        server.close()
        await ble
        if client.is_connected:
            try:
                await write("off")
                await client.disconnect()
            except Exception:
                pass
        log("Stopped.")
    return 0


async def test():
    if daemon_running():
        send("flash 255 0 0 2")
        log("Sent red flash through the daemon.")
        return 0
    from bleak import BleakClient

    cfg = load_config()
    if cfg.get("protocol") not in PROTOCOLS:
        log("No device configured. Run /led-setup first.")
        return 1
    protocol = cfg["protocol"]
    char = PROTOCOLS[protocol]["char"]
    async with BleakClient(cfg["address"], timeout=15) as client:
        await client.write_gatt_char(char, frame(protocol, "on"), response=False)
        await client.write_gatt_char(char, frame(protocol, "color", (255, 0, 0)), response=False)
        await asyncio.sleep(2)
        await client.write_gatt_char(char, frame(protocol, "off"), response=False)
    log("Done.")
    return 0


def set_preset(name, values):
    cfg = load_config()
    current = cfg["presets"].get(name, "")
    if values == ["off"]:
        new = "off"
    elif len(values) == 3:
        # Keep the preset's kind: a flash stays a flash with the same duration.
        words = current.split()
        new = "flash %s %s" % (" ".join(values), words[4]) if words[:1] == ["flash"] else "color " + " ".join(values)
    else:
        new = " ".join(values)
    parse(new, {})  # validate
    cfg["presets"][name] = new
    save_config(cfg)
    log('%s = "%s"' % (name, new))
    return 0


def main(argv):
    if len(argv) < 2:
        log(__doc__)
        return 1
    cmd, args = argv[1], argv[2:]
    if cmd == "send":
        # Called from hooks: never print, never fail, never block.
        try:
            send(" ".join(args))
        except BaseException:
            pass
        return 0
    if cmd == "status":
        running = daemon_running()
        log("running" if running else "stopped")
        return 0 if running else 1
    if cmd == "preset" and len(args) >= 2:
        try:
            return set_preset(args[0], args[1:])
        except ValueError as e:
            log("Invalid value:", e)
            return 1
    if cmd == "autostart":
        return autostart(args == ["remove"])
    if cmd == "start":
        return start()
    if cmd == "stop":
        return stop()
    if cmd in ("scan", "probe", "serve", "test") and sys.platform == "darwin" and not in_app() and build_app():
        return via_app(argv[1:])
    if cmd == "scan":
        return asyncio.run(scan())
    if cmd == "probe" and args:
        if daemon_running():
            log("The daemon holds the BLE connection. Stop it first (/led-stop).")
            return 1
        return asyncio.run(probe(args[0], args[1] if len(args) > 1 else None))
    if cmd == "serve":
        return asyncio.run(serve())
    if cmd == "test":
        return asyncio.run(test())
    log(__doc__)
    return 1


if __name__ == "__main__":
    code = 1
    try:
        code = main(sys.argv) or 0
    except ImportError:
        print("bleak is not installed: python3 -m pip install bleak", file=sys.stderr)
    finally:
        if in_app() and sys.argv[1:2] != ["serve"]:
            sys.stdout.flush()
            with open(os.path.join(HOME, "app.rc"), "w") as f:
                f.write(str(code))  # tells via_app() we're done
    sys.exit(code)
