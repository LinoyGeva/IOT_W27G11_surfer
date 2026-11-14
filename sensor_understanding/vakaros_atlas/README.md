# Vakaros Atlas 2 BLE specification and bench tools

This is the current reference for the direct BLE receiver. It documents the
wire exchange recovered from Connect and received independently on the Mac.
The [investigation history](INVESTIGATION.md) owns the experiments, measurements,
failed approaches and evidence files.

**Scope:** Atlas model `Atlas2,0`, last inspected firmware `0.32.0`. Live packet
reception on the Mac is established. The angle interpretation is supported by
recorded-data comparisons, but simultaneous live screen agreement, mounting
corrections, damping, power-cycle independence and Android/Pi operation remain
unverified. This is an observed protocol subset, not a vendor-supported SDK.

The target hub remains [Android directly on Raspberry Pi 4](../../Documentation/ARCHITECTURE.md).
Python is a standalone bench tool. Neither Connect, an Apple tool nor a cloud
service is a runtime dependency of the direct receiver.

## Files and responsibilities

| File | Purpose |
| --- | --- |
| `live_atlas.py` | Scan, device selection, GATT subscriptions, activation, packet classification, freshness, interval statistics and JSONL capture |
| `plot_atlas.py` | Live signed-angle graph and supervision of fresh BLE collector processes |
| `test_live_atlas.py` | Synthetic discovery, decoding, activation, silence and freshness checks |
| `test_plot_atlas.py` | Signed display, queue, statistics display and collector lifecycle checks |
| `requirements.txt` | BLE dependencies for the headless receiver |
| `requirements-plot.txt` | BLE dependencies plus Matplotlib for the graph |
| `README.md` | Current protocol, operation and integration guidance |
| `INVESTIGATION.md` | Chronological investigation and evidence |

The active tools contain no recorded-session downloader, old trigger probes or
recorded-plot fallback. The history explains where those experiments were kept.

## Discovery and identity

1. Power on the Atlas and close competing Atlas applications, including Connect.
2. Scan BLE advertisements. The bench default is a ten-second scan. Preserve the
   advertised name, receiver-local device identifier, RSSI, service UUIDs,
   manufacturer data and service data.
3. Identify the physical Atlas by comparing scans with it powered off/on. Names
   such as `Atlas` and `ATLAS270EF` have been seen; a name alone is not a unique
   identity. The scanner also retains unnamed devices.
4. Select that exact device identifier. The receiver never auto-connects to the
   first device with a matching name.
5. Connect and discover its GATT services and characteristic properties before
   subscribing or writing. Refuse an unexpected service/property layout.

On macOS, CoreBluetooth supplies a host-local UUID, not the device's on-air MAC
address. The identifier in our commands below is specific to this Mac. Scan
again on a different receiver; do not copy it into the Pi implementation.

```sh
local_data/atlas-venv/bin/python "sensor_understanding/vakaros_atlas/live_atlas.py" --scan
```

`--scan` records advertisements and exits without connecting or activating a device.

## GATT service and characteristics

All UUIDs below are full 128-bit UUIDs. Discover by UUID; ATT handles from a
phone trace must never be hard-coded on another connection or host.

| Role | UUID | Used capability |
| --- | --- | --- |
| Atlas service | `ac510001-0000-5a11-0076-616b61726f73` | Contains the proprietary characteristics |
| Command 1 | `ac510002-0000-5a11-0076-616b61726f73` | Write without response for stream activation |
| Main telemetry | `ac510003-0000-5a11-0076-616b61726f73` | Notifications carrying live packets and other replies |
| Command 2 | `ac510004-0000-5a11-0076-616b61726f73` | Observed in inventory; unused by the retained receiver |
| Auxiliary/data | `ac510005-0000-5a11-0076-616b61726f73` | Notifications; used by recorded transfers in the investigation |

The working direct-receiver sequence subscribes to **both main and auxiliary**
channels, matching the successful setup. Whether main-only subscription is
sufficient has not been isolated. Auxiliary notifications are captured as raw
bytes and are not interpreted as live angles.

## Subscribe and start streaming

Perform these operations in order on one connection:

1. Resolve the main and auxiliary characteristics and verify `notify` support.
2. Enable notifications on main and await completion.
3. Enable notifications on auxiliary and await completion.
4. Verify Command 1 supports write-without-response.
5. Write the following three application bytes to Command 1, once:

   ```text
   02 09 01
   ```

   In Bleak this is `write_gatt_char(COMMAND, START_STREAM, response=False)`.
   Do not include the ATT opcode or an ATT handle in these application bytes.
