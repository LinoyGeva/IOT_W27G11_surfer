"""Run isolated Python verification suites; hardware is always explicit opt-in."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def startTestRun(self):
        self.started = time.monotonic()  # Also covers setUpClass errors/skips.
        super().startTestRun()

    def record(self, test, outcome, message=""):
        self.records.append(dict(test=test.id(), outcome=outcome, message=message,
                                 seconds=time.monotonic() - self.started))

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "passed")

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.record(test, "failed", self._exc_info_to_string(error, test))

    def addError(self, test, error):
        super().addError(test, error)
        self.record(test, "error", self._exc_info_to_string(error, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skipped", reason)

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.record(subtest, "failed", self._exc_info_to_string(error, test))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["offline", "native", "health", "integration", "hardware", "replay"], default="offline")
    parser.add_argument("--sensor", choices=["all", "hr", "atlas", "controller"], default="all")
    parser.add_argument("--device", help="Exact BLE identifier on the computer running Python")
    parser.add_argument("--interactive", action="store_true", help="Allow prompts for receiver radio/device off/on")
    parser.add_argument("--pi", help="ADB Pi serial, e.g. 10.100.102.11:5555")
    parser.add_argument("--adb", default=str(Path.home() / "Library/Android/sdk/platform-tools/adb"))
    parser.add_argument("--radio-cycle", action="store_true", help="Allow automatic Pi Bluetooth off/on; requires ADB over Wi-Fi/Ethernet/USB")
    parser.add_argument("--case", help="Run only test IDs containing this substring")
    parser.add_argument("--csv", help="Original Atlas app CSV; read-only")
    parser.add_argument("--recorded", help="Reconstructed recorded position/orientation JSONL; read-only")
    parser.add_argument("--apk", help="Expected local hub APK for controller health integrity check")
    args = parser.parse_args()
    if args.suite == "hardware":
        parser.error("Sensor-dependent checks moved to --suite integration. For Pi-only Wi-Fi/BLE/storage checks use --suite health --sensor controller --pi SERIAL.")
    if args.suite == "health":
        if args.sensor not in ["all", "controller"] or not args.pi:
            parser.error("health requires --sensor controller --pi SERIAL; no sensor device is used")
        if args.device or args.interactive or args.radio_cycle:
            parser.error("health is sensor-independent and does not toggle radios; remove --device/--interactive/--radio-cycle")
    if args.device and args.device.upper() in {"ATLAS_IDENTIFIER", "HR_IDENTIFIER", "IDENTIFIER", "DEVICE_ID"}:
        parser.error("--device is an example placeholder. Scan first and replace it with the real BLE identifier shown on this computer.")
    if args.suite == "native" and args.sensor not in ["all", "controller"]:
        parser.error("native suite tests the Android controller")
    if args.suite == "replay":
        if args.sensor not in ["all", "atlas"] or not args.csv or not args.recorded:
            parser.error("replay requires --csv PATH --recorded PATH and Atlas target")
    if args.suite == "offline" and args.sensor == "controller":
        parser.error("Use --suite native for controller unit logic; it is Kotlin, not Python")
    if args.suite == "integration":
        if args.sensor == "all": parser.error("Select exactly one hardware target with --sensor")
        if args.sensor == "controller" and not args.pi: parser.error("Controller hardware requires --pi")
        if args.sensor != "controller" and not args.device: parser.error("Sensor hardware requires --device")
    if args.radio_cycle and not (args.suite == "integration" and args.sensor == "controller"):
        parser.error("--radio-cycle applies only to controller integration")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "local_data/unit_tests" / stamp
    output.mkdir(parents=True)
    # Clear inherited opt-ins: each invocation must explicitly authorize its scope.
    for key in ["SENSOR_TEST_NATIVE", "SENSOR_TEST_DEVICE", "SENSOR_TEST_INTERACTIVE",
                "SENSOR_TEST_PI", "SENSOR_TEST_RADIO_CYCLE", "SENSOR_TEST_CSV", "SENSOR_TEST_RECORDED", "SENSOR_TEST_APK"]:
        os.environ.pop(key, None)
    os.environ["SENSOR_TEST_OUTPUT"] = str(output)
    if args.suite == "native": os.environ["SENSOR_TEST_NATIVE"] = "1"
    if args.device: os.environ["SENSOR_TEST_DEVICE"] = args.device
    if args.interactive: os.environ["SENSOR_TEST_INTERACTIVE"] = "1"
    if args.pi: os.environ["SENSOR_TEST_PI"] = args.pi
    os.environ["SENSOR_TEST_ADB"] = args.adb
    if args.radio_cycle: os.environ["SENSOR_TEST_RADIO_CYCLE"] = "1"
    if args.csv: os.environ["SENSOR_TEST_CSV"] = args.csv
    if args.recorded: os.environ["SENSOR_TEST_RECORDED"] = args.recorded
    if args.apk: os.environ["SENSOR_TEST_APK"] = args.apk

    folders = {"hr": "garmin_hrm", "atlas": "vakaros_atlas", "controller": "controller"}
    targets = ["hr", "atlas"] if args.suite == "offline" and args.sensor == "all" else [
        "controller" if args.suite in ["native", "health"] else "atlas" if args.suite == "replay" else args.sensor]
    pattern = {"offline": "test_protocol.py", "native": "test_native.py", "health": "test_health.py", "integration": "test_hardware.py", "replay": "test_export.py"}[args.suite]
    discovery_root = ROOT / "Integration Tests" if args.suite == "integration" else HERE
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    def cases(group):
        for item in group:
            if isinstance(item, unittest.TestSuite): yield from cases(item)
            else: yield item
    for target in targets:
        tests = loader.discover(str(discovery_root / folders[target]), pattern=pattern, top_level_dir=str(discovery_root))
        suite.addTests(t for t in cases(tests) if not args.case or args.case in t.id())
    if args.suite == "offline":
        safety = loader.discover(str(HERE / "support"), pattern="test_safety.py", top_level_dir=str(HERE))
        suite.addTests(t for t in cases(safety) if not args.case or args.case in t.id())
    if suite.countTestCases() == 0: parser.error("No tests matched; empty suite is not a pass")
    print("Evidence:", output, flush=True)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.SubprocessError): commit = "unknown"
    metadata = dict(suite=args.suite, target=args.sensor, python=sys.version, platform=platform.platform(),
                    device=args.device, pi=args.pi,
                    input_mode="live" if args.suite in ["health", "integration"] else "replay" if args.suite == "replay" else "synthetic",
                    git_base=commit, working_tree=True, tests_run=result.testsRun,
                    successful=result.wasSuccessful(), cases=result.records)
    (output / "results.json").write_text(json.dumps(metadata, indent=2) + "\n")
    report = ET.Element("testsuite", name=args.suite, tests=str(result.testsRun),
                        failures=str(len(result.failures)), errors=str(len(result.errors)), skipped=str(len(result.skipped)))
    for row in result.records:
        case = ET.SubElement(report, "testcase", name=row["test"], time=str(row["seconds"]))
        if row["outcome"] != "passed":
            tag = {"failed": "failure", "error": "error", "skipped": "skipped"}[row["outcome"]]
            ET.SubElement(case, tag).text = row["message"]
    ET.ElementTree(report).write(output / "results.xml", encoding="utf-8", xml_declaration=True)
    # Entirely skipped hardware is not a successful hardware verification.
    passed = any(r["outcome"] == "passed" for r in result.records)
    if not passed:
        print("VERIFICATION INCOMPLETE: no test passed; skipped cases are not hardware evidence.", file=sys.stderr)
    return 0 if result.wasSuccessful() and passed else 1


if __name__ == "__main__":
    sys.exit(main())
