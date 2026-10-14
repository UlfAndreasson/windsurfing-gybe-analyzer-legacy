# Windsurfing Gybe Analyzer

Garmin FIT analyzer for detailed windsurfing gybe/tack analysis.

The repository is the canonical source for the analysis logic. It can be run locally on macOS, while the Lovable app provides the cloud/web UI around the same analysis concepts.

## What it does

- imports Garmin `.FIT` files or Garmin Connect export `.ZIP` files
- detects large direction changes from 1 Hz GPS data
- shows entry, minimum and exit speed for every detected turn
- calculates speed retention, course change, duration, turn distance, max turn rate and estimated effective radius
- shows the GPS arc and speed second-by-second for every turn
- measures recovery after the turn: time/distance back to planing, time to 90% of entry speed and speed at +5/+10 seconds
- estimates wind direction automatically, with optional manual `Vind från` override
- can classify `Gipp` vs `Tack` when wind direction is known
- supports a display-only `Min ingång` filter without re-running detection
- supports keyboard navigation through turns and through second-by-second data
- stores source files and analyses locally between app restarts

## Local app vs cloud app

The commands below are only needed if you want to run or test the **local Mac version**.

You do **not** need to run `git pull` or `./run.sh` to use the published Lovable/web app.

Local update and start:

```bash
cd ~/_code_local/windsurfing-gybe-analyzer
git pull
./run.sh
```

This does two things:

1. `git pull` downloads the latest repository changes to the Mac.
2. `./run.sh` starts the local analyzer at `http://127.0.0.1:8776`.

If you only use the cloud/web app, skip these commands.

## Run locally

```bash
cd ~/_code_local/windsurfing-gybe-analyzer
./run.sh
```

Default URL:

```text
http://127.0.0.1:8776
```

The port can be overridden:

```bash
GYBE_PORT=8780 ./run.sh
```

Everything in the local version runs on the Mac. Uploaded Garmin files are stored under `data/sessions/` and are not sent anywhere.

## Detection threshold vs display filter

These are intentionally separate controls:

- `Ingång minst` affects analysis/detection and therefore requires analysis/re-analysis.
- `Min ingång` only filters already detected turns in the UI; it does not alter the analysis.

The display filter applies consistently to map markers, the turn table and `↑` / `↓` navigation.

## Wind direction and Gipp/Tack

GPS alone shows course and turn direction but has a 180° wind-axis ambiguity. The analyzer can estimate the wind direction automatically from stable planing courses. A manually supplied **Vind från (°T)** overrides that estimate.

Example: if the wind comes from 250° true, enter `250`.

When wind direction is known, the turn midpoint is compared with the wind axis:

- midpoint nearest **wind-from** → Tack
- midpoint nearest **wind-to** → Gipp

The wind arrow on the GPS arc is shown when the wind direction is known. The arrowhead points downwind.

## Keyboard navigation

- click the **Detekterade svängar** table, then use `↑` / `↓` to step through turns
- click a row in the **second-by-second** table, then use `↑` / `↓` to step through the selected turn
- the selected second is highlighted in both the GPS arc and speed graph

## Saved sessions

Every successful local analysis is automatically persisted in:

```text
data/sessions/<file-hash>/
  source.fit | source.zip
  analysis.json
```

The same Garmin source file reuses the same session folder. A new analysis updates `analysis.json` while keeping the original source file. Previous sessions are available from **Tidigare analyser** after restarting the app.

## Direction labels

- `Vänster/BB` = left / babord turn direction
- `Höger/SB` = right / styrbord turn direction

These labels describe the direction of the turn. They are separate from the manoeuvre type `Gipp` / `Tack`.

## Radius

`Effektiv radie` is:

```text
path length through turn / course change in radians
```

With 1 Hz GPS it is an estimate intended primarily for comparing turns with each other, not a survey-grade geometric radius.

## Development

Prefer normal Git/GitHub/GitHub Actions workflows for code, tests, CI and documentation. Lovable should only be used for Lovable-specific runtime, backend/integration and publishing tasks.

Functional changes should update the relevant README/CHANGELOG/docs in the same workstream.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
./run-dev.sh
```

## Current version

v0.5.1
