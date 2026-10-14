from __future__ import annotations

from dataclasses import dataclass
import math
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
    wind_from_deg: float | None = None


@dataclass(slots=True)
class _PreparedPoint:
    source: TrackPoint
    x: float
    y: float
    smooth_x: float = 0.0
    smooth_y: float = 0.0
    course: float | None = None
    turn_rate: float | None = None


def normalize_degrees(value: float) -> float:
    return value % 360.0


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
    return normalize_degrees(math.degrees(math.atan2(sx, sy)))


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

    for i, point in enumerate(prepared):
        lo = max(0, i - 1)
        hi = min(n, i + 2)
        point.smooth_x = _mean([prepared[j].x for j in range(lo, hi)])
        point.smooth_y = _mean([prepared[j].y for j in range(lo, hi)])

    for i in range(2, n - 2):
        before = prepared[i - 2]
        after = prepared[i + 2]
        if after.source.timestamp - before.source.timestamp > 6:
            continue
        dx = after.smooth_x - before.smooth_x
        dy = after.smooth_y - before.smooth_y
        if math.hypot(dx, dy) < 4.0:
            continue
        prepared[i].course = normalize_degrees(math.degrees(math.atan2(dx, dy)))

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
    for i in range(max(0, start), min(end, len(prepared) - 1)):
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


def _actual_turn_change(
    prepared: list[_PreparedPoint], candidate: int, pre_course: float, post_course: float
) -> float:
    shortest = angular_difference(pre_course, post_course)
    local_rates = [
        prepared[j].turn_rate
        for j in range(max(0, candidate - 6), min(len(prepared), candidate + 7))
        if prepared[j].turn_rate is not None and abs(prepared[j].turn_rate) <= 120.0
    ]
    rate_signal = sum(local_rates) if local_rates else 0.0
    if abs(rate_signal) >= 2.0:
        return (1.0 if rate_signal > 0 else -1.0) * abs(shortest)
    return shortest


def classify_maneuver(pre_course: float, signed_change: float, wind_from_deg: float | None) -> dict:
    midpoint = normalize_degrees(pre_course + signed_change / 2.0)
    if wind_from_deg is None:
        return {"maneuver": "unknown", "turn_mid_course_deg": round(midpoint, 1)}

    wind_from = normalize_degrees(wind_from_deg)
    wind_to = normalize_degrees(wind_from + 180.0)
    to_from = abs(angular_difference(midpoint, wind_from))
    to_to = abs(angular_difference(midpoint, wind_to))
    maneuver = "tack" if to_from <= to_to else "gybe"
    return {
        "maneuver": maneuver,
        "turn_mid_course_deg": round(midpoint, 1),
        "wind_from_deg": round(wind_from, 1),
        "wind_to_deg": round(wind_to, 1),
        "wind_alignment_error_deg": round(min(to_from, to_to), 1),
    }


def _first_sustained_speed(
    prepared: list[_PreparedPoint],
    start: int,
    threshold_kt: float,
    *,
    max_seconds: float = 30.0,
    samples: int = 3,
) -> int | None:
    if not prepared or start >= len(prepared):
        return None
    start = max(0, start)
    start_time = prepared[start].source.timestamp
    for i in range(start, len(prepared) - samples + 1):
        if prepared[i].source.timestamp - start_time > max_seconds:
            break
        window = prepared[i : i + samples]
        if any(window[j + 1].source.timestamp - window[j].source.timestamp > 2 for j in range(len(window) - 1)):
            continue
        if all(p.source.speed_kt >= threshold_kt for p in window):
            return i
    return None


def _speed_near_seconds(prepared: list[_PreparedPoint], start: int, seconds: float) -> float | None:
    if start >= len(prepared):
        return None
    target = prepared[start].source.timestamp + seconds
    candidates = [
        p
        for p in prepared[start : min(len(prepared), start + int(seconds) + 8)]
        if abs(p.source.timestamp - target) <= 1.25
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: abs(p.source.timestamp - target)).source.speed_kt


