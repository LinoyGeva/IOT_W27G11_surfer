# Android hub

Implement the hub in `main/` and each device in its named sibling folder. See [Architecture](../Documentation/ARCHITECTURE.md) for responsibilities.

## Project layout

This folder is a single-module Gradle project (no `app/` module). [build.gradle.kts](build.gradle.kts) maps the flat folders as [source sets](https://developer.android.com/build/build-variants#change-default-source-set-configurations):

| Folder | Contents |
| --- | --- |
| `main/` | `AndroidManifest.xml`, `res/`, `kotlin/` (startup and control screen) |
| `maverick/` | `kotlin/` (SDK wrapper, HUD screen, connection state), `test/` (unit tests) |
| `garmin_hrm/`, `vakaros_atlas/` | Not implemented; add `kotlin/` and `test/` to the source sets when started |

Maverick integration uses the classic Maverick SDK (`com.everysight:evskit` / `nativeevskit` 2.6.1, minSdk 30). Its calls follow the official [Android samples](https://github.com/everysight-maverick/samples/tree/main/android) and [SDK docs](https://everysight.github.io/maverick_docs/).

## Local setup

1. Copy [SECRETS.example.properties](SECRETS.example.properties) to `SECRETS.local.properties` and fill in:
   - `github.user` / `github.packages_token`: a GitHub token with `read:packages`, required to download the SDK.
   - `maverick.api_key_file`: path to the key file from Everysight (for example `sdk.key` in this folder). Without it the app still builds and shows "API key missing", but the glasses will not authenticate.
2. Open this folder in Android Studio (JDK 17). The wrapper scripts are not committed; Android Studio uses [gradle-wrapper.properties](gradle/wrapper/gradle-wrapper.properties), or run `gradle wrapper` with a local Gradle 8.13.
3. On first launch, grant the Bluetooth permission, press **Pair glasses**, and select the glasses in the SDK's pairing UI. Later launches reconnect automatically.

## Status

| Check | Result |
| --- | --- |
| Connection-state unit tests (`maverick/test/`) | Pass, 7 tests, compiled outside Gradle with standalone Kotlin 2.2.20 + JUnit 4.13.2 |
| Gradle build / APK | Not yet built: needs the SDK token and an Android SDK |
| Glasses connection, HUD text, orientation readings | Not yet tested on hardware |

Unverified until the first build: `YprData.pitch`/`roll` (only `yaw` appears in the samples), and the angle units and clock of the orientation timestamp. Replace this table with verified build, install and test commands after the first run on the Pi.
