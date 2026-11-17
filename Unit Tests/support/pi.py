"""ADB-only controller checks: Python does not run on the Android Pi."""
import json
import os
import subprocess
import time
from .evidence import evidence


def adb(*arguments):
    return subprocess.run([os.environ["SENSOR_TEST_ADB"], "-s", os.environ["SENSOR_TEST_PI"],
                           *arguments], check=True, capture_output=True, text=True, timeout=15).stdout


def rows():
    records = []
    for line in adb("logcat", "-d", "-v", "raw", "-s", "AeroVisionHR:I").splitlines():
        try: record = json.loads(line)
        except ValueError: continue
        if isinstance(record, dict): records.append(record)
    return records


def wait_reading(previous=None, timeout=35, predicate=None):
    end = time.monotonic() + timeout
    all_records = []
    while time.monotonic() < end:
        all_records = rows()
        records = [r for r in all_records if r.get("event") == "heart_rate"]
        if records:
            last = records[-1]
            if previous is None:
                previous = last
            elif (last.get("run_id"), last.get("connection_id"), last.get("sequence")) != (
                    previous.get("run_id"), previous.get("connection_id"), previous.get("sequence")) and (
                    predicate is None or predicate(last)):
                evidence("pi_reading", reading=last)
                return last
        time.sleep(1)
    evidence("pi_wait_timeout", timeout_s=timeout, last_messages=all_records[-10:])
    phase = all_records[-1].get("phase", "unknown") if all_records else "no app logs"
    raise AssertionError(f"No NEW Pi telemetry; last logged phase={phase}. "
                         "Open AeroVision on the Pi, scan/select the worn band, "
                         "wait for STREAMING and keep the diagnostic app foreground. "
                         "Close Mac/phone receivers competing for the band.")
