"""Mac bench diagnostic only; no Android application code or simulated readings."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"
CAPTURE_DIR = Path(__file__).resolve().parents[2] / "local_data" / "garmin_hrm"


def decode_measurement(data):
    """Decode Bluetooth SIG Heart Rate Measurement; reject truncated fields."""
    if not data:
        raise ValueError("Missing flags")
    flags = data[0]
    offset = 1

    def take_uint(size):
        nonlocal offset
        if offset + size > len(data):
            raise ValueError("Truncated measurement")
        value = int.from_bytes(data[offset:offset + size], "little")
        offset += size
        return value

    result = {
        "flags": flags,
        "heart_rate_bpm": take_uint(2 if flags & 1 else 1),
        "contact_detected": bool(flags & 2) if flags & 4 else None,
        "energy_expended_kj": take_uint(2) if flags & 8 else None,
        "rr_intervals_ms": [],
    }
    if flags & 16:
        if offset == len(data):
            raise ValueError("RR flag set without intervals")
        while offset < len(data):
            result["rr_intervals_ms"].append(take_uint(2) * 1000 / 1024)
    if offset != len(data):
        raise ValueError("Unexpected trailing bytes")
    return result


async def run(args):
    # Lazy import lets parser tests and --help run without Bluetooth dependencies.
    from bleak import BleakClient, BleakScanner

    print("Scanning for 10 seconds...")
    found = await BleakScanner.discover(timeout=10, return_adv=True)
    for device, advert in found.values():
        if args.all or HR_SERVICE in advert.service_uuids or (
            args.device and device.address.lower() == args.device.lower()
        ):
            print(f"{device.address}  {advert.local_name or device.name or '(unnamed)'}")
    if not args.device:
        print("Copy the band's identifier, then rerun with --device IDENTIFIER.")
        print("If nothing appears, wear the band and try --all.")
        return

    selected = next((d for d, _ in found.values()
                     if d.address.lower() == args.device.lower()), None)
    if selected is None:
        raise RuntimeError("Selected device was not found. Scan again with --all.")

    disconnected = asyncio.Event()
    count = 0
    valid = 0
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    capture = CAPTURE_DIR / f"live-{stamp}.jsonl"
    with capture.open("x", encoding="utf-8") as output:
        def notify(_characteristic, data):
            nonlocal count, valid
            record = {
                "input_mode": "live",
                "received_at_utc": datetime.now(timezone.utc).isoformat(),
                "received_monotonic_ns": time.monotonic_ns(),
                "device_id": selected.address,
                "characteristic": HR_MEASUREMENT,
                "raw_hex": bytes(data).hex(),
            }
            count += 1
            try:
                record["decoded"] = decode_measurement(data)
                valid += 1
                print(f"{record['decoded']['heart_rate_bpm']} BPM  raw={record['raw_hex']}")
            except ValueError as error:
                record["decode_error"] = str(error)
                print(f"Invalid packet: {error}; raw={record['raw_hex']}")
            output.write(json.dumps(record) + "\n")
            output.flush()

        async with BleakClient(selected, disconnected_callback=lambda _: disconnected.set()) as client:
            print(f"Connected to {selected.name or selected.address} (verify model on band).")
            for service in client.services:
                print(f"Service {service.uuid}")
                for characteristic in service.characteristics:
                    print(f"  {characteristic.uuid} {characteristic.properties}")
            await client.start_notify(HR_MEASUREMENT, notify)
            print(f"Capturing for up to {args.seconds:g} seconds: {capture}")
            try:
                await asyncio.wait_for(disconnected.wait(), timeout=args.seconds)
            except asyncio.TimeoutError:
                pass
            if disconnected.is_set():
                raise RuntimeError("Band disconnected. Capture retained; rerun to reconnect.")
            await client.stop_notify(HR_MEASUREMENT)
    print(f"Captured {count} packets, {valid} decoded. File: {capture}")
    if not valid:
        raise RuntimeError("No valid heart-rate readings received; hardware check incomplete.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="List all nearby BLE devices")
    parser.add_argument("--device", help="Exact identifier shown by scan (UUID on macOS)")
    parser.add_argument("--seconds", type=float, default=30, help="Capture duration (default: 30)")
    args = parser.parse_args()
    if not 0 < args.seconds < float("inf"):
        parser.error("--seconds must be positive and finite")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Stopped; any received packets remain in the capture file.")
    except Exception as error:
        print(f"Diagnostic failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
