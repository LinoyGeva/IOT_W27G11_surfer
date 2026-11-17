"""Python entry point for assertions against the actual Kotlin controller.

These cases report native JUnit results, not a Python reimplementation of it.
"""
import os
from pathlib import Path
import subprocess
import unittest
import xml.etree.ElementTree as ET
from support.protocols import ROOT


class ControllerNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("SENSOR_TEST_NATIVE") != "1":
            raise unittest.SkipTest("Use --suite native to build/run real Kotlin controller unit tests")
        output = Path(os.environ["SENSOR_TEST_OUTPUT"])
        environment = dict(os.environ)
        environment.setdefault("GRADLE_USER_HOME", str(ROOT / "local_data/android-gradle"))
        jbr = Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home")
        if "JAVA_HOME" not in environment and jbr.is_dir(): environment["JAVA_HOME"] = str(jbr)
        with (output / "native-gradle.log").open("w") as log:
            result = subprocess.run([str(ROOT / "raspberry_pi_hub/gradlew"), "-p",
                str(ROOT / "raspberry_pi_hub"), "testDebugUnitTest", "--rerun-tasks",
                "--no-daemon", "--console=plain"], cwd=ROOT, env=environment,
                stdout=log, stderr=subprocess.STDOUT, timeout=300)
        if result.returncode:
            raise AssertionError("Native unit test/build failed; inspect " + str(output / "native-gradle.log"))
        cls.cases = {}
        for path in (ROOT / "raspberry_pi_hub/build/test-results/testDebugUnitTest").glob("TEST-*.xml"):
            (output / path.name).write_bytes(path.read_bytes())
            for case in ET.parse(path).getroot().findall("testcase"):
                cls.cases[case.get("name")] = case
        if not cls.cases: raise AssertionError("Gradle produced no JUnit cases; NO-SOURCE is not a pass")

    def passed(self, *names):
        for name in names:
            with self.subTest(native_case=name):
                self.assertIn(name, self.cases)
                case = self.cases[name]
                self.assertIsNone(case.find("failure"))
                self.assertIsNone(case.find("error"))
                self.assertIsNone(case.find("skipped"))

    def test_01_all_native_measurement_fields(self):
        self.passed("eightBitBpmAndAbsentFields", "unsignedEightBitBpmIsNotNegative",
                    "littleEndianSixteenBitBpmAndOptionalFields", "supportedContactCanBeAbsent",
                    "noContactSupportDoesNotInventContactStatus", "formatCanChangeBetweenNotifications",
                    "rrFlagWithNoIntervalsIsAllowedByVariableLengthField",
                    "fractionalRrUnitsAndUnsignedSixteenBitBoundaryArePreserved",
                    "malformedAndTrailingBytesAreRejected")

    def test_02_scan_subscription_and_failed_cccd(self):
        self.passed("scanningListsDevicesWithoutConnectingAndDeduplicatesAddresses",
                    "servicesAndSubscriptionMustCompleteBeforeAcceptingData",
                    "missingServicesAndFailedSubscriptionCannotBeStreaming",
                    "failedCccdWriteAndLateSuccessCannotBecomeStreaming")

    def test_03_freshness_and_clock_provenance(self):
        self.passed("malformedDataDoesNotRefreshAnOldMeasurement",
                    "measurementHasReceptionClockIdentitySequenceAndLiveMode")

    def test_04_reconnect_and_duplicate_listener_defence(self):
        self.passed("disconnectClearsReadingThenReconnectsWithNewIdentityAndIgnoresOldCallbacks",
                    "repeatedSelectionAndDuplicateCallbacksDoNotSubscribeTwice")

    def test_05_connection_and_inactive_stream_deadlines(self):
        self.passed("eachConnectionPhaseAndSilentStreamHasTimeout")

    def test_06_stop_cancels_recovery(self):
        self.passed("stoppingCancelsRecoveryAndRejectsLateData")
