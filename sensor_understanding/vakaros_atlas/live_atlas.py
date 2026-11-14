"""Notification-only Atlas bench receiver; live Heel/Trim protocol is unverified.

No recorded-session queries/downloads, interpolation or synthetic input. The
opt-in 020901 command was observed in the user's Connect capture before 020a
notifications, then produced notifications in the user's direct Mac test.
Field labels are supported by capture analysis; screen agreement is unverified.
See README.md for the protocol and INVESTIGATION.md for its evidence.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
import subprocess
import math
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
ATLAS_SERVICE = "ac510001-0000-5a11-0076-616b61726f73"
COMMAND = "ac510002-0000-5a11-0076-616b61726f73"
TELEMETRY_MAIN = "ac510003-0000-5a11-0076-616b61726f73"
TELEMETRY_AUX = "ac510005-0000-5a11-0076-616b61726f73"


class Journal:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.output = path.open("x", encoding="utf-8")
        self.started = time.monotonic_ns()

    def emit(self, event, **fields):
        now = time.monotonic_ns()
        record = {
            "event": event,
            "input_mode": "live",
            "received_at_utc": datetime.now(timezone.utc).isoformat(),
            "received_monotonic_ns": now,
            "elapsed_ms": round((now - self.started) / 1e6, 3),
            **fields,
        }
        line = json.dumps(record)
        self.output.write(line + "\n")
        self.output.flush()
        print(line, flush=True)

    def close(self):
        self.output.close()


def environment():
    packages = {}
    for name in ("bleak", "pyobjc-core", "pyobjc-framework-CoreBluetooth",
                 "pyobjc-framework-Cocoa", "pyobjc-framework-libdispatch", "dbus-fast"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            pass
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, timeout=5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unknown"
    return {"platform": platform.platform(), "python": sys.version,
            "packages": packages, "commit": commit}


async def discover(scanner, seconds, journal):
    found = await scanner.discover(timeout=seconds, return_adv=True)
    for device, advert in found.values():
        journal.emit(
            "advertisement", device_id=device.address,
            name=advert.local_name or device.name,
            rssi_dbm=advert.rssi,
            service_uuids=advert.service_uuids,
            manufacturer_data={str(k): bytes(v).hex()
                               for k, v in advert.manufacturer_data.items()},
            service_data={k: bytes(v).hex() for k, v in advert.service_data.items()},
        )
    return [device for device, _ in found.values()]


def positive_seconds(text):
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("Must be a positive finite number")
    return value


# Observed ATT Write Command to Command 1 in vakaros_ble1.pklg, record 3027.
# Never replay phone-specific ATT handles, initial settings queries or log requests.
START_STREAM = bytes.fromhex("02 09 01")


def inspect_packet(uuid, packet):
    """Classify first; never interpret a session reply as attitude telemetry."""
    raw = bytes(packet)
    if uuid.lower() != TELEMETRY_MAIN:
        return "unverified_other_channel", None
    if raw.startswith(b"\x02\x0b"):
        return "session_list_reply", None
    if not raw.startswith(b"\x02\x0a"):
        return "unknown_packet", None
    if len(raw) < 28:
        return "truncated_candidate", None
    trim, heel = struct.unpack_from("<ff", raw, 20)
    if not all(math.isfinite(v) for v in (trim, heel)):
        return "nonfinite_candidate", None
    # GPS does not gate attitude. Names, scale, signs and mounting are hypotheses.
    return "candidate_attitude", {"candidate_heel_deg": heel,
                                   "candidate_trim_deg": trim}


class LiveState:
    def __init__(self, stale_after):
        self.stale_after = stale_after
        self.last_candidate = None
        self.last_candidate_at = None
        self.packets = 0
        self.candidates = 0
        self.interval_count = 0
        self.interval_mean_s = 0.0

    def accept(self, uuid, packet, now):
        self.packets += 1
        kind, candidate = inspect_packet(uuid, packet)
        if candidate is not None:
            if self.last_candidate_at is not None:
                gap = max(0.0, now - self.last_candidate_at)
                self.interval_count += 1
                self.interval_mean_s += (gap - self.interval_mean_s) / self.interval_count
            self.last_candidate = candidate
            self.last_candidate_at = now
            self.candidates += 1
        return kind, candidate

    def snapshot(self, now, connected):
        age = None if self.last_candidate_at is None else max(0, now - self.last_candidate_at)
        fresh = connected and age is not None and age < self.stale_after
        state = ("disconnected" if not connected else
                 "waiting_for_candidate" if age is None else
                 "fresh_candidate" if fresh else "stale_candidate")
        return dict(connected=connected, stream_state=state,
                    packets=self.packets, candidate_packets=self.candidates,
                    angle_packet_interval_count=self.interval_count,
                    mean_angle_packet_gap_ms=(self.interval_mean_s * 1000
                                              if self.interval_count else None),
                    candidate_receive_age_s=age,
                    candidate_heel_deg=self.last_candidate["candidate_heel_deg"] if fresh else None,
                    candidate_trim_deg=self.last_candidate["candidate_trim_deg"] if fresh else None,
                    heel_trim_verified=False, device_sample_time=None,
                    clock_semantics="Mac notification reception; device sample time unknown")


async def listen(device, args, journal, client_factory):
    lost = asyncio.Event()
    state = LiveState(args.stale_after)
    active = []

    def notified(char, packet):
        if lost.is_set():
            return
        now = time.monotonic()
        kind, candidate = state.accept(char.uuid, packet, now)
        journal.emit("live_notification", device_id=device.address,
                     sequence=state.packets, characteristic_uuid=char.uuid,
                     raw_hex=bytes(packet).hex(), length=len(packet),
                     classification=kind, decoded=candidate,
                     quality="unverified", heel_trim_verified=False)
        if candidate is not None:
            # Publish in this callback: no page completion or batch accumulator.
            journal.emit("candidate_attitude", device_id=device.address,
                         sequence=state.packets, **state.snapshot(now, not lost.is_set()))

    async with client_factory(device, disconnected_callback=lambda _: lost.set()) as client:
        chars = [c for s in client.services if s.uuid.lower() == ATLAS_SERVICE
                 for c in s.characteristics]
        selected = [c for c in chars if c.uuid.lower() in (TELEMETRY_MAIN, TELEMETRY_AUX)
                    and "notify" in c.properties]
        if {c.uuid.lower() for c in selected} != {TELEMETRY_MAIN, TELEMETRY_AUX}:
            raise ValueError("Expected Atlas main and data notify channels not found")
        write_property = "write-without-response"
        commands = [c for c in chars if c.uuid.lower() == COMMAND
                    and write_property in c.properties]
        if args.start_stream and len(commands) != 1:
            raise ValueError(f"Command 1 must support {write_property}; no command sent")
        journal.emit("connected", device_id=device.address,
                     interpretation="BLE link only; live attitude not established")
        try:
            for char in selected:
                await client.start_notify(char, notified)
                active.append(char)
                journal.emit("subscribed", uuid=char.uuid)
            if args.start_stream:
                if lost.is_set() or not client.is_connected:
                    raise RuntimeError("Disconnected before activation; no command sent")
                payload = START_STREAM
                response = False
                journal.emit("request_attempt", uuid=commands[0].uuid, raw_hex=payload.hex(),
                             response=response,
                             purpose="phone-observed streaming command")
                await asyncio.wait_for(client.write_gatt_char(commands[0], payload, response=response), 5)
                journal.emit("start_write_completed",
                             streaming_established=False, gatt_response_requested=response)
            # The graph runs until closed; the standalone CLI remains bounded.
            deadline = None if args.seconds is None else time.monotonic() + args.seconds
            listening_since = time.monotonic()
            while not lost.is_set():
                if not client.is_connected:
                    lost.set()
                    break
                journal.emit("live_status", **state.snapshot(time.monotonic(), True))
                silence_limit = getattr(args, "silence_timeout", None)
                last_angle = state.last_candidate_at if state.last_candidate_at is not None else listening_since
                if silence_limit is not None and time.monotonic() - last_angle >= silence_limit:
                    journal.emit("stream_timeout", **state.snapshot(time.monotonic(), False),
                                 message=f"No angle packets for {silence_limit:g} seconds; restarting BLE collector")
                    raise TimeoutError("BLE connected but angle stream is silent; fresh connection required")
                remaining = 1 if deadline is None else deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    await asyncio.wait_for(lost.wait(), min(1, remaining))
                except asyncio.TimeoutError:
                    pass
            connected = not lost.is_set() and client.is_connected
            journal.emit("summary", **state.snapshot(time.monotonic(), connected),
                         interpretation="Candidate layout only; compare with Atlas screen before integration")
            return 0 if connected and state.candidates else 2
        finally:
            lost.set()
            if client.is_connected:
                for char in active:
                    try:
                        await client.stop_notify(char)
                    except Exception as error:
                        journal.emit("unsubscribe_error", uuid=char.uuid, error=str(error))


async def run(args, journal):
    from bleak import BleakClient, BleakScanner
    devices = await discover(BleakScanner, args.scan_seconds, journal)
    if getattr(args, "scan", False):
        journal.emit("scan_complete", devices=len(devices))
        return 0
    device = next((d for d in devices if d.address.lower() == args.device.lower()), None)
    if device is None:
        raise RuntimeError("Atlas not found in scan; verify power, proximity and competing connections")
    return await listen(device, args, journal, BleakClient)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--device", help="Exact device_id reported by --scan on this receiver")
    target.add_argument("--scan", action="store_true", help="List advertisements without connecting or writing")
    parser.add_argument("--seconds", type=positive_seconds, default=60)
    parser.add_argument("--scan-seconds", type=positive_seconds, default=10)
    parser.add_argument("--stale-after", type=positive_seconds, default=2,
                        help="Candidate reception freshness only; not a measured latency target")
    parser.add_argument("--start-stream", action="store_true",
                        help="Send observed 02 09 01 once, without response, after subscribing")
    parser.add_argument("--note", default="", help="Firmware, mounting and paired screen observations")
    args = parser.parse_args()
    if args.scan and args.start_stream:
        parser.error("--start-stream requires --device")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = ROOT / "local_data" / "vakaros_atlas" / f"notification-live-{stamp}.jsonl"
    journal = Journal(path)
    try:
        journal.emit("start", command="notification-only", device_id=args.device,
                     note=args.note, capture_path=str(path),
                     start_stream=args.start_stream,
                     **environment())
        return asyncio.run(run(args, journal))
    except KeyboardInterrupt:
        journal.emit("interrupted", reason="Stopped by user; capture retained")
        return 130
    except Exception as error:
        journal.emit("error", error=str(error))
        return 1
    finally:
        journal.close()


if __name__ == "__main__":
    sys.exit(main())
