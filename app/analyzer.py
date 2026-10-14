from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Iterable

from .fitlite import TrackPoint

EARTH_RADIUS_M = 6_371_000.0


@dataclass(slots=True)
class AnalyzerSettings:
    min_course_change_deg: float = 105.0
    min_entry_speed_kt: float = 4.0
    min_exit_speed_kt: float = 1.5
    planning_threshold_kt: float = 8.0
    dedupe_seconds: float = 15.0


@dataclass(slots=True)
class _PreparedPoint:
    source: TrackPoint
    x: float
    y: float
    smooth_x: float = 0.0
    smooth_y: float = 0.0
    course: float | None = None
    turn_rate: float | None = None


def angular_difference(start_deg: float, end_deg: float) -> float:
    """Shortest signed course change, positive clockwise, in [-180, 180)."""
    return ((end_deg - start_deg + 540.0) % 360.0) - 180.0


def circular_mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    if not vals:
        return None
    sx = sum(math.sin(math.radians(v)) for v in vals)
    sy = sum(math.cos(math.radians(v)) for v in vals)
    if abs(sx) < 1e-12 and abs(sy) < 1e-12:
        return None
    return (math.degrees(math.atan2(sx, sy)) + 360.0) % 360.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _local_xy(points: list[TrackPoint]) -> list[_PreparedPoint]:
    lat0 = math.radians(sum(p.lat for p in points) / len(points))
    origin_lat = points[0].lat
    origin_lon = points[0].lon
    prepared: list[_PreparedPoint] = []
    for point in points:
        x = math.radians(point.lon - origin_lon) * EARTH_RADIUS_M * math.cos(lat0)
        y = math.radians(point.lat - origin_lat) * EARTH_RADIUS_M
        prepared.append(_PreparedPoint(point, x, y))
    return prepared


def _prepare_geometry(points: list[TrackPoint]) -> list[_PreparedPoint]:
    prepared = _local_xy(points)
    n = len(prepared)

    # Three-point coordinate smoothing removes much of the 1 Hz GPS jitter without
    # hiding the overall shape of a gybe.
    for i, point in enumerate(prepared):
        lo = max(0, i - 1)
        hi = min(n, i + 2)
        point.smooth_x = _mean([prepared[j].x for j in range(lo, hi)])
        point.smooth_y = _mean([prepared[j].y for j in range(lo, hi)])

    # Course over ground from a four-second centred baseline. At very low speed
    # the GPS course is intentionally left undefined rather than inventing a heading.
    for i in range(2, n - 2):
        before = prepared[i - 2]
        after = prepared[i + 2]
        if after.source.timestamp - before.source.timestamp > 6:
            continue
        dx = after.smooth_x - before.smooth_x
        dy = after.smooth_y - before.smooth_y
        if math.hypot(dx, dy) < 4.0:
            continue
        prepared[i].course = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0

    # Signed turn rate from neighbouring course samples.
    for i in range(3, n - 3):
        a = prepared[i - 1]
        b = prepared[i + 1]
        if a.course is None or b.course is None:
            continue
        dt = b.source.timestamp - a.source.timestamp
        if dt <= 0 or dt > 4:
            continue
        prepared[i].turn_rate = angular_difference(a.course, b.course) / dt

    return prepared


def _speed_mean(prepared: list[_PreparedPoint], indices: range) -> float:
    vals = [prepared[i].source.speed_kt for i in indices if 0 <= i < len(prepared)]
    return _mean(vals)


def _course_mean(prepared: list[_PreparedPoint], indices: range, min_speed: float) -> float | None:
    vals = [
        prepared[i].course
        for i in indices
        if 0 <= i < len(prepared)
        and prepared[i].course is not None
        and prepared[i].source.speed_kt >= min_speed
    ]
    return circular_mean([v for v in vals if v is not None])


def _path_length(prepared: list[_PreparedPoint], start: int, end: int) -> float:
    total = 0.0
    for i in range(start, end):
        total += math.hypot(prepared[i + 1].x - prepared[i].x, prepared[i + 1].y - prepared[i].y)
    return total


