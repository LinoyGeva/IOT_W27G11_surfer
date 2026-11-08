# Hardware diagnostics

Each directory will contain a small runnable diagnostic with its setup, expected output and observed result.

| Directory | Purpose |
| --- | --- |
| `garmin_hrm/` | Real notification, decoding and reconnect |
| `vakaros_atlas/` | Discovery, captures and protocol validation |
| `maverick/` | Physical display and motion access from the Pi |
| `hub_integration/` | Concurrent links and source/network interruption |

Reuse production adapters where practical. Automated application tests remain beside their component source; diagnostic programs have not been implemented yet.
