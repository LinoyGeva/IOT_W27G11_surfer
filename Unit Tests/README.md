# Implementation tests

The Garmin and Atlas experiments have moved to
[sensor_understanding/](../sensor_understanding/README.md). They investigate the
sensors before integration and are separate from the Raspberry Pi implementation.

Implementation unit tests will be added when the Android/Pi code is initialized.
They should exercise the production decoders, state handling and other isolated
logic, using the module's configured test source sets. BLE/hardware checks and
end-to-end integration checks must be identified separately.

No final Android/Pi unit-test suite is implemented yet. Follow
[Development](../Documentation/DEVELOPMENT.md) when introducing it; this directory
does not supply a second application or test framework.
