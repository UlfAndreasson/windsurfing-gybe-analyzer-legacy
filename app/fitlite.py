"""Small FIT activity decoder focused on Garmin record messages.

The analyzer only needs timestamp, GPS position, distance, speed and heart rate.
This decoder intentionally implements the FIT container/protocol rather than the
entire Garmin profile. Unknown messages and fields are safely ignored.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import io
import struct
import zipfile
from typing import Any

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
SEMICIRCLE_TO_DEG = 180.0 / (2**31)
MPS_TO_KNOTS = 1.9438444924406

_BASE_TYPES: dict[int, tuple[str | None, int, int | None]] = {
    0: ("B", 1, 0xFF),
    1: ("b", 1, 0x7F),
    2: ("B", 1, 0xFF),
    3: ("h", 2, 0x7FFF),
    4: ("H", 2, 0xFFFF),
    5: ("i", 4, 0x7FFFFFFF),
    6: ("I", 4, 0xFFFFFFFF),
    7: (None, 1, None),
    8: ("f", 4, None),
    9: ("d", 8, None),
    10: ("B", 1, 0x00),
    11: ("H", 2, 0x0000),
    12: ("I", 4, 0x00000000),
    13: ("B", 1, 0xFF),
    14: ("q", 8, 0x7FFFFFFFFFFFFFFF),
    15: ("Q", 8, 0xFFFFFFFFFFFFFFFF),
    16: ("Q", 8, 0x0000000000000000),
}


class FitDecodeError(ValueError):
    pass


@dataclass(slots=True)
class TrackPoint:
    timestamp: int
    lat: float
    lon: float
    speed_kt: float
    distance_m: float | None
    heart_rate: int | None

    @property
    def time_utc(self) -> datetime:
        return FIT_EPOCH + timedelta(seconds=self.timestamp)


@dataclass(slots=True)
class _Definition:
    global_message: int
    architecture: int
    fields: list[tuple[int, int, int]]
    developer_fields: list[tuple[int, int, int]]


def _decode_primitive(raw: bytes, base_type: int, architecture: int) -> Any:
    kind = base_type & 0x1F
    spec = _BASE_TYPES.get(kind)
    if spec is None:
        return raw
    fmt, primitive_size, invalid = spec
    if kind == 7:
        return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    if fmt is None or not raw:
        return None
    if len(raw) % primitive_size:
        return raw
    endian = "<" if architecture == 0 else ">"
    values: list[Any] = []
    for offset in range(0, len(raw), primitive_size):
        value = struct.unpack(endian + fmt, raw[offset : offset + primitive_size])[0]
        values.append(None if invalid is not None and value == invalid else value)
    return values[0] if len(values) == 1 else values


def _extract_fit_bytes(payload: bytes, filename: str) -> bytes:
    if filename.lower().endswith(".zip") or payload[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                fit_names = [n for n in archive.namelist() if n.lower().endswith(".fit") and not n.endswith("/")]
                if not fit_names:
                    raise FitDecodeError("ZIP-filen innehåller ingen .FIT-fil")
                fit_name = max(fit_names, key=lambda n: archive.getinfo(n).file_size)
                if archive.getinfo(fit_name).file_size > 50 * 1024 * 1024:
                    raise FitDecodeError("FIT-filen är orimligt stor")
                return archive.read(fit_name)
        except zipfile.BadZipFile as exc:
            raise FitDecodeError("Ogiltig ZIP-fil") from exc
    return payload


def decode_activity(payload: bytes, filename: str = "activity.fit") -> list[TrackPoint]:
    data = _extract_fit_bytes(payload, filename)
    if len(data) < 14:
        raise FitDecodeError("Filen är för liten för att vara en FIT-fil")
    header_size = data[0]
    if header_size not in (12, 14) or data[8:12] != b".FIT":
        raise FitDecodeError("Filen har inte en giltig FIT-header")
    data_size = int.from_bytes(data[4:8], "little")
    data_start = header_size
    data_end = data_start + data_size
    if data_end > len(data):
        raise FitDecodeError("FIT-filen är avkortad")

    definitions: dict[int, _Definition] = {}
    records: list[dict[int, Any]] = []
    pos = data_start
    last_timestamp: int | None = None

    while pos < data_end:
        record_header = data[pos]
        pos += 1

        if record_header & 0x80:
            local = (record_header >> 5) & 0x03
            definition = definitions.get(local)
            if definition is None:
                raise FitDecodeError(f"Saknar definition för lokalt FIT-meddelande {local}")
            values: dict[int, Any] = {}
            if last_timestamp is not None:
                offset = record_header & 0x1F
                timestamp = (last_timestamp & ~0x1F) + offset
                if timestamp < last_timestamp:
                    timestamp += 0x20
                values[253] = timestamp
                last_timestamp = timestamp
            for field_num, size, base_type in definition.fields:
                if field_num == 253:
                    continue
                raw = data[pos : pos + size]
                pos += size
                values[field_num] = _decode_primitive(raw, base_type, definition.architecture)
            for _field_num, size, _developer_index in definition.developer_fields:
                pos += size
            if definition.global_message == 20:
                records.append(values)
            continue

        local = record_header & 0x0F
        if record_header & 0x40:
            has_developer_fields = bool(record_header & 0x20)
            if pos + 5 > data_end:
                raise FitDecodeError("Trasig FIT-definition")
            pos += 1
            architecture = data[pos]
            pos += 1
            byte_order = "little" if architecture == 0 else "big"
            global_message = int.from_bytes(data[pos : pos + 2], byte_order)
            pos += 2
            num_fields = data[pos]
            pos += 1
            fields: list[tuple[int, int, int]] = []
            for _ in range(num_fields):
                if pos + 3 > data_end:
                    raise FitDecodeError("Trasig FIT-fältdefinition")
                fields.append((data[pos], data[pos + 1], data[pos + 2]))
                pos += 3
            developer_fields: list[tuple[int, int, int]] = []
            if has_developer_fields:
                num_developer_fields = data[pos]
                pos += 1
                for _ in range(num_developer_fields):
                    developer_fields.append((data[pos], data[pos + 1], data[pos + 2]))
                    pos += 3
            definitions[local] = _Definition(global_message, architecture, fields, developer_fields)
            continue

        definition = definitions.get(local)
        if definition is None:
            raise FitDecodeError(f"Saknar definition för lokalt FIT-meddelande {local}")
        values: dict[int, Any] = {}
        for field_num, size, base_type in definition.fields:
            raw = data[pos : pos + size]
            pos += size
            values[field_num] = _decode_primitive(raw, base_type, definition.architecture)
        for _field_num, size, _developer_index in definition.developer_fields:
            pos += size
        timestamp = values.get(253)
        if isinstance(timestamp, int):
            last_timestamp = timestamp
        if definition.global_message == 20:
            records.append(values)

    points: list[TrackPoint] = []
    seen_timestamps: set[int] = set()
    for record in records:
        timestamp = record.get(253)
        raw_lat = record.get(0)
        raw_lon = record.get(1)
        if not isinstance(timestamp, int) or not isinstance(raw_lat, int) or not isinstance(raw_lon, int):
            continue
        if timestamp in seen_timestamps:
            continue
        seen_timestamps.add(timestamp)

        raw_speed = record.get(73)
        if not isinstance(raw_speed, (int, float)):
            raw_speed = record.get(6)
        speed_kt = float(raw_speed) / 1000.0 * MPS_TO_KNOTS if isinstance(raw_speed, (int, float)) else 0.0

        raw_distance = record.get(5)
        distance_m = float(raw_distance) / 100.0 if isinstance(raw_distance, (int, float)) else None
        heart_rate = record.get(3) if isinstance(record.get(3), int) else None

        points.append(
            TrackPoint(
                timestamp=timestamp,
                lat=raw_lat * SEMICIRCLE_TO_DEG,
                lon=raw_lon * SEMICIRCLE_TO_DEG,
                speed_kt=speed_kt,
                distance_m=distance_m,
                heart_rate=heart_rate,
            )
        )

    points.sort(key=lambda p: p.timestamp)
    if len(points) < 20:
        raise FitDecodeError("För få GPS-punkter i aktiviteten")
    return points
