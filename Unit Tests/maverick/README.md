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

Each hardware test will start from a fresh SDK session, disconnect and unregister
listeners on exit, and require no previous test run. Tests 2–4 are not implemented
yet.

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

With Gradle installed, run from the repository root:

```sh
gradle -p 'Unit Tests/maverick' verifySdk
```

This downloads and checks the vendor AAR and JVM library and lists native ABIs. It does not
compile an Android app or validate the license. Match the reported ABI to the Pi
before phase 2. No SDK binary or credential belongs in Git.

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
  `arm64-v8a`, `x86_64`. Android build and Pi runtime remain untested.
- Initial missing-credentials gate behaved correctly; the saved GitHub HTTPS
  credential returned HTTP 401. The new local package token resolved that block.
- ADB: no attached devices. No Pi/glasses hardware result is claimed.
