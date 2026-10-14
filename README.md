# Windsurfing Gybe Analyzer

Garmin FIT analyzer for detailed windsurfing gybe/tack analysis.

## Primary runtime: Lovable cloud app

The **Lovable-hosted web app is the primary way to use Gybe Analyzer**: sign in, upload Garmin `.FIT`/`.ZIP` files and keep saved sessions in the cloud.

The Python/FastAPI implementation in this repository remains the canonical reference for the analysis logic and can still be run locally on macOS as a fallback, for testing, or if the cloud app is unavailable.

The normal development workflow is Git/GitHub/GitHub Actions first. Lovable should be used only for Lovable-specific runtime, authentication/backend integration and publishing tasks.

### Authentication

The cloud app uses email/password authentication. Email auto-confirm is currently enabled because the shared/default auth mail sender did not reliably deliver confirmation messages. New accounts can therefore sign in immediately after signup without waiting for a confirmation email. If a custom SMTP sender is added later, email confirmation can be enabled again.

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
- stores source files and analyses locally between app restarts in the local fallback version

## Local Mac fallback

You do **not** need these commands to use the cloud/Lovable app.

Use them only if you want or need to run the analyzer locally:

```bash
cd ~/_code_local/windsurfing-gybe-analyzer
git pull
./run.sh
```

- `git pull` downloads the latest repository changes to the Mac.
- `./run.sh` starts the local analyzer at `http://127.0.0.1:8776`.

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

### External wind-data enrichment

A planned enhancement is to use external spot/station wind data as an additional input to the automatic estimate. For Fiskebäck the relevant Windguru resources are spot `1110010` and the GWC live station. External data should be treated as a **supporting prior**, not as a replacement for the GPS-derived estimate: compare the external wind direction with the two possible GPS wind-axis directions, choose the compatible side of the 180° ambiguity, and show the source/confidence in the UI. Manual `Vind från` must remain the final override.

For historical sessions, only use Windguru data when a matching historical observation/forecast is actually available for the activity timestamp; current forecast data must never be silently applied to an old session.

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

The same Garmin source file reuses the same session folder. A new analysis updates `analysis.json` while keeping the original source file. Previous sessions are available from **Tidigare analyser** after restarting the local app.

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
