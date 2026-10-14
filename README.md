# Windsurfing Gybe Analyzer — v0.53

Garmin FIT analyzer for detailed windsurfing gybe/tack analysis.

## Primary runtime: cloud app

The hosted app is the primary way to use Gybe Analyzer: sign in, upload Garmin `.FIT`/`.ZIP` files and keep saved sessions in the cloud.

Live app: `https://windsurfing-gybe-analyzer.lovable.app`

The Python/FastAPI implementation in this repository remains the reference for Garmin parsing and raw turn detection and can still be run locally on macOS as a fallback. Cloud-only presentation logic may derive additional information from the saved full track without mutating the canonical turn results.

### Authentication

The cloud app uses email/password authentication. Email auto-confirm is currently enabled because the shared/default auth sender did not reliably deliver confirmation messages. New accounts can therefore sign in immediately after signup. If a custom SMTP sender is added later, email confirmation can be enabled again.

## v0.53 cloud features

- imports Garmin `.FIT` files or Garmin Connect export `.ZIP` files
- saves private sessions per user and lets you select/re-analyze earlier sessions
- detects large course changes from 1 Hz GPS data
- shows entry, minimum and exit speed, retention, course change, turn distance, max turn rate and estimated effective radius
- shows the selected maneuver second-by-second with speed-coloured `Svängspår` and speed graph
- supports `Vänster/BB` and `Höger/SB` direction labels
- supports ↑/↓ navigation between turns and through second-by-second data
- has a display-only `Min ingång` filter that does not re-run detection; when no detected turn matches, the hint is shown inline on the slider row
- estimates wind direction from stable planing courses when no manual wind is supplied
- shows wind source/confidence and a wind arrow that points downwind
- flags conservative `Misstänkt bad/fall` cases without asserting them as fact
- flags `Stallad/långsam vändning` separately when a planing entry nearly stops but sustained planing returns within 20 seconds
- shows the rich `Detekterade svängar` table as one data row per maneuver, with compact two-line header labels and a narrow status-icon column
- keeps the compact synchronized `Svänglista` balanced across `#`, status, Typ, Riktning, Till planing and Radie*
- offers System, Ljust, Mörkt and `Custom mörkt`; the existing stored value `lovable-dark` is kept for backward compatibility

### v0.53 UI refinements

- slightly larger session metadata while retaining responsive wrapping
- `Vänd vind 180°` lives inside `Analysinställningar`
- the visible `Sparad i molnet` badge is removed; cloud saving behavior is unchanged
- `Svängens GPS-ark` is renamed to **Svängspår**
- `Svängspår` initially frames the actual maneuver/min-speed area instead of letting a long recovery tail flatten the turn visually
- `+`, `−`, mouse-wheel/trackpad zoom and panning are supported; `Återställ` returns to the full displayed maneuver path
- zoom is view-only and does not mutate source data, turn detection, speed colours, wind overlay or second-by-second keyboard navigation
- cloud regression suite: 57/57 tests passing; saved-session browser checks passed at 1440 and 1280 px without page-level horizontal overflow

## Recovery after the maneuver

The cloud UI no longer stops the recovery view at 30 seconds.

For each detected turn it derives recovery from the saved full session track, bounded by the **next detected maneuver or the end of the session**:

- sustained planing = 3 consecutive samples at/above the planing threshold, with no gap greater than 2 s
- time and distance back to planing
- time from turn end to planing
- time to 90% of entry speed
- speed at +5 s and +10 s

If both planing and 90% entry speed are reached, the detailed Svängspår, speed graph and second-by-second table continue for at least 10 seconds after the later marker, without passing the next maneuver/session boundary. If either target is not reached, the detail continues all the way to that boundary.

The status therefore says `Ja · X s`, `Ej före nästa sväng` or `Ej före passets slut` instead of the old `Ej inom 30 s`.

Existing saved analyses can use this derived recovery view from their saved full track without re-running turn detection. Entry/min/exit and raw turn detection are not silently redefined.

### Slow/stalled maneuver vs bad/fall

These are display-only coaching heuristics and do not change canonical turn detection:

- `Misstänkt bad/fall` remains the conservative warning for a long very-slow/no-recovery case.
- `Stallad/långsam vändning` requires entry at/above the planing threshold, at least 2 consecutive samples ≤4.0 kt around the turn (no gap >2 s), at least one sample ≤3.0 kt, and sustained planing recovery within 20 s of the min-speed/apex.
- `Misstänkt bad/fall` takes precedence; a maneuver is never labelled as both.

## Sessionsspår and map

The cloud app shows the full FIT track on a geographic map using Leaflet and OpenStreetMap tiles:

- activity bounds fitted automatically
- speed-coloured track
- clickable maneuver markers
- selected maneuver highlighted
- wind-direction overlay
- SVG track fallback if Leaflet/map tiles fail

### Map privacy

The FIT/ZIP file and full track are not uploaded to the map provider; the track is drawn locally in the browser. Loading map tiles makes normal tile requests to OpenStreetMap's tile servers, which reveal the approximate viewed area through tile coordinates/zoom and the viewer's IP address, as with a normal web map.

## Wind direction and Gipp/Tack

GPS course data identifies the wind **axis** well but cannot always resolve which end of that axis is wind-from versus wind-to. That is an inherent 180° ambiguity.

The cloud display therefore classifies a maneuver using course samples through the actual turn rather than only the midpoint:

- ignore noisy COG samples below roughly 3 kt
- closest passage to **wind-from** → Tack / head-to-wind
- closest passage to **wind-to** → Gipp / downwind
- confidence combines wind confidence, closest-passage error and how clearly one axis end is closer
- uncertain results are shown as `Gipp?`, `Tack?` or `Okänd`

For non-strong automatic estimates the opposite axis direction is also shown, e.g. `Vind ≈72°T (alt 252°T)`.

`Vänd vind 180°` applies the opposite direction as a manual override and re-runs the active session so all Gipp/Tack labels can be corrected together. Clearing the manual wind field returns to automatic estimation.

## External wind-data enrichment

FIT data contains latitude/longitude and the activity timestamp, so a future supported external wind lookup must work from the **session location + session time**, worldwide.

Preferred future source order:

1. nearest suitable real wind station/anemometer covering the activity time
2. nearest suitable forecast spot covering the activity time
3. GPS-derived estimate
4. manual `Vind från` remains the final override

For Fiskebäck, Windguru spot `1110010` and the GWC station are relevant examples, but nothing in the application logic should assume Fiskebäck.

No automatic Windguru lookup is currently implemented because a stable credential-free discovery + historical-data API for arbitrary nearby stations/spots has not been verified. Current forecast data must never be silently applied to an old session.

## Local Mac fallback

You do **not** need these commands to use the cloud app. Use them only if you want or need to run the local fallback:

```bash
cd ~/_code_local/windsurfing-gybe-analyzer
git pull
./run.sh
```

The local app starts at:

```text
http://127.0.0.1:8776
```

Override the port if needed:

```bash
GYBE_PORT=8780 ./run.sh
```

Local uploads are stored under `data/sessions/` and remain on the Mac.

## Radius

`Effektiv radie` is:

```text
path length through turn / course change in radians
```

With 1 Hz GPS it is an estimate intended primarily for comparing turns with each other, not a survey-grade geometric radius.

## Development

Prefer Git/GitHub/GitHub Actions for code, tests, CI and documentation. Use Lovable only for cloud-runtime/backend/integration/publishing work that needs it. Functional changes should update README/CHANGELOG/docs in the same workstream.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
./run-dev.sh
```
