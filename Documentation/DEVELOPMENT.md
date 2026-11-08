# Development

## Implementation sequence

1. Select and boot Android on the Pi. Record image source, release/checksum, API level, ABI, power setup and Bluetooth/Wi-Fi behavior.
2. Initialize the Android project in `raspberry_pi_hub/` and map its source sets to the four folders listed in the [hub guide](../raspberry_pi_hub/README.md). Keep the flat layout; Java/Kotlin package declarations do not require the repository to mirror a long package path.
3. Run a minimal app and the Maverick vendor sample on the actual Pi. Verify an HRM notification and investigate Atlas live access before committing to its fields.
4. Agree on one sample contract. Implement sensor → telemetry → HUD, then local persistence, cloud ingestion and coach display.
5. Test concurrent links and interruption/recovery before adding further features.

Add build, install and test commands to the relevant component README when they have been verified. Record tested versions in the root README. Framework projects and dependency versions are not supplied by this scaffold.

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

Keep standalone hardware diagnostics in [Unit Tests](<../Unit Tests/README.md>). Add automated logic and Android runtime tests when the build project is initialized, with their locations configured in its source sets.

For a hardware result, record the commit, device/image/SDK versions, setup, input mode, expected behavior, observed result and limitation. Report measured latency and losses with the clock method and workload. Synthetic or replay input must remain identifiable throughout the pipeline.