def _confidence(entry: float, exit_: float, course_change: float, duration: float, gap_free: bool) -> int:
    score = 25
    score += min(25, int(max(0.0, entry - 4.0) * 2.0))
    score += min(20, int(max(0.0, exit_ - 1.5) * 2.0))
    score += 15 if 120.0 <= abs(course_change) <= 180.0 else 5
    score += 10 if 2.0 <= duration <= 12.0 else 2
    score += 5 if gap_free else 0
    return max(0, min(100, score))


def analyze(points: list[TrackPoint], settings: AnalyzerSettings | None = None) -> dict:
    settings = settings or AnalyzerSettings()
    prepared = _prepare_geometry(points)
    n = len(prepared)

    scores = [0.0] * n
    references: dict[int, tuple[float, float, float, float]] = {}

    # A windsurfing gybe/tack appears as two stable runs separated by a large course
    # change. Compare the approach and exit courses instead of relying on noisy GPS
    # heading at the lowest-speed point in the middle of the manoeuvre.
    for i in range(10, n - 10):
        if prepared[i + 8].source.timestamp - prepared[i - 8].source.timestamp > 20:
            continue
        pre = range(i - 9, i - 4)
        post = range(i + 5, i + 10)
        pre_course = _course_mean(prepared, pre, 4.0)
        post_course = _course_mean(prepared, post, 3.0)
        if pre_course is None or post_course is None:
            continue
        change = abs(angular_difference(pre_course, post_course))
        entry_probe = _speed_mean(prepared, pre)
        exit_probe = _speed_mean(prepared, post)
        if (
            change >= settings.min_course_change_deg
            and entry_probe >= settings.min_entry_speed_kt
            and exit_probe >= settings.min_exit_speed_kt
        ):
            scores[i] = change
            references[i] = (pre_course, post_course, entry_probe, exit_probe)

    raw_candidates: list[int] = []
    for i in range(10, n - 10):
        if scores[i] <= 0:
            continue
        local = scores[max(0, i - 4) : min(n, i + 5)]
        if scores[i] >= max(local):
            raw_candidates.append(i)

    selected: list[int] = []
    for candidate in sorted(raw_candidates, key=lambda idx: scores[idx], reverse=True):
        timestamp = prepared[candidate].source.timestamp
        if all(abs(timestamp - prepared[other].source.timestamp) >= settings.dedupe_seconds for other in selected):
            selected.append(candidate)
    selected.sort()

    gybes: list[dict] = []
    for candidate in selected:
        pre_course, post_course, _, _ = references[candidate]
        signed_change = angular_difference(pre_course, post_course)
        direction_sign = 1.0 if signed_change >= 0 else -1.0
        total_change = abs(signed_change)

        progress: list[tuple[int, float]] = []
        for j in range(max(0, candidate - 10), min(n, candidate + 11)):
            course = prepared[j].course
            if course is None:
                continue
            value = direction_sign * angular_difference(pre_course, course)
            if value < -30.0:
                value += 360.0
            progress.append((j, value))

        start_threshold = max(10.0, total_change * 0.10)
        end_threshold = min(total_change - 10.0, total_change * 0.90)
        start = next((j for j, value in progress if value >= start_threshold), candidate - 4)
        end = next((j for j, value in progress if j >= start and value >= end_threshold), candidate + 4)
        start = max(0, start)
        end = min(n - 1, end)
        if end <= start:
            start = max(0, candidate - 4)
            end = min(n - 1, candidate + 4)

        entry_indices = range(max(0, start - 3), start)
        exit_indices = range(end + 1, min(n, end + 4))
        entry_speed = _speed_mean(prepared, entry_indices)
        exit_speed = _speed_mean(prepared, exit_indices)

        turn_indices = list(range(start, end + 1))
        apex = min(turn_indices, key=lambda idx: prepared[idx].source.speed_kt)
        min_speed = prepared[apex].source.speed_kt
        duration = float(prepared[end].source.timestamp - prepared[start].source.timestamp)
        turn_distance = _path_length(prepared, start, end)
        effective_radius = turn_distance / math.radians(total_change) if total_change > 1.0 else None
        rates = [abs(prepared[j].turn_rate) for j in turn_indices if prepared[j].turn_rate is not None]
        max_turn_rate = max(rates) if rates else None
        gap_free = all(
            prepared[j + 1].source.timestamp - prepared[j].source.timestamp <= 2 for j in range(start, end)
        )

        detail_start = max(0, start - 5)
        detail_end = min(n - 1, end + 5)
        detail_points: list[dict] = []
        apex_time = prepared[apex].source.timestamp
        for j in range(detail_start, detail_end + 1):
            p = prepared[j]
            detail_points.append(
                {
                    "t": p.source.timestamp - apex_time,
                    "time_utc": p.source.time_utc.isoformat(),
                    "lat": round(p.source.lat, 7),
                    "lon": round(p.source.lon, 7),
                    "x": round(p.x, 2),
                    "y": round(p.y, 2),
                    "speed_kt": round(p.source.speed_kt, 2),
                    "course_deg": round(p.course, 1) if p.course is not None else None,
                    "turn_rate_dps": round(p.turn_rate, 1) if p.turn_rate is not None else None,
                    "phase": "turn" if start <= j <= end else "context",
                }
            )

        entry_retention = (exit_speed / entry_speed * 100.0) if entry_speed > 0.1 else None
        min_retention = (min_speed / entry_speed * 100.0) if entry_speed > 0.1 else None
        gybes.append(
            {
                "id": len(gybes) + 1,
                "candidate_index": candidate,
                "time_utc": prepared[candidate].source.time_utc.isoformat(),
                "direction": "right" if signed_change > 0 else "left",
                "entry_speed_kt": round(entry_speed, 2),
                "min_speed_kt": round(min_speed, 2),
                "exit_speed_kt": round(exit_speed, 2),
                "exit_retention_pct": round(entry_retention, 1) if entry_retention is not None else None,
                "min_retention_pct": round(min_retention, 1) if min_retention is not None else None,
                "duration_s": round(duration, 1),
                "course_change_deg": round(signed_change, 1),
                "turn_distance_m": round(turn_distance, 1),
                "effective_radius_m": round(effective_radius, 1) if effective_radius is not None else None,
                "max_turn_rate_dps": round(max_turn_rate, 1) if max_turn_rate is not None else None,
                "planning_through": min_speed >= settings.planning_threshold_kt,
                "confidence": _confidence(entry_speed, exit_speed, signed_change, duration, gap_free),
                "center": {
                    "lat": round(prepared[candidate].source.lat, 7),
                    "lon": round(prepared[candidate].source.lon, 7),
                    "x": round(prepared[candidate].x, 2),
                    "y": round(prepared[candidate].y, 2),
                },
                "points": detail_points,
            }
        )

    start_time = points[0].time_utc
    end_time = points[-1].time_utc
    distance_candidates = [p.distance_m for p in points if p.distance_m is not None]
    distance_m = max(distance_candidates) - min(distance_candidates) if distance_candidates else _path_length(prepared, 0, n - 1)
    max_speed = max(p.speed_kt for p in points)
    moving_speeds = [p.speed_kt for p in points if p.speed_kt > 0.5]

    track = [
        {
            "t": p.source.timestamp - points[0].timestamp,
            "lat": round(p.source.lat, 7),
            "lon": round(p.source.lon, 7),
            "x": round(p.x, 2),
            "y": round(p.y, 2),
            "speed_kt": round(p.source.speed_kt, 2),
        }
        for p in prepared
    ]

    return {
        "summary": {
            "start_utc": start_time.isoformat(),
            "end_utc": end_time.isoformat(),
            "duration_s": int(points[-1].timestamp - points[0].timestamp),
            "distance_km": round(distance_m / 1000.0, 3),
            "max_speed_kt": round(max_speed, 2),
            "mean_moving_speed_kt": round(_mean(moving_speeds), 2) if moving_speeds else 0.0,
            "gps_points": len(points),
            "detected_turns": len(gybes),
            "planning_through": sum(1 for g in gybes if g["planning_through"]),
        },
        "settings": {
            "min_course_change_deg": settings.min_course_change_deg,
            "min_entry_speed_kt": settings.min_entry_speed_kt,
            "min_exit_speed_kt": settings.min_exit_speed_kt,
            "planning_threshold_kt": settings.planning_threshold_kt,
        },
        "track": track,
        "gybes": gybes,
    }
