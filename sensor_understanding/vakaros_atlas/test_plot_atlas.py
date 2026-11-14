"""Synthetic protocol checks; no GUI window or Bluetooth hardware is used."""

import asyncio
from collections import deque
import queue
import io
import json
import signal
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from plot_atlas import CollectorSupervisor, collect_live, draw, enqueue_update, live_sample


class LiveGraphTests(unittest.TestCase):
    def candidate(self):
        return dict(event="candidate_attitude", input_mode="live",
                    received_at_utc="2026-11-10T11:32:00+00:00",
                    received_monotonic_ns=10_000_000_000,
                    candidate_heel_deg=357.5, candidate_trim_deg=359.0)

    def test_signed_display_preserves_raw_fields_and_receive_time(self):
        sample = live_sample(self.candidate())
        self.assertEqual(sample["candidate_roll_deg"], -2.5)
        self.assertEqual(sample["candidate_pitch_deg"], -1)
        self.assertEqual(sample["candidate_heel_deg"], 357.5)
        self.assertEqual(sample["received_monotonic_ns"], 10_000_000_000)
        self.assertIn("reception", sample["timestamp_semantics"])

    def test_replay_and_non_angle_events_cannot_enter_live_graph(self):
        for changes in ({"input_mode": "replay"}, {"event": "recorded_sample"},
                        {"candidate_heel_deg": None}, {"candidate_trim_deg": float("nan")}):
            self.assertIsNone(live_sample({**self.candidate(), **changes}))

    def test_slow_gui_keeps_newest_update_without_blocking_collector(self):
        updates = queue.Queue(maxsize=2)
        for n in (1, 2, 3):
            enqueue_update(updates, {"sequence": n})
        self.assertEqual(updates.get_nowait()["sequence"], 2)
        self.assertEqual(updates.get_nowait()["sequence"], 3)

    def test_stale_or_stopped_source_clears_numbers_but_preserves_history(self):
        history = deque([live_sample(self.candidate())])
        for now, active, expected in ((10.1, True, "Heel: -2.50°     Trim: -1.00°"),
                                       (13, True, "Heel: —°     Trim: —°"),
                                       (10.1, False, "Heel: —°     Trim: —°")):
            view = tuple(Mock() for _ in range(9))
            with patch("plot_atlas.time.monotonic", return_value=now):
                draw(view, history, "test", received_clock=10, source_active=active)
            self.assertEqual(view[3].set_text.call_args.args[0], expected)
            self.assertEqual(len(history), 1)

    def test_average_packet_interval_is_displayed_in_milliseconds(self):
        view = tuple(Mock() for _ in range(9))
        draw(view, [], "Waiting", mean_gap_ms=250.25)
        self.assertIn("250.2 ms (this connection)", view[7].set_text.call_args.args[0])


class LiveCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_graph_uses_unbounded_notification_receiver_with_observed_start(self):
        journal = Mock()
        receiver = AsyncMock(return_value=2)
        with patch("plot_atlas.Journal", return_value=journal), \
             patch("plot_atlas.environment", return_value={}), \
             patch("live_atlas.run", receiver):
            result = await collect_live(SimpleNamespace(device="synthetic"))
        config = receiver.call_args.args[0]
        self.assertTrue(config.start_stream)
        self.assertIsNone(config.seconds)
        self.assertEqual(config.silence_timeout, 8)
        self.assertEqual(result, 2)
        journal.close.assert_called_once()


class SupervisorTests(unittest.TestCase):
    def test_real_child_process_output_and_fresh_process_on_retry(self):
        updates = queue.Queue()
        command = [sys.executable, "-u", "-c",
                   'import json; print(json.dumps({"event":"status","input_mode":"synthetic"}), flush=True)']
        supervisor = CollectorSupervisor(command, updates)
        try:
            supervisor.tick(0)
            first_pid = supervisor.process.pid
            self.assertEqual(updates.get(timeout=5)["_collector_generation"], 1)
            supervisor.process.wait(timeout=5)
            supervisor.tick(1)
            supervisor.tick(3)
            self.assertNotEqual(first_pid, supervisor.process.pid)
            self.assertEqual(updates.get(timeout=5)["_collector_generation"], 2)
            supervisor.process.wait(timeout=5)
        finally:
            supervisor.close()

    def supervisor(self):
        children = []
        class Child:
            def __init__(self):
                self.code = None
                self.stdout = io.StringIO("")
                self.signals, self.killed = [], False
            def poll(self): return self.code
            def wait(self, timeout=None):
                if self.code is None:
                    raise subprocess.TimeoutExpired("synthetic", timeout)
                return self.code
            def send_signal(self, value): self.signals.append(value)
            def kill(self): self.killed, self.code = True, -9
        def spawn(*args, **kwargs):
            self.assertTrue(all(c.code is not None for c in children))
            child = Child()
            children.append(child)
            return child
        return CollectorSupervisor(["synthetic"], queue.Queue(), process_factory=spawn), children

    @patch("plot_atlas.threading.Thread")
    def test_exited_collector_restarts_as_new_process_after_delay(self, thread):
        supervisor, children = self.supervisor()
        self.assertEqual(supervisor.tick(0), ("started", 1))
        children[0].code = 2
        self.assertEqual(supervisor.tick(1), ("stopped", 2))
        self.assertIsNone(supervisor.tick(2))
        self.assertEqual(supervisor.tick(3), ("started", 2))
        self.assertIsNot(children[0], children[1])

    @patch("plot_atlas.threading.Thread")
    def test_hung_cleanup_is_killed_before_another_collector_starts(self, thread):
        supervisor, children = self.supervisor()
        supervisor.tick(0)
        supervisor.restart(1)
        supervisor.restart(2)
        self.assertEqual(children[0].signals, [signal.SIGINT])
        supervisor.tick(3.9)
        self.assertFalse(children[0].killed)
        supervisor.tick(4)
        self.assertTrue(children[0].killed)
        self.assertEqual(len(children), 1)
        supervisor.tick(4.1)
        supervisor.tick(6.1)
        self.assertEqual(len(children), 2)

    def test_reader_tags_output_with_its_original_process_generation(self):
        supervisor, _ = self.supervisor()
        child = SimpleNamespace(stdout=io.StringIO(json.dumps({"event": "candidate_attitude"}) + "\n"))
        supervisor.generation = 2
        supervisor.read_output(child, 1)
        self.assertEqual(supervisor.updates.get_nowait()["_collector_generation"], 1)
        self.assertTrue(child.stdout.closed)


if __name__ == "__main__":
    unittest.main()
