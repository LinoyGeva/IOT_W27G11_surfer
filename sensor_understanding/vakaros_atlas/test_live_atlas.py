"""Synthetic fixtures only; no verified hardware angles or radio access."""
import asyncio
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace as NS
import unittest

from live_atlas import (ATLAS_SERVICE, TELEMETRY_AUX, COMMAND, TELEMETRY_MAIN,
                        START_STREAM, Journal, LiveState, discover, inspect_packet, listen,
                        positive_seconds)


def packet(trim=7.5, heel=-12.0):
    # Synthetic external-layout hypothesis with zero GPS.
    raw = bytearray(28)
    raw[:2] = b"\x02\x0a"
    struct.pack_into("<ff", raw, 20, trim, heel)
    return bytes(raw)


class JournalTests(unittest.TestCase):
    def test_real_logger_serializes_to_file_and_stdout_on_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            output = io.StringIO()
            log = Journal(path)
            try:
                with redirect_stdout(output):
                    log.emit("start", input_mode="synthetic", note="logger regression")
            finally:
                log.close()
            row = json.loads(path.read_text())
            self.assertEqual(row, json.loads(output.getvalue()))
            self.assertEqual(row["event"], "start")
            self.assertEqual(row["input_mode"], "synthetic")
            self.assertGreater(row["received_monotonic_ns"], 0)


class PacketTests(unittest.TestCase):
    def test_duration_rejects_nonpositive_or_nonfinite_input(self):
        for text in ("0", "-1", "nan", "inf"):
            with self.subTest(text=text), self.assertRaises(argparse.ArgumentTypeError):
                positive_seconds(text)
        self.assertEqual(positive_seconds("0.5"), .5)

    def test_mean_uses_consecutive_angle_arrivals_and_resets_for_new_connection(self):
        state = LiveState(2)
        state.accept(TELEMETRY_MAIN, packet(), 10)
        self.assertIsNone(state.snapshot(10, True)["mean_angle_packet_gap_ms"])
        state.accept(TELEMETRY_MAIN, packet(), 10.2)
        state.accept(TELEMETRY_MAIN, b"\x02\x0b", 10.3)
        state.accept(TELEMETRY_MAIN, packet(), 10.7)
        snapshot = state.snapshot(11, True)
        self.assertEqual(snapshot["angle_packet_interval_count"], 2)
        self.assertAlmostEqual(snapshot["mean_angle_packet_gap_ms"], 350)
        replacement = LiveState(2)
        replacement.accept(TELEMETRY_MAIN, packet(), 100)
        self.assertIsNone(replacement.snapshot(100, True)["mean_angle_packet_gap_ms"])

    def test_session_replies_never_become_angles_even_when_long(self):
        for raw in (b"\x02\x0b", b"\x02\x0b" + bytes(220)):
            self.assertEqual(inspect_packet(TELEMETRY_MAIN, raw), ("session_list_reply", None))

    def test_log_channel_cannot_be_mistaken_for_live_attitude(self):
        self.assertIsNone(inspect_packet(TELEMETRY_AUX, packet())[1])

    def test_zero_gps_does_not_block_candidate_but_bad_payload_does(self):
        kind, values = inspect_packet(TELEMETRY_MAIN, packet())
        self.assertEqual(kind, "candidate_attitude")
        self.assertEqual(values, {"candidate_heel_deg": -12, "candidate_trim_deg": 7.5})
        for raw in (b"", packet()[:27], packet(float("nan")), packet(heel=float("inf"))):
            self.assertIsNone(inspect_packet(TELEMETRY_MAIN, raw)[1])

    def test_non_attitude_packets_do_not_refresh_old_angles(self):
        state = LiveState(2)
        state.accept(TELEMETRY_MAIN, packet(), 10)
        self.assertEqual(state.snapshot(11, True)["candidate_heel_deg"], -12)
        state.accept(TELEMETRY_MAIN, b"\x02\x0b" + bytes(220), 12)
        stale = state.snapshot(12, True)
        self.assertEqual(stale["stream_state"], "stale_candidate")
        self.assertIsNone(stale["candidate_heel_deg"])
        self.assertEqual(stale["candidate_packets"], 1)
        state.accept(TELEMETRY_MAIN, packet(heel=4), 13)
        self.assertEqual(state.snapshot(13, True)["candidate_heel_deg"], 4)
        self.assertIsNone(state.snapshot(13, False)["candidate_heel_deg"])
        self.assertEqual(state.snapshot(13, False)["stream_state"], "disconnected")
        self.assertFalse(stale["heel_trim_verified"])


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_preserves_unnamed_device_identity_and_advertisement_bytes(self):
        records = []
        device = NS(address="synthetic-id", name=None)
        class Scanner:
            @staticmethod
            async def discover(**kwargs):
                return {device.address: (device, NS(local_name=None, rssi=-50,
                         service_uuids=[ATLAS_SERVICE], manufacturer_data={0x069d: b"\x00\xff"},
                         service_data={"synthetic-service": b"\x80"}))}
        class Log:
            def emit(self, event, **fields): records.append(dict(event=event, **fields))
        self.assertEqual(await discover(Scanner, 1, Log()), [device])
        self.assertEqual(records[0]["device_id"], "synthetic-id")
        self.assertEqual(records[0]["manufacturer_data"], {str(0x069d): "00ff"})
        self.assertIsNone(records[0]["name"])


class ListenerTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, start=False, candidate=True, disconnect=False,
                       without_response=True, silence_timeout=None):
        log = []
        class Journal:
            def emit(self, event, **fields):
                log.append({"event": event, **fields})
        chars = [NS(uuid=TELEMETRY_MAIN, properties=["notify"]),
                 NS(uuid=TELEMETRY_AUX, properties=["notify"]),
                 NS(uuid=COMMAND, properties=["write"] +
                    (["write-without-response"] if without_response else []))]
        class Client:
            is_connected = True
            services = [NS(uuid=ATLAS_SERVICE, characteristics=chars)]
            writes = []
            stopped = []
            async def __aenter__(self): return self
            async def __aexit__(self, *args): self.is_connected = False
            async def start_notify(self, char, callback):
                if char.uuid == TELEMETRY_MAIN:
                    callback(char, packet() if candidate else b"\x02\x0b" + bytes(220))
                    # Sample must already be emitted before start_notify returns.
                    if candidate:
                        assert any(r["event"] == "candidate_attitude" for r in log)
                    if disconnect:
                        self.is_connected = False
                        self.disconnected(self)
            async def stop_notify(self, char): self.stopped.append(char.uuid)
            async def write_gatt_char(self, char, raw, response):
                assert len([r for r in log if r["event"] == "subscribed"]) == 2
                self.writes.append((char.uuid, raw, response))
        client = Client()
        def factory(device, disconnected_callback):
            client.disconnected = disconnected_callback
            return client
        args = NS(stale_after=2, start_stream=start, seconds=.001,
                  silence_timeout=silence_timeout)
        code = await listen(NS(address="synthetic"), args, Journal(), factory)
        return code, client, log

    async def test_publishes_per_callback_without_commands_or_downloads(self):
        code, client, log = await self.exercise()
        self.assertEqual(code, 0)
        self.assertEqual(client.writes, [])
        self.assertEqual(set(client.stopped), {TELEMETRY_MAIN, TELEMETRY_AUX})
        self.assertTrue(any(r["event"] == "candidate_attitude" for r in log))

    async def test_connected_without_angles_times_out_instead_of_waiting_forever(self):
        with self.assertRaisesRegex(TimeoutError, "stream is silent"):
            await self.exercise(candidate=False, silence_timeout=.000001)

    async def test_phone_observed_command_uses_write_without_response_after_subscriptions(self):
        _, client, log = await self.exercise(start=True)
        self.assertEqual(START_STREAM, bytes.fromhex("02 09 01"))
        self.assertEqual(client.writes, [(COMMAND, START_STREAM, False)])
        completed = next(r for r in log if r["event"] == "start_write_completed")
        self.assertFalse(completed["streaming_established"])
        self.assertFalse(completed["gatt_response_requested"])

    async def test_refuses_unavailable_write_mode(self):
        with self.assertRaisesRegex(ValueError, "write-without-response"):
            await self.exercise(start=True, without_response=False)

    async def test_session_traffic_and_disconnect_are_not_successful_streams(self):
        for kwargs in ({"candidate": False}, {"disconnect": True}):
            code, _, log = await self.exercise(**kwargs)
            self.assertEqual(code, 2)
            summary = next(r for r in log if r["event"] == "summary")
            self.assertFalse(summary["heel_trim_verified"])


if __name__ == "__main__":
    unittest.main()
