# Sensor understanding

Standalone bench tools used to learn device discovery, BLE protocols, packet
formats, timing and behavior before implementing the Raspberry Pi adapters.

| Sensor | Investigation |
| --- | --- |
| [garmin_hrm/](garmin_hrm/README.md) | HR-band discovery, real notifications and heart-rate packet decoding |
| [vakaros_atlas/](vakaros_atlas/README.md) | Atlas BLE specification, live receiver and graph; [investigation history](vakaros_atlas/INVESTIGATION.md) |

These experiments are separate from the Android hub and its implementation test
suite. The adjacent `test_*.py` files are regression checks for the exploratory
decoders and bench harnesses; they do not validate the final Pi implementation.
Keep them with the tools they check. Each sensor guide gives its run commands,
evidence and remaining hardware checks.

Raw captures and virtual environments remain under ignored `local_data/`.
Use `live`, `replay` and `synthetic` input labels as appropriate. Moving the tools
does not change their capture locations or convert past evidence into a Pi result.

The next phase implements device adapters under `raspberry_pi_hub/` and adds
tests for that implementation. Follow [Architecture](../Documentation/ARCHITECTURE.md)
and [Development](../Documentation/DEVELOPMENT.md); [Unit Tests](<../Unit Tests/README.md>)
describes the distinction from these investigations.
