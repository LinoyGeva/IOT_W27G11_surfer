# Sensor and controller integration checks

These checks connect multiple real components. They are separate from software
unit tests, Pi-only health diagnostics and interactive inspection tools.

```text
Integration Tests/
  ble_checks.py                  Shared direct BLE connection/fault assertions
  garmin_hrm/test_hardware.py     Real Garmin on the Python receiver
  vakaros_atlas/test_hardware.py  Real Atlas on the Python receiver
  controller/test_hardware.py    Real Android Pi + Garmin, driven over ADB
```

Run through the shared [Python runner](<../Unit Tests/README.md>) from the repository
root using `--suite integration`. The old `--suite hardware` spelling now returns
an explanation rather than hiding sensor integration inside a controller health
check. Pi-only Wi-Fi/BLE/storage checks use `--suite health` and require no sensor.
The direct sensor cases 07–10 and Pi/Garmin cases 07–09 retain their previous IDs;
only their location and suite name changed.

## Direct sensor integration

Use a dedicated environment, Python 3.11+ explicitly if installed; the existing
working Atlas environment is also usable. For a new environment:

```sh
python3.12 -m venv local_data/sensor-tests-venv
local_data/sensor-tests-venv/bin/python -m pip install --only-binary=:all: -r "Unit Tests/requirements.txt"
```

First use the existing sensor scan commands to find the exact identifier on the
computer running Python. Close plots/receivers/phone apps competing for that
sensor. Wear the HR strap; power on Atlas and provide conditions where it emits
its live stream. A macOS identifier cannot be copied to a different receiver.

`HR_IDENTIFIER` and `ATLAS_IDENTIFIER` below are placeholders, not device names.
Replace them with the exact identifier printed by your scan. For example, scan
Atlas using `local_data/sensor-tests-venv/bin/python sensor_understanding/vakaros_atlas/live_atlas.py --scan`;
scan HR using `local_data/sensor-tests-venv/bin/python sensor_understanding/garmin_hrm/hr_diagnostic.py --all`.
The runner rejects known placeholder strings before touching Bluetooth.

```sh
local_data/sensor-tests-venv/bin/python "Unit Tests/run_tests.py" --suite integration --sensor hr --device HR_IDENTIFIER
local_data/sensor-tests-venv/bin/python "Unit Tests/run_tests.py" --suite integration --sensor atlas --device ATLAS_IDENTIFIER
```

Those commands run discovery/live telemetry and explicitly skip the two manual
fault cases. Add `--interactive` to run all four, with prompts to switch the
receiver's Bluetooth off/on and to deactivate/restore the selected sensor.
Recovery creates fresh BLE clients, scans, resubscribes, and reactivates Atlas.
It verifies the Python diagnostic path; it does not prove the Android adapter's
own reconnect policy. Use the controller test for that.

Use `--case test_09` to run only reconnection, or `--case test_10` for absence.
On macOS grant Bluetooth permission to the app launching Python (Terminal or
VS Code). No PacketLogger or Apple developer download is needed at runtime.
Do not connect these Mac BLE tests to a sensor simultaneously used by the Pi.

## Controller + Garmin integration

Install/launch the [hub app](../raspberry_pi_hub/README.md), activate the Garmin,
select it in the diagnostic panel, and leave that panel visible. The current
foreground-only limitation is still present. Python remains on the Mac; it is
not installed on Android.

```sh
python3 -B "Unit Tests/run_tests.py" --suite integration --sensor controller --pi 10.100.102.11:5555
python3 -B "Unit Tests/run_tests.py" --suite integration --sensor controller --pi 10.100.102.11:5555 --radio-cycle
```

Use `--adb /path/to/adb` if needed. The first command skips the radio fault. The
second explicitly authorizes switching **Pi Bluetooth** off for 12 seconds and
restoring it in cleanup, then waiting up to 60 seconds for automatic recovery.
Keep ADB connected over Wi-Fi/Ethernet/USB, not through Bluetooth. The check
requires the same run ID and device, a later connection ID and new telemetry;
a manual app restart is a failure. It does not claim recovery latency from a
sensor timestamp. Other Bluetooth devices on the Pi are also interrupted.

## Evidence and limitations

The shared runner saves pass/fail/skip results and live evidence in ignored
`local_data/unit_tests/<UTC-run-id>/`; result metadata says `suite=integration`.
That historical output parent is shared across all suite types and does not
change their classification. A skipped check is not successful hardware evidence.

The current Pi/Garmin integration needs the foreground diagnostic activity. It
does not test unattended acquisition, Atlas on Android, multi-sensor concurrency,
or delivery to glasses/cloud. Earlier Garmin Pi evidence is in the
[Garmin guide](../raspberry_pi_hub/garmin_hrm/README.md). The latest Pi/Garmin run
failed its live baseline while the app log ended in STOPPED/IDLE; do not count
that as a reconnect pass. New direct-BLE manual fault scenarios remain pending.
