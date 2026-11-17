"""Read-only comparison of app CSV with previously reconstructed recorded data.

Recorded VKX payloads and live 020a notifications are different message formats.
This helper does not infer live byte offsets from CSV column order.
"""
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path


def timestamp_ms(value):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try: return round(datetime.strptime(value, fmt).timestamp() * 1000)
        except ValueError: pass
    raise ValueError("Unsupported timestamp: " + value)


def euler(q):
    w, x, y, z = q
    return (math.degrees(math.atan2(2 * (w*x + y*z), 1 - 2 * (x*x + y*y))),
            math.degrees(math.asin(max(-1, min(1, 2 * (w*y - z*x))))),
            math.degrees(math.atan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z))) % 360)


def compare(csv_path, recorded_path):
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"timestamp", "latitude", "longitude", "sog_kts", "cog", "hdg_true",
                "heel", "trim", "altitude_m", "declination", "q_w", "q_x", "q_y", "q_z"}
    if not rows or not required.issubset(rows[0]): raise ValueError("CSV empty or required columns missing")
    records = {}
    for line in Path(recorded_path).read_text().splitlines():
        record = json.loads(line)
        if record.get("record_type") == "position_velocity_orientation":
            stamp = record["timestamp_unix_ms"]
            if stamp in records and records[stamp] != record:
                raise ValueError("Ambiguous duplicate recorded timestamp")
            records[stamp] = record
    errors, unmatched, floor_matches, matched = {}, [], 0, 0
    for index, row in enumerate(rows, 2):
        record = records.get(timestamp_ms(row["timestamp"]))
        if record is None:
            unmatched.append(index)
            continue
        matched += 1
        roll, pitch, yaw = euler([record["quaternion_" + axis] for axis in "wxyz"])
        expected = {"latitude": record["latitude_deg"], "longitude": record["longitude_deg"],
                    "sog_kts": record["sog_m_s"] * 3600 / 1852,
                    "cog": math.degrees(record["cog_rad"]) % 360,
                    "hdg_true": yaw, "heel": roll, "trim": pitch,
                    "altitude_m": record["altitude_m"],
                    **{"q_" + axis: record["quaternion_" + axis] for axis in "wxyz"}}
        for field, value in expected.items():
            actual = float(row[field])
            if not math.isfinite(actual) or not math.isfinite(value): raise ValueError("Nonfinite " + field)
            delta = abs(actual - value)
            if field in ("cog", "hdg_true", "heel"): delta = abs((actual - value + 180) % 360 - 180)
            errors.setdefault(field, []).append(delta)
        floor_matches += float(row["altitude_m"]) == math.floor(record["altitude_m"])
    return {"input_mode": "replay", "csv_rows": len(rows), "matched_rows": matched,
            "unmatched_csv_lines": unmatched, "altitude_floor_matches": floor_matches,
            "declination_values": sorted({float(r["declination"]) for r in rows}),
            "max_absolute_error": {k: max(v) for k, v in errors.items()},
            "source_sha256": {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest()
                              for p in (csv_path, recorded_path)},
            "limitations": ["Recorded-session comparison, not synchronized live telemetry",
                            "Declination has no independently decoded reference here",
                            "Live heading/speed semantics and device clock remain unresolved"]}
