# Unit tests and standalone controller diagnostics

Interactive inspection/plots remain in [`sensor_understanding/`](../sensor_understanding/README.md).
Tests that need a sensor connection are in [`Integration Tests/`](<../Integration Tests/README.md>).
This directory owns isolated parsing tests, the native software unit-test entry
point, private recorded-data comparisons and sensor-independent Pi health checks.

## Organization

```text
Unit Tests/
  run_tests.py          Shared Python runner, results and suite selection
  requirements.txt      Optional BLE dependencies for the integration suite
  garmin_hrm/
    test_protocol.py    Six synthetic HR decoding checks
  vakaros_atlas/
    test_protocol.py    Six synthetic decoding/state/subscription checks
    test_export.py      Three optional recorded app-export comparisons
  controller/
    test_native.py      Six Python groups invoking the real Kotlin unit tests
    test_health.py      Eight Pi-only health checks; no HR or Atlas required
  support/              Shared test helpers and four fault-harness safety regressions
```

## Choose the right suite

| Suite | Dependencies | Purpose |
| --- | --- | --- |
| `offline` | Python standard library; synthetic packets/fakes | Existing Python headless decoders, Atlas freshness/subscription behavior and fault-harness prerequisites |
| `native` | Java/Android SDK/Gradle; no Pi or sensor | Actual Kotlin production parsing/session logic, invoked by Python |
| `health` | Android Pi reachable by ADB; no sensor | Boot/services, BLE readiness, Wi-Fi association/routing, storage and hub APK integrity |
| `replay` | Private app CSV and reconstructed recorded samples | Recorded field mapping/units; no live or screen-validation claim |
| `integration` | Real sensor(s), and Pi for the controller case | Connect/subscribe/stream and fault recovery across real components; source in `Integration Tests/` |

The native suite groups 19 Kotlin cases into six Python-reported checks; those
six are not additional independent unit tests. It tests production code, not a
Python controller imitation. Broader controller forwarding/background logic and
the Android Atlas adapter remain unimplemented.

The course's “Unit Tests” terminology also covers standalone device diagnostics.
Here, `health` is a standalone controller diagnostic; `offline`/`native` are
software unit tests. Integration checks retain their explicit separate name.

## Software checks without hardware

Run from the repository root:

```sh
python3 -B "Unit Tests/run_tests.py" --suite offline
python3 -B "Unit Tests/run_tests.py" --suite offline --sensor hr
python3 -B "Unit Tests/run_tests.py" --suite offline --sensor atlas
python3 -B "Unit Tests/run_tests.py" --suite native
```

Offline orchestration needs only the standard library (verified with Python 3.9;
Python 3.11+ recommended). It imports existing headless parsing helpers, without
launching their command-line programs, GUI or Bluetooth acquisition.

Garmin cases cover unsigned 8/16-bit and zero BPM, contact/energy/RR flags and
units, missing fields, malformed lengths and optional-field resets. Atlas cases
cover angle offsets including zero GPS, channel/header/length classification,
nonfinite rejection, stale/disconnected values, valid-packet gaps, opaque bytes,
subscription/activation ordering, cleanup and invalid GATT layouts. Four shared
safety tests prevent wrong-device absence passes and misleading restore prompts.

The inspection HR decoder still rejects an RR flag with zero intervals; the
production Android decoder accepts that SIG-compatible case. Atlas unknown clock,
heading/speed and tail meanings are not invented. See its
[protocol and CSV field reference](../sensor_understanding/vakaros_atlas/README.md).

The native suite uses the [hub Java/SDK setup](../raspberry_pi_hub/README.md) and
fails if a required JUnit case fails/skips or Gradle produces no cases. It covers
production decoding, selection/subscription/CCCD failure, freshness/clock provenance,
reconnect/old or duplicate callbacks, connection/silence timeouts and explicit stop.

## Pi controller health — no sensor needed

Keep the Pi booted, joined to Wi-Fi and Bluetooth enabled. ADB must be connected.
The AeroVision screen does not have to be open, and neither Garmin nor Atlas
needs to be powered on.

```sh
python3 -B "Unit Tests/run_tests.py" --suite health --sensor controller --pi 10.100.102.11:5555
```

| Case | Assertion |
| --- | --- |
| 01 | Android boot completed and API level supports the hub |
| 02 | Activity, package, Wi-Fi and Bluetooth manager services respond |
| 03 | Android reports Bluetooth LE hardware support |
| 04 | Bluetooth adapter is enabled and fully ON |
| 05 | Wi-Fi is enabled and associated with an access point |
| 06 | Wi-Fi has usable IPv4 and a default gateway on that interface |
| 07 | A uniquely named temporary `/data/local/tmp` file survives a write/read round trip, then is removed |
| 08 | Installed hub APK SHA-256 matches the expected local build |

Use `--adb /path/to/adb` if needed. Case 08 defaults to the built debug APK;
use `--apk /path/to/expected.apk` to select another known build. If the local
reference is absent, that integrity check is explicitly skipped. A checksum
mismatch can mean an older installed version; it does not alone prove corruption.
The other seven health checks do not depend on the hub app being installed.

This suite does not toggle radios or connect to a sensor. It verifies Wi-Fi
association/IP/routing, not Internet or DNS availability. BLE readiness does not
prove a peer link or RF performance. The storage round trip and APK checksum
are bounded integrity checks, not a complete SD-card/filesystem/Android-partition
verification. A full corruption check requires a known image/reference and a
separate maintenance procedure; this suite does not claim to supply one.

## Run the private CSV replay comparison

```sh
python3 -B "Unit Tests/run_tests.py" --suite replay --csv "packet_inspection/A10 11-10-2026.csv" --recorded local_data/vakaros_atlas/pklg-20261110/downloaded-records.jsonl
```

These files are private and stay outside Git. `--recorded` is the already
reconstructed capture data, not a live notification log. Without either file,
this replay check is unavailable; do not replace it with synthetic data and call
that a recording match. The original files are never modified. The comparison
writes source hashes and per-field error maxima to `export-comparison.json`.

## Results and evidence

Every run saves `results.json` and JUnit-compatible `results.xml` under ignored
`local_data/unit_tests/<UTC-run-id>/`. Metadata records the suite and source mode
(`synthetic`, `replay` or `live`). Health/integration runs also save private
`hardware.jsonl`; host clocks are reception/diagnostic clocks, not sensor clocks.
Original recordings and network details stay outside Git. Exit 0 requires no
failures and at least one passed case; skipped checks are not passes. Empty case
filters and the obsolete `--suite hardware` command produce explanatory errors.

Verified on 2026-11-14: all 16 offline checks; six native groups backed by 19
Kotlin tests; three replay checks matching 727 exported samples; and **all eight
Pi-only health checks**, without a sensor connection. The sensor-dependent
integration results and limitations belong to the separate
[integration guide](<../Integration Tests/README.md>).
