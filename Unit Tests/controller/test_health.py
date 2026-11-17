"""Sensor-independent Android Pi health checks, driven from Python over ADB.

These are on-device diagnostics, not proof of full filesystem/SD integrity.
No HR/Atlas, app foreground state or telemetry is required.
"""
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import unittest
import uuid
from support import pi
from support.evidence import evidence
from support.protocols import ROOT


class ControllerHealthTests(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("SENSOR_TEST_PI"):
            self.skipTest("Controller health requires --pi SERIAL")

    def test_01_android_boot_completed_and_supported(self):
        self.assertEqual(pi.adb("shell", "getprop", "sys.boot_completed").strip(), "1")
        sdk = int(pi.adb("shell", "getprop", "ro.build.version.sdk").strip())
        self.assertGreaterEqual(sdk, 31)
        evidence("health_boot", sdk=sdk, boot_completed=True)

    def test_02_core_android_services_respond(self):
        for service in ("activity", "package", "wifi", "bluetooth_manager"):
            with self.subTest(service=service):
                self.assertRegex(pi.adb("shell", "service", "check", service),
                                 r"Service\s+\S+:\s+found\b")
        evidence("health_services", services=["activity", "package", "wifi", "bluetooth_manager"])

    def test_03_ble_hardware_is_advertised(self):
        self.assertIn("android.hardware.bluetooth_le", pi.adb("shell", "pm", "list", "features"))
        evidence("health_ble_feature", supported=True)

    def test_04_bluetooth_adapter_is_on(self):
        status = pi.adb("shell", "dumpsys", "bluetooth_manager")
        self.assertRegex(status, r"(?m)^\s*enabled:\s*true\s*$", "Pi Bluetooth is disabled")
        self.assertRegex(status, r"(?m)^\s*state:\s*ON\s*$", "Pi Bluetooth is not fully ON")
        evidence("health_bluetooth", enabled=True, state="ON",
                 limitation="Adapter readiness only; no peer connection or BLE RF test")

    def test_05_wifi_enabled_and_associated(self):
        status = pi.adb("shell", "cmd", "wifi", "status")
        self.assertIn("Wifi is enabled", status)
        self.assertIn("Wifi is connected to", status, "Pi is not associated with an access point")
        self.assertIn("Supplicant state: COMPLETED", status)
        evidence("health_wifi_association", enabled=True, associated=True)

    def test_06_wifi_has_ipv4_and_default_route(self):
        interface = pi.adb("shell", "getprop", "wifi.interface").strip() or "wlan0"
        self.assertRegex(interface, r"^[A-Za-z0-9_.-]+$")
        addresses = pi.adb("shell", "ip", "-4", "addr", "show", "dev", interface)
        values = re.findall(r"\binet\s+([0-9.]+)/", addresses)
        usable = [v for v in values if not (ipaddress.ip_address(v).is_loopback or
                                           ipaddress.ip_address(v).is_link_local or
                                           ipaddress.ip_address(v).is_unspecified)]
        self.assertTrue(usable, "Wi-Fi has no usable assigned IPv4 address")
        routes = pi.adb("shell", "ip", "-4", "route", "show", "table", "all", "dev", interface)
        self.assertRegex(routes, r"(?m)^default\s+via\s+[0-9.]+", "Wi-Fi has no default gateway")
        evidence("health_wifi_routing", interface=interface, ipv4=usable,
                 limitation="Association/IP/route only; DNS and Internet access are not asserted")

    def test_07_data_storage_write_read_roundtrip(self):
        token = uuid.uuid4().hex
        path = "/data/local/tmp/aerovision-health-" + token
        try:
            # Both strings are generated here (hex UUID/fixed path), never user shell input.
            pi.adb("shell", "printf '%s' '" + token + "' > '" + path + "'")
            self.assertEqual(pi.adb("shell", "cat", path), token)
            evidence("health_storage_roundtrip", verified=True,
                     limitation="Small /data write/read only; not a full SD-card or filesystem scan")
        finally:
            pi.adb("shell", "rm", "-f", path)  # Only this test's uniquely named file.

    def test_08_installed_hub_apk_matches_expected_build(self):
        expected = Path(os.environ.get("SENSOR_TEST_APK", str(
            ROOT / "raspberry_pi_hub/build/outputs/apk/debug/AeroVisionHub-debug.apk")))
        if not expected.is_file():
            self.skipTest("Expected local APK unavailable; build it or supply --apk PATH")
        locations = pi.adb("shell", "pm", "path", "org.aerovision.hub").splitlines()
        self.assertEqual(len(locations), 1, "Expected one installed monolithic hub APK; app missing or split installation")
        self.assertTrue(locations[0].startswith("package:"))
        location = locations[0][len("package:"):]
        self.assertRegex(location, r"^/data/app/[A-Za-z0-9_./+~=-]+\.apk$")
        remote = pi.adb("shell", "sha256sum", location).split()[0]
        local = hashlib.sha256(expected.read_bytes()).hexdigest()
        self.assertEqual(remote, local, "Installed APK differs from expected build; may be an older version, not necessarily corruption")
        evidence("health_apk_integrity", sha256=local, matched=True,
                 limitation="Hub APK only; does not verify Android OS partitions")
