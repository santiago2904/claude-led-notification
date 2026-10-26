"""Run with: python3 -m unittest discover tests

Uses a fake `bleak` module, so no hardware or bleak install is needed.
"""
import asyncio
import json
import os
import shutil
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
        # Short path: Unix socket paths are limited to ~104 chars on macOS.
        self.home = tempfile.mkdtemp(prefix="led")
        self.addCleanup(shutil.rmtree, self.home, True)
        os.environ["CLAUDE_LED_HOME"] = self.home
        sys.modules["bleak"] = types.SimpleNamespace(BleakClient=FakeClient)
        sys.path.insert(0, os.path.dirname(SCRIPT))
        sys.modules.pop("led", None)
        import led

        self.led = led
        FakeClient.instances.clear()
        with open(os.path.join(self.home, "config.json"), "w") as f:
            json.dump({"address": "AA:BB", "protocol": "ELK-BLEDOM"}, f)

    def test_send_without_daemon_is_silent(self):
        env = dict(os.environ, CLAUDE_LED_HOME=self.home)
        for args in (["send", "thinking"], ["send"], ["send", "garbage", "x"]):
            p = subprocess.run([sys.executable, SCRIPT] + args, env=env, capture_output=True, timeout=5)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, b"", b""))

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
            while not os.path.exists(led.SOCK):
                await asyncio.sleep(0.01)
            client = FakeClient.instances[0]
            loop = asyncio.get_running_loop()

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

            os.kill(os.getpid(), __import__("signal").SIGTERM)
            self.assertEqual(await asyncio.wait_for(daemon, 7), 0)
            self.assertFalse(os.path.exists(led.SOCK))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
