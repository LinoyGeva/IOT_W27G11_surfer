"""Opt-in direct BLE hardware assertions. No plots or simulated hardware results."""
import asyncio
import os
import time
import unittest
from support.protocols import hr, atlas
from support.evidence import evidence


class Probe:
    def __init__(self, sensor, target):
        self.sensor, self.target = sensor, target
        self.client = None
        self.active = []
        self.valid = []
        self.lost = asyncio.Event()

    async def discover(self):
        from bleak import BleakScanner
        devices = await BleakScanner.discover(timeout=7)
        return next((d for d in devices if d.address.lower() == self.target.lower()), None)

    async def connect(self):
        from bleak import BleakClient
        device = await self.discover()
        if device is None:
            raise AssertionError("Selected device absent from scan (not a connection or decoding failure)")
        self.client = BleakClient(device, disconnected_callback=lambda _: self.lost.set(), timeout=10)
        await asyncio.wait_for(self.client.connect(), 12)
        evidence("connected", sensor=self.sensor, device=self.target)
        service_uuid = hr.HR_SERVICE if self.sensor == "hr" else atlas.ATLAS_SERVICE
        service = self.client.services.get_service(service_uuid)
        if service is None: raise AssertionError("Connected but expected service missing")
        channels = [hr.HR_MEASUREMENT] if self.sensor == "hr" else [atlas.TELEMETRY_MAIN, atlas.TELEMETRY_AUX]
        for uuid in channels:
            char = service.get_characteristic(uuid)
            if char is None or "notify" not in char.properties:
                raise AssertionError("Connected but notification characteristic/property missing: " + uuid)
            def callback(_char, raw, channel=uuid):
                raw = bytes(raw)
                try:
                    decoded = hr.decode_measurement(raw) if self.sensor == "hr" else atlas.inspect_packet(channel, raw)[1]
                    if decoded is not None: self.valid.append(decoded)
                    evidence("notification", sensor=self.sensor, channel=channel, raw_hex=raw.hex(), decoded=decoded)
                except ValueError as exc:
                    evidence("decode_error", sensor=self.sensor, raw_hex=raw.hex(), error=str(exc))
            await asyncio.wait_for(self.client.start_notify(char, callback), 10)
            self.active.append(char)
        if self.sensor == "atlas":
            command = service.get_characteristic(atlas.COMMAND)
            if command is None or "write-without-response" not in command.properties:
                raise AssertionError("Atlas Command 1 write-without-response missing")
            await asyncio.wait_for(self.client.write_gatt_char(command, atlas.START_STREAM, response=False), 5)
            evidence("activation", sensor=self.sensor, raw_hex=atlas.START_STREAM.hex())

    async def readings(self):
        deadline = time.monotonic() + 10
        while len(self.valid) < 2 and time.monotonic() < deadline:
            if self.lost.is_set(): raise AssertionError("Connection lost before two valid measurements")
            await asyncio.sleep(0.1)
        if len(self.valid) < 2:
            raise AssertionError("Connected/subscribed but no valid telemetry: check activation/contact/GPS; not a scan failure")

    async def close(self):
        if self.client is not None:
            try:
                await asyncio.wait_for(self.client.disconnect(), 8)
            finally:
                self.active.clear()


class SensorHardwareChecks(unittest.IsolatedAsyncioTestCase):
    sensor = None

    def setUp(self):
        self.target = os.environ.get("SENSOR_TEST_DEVICE")
        if not self.target: self.skipTest("Hardware requires explicit --device from this receiver's scan")
        evidence("test_start", test=self.id(), sensor=self.sensor)

    async def test_07_device_discovery(self):
        self.assertIsNotNone(await Probe(self.sensor, self.target).discover(), "Selected sensor did not advertise")

    async def test_08_connect_subscribe_and_live_parse(self):
        probe = Probe(self.sensor, self.target)
        try:
            await probe.connect()
            await probe.readings()
            self.assertTrue(probe.client.is_connected)
        finally:
            await probe.close()

    async def test_09_bluetooth_off_on_and_reconnect(self):
        if os.environ.get("SENSOR_TEST_INTERACTIVE") != "1":
            self.skipTest("Requires --interactive: operator toggles the BLE receiver's Bluetooth")
        before = Probe(self.sensor, self.target)
        after = None
        radio_change_requested = False
        try:
            await before.connect()
            await before.readings()
            radio_change_requested = True
            await asyncio.to_thread(input, "Turn OFF Bluetooth on the computer running Python, then press Enter: ")
            await asyncio.wait_for(before.lost.wait(), 12)
            self.assertFalse(before.client.is_connected)
        finally:
            # Always restore the operator-controlled radio even if loss detection fails.
            if radio_change_requested:
                await asyncio.to_thread(input, "Turn Bluetooth back ON, then press Enter: ")
            await before.close()
        for attempt in range(3):
            after = Probe(self.sensor, self.target)
            try:
                await after.connect()
                await after.readings()
                evidence("reconnected", sensor=self.sensor, attempt=attempt + 1)
                return
            except Exception as exc:
                evidence("reconnect_attempt_failed", sensor=self.sensor, error=str(exc))
                if attempt == 2: raise
                await asyncio.sleep(2)
            finally:
                await after.close()

    async def test_10_inactive_device_diagnostic(self):
        if os.environ.get("SENSOR_TEST_INTERACTIVE") != "1":
            self.skipTest("Requires --interactive and physically powering off/deactivating the selected sensor")
        baseline = Probe(self.sensor, self.target)
        sensor_change_requested = False
        try:
            # Absence alone is meaningless for a wrong or never-seen identifier.
            # Require the correct service/subscription layout while powered on.
            await baseline.connect()
            await baseline.close()
            evidence("inactive_check_baseline", sensor=self.sensor, device=self.target)
            sensor_change_requested = True
            await asyncio.to_thread(input, "Power OFF/deactivate the selected sensor; keep receiver Bluetooth ON. Press Enter: ")
            self.assertIsNone(await Probe(self.sensor, self.target).discover(),
                              "Device still advertises; this is not proof of an inactive sensor")
            evidence("expected_device_absent", sensor=self.sensor, device=self.target)
        finally:
            try:
                if sensor_change_requested:
                    await asyncio.to_thread(input, "Restore/activate the sensor, then press Enter: ")
            finally:
                await baseline.close()
