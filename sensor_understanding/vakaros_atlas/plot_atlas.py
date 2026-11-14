"""Live Atlas BLE angle graph with packet-gap statistics and recovery.

Live packet arrival is verified; angle/screen agreement remains a bench check.
"""

import argparse
import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from live_atlas import Journal, ROOT, environment

DISPLAY_TIMEZONE = ZoneInfo("Asia/Jerusalem")


def live_sample(record):
    """Adapt notification events to the graph without inventing device time.

Keep the original raw angle fields; signed wrapping is a display hypothesis,
not a calibration, mounting correction or verified screen transformation.
"""
    if record.get("event") != "candidate_attitude" or record.get("input_mode") != "live":
        return None
    heel, trim = record.get("candidate_heel_deg"), record.get("candidate_trim_deg")
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (heel, trim)):
        return None
    received = datetime.fromisoformat(record["received_at_utc"])
    return {**record, "timestamp_unix_ms": received.timestamp() * 1000,
            "timestamp_semantics": "Mac notification reception; device sample time unknown",
            "candidate_roll_deg": (heel + 180) % 360 - 180,
            "candidate_pitch_deg": (trim + 180) % 360 - 180}


def enqueue_update(updates, record):
    """Never let a slow GUI block BLE: retain newest display events.

    All packets remain in the collector's JSONL even if the GUI falls behind.
    """
    try:
        updates.put_nowait(record)
    except queue.Full:
        try:
            updates.get_nowait()
        except queue.Empty:
            pass
        updates.put_nowait(record)


async def collect_live(args):
    from live_atlas import run
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    journal = Journal(ROOT / "local_data" / "vakaros_atlas" / f"notification-live-{stamp}.jsonl")
    config = SimpleNamespace(device=args.device, scan_seconds=10, stale_after=2,
                             seconds=None, start_stream=True,
                             silence_timeout=8)
    try:
        journal.emit("start", mode="live notification graph", device_id=args.device,
                     start_stream=True, **environment())
        return await run(config, journal)
    except Exception as error:
        journal.emit("error", error=str(error))
        return 1
    finally:
        journal.close()


class CollectorSupervisor:
    """Restart the BLE process, not just its client, while retaining the GUI.

    A dead/silent CoreBluetooth session must not keep the same process alive.
    Every retry gets a new Python process and a generation tag for its output.
    """
    def __init__(self, command, updates, retry=True, process_factory=None):
        self.command, self.updates, self.retry = command, updates, retry
        self.process_factory = process_factory or subprocess.Popen
        self.process = None
        self.generation = 0
        self.next_start = 0
        self.stopping_until = None

    def read_output(self, process, generation):
        try:
            for line in process.stdout:
                try:
                    record = json.loads(line)
                except ValueError:
                    record = {"event": "error", "error": line.strip()[:300]}
                if record.get("event") in ("candidate_attitude", "live_status",
                                            "summary", "connected", "stream_timeout",
                                            "status", "error", "session"):
                    enqueue_update(self.updates, {**record, "_collector_generation": generation})
        finally:
            process.stdout.close()

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if self.process is not None:
            code = self.process.poll()
            if code is None:
                if self.stopping_until is not None and now >= self.stopping_until:
                    self.process.kill()
                    self.stopping_until = None
                return None
            self.process.wait()
            self.process = None
            self.stopping_until = None
            self.next_start = now + 2 if self.retry else float("inf")
            return "stopped", code
        if now < self.next_start:
            return None
        self.generation += 1
        process = self.process_factory(self.command, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True)
        self.process = process
        threading.Thread(target=self.read_output, args=(process, self.generation), daemon=True).start()
        return "started", self.generation

    def restart(self, now=None):
        if self.process is not None and self.process.poll() is None and self.stopping_until is None:
            try:
                self.process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                return
            self.stopping_until = (time.monotonic() if now is None else now) + 3

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.restart()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            else:
                self.process.wait()
            self.process = None


