# Maverick hardware tests

Target: Raspberry Pi 4 running Android directly. These are hardware integration
checks, with manual IMU/HUD validation. Keep them separate from production code.

## Four phases

Verify and commit each phase before starting the next. Never report a physical
test as passed from a build, simulator, or documentation-tool response.

| Phase | Gate before the next phase |
| --- | --- |
| 1. MCP + SDK setup | MCP handshake and tool call work; `verifySdk` passes |
| 2. Connection | On the Pi, SDK reaches authenticated `onReady`; timeout/error fails |
| 3. IMU read | Independent connection; stream live IMU for 30 seconds; user checks movement against values |
| 4. HUD write | Independent connection; show a short test message; user confirms visibility |

Each hardware test starts from a fresh SDK session, disconnects and unregisters
listeners on exit, and requires no previous test run. All four phases passed,
including user validation of IMU movement/value changes and visible HUD blinking.

## Phase 1

The [official MCP](https://everysight.github.io/maverick_docs/libraries-api/mcp/)
provides documentation/API tools; it does not connect to physical glasses.
Register it in Codex:

```sh
codex mcp add everysight-maverick --url https://mcp-sdk.everysight.com/mcp
codex mcp get everysight-maverick
```

If the registered tools are not visible, restart the agent session.
Registration alone is not a successful tool call.

The [Android SDK](https://everysight.github.io/maverick_docs/libraries-api/android/)
uses **two separate credentials**:

- Root `glasses_sdk.key`: existing, ignored glasses developer license. Later,
  package it as `sdk.key` in the local test APK; never log its contents.
- GitHub username + token with `read:packages`: downloads SDK **2.6.1**.
  Set `github.user` and `github.token` in the ignored `SECRETS.local.properties`
  in this folder, or set `GITHUB_ACTOR` and `GITHUB_TOKEN`.

With JDK 17+ configured, run from the repository root:

```sh
'Unit Tests/maverick/gradlew' -p 'Unit Tests/maverick' verifySdk
```

This downloads and checks the vendor AAR and JVM library and lists native ABIs. It does not
compile an Android app or validate the license. Match the reported ABI to the Pi
before phase 2. No SDK binary or credential belongs in Git.

## Phase 2 — handshake

Requires JDK 17+, Android SDK platform/build tools 36, and the Pi connected to ADB.
Set `ANDROID_HOME` to the SDK directory. Build/test commands run in this folder.
The build copies the ignored root glasses key into generated APK assets as
`sdk.key`; treat the APK as private too.

Power on the glasses near the Pi, enable Bluetooth on the Pi, and close any
other app connected to the glasses and Android's Pair new device screen.
The Pi needs internet for certificate
generation and a correct system clock.

```sh
./gradlew assembleDebug assembleDebugAndroidTest lintDebug
ANDROID_SERIAL=<PI_SERIAL> ./gradlew connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.class=org.aerovision.maverick.HandshakeTest
```

Keep the Pi screen awake during discovery. The test scans BLE advertisements for
10 seconds, selecting devices by the Maverick service UUID or the documented
`EV` + digits name pattern. It requires exactly one candidate; the SDK handshake
then verifies it is usable glasses. To select an exact advertised name, append
`-Pandroid.testInstrumentationRunnerArguments.name=EV0662`. To bypass scanning
with a known address, use
`-Pandroid.testInstrumentationRunnerArguments.address=AA:BB:CC:DD:EE:FF`.
It waits up to 60 seconds for authenticated `onReady`, then checks `isReady()`.
Success is `PASS test=handshake authenticated=true` plus the runner's successful
test result. Bluetooth `CONNECTED` alone is insufficient.

## Phase 3 — IMU

Run this test alone; it scans and authenticates independently:

```sh
ANDROID_SERIAL=<PI_SERIAL> ./gradlew connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.class=org.aerovision.maverick.ImuTest
```

After `STREAM_START`, hold still for 5 seconds, gently tilt/rotate the glasses,
then hold still again. The window lasts 30 seconds. Check that acceleration
changes with tilt, gyroscope values respond to rotation and settle when still,
and magnetic axes vary with heading. This is user validation, not calibration.

Logs show `acc` in m/s², `gyro` in rad/s and `mag` in mGauss, with the original
SDK `ts_ns` and Pi receipt time `rx_ms` relative to the window setup. Callbacks
can arrive in batches. Non-repeated callbacks are counted and values checked for
finiteness; duplicate timestamps are counted separately. Backwards SDK timestamps
are preserved and reported with `TIMING_WARNING` and `BACKWARDS`, not rewritten.
A sensor with no new timestamp for 3 seconds fails the delivery check after
the initial 5-second grace period. Logs are limited to about two samples per
second per sensor; log-line count is not a packet-loss measurement.

Sensors are disabled and listeners removed at the end. The runner verifies
delivery; `manual_validation=pending` requires the user's movement/value check
before phase 3 is complete.

The IMU test turns on a blank display, as in the vendor sensor sample, to keep
the SDK rendering/sensor pipeline active. This does not test visible HUD content.

## Phase 4 — HUD write

Wear the glasses, then run this test alone:

```sh
ANDROID_SERIAL=<PI_SERIAL> ./gradlew connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.class=org.aerovision.maverick.HudTest
```

It scans/authenticates independently and displays centered green **MAVERICK OK**
text, alternating one second visible / one second hidden for 16 seconds. It then
removes the screen, turns off the display and disconnects. The runner checks
connection and write completion; the user must confirm visibility and blinking.

## Laptop logs

Use ADB logcat over USB initially; it needs no extra logging service. The test
runs on Android on the Pi, while the laptop displays its logs:

```sh
adb devices -l
adb -s <PI_SERIAL> logcat -v monotonic 'MaverickTest:I' '*:S'
```

The hardware tests will use `MaverickTest` for short state/error lines, source
mode (`live`), IMU axes with units, original SDK sample time when available,
and a final sample count. Preserve sample timing; Bluetooth may deliver batches.
Successful data delivery is separate from the user's physical validation.

## Verification — 2026-11-24

- Official MCP health: healthy, SDK version 2.6.1; six tools listed.
- MCP JSON-RPC `initialize` and `tools/call` (`get_code_sample`): succeeded;
  Android Hello World returned. The native Codex MCP tool call also succeeded.
- Codex registration: `everysight-maverick`, enabled, HTTP endpoint `/mcp`.
- Gradle 9.1.0: `help` and `verifySdk` passed using local package credentials.
  Verified `NativeEvsKit-jvm-2.6.1.jar` and `evskit-2.6.1.aar`; native ABIs:
  `arm64-v8a`, `x86_64`.
- Initial missing-credentials gate behaved correctly; the saved GitHub HTTPS
  credential returned HTTP 401. The new local package token resolved that block.
- Phase 2: Android/test APK builds and `lintDebug` passed (warnings only).
  Pi handshake passed with automatic discovery and no name/address arguments:
  85 advertisements, one Maverick candidate, one test, zero failures;
  `CONNECTED` → `AUTH` → `READY` → PASS → STOP. No IMU/HUD result yet.
- Initial service-only scan found zero devices; exact-name discovery succeeded.
  The final automatic scan selects the vendor service UUID or `EV` name pattern.
  The Pi's wireless ADB address changed during setup; it was reconnected.
  Its clock was corrected from November 14 to November 24 before authentication.
- Tested versions are recorded in the [project version table](../../README.md#software-versions).
  Setup, failed/passed runner reports, logs and tested-source hashes are local
  under `local_data/maverick/phase2-20261124/` (ignored).
- Phase 3 delivery passed for a 30-second window with the blank display on:
  non-repeated callbacks `acc=987`, `gyro=987`, `mag=786`; repeated timestamps
  `acc=2180`, `gyro=2180`, `mag=5`; one backwards magnetometer timestamp.
  The user watched terminal logs and confirmed expected movement/value changes.
  The standalone handshake regression and lint passed.
- Earlier IMU attempts exposed repeated/backwards SDK timestamps, a remote
  power-off disconnect, and one native Pi Bluetooth assertion/restart while
  system discovery was active. Those failures remain in ignored local evidence
  under `local_data/maverick/phase3-20261124/`; long-term link/timing robustness
  and calibration are not established by these checks.
- Phase 4: APK build and lint passed; standalone Pi HUD test passed (one test,
  zero failures). The user confirmed the green message and blinking were visible.
  Runner reports, logs, source hashes and manual confirmation are local under
  `local_data/maverick/phase4-20261124/` (ignored).