def _recovery_metrics(
    prepared: list[_PreparedPoint],
    apex: int,
    end: int,
    entry_speed: float,
    planning_threshold_kt: float,
) -> dict:
    planning_idx = (
        apex
        if prepared[apex].source.speed_kt >= planning_threshold_kt
        else _first_sustained_speed(prepared, apex, planning_threshold_kt)
    )
    target_90 = max(planning_threshold_kt, entry_speed * 0.90)
    ninety_idx = (
        apex
        if prepared[apex].source.speed_kt >= target_90
        else _first_sustained_speed(prepared, apex, target_90)
    )

    def elapsed(idx: int | None, origin: int) -> float | None:
        return None if idx is None else max(0.0, prepared[idx].source.timestamp - prepared[origin].source.timestamp)

    speed5 = _speed_near_seconds(prepared, apex, 5.0)
    speed10 = _speed_near_seconds(prepared, apex, 10.0)
    return {
        "time_to_planing_s": round(elapsed(planning_idx, apex), 1) if planning_idx is not None else None,
        "time_from_turn_end_to_planing_s": round(elapsed(planning_idx, end), 1) if planning_idx is not None else None,
        "distance_to_planing_m": round(_path_length(prepared, apex, planning_idx), 1) if planning_idx is not None else None,
        "time_to_90pct_entry_s": round(elapsed(ninety_idx, apex), 1) if ninety_idx is not None else None,
        "speed_5s_after_kt": round(speed5, 2) if speed5 is not None else None,
        "speed_10s_after_kt": round(speed10, 2) if speed10 is not None else None,
        "planning_recovered": planning_idx is not None,
        "planning_recovery_index": planning_idx,
        "entry90_recovery_index": ninety_idx,
    }


