# HR band: first Mac experiment

Goal: capture real Bluetooth packets and decode BPM. This standalone Python tool
is separate from the final Android hub. Intended device: Garmin HRM-Dual;
confirm the model on your band before treating results as Garmin evidence.

## Run

Wear and activate the band according to its manual. Turn Bluetooth on. Allow
Bluetooth access for Terminal or VS Code when macOS asks. If connection fails,
close other apps connected to the band and retry.

From the repository root (setup commands, not yet verified with hardware):

```sh
python3 -m venv local_data/hr-venv
source local_data/hr-venv/bin/activate
python -m pip install -r "sensor_understanding/garmin_hrm/requirements.txt"
python "sensor_understanding/garmin_hrm/hr_diagnostic.py"
```

Copy the band's identifier from the scan, then replace `IDENTIFIER` below:

```sh
python "sensor_understanding/garmin_hrm/hr_diagnostic.py" --device IDENTIFIER --seconds 30
```

If the scan shows no band, rerun with `--all`. Select only your own device.
The program lists services, subscribes to heart-rate notifications, and prints
BPM and raw bytes. Raw packets, decoded fields and host receipt timestamps go
to `local_data/garmin_hrm/live-*.jsonl` (ignored by Git). These timestamps are
not sensor measurement times. Unexpected disconnection ends the run visibly;
rerun the command to test manual reconnection. Automatic recovery is a later step.

## Understand the packet

The [Bluetooth Heart Rate Service](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/HRS_v1.0/out/en/index-en.html)
defines service `180D` and measurement characteristic `2A37`. The first byte
contains flags: bit 0 selects 8/16-bit BPM, bits 1–2 describe skin contact,
bit 3 adds energy expended, and bit 4 adds RR intervals. Multi-byte numbers are
little-endian; RR units are 1/1024 second. Optional fields are decoded when
present; their availability on this band is unverified.

Synthetic example: `00 48` means flags `00`, then `0x48` = **72 BPM**.
The tool receives notifications using [Bleak](https://bleak.readthedocs.io/en/stable/api/client.html).
[Bleak 0.22.3](https://pypi.org/project/bleak/0.22.3/) supports Python 3.9.

## Check and record

Expected: real notifications containing decodable heart rate, then another
successful capture after disconnecting and reconnecting. Compare with a trusted
display if available; otherwise mark numerical accuracy as unverified.

Observed hardware result: **pending**. Keep the capture locally and record the
commit, band model/firmware (or unknown), macOS/Python/Bleak versions, setup,
input mode (`live`), expected/observed behavior and limitations, as required by
[Development](../../Documentation/DEVELOPMENT.md).

Decoder checks need no band or installed Bleak (all inputs are synthetic):

```sh
python3 -B -m unittest discover -s "sensor_understanding/garmin_hrm" -p 'test_*.py' -v
```
