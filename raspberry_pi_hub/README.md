# Android hub

One native Android application runs directly on the Pi. Gradle maps `main/`, `garmin_hrm/`, `vakaros_atlas/` and `maverick/` to its Kotlin source set, and `tests/` to its local JVM tests. See [Architecture](../Documentation/ARCHITECTURE.md) for responsibilities.

The first implementation is [Garmin HR acquisition](garmin_hrm/README.md). Atlas, Maverick, storage, upload and Flutter integration remain separate milestones.

The Pi screen is the hub's diagnostic/operator panel. The intended unattended
acquisition/transmission role and the current screen-lifecycle limitation are
defined in [Architecture](../Documentation/ARCHITECTURE.md#deployment).

## Build and unit tests

Install Android SDK platform 36 and build tools 36.0.0. Point an ignored `local.properties` at your SDK (`sdk.dir=/absolute/path/to/sdk`), or configure the SDK through Android Studio. The local setup uses the ignored `local_data/android-sdk/` directory.

From the repository root on this Mac:

```sh
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export GRADLE_USER_HOME="$PWD/local_data/android-gradle"
./raspberry_pi_hub/gradlew -p raspberry_pi_hub testDebugUnitTest assembleDebug lintDebug
```

The wrapper pins Gradle and its distribution checksum. Test reports are in `raspberry_pi_hub/build/reports/tests/testDebugUnitTest/`; the debug APK is `raspberry_pi_hub/build/outputs/apk/debug/AeroVisionHub-debug.apk`. Build outputs and SDK/cache files stay outside Git.

## Run on the Pi

With ADB connected to your Android Pi:

```sh
ADB="$HOME/Library/Android/sdk/platform-tools/adb"
PI_ADB_SERIAL="10.100.102.11:5555"  # Replace if the Pi address changes.
"$ADB" -s "$PI_ADB_SERIAL" install -r raspberry_pi_hub/build/outputs/apk/debug/AeroVisionHub-debug.apk
"$ADB" -s "$PI_ADB_SERIAL" shell am start -n org.aerovision.hub/.HubActivity
"$ADB" -s "$PI_ADB_SERIAL" logcat -v raw -s AeroVisionHR:I
```

Wear/activate the band, close competing connections, grant Nearby devices permission, scan, and select your band. Keep the app visible during this foreground acquisition milestone. Stop disconnects and cancels retries; leaving the app also stops acquisition. Returning requires scanning/selecting again.