def _wind_course_clusters(
    prepared: list[_PreparedPoint], planning_threshold_kt: float
) -> tuple[float, float, int] | None:
    stable = [
        p
        for p in prepared
        if p.course is not None
        and p.source.speed_kt >= max(6.0, planning_threshold_kt)
        and (p.turn_rate is None or abs(p.turn_rate) <= 4.0)
    ]
    if len(stable) < 30:
        return None

    bins = [0.0] * 36
    for p in stable:
        bins[int((p.course or 0.0) // 10) % 36] += max(1.0, p.source.speed_kt)
    first_bin = max(range(36), key=lambda i: bins[i])
    first_center = first_bin * 10.0 + 5.0
    allowed = [
        i
        for i in range(36)
        if 70.0 <= abs(angular_difference(first_center, i * 10.0 + 5.0)) <= 180.0
    ]
    if not allowed:
        return None
    second_bin = max(allowed, key=lambda i: bins[i])
    second_center = second_bin * 10.0 + 5.0

    group1 = [
        p.course
        for p in stable
        if p.course is not None and abs(angular_difference(first_center, p.course)) <= 35.0
    ]
    group2 = [
        p.course
        for p in stable
        if p.course is not None and abs(angular_difference(second_center, p.course)) <= 35.0
    ]
    if len(group1) < 10 or len(group2) < 10:
        return None
    c1 = circular_mean(group1)
    c2 = circular_mean(group2)
    if c1 is None or c2 is None:
        return None
    separation = abs(angular_difference(c1, c2))
    if separation < 70.0:
        return None
    return c1, c2, len(stable)


def _wind_orientation_score(gybes: list[dict], wind_from: float) -> float:
    score = 0.0
    for g in gybes:
        classification = classify_maneuver(g["entry_course_deg"], g["course_change_deg"], wind_from)
        quality = min(1.0, max(0.0, g["min_speed_kt"] / max(g["entry_speed_kt"], 1.0)))
        if classification["maneuver"] == "gybe":
            score += (quality - 0.22) + 0.08
        else:
            score += 0.42 - quality
    return score


def estimate_wind(prepared: list[_PreparedPoint], gybes: list[dict], planning_threshold_kt: float) -> dict:
    clusters = _wind_course_clusters(prepared, planning_threshold_kt)
    if clusters is None:
        return {"from_deg": None, "to_deg": None, "source": "unknown", "confidence": 0}

    c1, c2, sample_count = clusters
    delta = angular_difference(c1, c2)
    bisector = normalize_degrees(c1 + delta / 2.0)
    candidate_a = bisector
    candidate_b = normalize_degrees(bisector + 180.0)

    score_a = _wind_orientation_score(gybes, candidate_a)
    score_b = _wind_orientation_score(gybes, candidate_b)
    chosen = candidate_a if score_a >= score_b else candidate_b
    score_gap = abs(score_a - score_b)
    separation = abs(delta)

    cluster_quality = max(0.0, 1.0 - abs(separation - 140.0) / 100.0)
    sample_quality = min(1.0, sample_count / 300.0)
    orientation_quality = min(1.0, score_gap / max(2.0, len(gybes) * 0.35)) if gybes else 0.15
    confidence = int(round(100.0 * (0.45 * cluster_quality + 0.30 * sample_quality + 0.25 * orientation_quality)))

    return {
        "from_deg": round(chosen, 1),
        "to_deg": round(normalize_degrees(chosen + 180.0), 1),
        "source": "estimated",
        "confidence": max(10, min(95, confidence)),
        "reach_courses_deg": [round(c1, 1), round(c2, 1)],
        "course_separation_deg": round(separation, 1),
        "stable_samples": sample_count,
    }


def analyze(points: list[TrackPoint], settings: AnalyzerSettings | None = None) -> dict:
    if len(points) < 25:
        raise ValueError("För få GPS-punkter för svänganalys")

    settings = settings or AnalyzerSettings()
    prepared = _prepare_geometry(points)
    n = len(prepared)

    scores = [0.0] * n
    references: dict[int, tuple[float, float, float, float]] = {}
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
        signed_change = _actual_turn_change(prepared, candidate, pre_course, post_course)
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

        recovery = _recovery_metrics(prepared, apex, end, entry_speed, settings.planning_threshold_kt)
        planning_idx = recovery.pop("planning_recovery_index")
        ninety_idx = recovery.pop("entry90_recovery_index")
        recovery_indices = [idx for idx in (planning_idx, ninety_idx) if idx is not None]
        detail_start = max(0, start - 5)
        detail_end = min(n - 1, max([end + 15, *recovery_indices]))
        detail_points: list[dict] = []
        apex_time = prepared[apex].source.timestamp
        for j in range(detail_start, detail_end + 1):
            p = prepared[j]
            if start <= j <= end:
                phase = "turn"
            elif j > end:
                phase = "recovery"
            else:
                phase = "context"
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
                    "phase": phase,
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
                "maneuver": "unknown",
                "turn_mid_course_deg": round(normalize_degrees(pre_course + signed_change / 2.0), 1),
                "entry_course_deg": round(pre_course, 1),
                "exit_course_deg": round(post_course, 1),
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
                **recovery,
                "center": {
                    "lat": round(prepared[candidate].source.lat, 7),
                    "lon": round(prepared[candidate].source.lon, 7),
                    "x": round(prepared[candidate].x, 2),
                    "y": round(prepared[candidate].y, 2),
                },
                "points": detail_points,
            }
        )

    if settings.wind_from_deg is not None:
        wind_from = normalize_degrees(settings.wind_from_deg)
        wind = {
            "from_deg": round(wind_from, 1),
            "to_deg": round(normalize_degrees(wind_from + 180.0), 1),
            "source": "manual",
            "confidence": 100,
        }
    else:
        wind = estimate_wind(prepared, gybes, settings.planning_threshold_kt)
        wind_from = wind.get("from_deg")

    for g in gybes:
        g.update(classify_maneuver(g["entry_course_deg"], g["course_change_deg"], wind_from))

    start_time = points[0].time_utc
    end_time = points[-1].time_utc
    distance_candidates = [p.distance_m for p in points if p.distance_m is not None]
    distance_m = (
        max(distance_candidates) - min(distance_candidates)
        if distance_candidates
        else _path_length(prepared, 0, n - 1)
    )
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
            "detected_gybes": sum(1 for g in gybes if g["maneuver"] == "gybe"),
            "detected_tacks": sum(1 for g in gybes if g["maneuver"] == "tack"),
            "planning_through": sum(1 for g in gybes if g["planning_through"]),
        },
        "settings": {
            "min_course_change_deg": settings.min_course_change_deg,
            "min_entry_speed_kt": settings.min_entry_speed_kt,
            "min_exit_speed_kt": settings.min_exit_speed_kt,
            "planning_threshold_kt": settings.planning_threshold_kt,
            "wind_from_deg": round(wind_from, 1) if wind_from is not None else None,
        },
        "wind": wind,
        "track": track,
        "gybes": gybes,
    }