6. Process each incoming main notification immediately. A completed write is not
   proof of streaming; actual valid angle packets must arrive.

At GATT level, notification subscription configures the characteristic's CCCD
(UUID `0x2902`); the notification-enable descriptor value is `01 00`. Bleak's
`start_notify` handles this. On Android, arrange both local notification routing
and the descriptor writes, and wait for their completion before activation.
Keep asynchronous GATT operations serialized.

There is no additional application authentication step in our successful direct
run. That observation does not prove all Atlas firmware behaves identically.
The retained receiver does not send the phone's other initialization queries,
request session lists, read telemetry by polling or download log chunks.

No application stop command has been established. Shutdown disables active
subscriptions where possible and disconnects. Do not guess a complementary
opcode or a reset command.

## Main live packet layout

Offsets are **zero-based within the notification value**, excluding ATT headers
and handles. The captured live notifications were 35 bytes and began `02 0a`.
The retained angle parser requires that exact prefix and at least 28 bytes so
both angle floats are present; it does not claim every accepted shorter packet
is a complete 35-byte message. All interpreted floats are little-endian IEEE-754
binary32 values.

| Offset | Bytes | Encoding | Interpretation and confidence |
| --- | ---: | --- | --- |
| 0 | 1 | U8 | Observed byte `02` |
| 1 | 1 | U8 | Observed live discriminator `0a` |
| 2–7 | 6 | Opaque | Changing counter/time-like bytes; origin, units and rollover unverified |
| 8–11 | 4 | F32 LE | Latitude candidate, consistent with geographic coordinates; not emitted by the current angle receiver |
| 12–15 | 4 | F32 LE | Longitude candidate, consistent with geographic coordinates; not emitted by the current angle receiver |
| 16–19 | 4 | F32 LE | Heading candidate; true/magnetic reference and corrections unverified |
| 20–23 | 4 | F32 LE | Trim candidate in degrees; mapping supported by the comparison in the history |
| 24–27 | 4 | F32 LE | Heel candidate in degrees; mapping supported by the comparison in the history |
| 28–31 | 4 | F32 LE | Unvalidated scalar; external code calls this speed, but units/meaning are not established here |
| 32–34 | 3 | Opaque | Unknown tail; do not assume flags, battery, sequence or checksum semantics |

The current code intentionally exposes only the two angle candidates and raw
packet evidence. It does not turn the other candidates into verified metrics.
Quaternion values used during the earlier investigation came from recorded VKX
logs and are not decoded from this live message.

### Angle extraction and signed display

The receiver reads `struct.unpack_from("<ff", packet, 20)` as `(trim, heel)`.
It rejects a candidate if either angle is nonfinite. It preserves raw angles in
its JSONL; the graph displays each using:

```python
signed_degrees = (raw_degrees + 180.0) % 360.0 - 180.0
```

For example, raw `357.48` becomes approximately `-2.52`. This is wrapping to
`[-180, 180)`, not a mounting correction, calibration or an added low-pass filter.
Raw angles and graph values must not be confused in comparisons.

GPS validity does not gate angle processing. A notification with near-zero or
missing GPS can still carry usable angles. The decoder does not invent zero
for absent, nonfinite or rejected angle fields.

### Packet classification

Only a main-channel packet with the live prefix is considered for attitude.
A `02 0b` main reply is a **recorded session-list response**, even if it is long
enough to contain arbitrary float-looking bytes. It must not refresh angles or
statistics. Unknown subtypes, truncated candidates and packets from other
channels remain raw evidence. The recorded-transfer CRC framing is not applied
to this live packet; no additional live-message checksum has been established.

## Timing, statistics and freshness

