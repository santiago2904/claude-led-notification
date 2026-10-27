"""Run with: python3 -m unittest discover tests

Uses a fake `bleak` module, so no hardware or bleak install is needed.
"""
import asyncio
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import types
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "led.py")


class FakeClient:
    instances = []

    def __init__(self, address, **kwargs):
        self.address = address
        self.is_connected = False
        self.writes = []
        FakeClient.instances.append(self)

    async def connect(self, **kwargs):
        self.is_connected = True

    async def disconnect(self):
        self.is_connected = False

    async def write_gatt_char(self, char, data, response=True):
        self.writes.append(data.hex())


class LedTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="led")
        self.addCleanup(shutil.rmtree, self.home, True)
        os.environ["CLAUDE_LED_HOME"] = self.home
        with socket.socket() as s:  # a free port, so tests never hit a real daemon
            s.bind(("127.0.0.1", 0))
            os.environ["CLAUDE_LED_PORT"] = str(s.getsockname()[1])
        sys.modules["bleak"] = types.SimpleNamespace(BleakClient=FakeClient)
        sys.path.insert(0, os.path.dirname(SCRIPT))
        sys.modules.pop("led", None)
        import led

        self.led = led
        FakeClient.instances.clear()
        with open(os.path.join(self.home, "config.json"), "w") as f:
            json.dump({"address": "AA:BB", "protocol": "ELK-BLEDOM"}, f)

    def test_send_without_daemon_is_silent(self):
        env = dict(os.environ)
        for args in (["send", "thinking"], ["send"], ["send", "garbage", "x"]):
            p = subprocess.run([sys.executable, SCRIPT] + args, env=env, capture_output=True, timeout=5)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, b"", b""))

    def test_hook_commands_are_silent_without_daemon(self):
        # Runs hooks.json exactly as Claude Code does (bash), including the
        # python3 -> python fallback that Windows relies on.
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not available")
        root = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(root, "hooks", "hooks.json")) as f:
            hooks = json.load(f)["hooks"]
        for event, groups in hooks.items():
            cmd = groups[0]["hooks"][0]["command"].replace("${CLAUDE_PLUGIN_ROOT}", os.path.abspath(root).replace("\\", "/"))
            p = subprocess.run([bash, "-c", cmd], capture_output=True, timeout=10)
            self.assertEqual((event, p.returncode, p.stdout, p.stderr), (event, 0, b"", b""))

    @unittest.skipUnless(importlib.util.find_spec("bleak") or os.environ.get("CI"), "needs the real bleak")
    def test_start_stop(self):
        # Spawns the real detached daemon. There is no strip, so it just keeps retrying BLE.
        if sys.platform == "darwin":
            self.skipTest("macOS goes through LED Notify.app; verified by hand")
        run = lambda *a: subprocess.run([sys.executable, SCRIPT] + list(a), capture_output=True, text=True, timeout=30)
        self.assertEqual(run("start").stdout.strip(), "running")
        self.assertEqual(run("status").stdout.strip(), "running")
        self.assertEqual(run("start").stdout.strip(), "Already running.")
        self.assertEqual(run("stop").stdout.strip(), "stopped")
        self.assertEqual(run("status").stdout.strip(), "stopped")

    def test_parse(self):
        presets = self.led.DEFAULT_PRESETS
        self.assertEqual(self.led.parse("thinking", presets), ("color", (0, 0, 40), None))
        self.assertEqual(self.led.parse("done", presets), ("flash", (255, 0, 0), 3.0))
        self.assertEqual(self.led.parse("off", presets), ("off", None, None))
        for bad in ("color 1 2", "color 0 0 256", "flash 1 2 3 0", "blink"):
            self.assertRaises(ValueError, self.led.parse, bad, presets)

    def test_set_preset_keeps_flash_duration(self):
        self.led.set_preset("done", ["0", "255", "0"])
        self.led.set_preset("thinking", ["off"])
        presets = self.led.load_config()["presets"]
        self.assertEqual(presets["done"], "flash 0 255 0 3")
        self.assertEqual(presets["thinking"], "off")
        self.assertRaises(ValueError, self.led.set_preset, "done", ["0", "999", "0"])

    def test_serve(self):
        led = self.led
        on, off = led.PROTOCOLS["ELK-BLEDOM"]["on"], led.PROTOCOLS["ELK-BLEDOM"]["off"]
        color = lambda r, g, b: led.frame("ELK-BLEDOM", "color", (r, g, b)).hex()

        async def run():
            daemon = asyncio.ensure_future(led.serve())
            loop = asyncio.get_running_loop()
            while not await loop.run_in_executor(None, led.daemon_running):
                await asyncio.sleep(0.01)
            client = FakeClient.instances[0]

            async def send(cmd):
                await loop.run_in_executor(None, led.send, cmd)
                await asyncio.sleep(0.05)

            self.assertTrue(await loop.run_in_executor(None, led.daemon_running))

            # Preset
            await send("thinking")
            self.assertEqual(client.writes, [on, color(0, 0, 40)])

            # Flash turns off after N seconds
            client.writes.clear()
            await send("flash 255 0 0 0.2")
            self.assertEqual(client.writes, [on, color(255, 0, 0)])
            await asyncio.sleep(0.3)
            self.assertEqual(client.writes[-1], off)

            # A new command cancels the pending off
            client.writes.clear()
            await send("done")  # flash 3 s
            await send("thinking")
            await asyncio.sleep(0.1)
            self.assertEqual(client.writes[-1], color(0, 0, 40))
            client.writes.clear()
            await send("flash 0 255 0 0.2")
            await send("color 1 2 3")
            await asyncio.sleep(0.3)
            self.assertNotIn(off, client.writes)

            # Invalid commands are ignored, daemon keeps working
            await send("nonsense")
            await send("off")
            self.assertEqual(client.writes[-1], off)

            # `stop` sends "quit": the daemon turns the strip off and exits cleanly
            client.writes.clear()
            await send("quit")
            self.assertEqual(await asyncio.wait_for(daemon, 7), 0)
            self.assertEqual(client.writes, [off])
            self.assertFalse(await loop.run_in_executor(None, led.daemon_running))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
