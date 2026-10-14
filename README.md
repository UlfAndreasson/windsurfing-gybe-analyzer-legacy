# Windsurfing Gybe Analyzer

Local Garmin FIT analyzer for detailed windsurfing gybe/tack analysis on macOS.

## What it does

- imports Garmin `.FIT` files or Garmin Connect export `.ZIP` files
- detects large direction changes from 1 Hz GPS data
- shows entry, minimum and exit speed for every detected turn
- calculates speed retention, course change, duration, turn distance, max turn rate and estimated effective radius
- shows the GPS arc and speed second-by-second for every turn
- colors the GPS arc continuously by speed: blue → green → yellow → red
- supports keyboard navigation through turns and through second-by-second data
- stores source files and analyses locally between app restarts
- can classify `Gipp` vs `Tack` and draw a wind arrow when `Vind från` is supplied

Everything runs locally on the Mac. Uploaded Garmin files are stored under `data/sessions/` and are not sent anywhere.

## Run

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

## Update

```bash
cd ~/_code_local/windsurfing-gybe-analyzer
git pull
./run.sh
```

## Wind direction and Gipp/Tack

GPS alone shows course and turn direction, but it cannot determine which end of the wind axis the wind comes from. There is a 180° ambiguity. Therefore the app only labels a turn as `Gipp` or `Tack` when **Vind från (°T)** is supplied.

Example: if the wind comes from 250° true, enter `250`.

The classification then uses the course at the midpoint of the actual turn:

- midpoint nearest **wind-from** → Tack
- midpoint nearest **wind-to** → Gipp

The wind arrow on the GPS arc is only shown when the wind direction is known. The label states `Vind från xxx°T`; the arrowhead points downwind.

## Keyboard navigation

- click the **Detekterade svängar** table, then use `↑` / `↓` to step through turns
- click a row in the **second-by-second** table, then use `↑` / `↓` to step through the selected turn
- the selected second is highlighted in both the GPS arc and speed graph

## Saved sessions

Every successful analysis is automatically persisted in:

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

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
./run-dev.sh
```

## Current version

v0.4.0