The demonstrated direct stream is approximately four packets per second; the
measurements and their setup are in the [history](INVESTIGATION.md#direct-mac-reception).
This is an observation, not a guaranteed device rate or end-to-end latency.

Each packet is journaled with raw hex, channel UUID, sequence, host UTC reception
time and host monotonic reception time. The unknown device clock bytes are not
used to calculate sample age. `input_mode=live` describes direct acquisition;
`heel_trim_verified=false` preserves the current validation limitation.

`mean_angle_packet_gap_ms` is the arithmetic mean of intervals between consecutive
**valid angle** callbacks in the current connection. It is unavailable before the
second candidate. `angle_packet_interval_count` counts the contributing intervals.
Unrelated packets cannot refresh it, and disconnect duration is excluded because
a fresh connection has a new state. The graph's time-since-reception indicator
is separate from this average.

After two seconds without a valid candidate, current numeric values become
unavailable. Existing graph lines are history. A connected BLE link with a stale
stream must never be presented as current telemetry.

## Graph lifecycle and reconnect policy

The GUI is separate from the BLE collector. It refreshes around every 50 ms and
plots incoming reception timestamps without sample interpolation or smoothing.
A bounded display queue favors recent updates if rendering falls behind; the
collector still writes original packets to JSONL. Delayed GUI delivery preserves
original reception timestamps and cannot make a stale packet fresh.

The current Mac recovery policy is:

| Condition | Action |
| --- | --- |
| Disconnect, failed connection or absent device | End the attempt; keep the graph open |
| Eight seconds without valid angles, even if BLE is connected | Collector exits so the connection can be rebuilt |
| GUI sees ten seconds of stream silence or 35 seconds of stuck startup | Ask the collector to stop |
| Collector fails to stop within three seconds | Terminate that process before replacing it |
| Previous collector has exited | Wait two seconds; launch a fresh collector process and rescan |
| New connection succeeds | Resubscribe, activate once, reset mean-gap statistics and plot history |
| Window closes | Stop collector and retries |

This fresh-process recovery replaces the earlier in-process loop. Its logic is
covered by software tests; repeatable physical recovery still needs a new test.
It is a Mac bench workaround, not a requirement to restart the Android hub.

## Run and verify

Run from the AeroVision repository root. With the existing plotting environment:

```sh
local_data/atlas-venv/bin/python "sensor_understanding/vakaros_atlas/plot_atlas.py" --device 00607A8E-48B3-0CEF-314F-1D24CC144127
```

For a bounded headless acquisition:

```sh
local_data/atlas-venv/bin/python "sensor_understanding/vakaros_atlas/live_atlas.py" --device 00607A8E-48B3-0CEF-314F-1D24CC144127 --start-stream --seconds 60
```

Omit `--start-stream` for a subscription-only observation. The headless command
makes one connection attempt; the graph provides continuous recovery. Exit 0
means candidates arrived while connected, 2 means no candidates/disconnect,
1 indicates an error and 130 indicates interruption. These codes do not certify
screen agreement.

For a fresh environment, select an installed Python 3.11+ explicitly (the example
uses Python 3.12) and install the appropriate requirements. Do not rebuild an
already working environment merely to run the retained tools:

```sh
python3.12 -m venv local_data/atlas-venv
local_data/atlas-venv/bin/python -m pip install --only-binary=:all: -r "sensor_understanding/vakaros_atlas/requirements-plot.txt"
```

`requirements.txt` alone is sufficient for headless use. The pins reflect the
previously installed Mac bench environment; a fresh installation was not repeated
as part of this cleanup. The existing Python 3.9 environment remains usable;
Python 3.12 was also used successfully for the independent receiver. If macOS
requests Bluetooth permission, allow the app running Python, such as Terminal
or VS Code. The PyObjC platform markers do not apply to non-macOS hosts.

Captures are created under ignored `local_data/vakaros_atlas/notification-live-*.jsonl`.
Phone traces and app exports stay in ignored `packet_inspection/`. They are not
required to run the receiver.

```sh
python3 -B -m unittest discover -s "sensor_understanding/vakaros_atlas" -p "test_*.py" -v
```

The retained suite verifies discovery, header/length/channel validation, zero-GPS
angle handling, command ordering and write mode, stale values, signed display,
mean gaps, nonblocking display updates, silence timeout and collector process
replacement. Synthetic fixtures and child-process tests are not hardware results.

## Porting the protocol to the Android Pi

Implement the device adapter directly in `raspberry_pi_hub/vakaros_atlas/` and
use the shared app lifecycle in `raspberry_pi_hub/main/`, following
[Architecture](../../Documentation/ARCHITECTURE.md) and
[Development](../../Documentation/DEVELOPMENT.md). Do not introduce a separate
Linux/Android bridge or depend on the Mac process supervisor.

Use Android BLE scanning, the Pi-local device identity, GATT discovery,
notification routing and CCCD completion, then the same application payload and
byte parsing described above. Serialize asynchronous GATT operations; after
source loss release the old GATT/listeners and build a fresh connection with
bounded retry delays. Preserve raw fields, units, source/session identity,
reception clocks and missing/stale state in the adapter's output.

Before promoting the angle labels to verified Heel/Trim: compare signed values
simultaneously with the Atlas screen in neutral and both tilt directions;
record mounting, offsets and damping. Then test power cycling with Connect
closed, recovery, concurrent device links and physical delivery timing on the
actual Android/Pi image. Packet spacing alone cannot establish sensor latency,
and success on the Mac cannot establish Android/Pi compatibility.
