# Windsurfing Gybe Analyzer

Local Garmin FIT analyzer for detailed windsurfing turn / gybe analysis.

## Current status — v0.3.1

Implemented:

- Garmin `.FIT` and Garmin export `.ZIP` import.
- Built-in FIT decoder for the activity fields needed by this project; no cloud upload.
- 1 Hz GPS track and Garmin enhanced speed extraction.
- Automatic detection of large tack changes / gybe candidates.
- Per-turn metrics:
  - entry, minimum and exit speed
  - exit and minimum speed retention
  - duration
  - signed course change
  - maximum estimated turn rate
  - distance through the turn
  - effective turn radius
  - simple planing-through heuristic
  - detection confidence
- Session track with numbered turn markers.
- Detailed GPS arc and second-by-second speed view.
- Local-only browser UI.

The current detector deliberately calls detections **turn candidates** internally. Wind direction is not yet inferred, so a large course reversal cannot yet be reliably labelled gybe vs tack. That is planned for v0.5.

## Run on macOS

```bash
git clone https://github.com/UlfAndreasson/windsurfing-gybe-analyzer.git
cd windsurfing-gybe-analyzer
./run.sh
```

`run.sh` creates `.venv`, installs the small Python dependency set and opens:

```text
http://127.0.0.1:8776
```

Then drag a Garmin `.FIT` file or Garmin Connect export `.ZIP` into the page.

Default port is `8776` so it does not collide with Portfolio Local on `8765`. Override it when needed:

```bash
GYBE_PORT=8780 ./run.sh
```

### Development

After the first `./run.sh` setup:

```bash
./run-dev.sh
```

Run tests:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Detection approach

The v0.3 detector is intentionally transparent and tunable:

1. Convert GPS coordinates to local XY metres.
2. Apply a small three-point position smoother.
3. Estimate course over ground from a centred four-second baseline.
4. Compare stable approach and exit course windows around every point.
5. Keep course reversals above the configured threshold.
6. De-duplicate overlapping candidates.
7. Estimate practical turn start/end at roughly 10% / 90% of the course transition.
8. Calculate speed retention and geometry from the original 1 Hz records.

Defaults:

- minimum course change: `105°`
- minimum approach speed: `4 kt`
- minimum exit speed: `1.5 kt`
- planing heuristic: minimum speed `>= 8 kt`

All four are exposed in the UI so they can be calibrated against real sessions.

## Radius caveat

Garmin EPIX Gen 2 activity GPS is normally recorded at 1 Hz. At 20 kt the board travels roughly 10 m per sample, so a highly precise instantaneous radius is not supported by the source data.

The app therefore reports **effective radius**:

```text
turn path length / course change in radians
```

It is useful for comparing gybes, but should not be interpreted as centimetre-accurate geometry.

## Roadmap

### v0.4

- Compare selected gybes, aligned around minimum speed / apex.
- Ranking: best / worst by exit retention, minimum retention and radius.
- Manual include/exclude for false detections.
- Persist analysis metadata locally without modifying the original FIT.

### v0.5

- Infer the two dominant sailing headings and wind axis.
- Classify gybe vs tack and port → starboard / starboard → port.
- Manual wind-direction override.

### v0.6

- Multi-session history and training trends.
- Optional map tiles behind the local XY/GPS track.
- Export gybe table to CSV / JSON.

## Privacy

Activity files are processed by the local FastAPI process on `127.0.0.1`. The application does not upload Garmin activity data to a backend service.
