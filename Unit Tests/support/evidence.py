"""Private live diagnostic evidence shared by health and integration suites."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


def evidence(event, **fields):
    directory = Path(os.environ["SENSOR_TEST_OUTPUT"])
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "hardware.jsonl").open("a") as stream:
        stream.write(json.dumps({"event": event, "input_mode": "live",
            "host_utc": datetime.now(timezone.utc).isoformat(),
            "host_monotonic_ns": time.monotonic_ns(), **fields}) + "\n")
