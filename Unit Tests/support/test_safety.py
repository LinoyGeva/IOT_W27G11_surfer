"""Synthetic regressions for fault-test prerequisites; no physical BLE access."""
import os
import unittest
from unittest.mock import AsyncMock, patch
from support.protocols import load

ble_checks = load("integration_ble_safety", "Integration Tests/ble_checks.py")


class HardwarePrerequisiteTests(unittest.IsolatedAsyncioTestCase):
    async def check(self, method, baseline_error=False, still_present=False):
        case = ble_checks.SensorHardwareChecks(method)
        case.sensor, case.target = "atlas", "synthetic-device"
        probe = type("FakeProbe", (), {})()
        probe.connect = AsyncMock(side_effect=AssertionError("baseline missing") if baseline_error else None)
        probe.close = AsyncMock()
        probe.discover = AsyncMock(return_value=object() if still_present else None)
        with patch.dict(os.environ, {"SENSOR_TEST_INTERACTIVE": "1"}), \
             patch.object(ble_checks, "Probe", return_value=probe), \
             patch.object(ble_checks, "evidence"), patch("builtins.input", return_value="") as prompt:
            error = None
            try:
                await getattr(case, method)()
            except AssertionError as exc:
                error = exc
            return probe, prompt, error

    async def test_unknown_device_cannot_pass_absence_check(self):
        probe, prompt, error = await self.check("test_10_inactive_device_diagnostic", baseline_error=True)
        self.assertIsNotNone(error)
        prompt.assert_not_called()
        probe.discover.assert_not_awaited()
        probe.close.assert_awaited()

    async def test_failed_reconnect_setup_does_not_prompt_radio_restore(self):
        probe, prompt, error = await self.check("test_09_bluetooth_off_on_and_reconnect", baseline_error=True)
        self.assertIsNotNone(error)
        prompt.assert_not_called()
        probe.close.assert_awaited()

    async def test_absence_requires_successful_baseline_then_operator_change(self):
        probe, prompt, error = await self.check("test_10_inactive_device_diagnostic")
        self.assertIsNone(error)
        probe.connect.assert_awaited_once()
        probe.discover.assert_awaited_once()
        self.assertEqual(prompt.call_count, 2)

    async def test_device_still_present_fails_and_requests_restoration(self):
        probe, prompt, error = await self.check("test_10_inactive_device_diagnostic", still_present=True)
        self.assertIsNotNone(error)
        self.assertEqual(prompt.call_count, 2)
        probe.close.assert_awaited()
