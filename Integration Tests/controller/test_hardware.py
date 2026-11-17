import os
import time
import unittest
from support import pi
from support.evidence import evidence


class PiHardwareTests(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("SENSOR_TEST_PI"):
            self.skipTest("Requires --pi SERIAL and --adb PATH; tests real Android Pi")

    def test_07_android_ble_and_application_ready(self):
        self.assertGreaterEqual(int(pi.adb("shell", "getprop", "ro.build.version.sdk").strip()), 31)
        self.assertIn("android.hardware.bluetooth_le", pi.adb("shell", "pm", "list", "features"))
        self.assertIn("package:", pi.adb("shell", "pm", "path", "org.aerovision.hub"))
        evidence("pi_ready", sdk=pi.adb("shell", "getprop", "ro.build.version.sdk").strip())

    def test_08_new_live_controller_reading_has_provenance(self):
        row = pi.wait_reading()
        self.assertEqual(row["input_mode"], "live")
        self.assertEqual(row["phase"], "STREAMING")
        for field in ["run_id", "connection_id", "sequence", "received_utc_ms",
                      "received_monotonic_ms", "raw_hex", "device_address", "bpm"]:
            self.assertIsNotNone(row[field], field)

    def test_09_pi_radio_loss_stale_and_automatic_recovery(self):
        if os.environ.get("SENSOR_TEST_RADIO_CYCLE") != "1":
            self.skipTest("Requires --radio-cycle; temporarily changes the Pi's Bluetooth setting")
        before = pi.wait_reading()
        self.assertEqual(before["input_mode"], "live")
        try:
            pi.adb("shell", "svc", "bluetooth", "disable")
            time.sleep(12)
            records = pi.rows()
            # Locate baseline by full identity rather than log-buffer length.
            baseline = next(i for i, r in enumerate(records) if all(
                r.get(k) == before[k] for k in ["run_id", "connection_id", "sequence"]))
            status = [r for r in records[baseline + 1:] if r.get("event") == "status"]
            evidence("pi_radio_off", statuses=status)
            self.assertTrue(any(r.get("phase") in ["STALE", "RETRYING"] for r in status))
        finally:
            pi.adb("shell", "svc", "bluetooth", "enable")
        after = pi.wait_reading(before, timeout=60, predicate=lambda row:
            row.get("run_id") != before["run_id"] or row.get("connection_id", 0) > before["connection_id"])
        self.assertEqual(after["run_id"], before["run_id"], "App restarted: not automatic recovery")
        self.assertEqual(after["device_address"], before["device_address"])
        self.assertGreater(after["connection_id"], before["connection_id"])
        self.assertEqual(after["input_mode"], "live")
        evidence("pi_recovered", before=before, after=after)