def create_view():
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates

    figure, axis = plt.subplots(figsize=(10, 6))
    figure.canvas.manager.set_window_title("Atlas live Heel / Trim")
    figure.subplots_adjust(top=0.59, bottom=0.16)
    figure.text(0.08, 0.94, "ATLAS • LIVE BLE NOTIFICATIONS", fontsize=14, weight="bold")
    numbers = figure.text(0.08, 0.86, "Heel: —°     Trim: —°", fontsize=23)
    clock = figure.text(0.08, 0.70, "", fontsize=11, family="monospace", linespacing=1.5)
    status = figure.text(0.08, 0.63, "Waiting for data…", fontsize=10)
    figure.text(0.08, 0.035, "Candidate angles only • screen signs, mounting, offsets and dampening unverified", fontsize=9)
    roll, = axis.plot([], [], label="Candidate Heel", color="#0077bb", linewidth=2)
    pitch, = axis.plot([], [], label="Candidate Trim", color="#dd6600", linewidth=2)
    axis.axhline(0, color="#999999", linewidth=0.6)
    axis.set_xlabel("Mac receive time (Asia/Jerusalem)")
    axis.xaxis.set_major_formatter(dates.DateFormatter("%H:%M:%S", tz=DISPLAY_TIMEZONE))
    axis.set_ylabel("Degrees")
    axis.legend(loc="upper right")
    axis.grid(alpha=0.2)
    empty = axis.text(0.5, 0.5, "Waiting for live angle notifications",
                      transform=axis.transAxes, ha="center", va="center", color="#666666", fontsize=12,
                      bbox=dict(facecolor="white", edgecolor="none", alpha=0.9))
    axis.tick_params(axis="both", which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
    return plt, figure, axis, numbers, status, roll, pitch, clock, empty


def draw(view, history, message, received_clock=None, source_active=True,
         mean_gap_ms=None):
    _, figure, axis, numbers, status, roll, pitch, clock, empty = view
    now = time.time()
    current = datetime.fromtimestamp(now, DISPLAY_TIMEZONE)

    def label(value):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + value.strftime(" %Z")

    sample_label = "Latest BLE reception:    "
    gap_label = "Since received:"
    mean_label = (f"\nMean angle-packet gap:     {mean_gap_ms:.1f} ms (this connection)"
                  if mean_gap_ms is not None else "\nMean angle-packet gap:     —")
    clock.set_text(f"Current time:             {label(current)}\n{sample_label} —\n{gap_label}                      —" + mean_label)
    if history:
        empty.set_visible(False)
        axis.tick_params(axis="both", which="both", bottom=True, left=True, labelbottom=True, labelleft=True)
        newest = history[-1]
        latest = datetime.fromtimestamp(newest["timestamp_unix_ms"] / 1000, DISPLAY_TIMEZONE)
        x = [datetime.fromtimestamp(r["timestamp_unix_ms"] / 1000, DISPLAY_TIMEZONE) for r in history]
        roll.set_data(x, [r["candidate_roll_deg"] for r in history])
        pitch.set_data(x, [r["candidate_pitch_deg"] for r in history])
        axis.relim()
        axis.autoscale_view()
        axis.set_xlim(latest - timedelta(seconds=120), latest + timedelta(seconds=1))
        names = ("Heel", "Trim")
        numbers.set_text(f"{names[0]}: {newest['candidate_roll_deg']:+.2f}°     "
                         f"{names[1]}: {newest['candidate_pitch_deg']:+.2f}°")
        idle = time.monotonic() - received_clock if received_clock is not None else 0
        stale = received_clock is None or idle >= 2 or not source_active
        color = "#aa3333" if stale else "#555555"
        if stale:
            numbers.set_text("Heel: —°     Trim: —°")
            message = "STALE — history only; " + message
        clock.set_text(f"Current time:             {label(current)}\n{sample_label} {label(latest)}\n"
                       f"{gap_label:25} {idle:+.3f} seconds" + mean_label)
        status.set_text(message)
        status.set_color(color)
        clock.set_color(color)
        numbers.set_color(color)
    else:
        empty.set_visible(True)
        axis.tick_params(axis="both", which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
        roll.set_data([], [])
        pitch.set_data([], [])
        numbers.set_text("Heel: —°     Trim: —°")
        numbers.set_color("#555555")
        clock.set_color("#555555")
        status.set_text(message)
    figure.canvas.draw_idle()


def show(args):
    view = create_view()
    plt, figure = view[:2]
    history = deque(maxlen=1000)
    updates = queue.Queue(maxsize=256)
    command = [sys.executable, str(Path(__file__).resolve()), "--collector",
               "--device", args.device]
    supervisor = CollectorSupervisor(command, updates)
    plt.show(block=False)
    message, received_clock = "Connecting…", None
    source_connected = False
    mean_gap_ms, connection_attempt = None, None
    attempt_started_at, connected_at = time.monotonic(), None
    try:
        while plt.fignum_exists(figure.number):
            transition = supervisor.tick()
            if transition is not None:
                source_connected, mean_gap_ms = False, None
                if transition[0] == "started":
                    attempt_started_at, connected_at = time.monotonic(), None
                message = (f"Connecting with fresh BLE collector (attempt {transition[1]})…"
                           if transition[0] == "started" else
                           "Collector stopped; reconnecting in 2 seconds…")
            while True:
                try:
                    record = updates.get_nowait()
                except queue.Empty:
                    break
                if record.get("_collector_generation") != supervisor.generation:
                    continue
                if supervisor.stopping_until is not None:
                    continue
                if record["event"] == "candidate_attitude":
                    sample = live_sample(record)
                    if sample is not None:
                        generation = record.get("_collector_generation")
                        if generation is not None and generation != connection_attempt:
                            history.clear()
                            connection_attempt = generation
                        history.append(sample)
                        # Preserve source reception time even if the GUI stalls.
                        received_clock = record["received_monotonic_ns"] / 1e9
                        source_connected = True
                        mean_gap_ms = record.get("mean_angle_packet_gap_ms")
                        message = "Receiving live BLE candidates • signed display • screen agreement unverified"
                elif record["event"] == "stream_timeout":
                    source_connected = False
                    mean_gap_ms = None
                    message = record["message"]
                    supervisor.restart()
                elif record["event"] == "connected":
                    history.clear()
                    connection_attempt = record.get("_collector_generation")
                    received_clock, mean_gap_ms = None, None
                    source_connected = True
                    connected_at = record["received_monotonic_ns"] / 1e9
                    message = "Connected; waiting for live angle packets"
                elif record["event"] in ("live_status", "summary"):
                    source_connected = record.get("connected", False)
                    mean_gap_ms = record.get("mean_angle_packet_gap_ms") if source_connected else None
                    message = {"waiting_for_candidate": "Connected; waiting for live angle packets",
                               "fresh_candidate": "Receiving live BLE candidates • screen agreement unverified",
                               "stale_candidate": "No recent live angle packets",
                               "disconnected": "Atlas disconnected; reconnecting…"}.get(
                                   record.get("stream_state"), "Waiting for live data")
                    if not source_connected:
                        supervisor.restart()
                else:
                    if record["event"] == "error":
                        source_connected = False
                        mean_gap_ms = None
                        supervisor.restart()
                    message = record.get("error", record.get("message", ""))
                    if record["event"] == "session":
                        history.clear()
            running = supervisor.process is not None and supervisor.process.poll() is None
            if running and supervisor.stopping_until is None:
                now = time.monotonic()
                last_activity = received_clock if received_clock is not None else connected_at
                stream_stuck = source_connected and last_activity is not None and now - last_activity >= 10
                startup_stuck = not source_connected and now - attempt_started_at >= 35
                if stream_stuck or startup_stuck:
                    source_connected, mean_gap_ms = False, None
                    message = "BLE collector is unresponsive; restarting with a fresh process…"
                    supervisor.restart(now)
            draw(view, history, message, received_clock,
                 source_active=running and source_connected,
                 mean_gap_ms=mean_gap_ms)
            plt.pause(0.05)
    finally:
        supervisor.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Atlas identifier from live_atlas.py --scan")
    parser.add_argument("--collector", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        return asyncio.run(collect_live(args)) if args.collector else show(args)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"Plot failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
