# AeroVision

**SURFER · Group 11 · Technion ICST**

AeroVision provides windsurfing telemetry through a heads-up display and a coach application. A Raspberry Pi 4 running Android collects sensor data, drives Everysight Maverick glasses, and synchronizes sessions with the cloud.

**Stage:** first Android hub milestone: Garmin HR decoding, unit tests and Pi BLE acquisition. See the [Garmin guide](raspberry_pi_hub/garmin_hrm/README.md) for validation and limitations. Team members: pending confirmation.

## Project guide

| Document | Purpose |
| --- | --- |
| [Architecture](Documentation/ARCHITECTURE.md) | Components, source directories and device integration |
| [Development](Documentation/DEVELOPMENT.md) | Implementation sequence, configuration and verification |
| [Sensor understanding](sensor_understanding/README.md) | Per-sensor bench tools, protocol notes and investigation evidence |
| [Course submission](Documentation/COURSE_SUBMISSION.md) | Required deliverables and unresolved course details |
| [Project proposal](<agent_docs/project proposal.pdf>) | Original proposal; available locally in the ignored agent_docs directory |

## Repository

```text
raspberry_pi_hub/
  main/            Hub startup, processing, storage and upload
  garmin_hrm/      Heart-rate device implementation
  vakaros_atlas/   Board device implementation
  maverick/        Glasses SDK and display implementation
  tests/           Production Android module's local JVM tests
flutter_app/       Coach application
cloud/             Backend and access rules
contracts/         Shared data definitions
sensor_understanding/  Per-sensor bench tools, protocols and investigation history
Unit Tests/        Isolated software tests, replay checks and Pi-only health diagnostics
Integration Tests/  Real sensor connections, telemetry and recovery checks
Parameters/        Public configuration catalog
Documentation/     Design, development and course requirements
Assets/            Poster and project media
agent_docs/         Local agent instructions and proposal
```

## Hardware

Planned quantities for one rider; equipment availability remains to be confirmed.

| Item | Quantity | Function |
| --- | --- | --- |
| Raspberry Pi 4 | 1 | Android hub |
| Garmin HRM-Dual | 1 | Heart-rate input |
| Vakaros Atlas 2 | 1 | Board telemetry; live protocol unverified |
| Everysight Maverick | 1 | HUD and motion readings |
| Storage, power, enclosure and network equipment | To determine | Deployment |

## Software versions

| Component | Tested version |
| --- | --- |
| Pi Android image and API level | emteria Android 14 / API 34; image checksum not recorded |
| Hub build tools and dependencies | Gradle 9.1.0, Android Gradle Plugin 9.0.1, compile/target SDK 36, min SDK 31, build tools 36.0.0, JUnit 4.13.2 |
| Build Java runtime | Android Studio bundled JBR 25.0.3; Java/Kotlin bytecode target 17 |
| Maverick SDK and device firmware | Pending |
| Flutter and backend dependencies | Pending |

Record versions after successful builds and device tests.

## Submission figures

The final connection diagram belongs in [Documentation/connection diagram/](<Documentation/connection diagram/>), and the poster in [Assets/](Assets/). Both are pending; embed their final images here before submission.

Part of the [Interdisciplinary Center for Smart Technologies](https://icst.cs.technion.ac.il/), Taub Faculty of Computer Science, Technion.
