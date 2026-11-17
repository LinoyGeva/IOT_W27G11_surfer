# Garmin HR: first Android hub milestone

This adapter acquires live heart-rate notifications directly on the Android Pi.
The [Mac sensor investigation](../../sensor_understanding/garmin_hrm/README.md)
remains separate. Build/install commands belong in the [hub guide](../README.md).

## Plan and implementation

1. Write unit tests for packet decoding and connection/freshness behavior.
2. Implement that logic independently of Android, then connect it to native BLE.
3. Build and install on the Pi; establish live reception, interrupt Bluetooth,
   restore it, and inspect recovery separately from unit-test results.

`HeartRateDecoder.kt` parses the standard Heart Rate Measurement characteristic.
`GarminSession.kt` owns connection state, freshness, retries and reading provenance.
`AndroidGarminBle.kt` owns Android scanning, GATT callbacks and subscription.
`main/HubActivity.kt` displays readings and emits JSON to the `AeroVisionHR` logcat
tag. No Python receiver, Flutter runtime or Linux bridge runs on the Pi.

Discovery filters for Heart Rate Service `180D`; the user selects their band.
Each connection attempt rediscovers that selected address before opening a fresh
GATT client (`autoConnect=false`, LE transport). Service discovery requires a
notifying `2A37` characteristic and `2902` CCCD. Local notification routing is
enabled, then `01 00` is written to the CCCD. Subscription is ready only after
the descriptor-write callback succeeds; a real valid notification is required
before reporting `STREAMING`. No proprietary Garmin start command is used.

The decoder follows the [Bluetooth Heart Rate Service specification](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/HRS_v1.0/out/en/index-en.html):

| Field | Interpretation |
| --- | --- |
| Flags | First byte; controls format and optional fields |
| Heart rate | Unsigned 8-bit, or unsigned little-endian 16-bit when bit 0 is set; BPM |
| Contact | Bit 2 declares support; bit 1 then indicates contact; otherwise unknown |
| Energy | Optional unsigned little-endian 16-bit kJ, controlled by bit 3 |
| RR intervals | Optional little-endian 16-bit values, controlled by bit 4; each unit is 1/1024 second |

Truncated fields, incomplete RR values and unexpected trailing bytes are rejected.
The variable RR field may contain zero intervals. Zero BPM is distinct from a
missing measurement; the parser does not impose physiological limits.

## Freshness and recovery policy

The scan window and each connection/discovery/subscription deadline are 10 seconds.
At 5 seconds without a valid notification, BPM is hidden and the state becomes
`STALE`. At 10 seconds, the connection is closed and retried after 2 seconds.
Disconnects and GATT failures also trigger cleanup/retry. These are receiver
policies, not measured sensor sample latency. Retries rediscover only the selected
address, rather than choosing another nearby band.

Old callbacks are rejected using session generations and GATT object identity.
Each connection gets a new connection ID and resets its sequence. Stop cancels
retries. Acquisition is foreground-only: leaving the activity stops it; returning
requires scanning/selecting again. A background service is a later milestone.

Each accepted reading contains raw hex, decoded fields, selected device address,
run ID, connection ID, sequence and `input_mode=live`. Reception UTC and Android
`elapsedRealtime` are host metadata, not bytes sent by the band. Freshness uses
the monotonic reception clock. The BLE measurement has no sensor timestamp or
sequence counter, so host arrival gaps cannot prove sensor sample latency or
radio packet loss. RR intervals describe beats, not BLE delivery times.

## Verification

Tests in `../tests/garmin_hrm/` were written before their production classes. The
initial test compilation failed on missing decoder/session types; after implementation,
**19 local JVM tests pass**: nine decoder tests and ten session tests. The session
tests use a fake BLE port and clock, without real radio calls or sleeps.

Coverage includes unsigned 8/16-bit values, flag changes, contact/energy/RR units,
malformed lengths, discovery and subscription ordering, scan deduplication,
freshness, invalid-packet handling, deadlines, disconnect/retry, late and duplicate
callbacks, failed subscription, and explicit stop. They validate production logic;
they do not validate Android permissions, the radio or physical accuracy.

The debug APK builds and Android lint completes with no errors. Remaining lint
warnings concern available dependency updates, backup configuration, a launcher
icon and UI text localization. See the root [tested versions](../../README.md#software-versions).

### Pi bench record — 2026-11-14

- **Question/acceptance:** Does the native Android adapter receive the worn band,
  hide expired data and resume after Bluetooth interruption without restarting?
- **Operator/source:** Automated Mac/ADB bench with the user wearing the band;
  working-tree implementation, not a committed release. Local evidence includes
  APK/source hashes and red/green build output.
- **Setup:** Raspberry Pi 4, emteria Android 14/API 34; HRM-Dual advertised as
  `HRM-Dual:764626`; user confirmed competing apps closed. Band firmware and image
  checksum were not recorded. Live input; no synthetic packets injected into the app.
- **Baseline:** 395 consecutive receiver records over 290.212 seconds, BPM 56–82,
  median host reception gap 742 ms, maximum 991 ms. Successful service discovery,
  CCCD subscription and real notifications were observed. This is delivery timing,
  not physiological accuracy or end-to-end sample latency.
- **Fault and diagnosis:** Turning Pi Bluetooth off correctly removed current BPM
  and led to retries. Direct GATT reconnects after restoring Bluetooth timed out;
  a manual rescan recovered. That initial attempt is not an automatic-recovery pass.
  The Android port was changed to rediscover the selected band before each connection.
- **Recovery after fix:** With Bluetooth disabled for 12 seconds, the log showed
  `STALE`, then retries, then discovery/subscription and live notifications after
  restoration. The same run ID continued from connection 1 to connection 3
  (connection 2 failed while Bluetooth was off). The first recovered sequence
  was 1; eight recovered readings were captured at the first check, without a
  manual rescan or app restart. The receive gap across the interruption was
  16.086 seconds, including the deliberate outage; this is not a sensor latency.
  The follow-up capture reached 100 readings on connection 3 with unique receiver
  sequences; the Pi screen showed `STREAMING`, 67 BPM, packet 100.
- **Evidence:** Ignored `local_data/garmin_hrm/pi-20261114/` contains app JSON/logcat,
  screenshots, test reports, build logs and the experiment summary. Device addresses
  and captures are kept local.
- **Limits:** No independent HR reference comparison, background acquisition,
  permission-denial hardware test, multi-sensor concurrency, glasses/cloud delivery
  or extended soak test has been completed. The current app does not persist
  telemetry; logcat is bench evidence and can rotate.
