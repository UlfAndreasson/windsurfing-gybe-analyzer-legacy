import math
import unittest

from app.analyzer import AnalyzerSettings, angular_difference, analyze
from app.fitlite import TrackPoint


def synthetic_turn() -> list[TrackPoint]:
    # Straight north, smooth 180 degree clockwise U-turn, straight south.
    points=[]; lat0=57.65; lon0=11.85; t0=1_000_000; x=0.0; y=0.0; heading=0.0; distance=0.0
    for i in range(70):
        if i < 25: heading=0.0
        elif i <= 35: heading=(i-25)*18.0
        else: heading=180.0
        speed_kt = 14.0 if i < 25 or i > 35 else 10.0
        mps=speed_kt/1.9438444924406
        x += math.sin(math.radians(heading))*mps
        y += math.cos(math.radians(heading))*mps
        distance += mps
        lat=lat0 + math.degrees(y/6_371_000.0)
        lon=lon0 + math.degrees(x/(6_371_000.0*math.cos(math.radians(lat0))))
        points.append(TrackPoint(t0+i,lat,lon,speed_kt,distance,120))
    return points


class AnalyzerTests(unittest.TestCase):
    def test_angular_difference_wrap(self):
        self.assertAlmostEqual(angular_difference(350, 10), 20)
        self.assertAlmostEqual(angular_difference(10, 350), -20)

    def test_detects_synthetic_u_turn(self):
        result=analyze(synthetic_turn(), AnalyzerSettings(min_course_change_deg=100,min_entry_speed_kt=4,min_exit_speed_kt=2))
        self.assertGreaterEqual(len(result["gybes"]),1)
        best=max(result["gybes"], key=lambda g: abs(g["course_change_deg"]))
        self.assertGreater(abs(best["course_change_deg"]),140)
        self.assertGreater(best["entry_speed_kt"],10)
        self.assertGreater(best["effective_radius_m"],0)


if __name__ == "__main__":
    unittest.main()
