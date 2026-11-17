# Development

## Implementation sequence

1. Select and boot Android on the Pi. Record image source, release/checksum, API level, ABI, power setup and Bluetooth/Wi-Fi behavior.
2. Initialize the Android project in `raspberry_pi_hub/` and map its source sets to the four folders listed in the [hub guide](../raspberry_pi_hub/README.md). Keep the flat layout; Java/Kotlin package declarations do not require the repository to mirror a long package path.
3. Run a minimal app and the Maverick vendor sample on the actual Pi. Verify an HRM notification and investigate Atlas live access before committing to its fields.
4. Agree on one sample contract. Implement sensor → telemetry → HUD, then local persistence, cloud ingestion and coach display.
5. Test concurrent links and interruption/recovery before adding further features.

The Android project and first Garmin milestone are initialized; verified commands are in the [hub guide](../raspberry_pi_hub/README.md). Record tested versions in the root README. Other component projects remain to be implemented.

## Configuration

Document public settings in [Parameters](../Parameters/README.md). Component secrets templates use `SECRETS.example.*`; local copies use `SECRETS.local.*` and are ignored by Git. Configuration loading remains to be implemented. Client applications must not contain backend administrator credentials.

## Verification

| Area | Check |
| --- | --- |
| Parsing | Packet flags, lengths, units, invalid and missing fields |
| Freshness | Source loss becomes visible; old records never appear current |
| Recovery | Reconnect leaves one listener; independent sources continue |
| Persistence and upload | Bounded queue, overflow behavior, restart recovery and idempotent retries |
| Concurrency | HRM, board and glasses active together under upload load |
| Isolation | Rider/session assignments and cloud access rules prevent data mixing |
| Motion | Axes, calibration and original sample timing are preserved |

Keep exploratory sensor receivers, protocol notes and bench experiments in
[sensor_understanding](../sensor_understanding/README.md), under one subdirectory
per sensor. Their local decoder/harness regression checks remain alongside those
tools; they are not the Android/Pi implementation's test suite. Production Garmin
unit tests use `raspberry_pi_hub/tests/`; Android radio/hardware evidence is recorded
separately in the [Garmin guide](../raspberry_pi_hub/garmin_hrm/README.md). Add tests
for subsequent components using the configured source sets. See
[implementation test guidance](<../Unit Tests/README.md>).

`Unit Tests/run_tests.py` is the Python entry point for offline sensor checks,
the native controller unit suite, sensor-independent Pi health and private CSV replay.
Sensor-dependent BLE/ADB checks live in `Integration Tests/` and run with
`--suite integration`; Pi-only Wi-Fi/BLE/storage diagnostics use `--suite health`.
The runner keeps interactive inspection separate and records pass/fail/skip evidence in
ignored `local_data/unit_tests/`. See its README for exact target and hardware scope.

For a hardware result, record the commit, device/image/SDK versions, setup, input mode, expected behavior, observed result and limitation. Report measured latency and losses with the clock method and workload. Synthetic or replay input must remain identifiable throughout the pipeline.
