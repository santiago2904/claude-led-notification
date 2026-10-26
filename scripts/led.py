#!/usr/bin/env python3
"""led-notify: make a Bluetooth LED strip react to Claude Code.

Usage:
  led.py scan                      list nearby BLE devices
  led.py probe ADDR [PROTOCOL]     try known protocols and save the one that works
  led.py serve                     daemon: keep the BLE connection open, listen on a Unix socket
  led.py send PRESET|COMMAND       used by hooks: silent, 0.5 s timeout, never fails
  led.py status                    is the daemon running?
  led.py preset NAME VALUE...      change a preset in config.json
  led.py test                      red for 2 s, then off

Commands: "color R G B", "flash R G B SECONDS", "off".
Presets:  thinking, done, attention, off (editable in config.json).

Config, socket and log live in ~/.config/claude-led/ (override with CLAUDE_LED_HOME),
so updating the plugin never wipes them.
"""
import asyncio
import json
import os
import signal
import socket
import sys

HOME = os.path.expanduser(os.environ.get("CLAUDE_LED_HOME", "~/.config/claude-led"))
CONFIG = os.path.join(HOME, "config.json")
SOCK = os.path.join(HOME, "led.sock")

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
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(0.5)
            s.connect(SOCK)
            s.sendall(b"ping\n")
            return s.recv(16).startswith(b"ok")
    except OSError:
        return False


def send(cmd):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(0.5)
        s.connect(SOCK)
        s.sendall(cmd.encode() + b"\n")


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
    os.makedirs(HOME, exist_ok=True)
    if os.path.exists(SOCK):
        os.unlink(SOCK)

    protocol = cfg["protocol"]
    char = PROTOCOLS[protocol]["char"]
    client = BleakClient(cfg["address"])
    lock = asyncio.Lock()
    pending_off = None
    stop = asyncio.Event()

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
            elif cmd:
                await apply(cmd)
        except Exception as e:
            log("error:", e)
        finally:
            writer.close()

    async def keep_connected():
        while not stop.is_set():
            if not client.is_connected:
                try:
                    await client.connect(timeout=10)
                    log("Connected to", cfg["address"], "(%s)" % protocol)
                except Exception as e:
                    log("BLE connect failed, retrying in 5 s:", e)
            try:
                await asyncio.wait_for(stop.wait(), 5)
            except asyncio.TimeoutError:
                pass

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    server = await asyncio.start_unix_server(handle, SOCK)
    log("Listening on", SOCK)
    ble = asyncio.ensure_future(keep_connected())
    try:
        await stop.wait()
    finally:
        server.close()
        if os.path.exists(SOCK):
            os.unlink(SOCK)
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
    try:
        sys.exit(main(sys.argv))
    except ImportError:
        print("bleak is not installed: python3 -m pip install bleak", file=sys.stderr)
        sys.exit(1)
