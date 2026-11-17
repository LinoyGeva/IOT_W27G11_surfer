import math
import struct
import unittest
from types import SimpleNamespace
from support.protocols import atlas


def packet(trim=12.5, heel=357.25, gps=(0.0, 0.0)):
    raw = bytearray(35)
    raw[:2] = b"\x02\x0a"
    struct.pack_into("<fffff", raw, 8, *gps, 123.0, trim, heel)
    return bytes(raw)


class AtlasProtocolTests(unittest.TestCase):
    """Only observed angle semantics are asserted; remaining bytes stay opaque."""

    def test_01_angle_order_offsets_and_zero_gps(self):
        for gps in [(0, 0), (32.1, 34.8)]:
            kind, decoded = atlas.inspect_packet(atlas.TELEMETRY_MAIN, packet(gps=gps))
            self.assertEqual(kind, "candidate_attitude")
            self.assertEqual(decoded, {"candidate_heel_deg": 357.25, "candidate_trim_deg": 12.5})

    def test_02_channels_prefixes_and_truncation(self):
        for channel, raw, kind in [
            (atlas.TELEMETRY_AUX, packet(), "unverified_other_channel"),
            (atlas.TELEMETRY_MAIN, b"\x02\x0b" + packet()[2:], "session_list_reply"),
            (atlas.TELEMETRY_MAIN, b"\x02\x01", "unknown_packet"),
            (atlas.TELEMETRY_MAIN, packet()[:27], "truncated_candidate")]:
            with self.subTest(kind=kind):
                self.assertEqual(atlas.inspect_packet(channel, raw), (kind, None))

    def test_03_nonfinite_fields_are_missing(self):
        for value in [math.nan, math.inf, -math.inf]:
            for raw in [packet(trim=value), packet(heel=value)]:
                self.assertEqual(atlas.inspect_packet(atlas.TELEMETRY_MAIN, raw), ("nonfinite_candidate", None))

    def test_04_freshness_silence_disconnect_and_new_session(self):
        state = atlas.LiveState(2)
        self.assertEqual(state.snapshot(0, True)["stream_state"], "waiting_for_candidate")
        state.accept(atlas.TELEMETRY_MAIN, packet(), 1)
        self.assertIsNotNone(state.snapshot(2.9, True)["candidate_heel_deg"])
        self.assertIsNone(state.snapshot(3, True)["candidate_heel_deg"])
        self.assertIsNone(state.snapshot(1.1, False)["candidate_trim_deg"])
        self.assertIsNone(atlas.LiveState(2).snapshot(4, True)["candidate_heel_deg"])

    def test_05_only_valid_angles_refresh_gap_and_unknown_bytes_do_not_gate(self):
        state = atlas.LiveState(2)
        raw = bytearray(packet())
        raw[2:8] = b"\xff" * 6
        raw[28:] = b"\xff" * 7  # Unknown clock/scalar/tail: not verified fields.
        state.accept(atlas.TELEMETRY_MAIN, raw, 1)
        state.accept(atlas.TELEMETRY_MAIN, b"\x02\x0b", 1.1)
        state.accept(atlas.TELEMETRY_MAIN, raw, 1.25)
        snapshot = state.snapshot(1.25, True)
        self.assertEqual(snapshot["mean_angle_packet_gap_ms"], 250)
        self.assertEqual(snapshot["angle_packet_interval_count"], 1)
        self.assertFalse(snapshot["heel_trim_verified"])
        self.assertIsNone(snapshot["device_sample_time"])


class AtlasSubscriptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_06_subscribe_before_activation_and_reject_wrong_layout(self):
        calls = []
        chars = [SimpleNamespace(uuid=atlas.TELEMETRY_MAIN, properties=["notify"]),
                 SimpleNamespace(uuid=atlas.TELEMETRY_AUX, properties=["notify"]),
                 SimpleNamespace(uuid=atlas.COMMAND, properties=["write-without-response"])]

        class Client:
            is_connected = True
            services = [SimpleNamespace(uuid=atlas.ATLAS_SERVICE, characteristics=chars)]
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def start_notify(self, char, callback):
                calls.append(("subscribe", char.uuid))
                if char.uuid == atlas.TELEMETRY_MAIN: callback(char, packet())
            async def write_gatt_char(self, char, payload, response): calls.append(("write", payload, response))
            async def stop_notify(self, char): calls.append(("stop", char.uuid))

        journal = SimpleNamespace(emit=lambda *args, **kw: None)
        args = SimpleNamespace(stale_after=2, start_stream=True, seconds=0.001, silence_timeout=None)
        result = await atlas.listen(SimpleNamespace(address="synthetic-atlas"), args, journal, lambda *a, **kw: Client())
        self.assertEqual(result, 0)
        self.assertEqual(calls[:3], [("subscribe", atlas.TELEMETRY_MAIN), ("subscribe", atlas.TELEMETRY_AUX), ("write", b"\x02\x09\x01", False)])
        self.assertEqual(len([c for c in calls if c[0] == "stop"]), 2)
        chars.pop(1)
        with self.assertRaisesRegex(ValueError, "notify channels"):
            await atlas.listen(SimpleNamespace(address="synthetic-atlas"), args, journal, lambda *a, **kw: Client())
