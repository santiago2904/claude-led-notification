# Contributing

Bug reports, tested-controller reports and new protocols are welcome. Keep the code simple: `bleak` is the only dependency, and the hooks must never block or print anything.

Run the tests before opening a PR:

```
python3 -m unittest discover tests
claude plugin validate .
```

## Adding a new protocol

If `probe` says *No known protocol matches this device* (it then lists the writable characteristics), or none of the candidates lights the strip, you can capture what the phone app sends and add it.

### 1. Capture the BLE traffic (Android)

1. Enable **Developer options** (tap *Build number* 7 times).
2. In Developer options, enable **Bluetooth HCI snoop log**. Toggle Bluetooth off and on.
3. Open the controller's app and do a few distinct actions, slowly, noting the order: turn on, turn off, set pure red, pure green, pure blue.
4. Get the log:
   - `adb bugreport bugreport.zip` and look for `btsnoop_hci.log` inside (usually under `FS/data/misc/bluetooth/logs/`), or
   - on some phones, pull it directly: `adb pull /sdcard/btsnoop_hci.log`.
5. Turn the snoop log off again.

(iOS: use Apple's *Bluetooth logging profile* with PacketLogger on a Mac.)

### 2. Read it in Wireshark

Open the log and apply this display filter:

```
btatt.opcode == 0x52 || btatt.opcode == 0x12
```

`0x52` is *Write Command* (write without response) and `0x12` is *Write Request*. For each packet note:

- the **handle / characteristic UUID** being written (expand the ATT layer; Wireshark shows the UUID if it saw service discovery, otherwise match the handle against the `probe` output),
- the **value** bytes.

Compare the packets for red, green and blue: the bytes that change are R, G and B. Whatever stays the same is the frame header/footer.

Example (ELK-BLEDOM, pure red): `7e 00 05 03 ff 00 00 00 ef`.

### 3. Add it to `PROTOCOLS`

In `scripts/led.py`, add an entry. Frames are hex strings; `{r:02x}`, `{g:02x}`, `{b:02x}` are replaced with the color bytes:

```python
PROTOCOLS = {
    ...
    "MyController": {
        "char": "0000xxxx-0000-1000-8000-00805f9b34fb",  # characteristic UUID, lowercase
        "on": "aa0101bb",
        "off": "aa0100bb",
        "color": "aa02{r:02x}{g:02x}{b:02x}bb",
    },
}
```

If the controller has no separate power command, use the color frame with black for `off` and repeat any harmless frame for `on`.

### 4. Test and open a PR

```
python3 scripts/led.py probe <ADDRESS> "MyController"
python3 scripts/led.py test
```

In the PR, add a row to the *Tested controllers* table in the README (model, BLE name, protocol) and, if you can, attach the relevant Wireshark packets.
