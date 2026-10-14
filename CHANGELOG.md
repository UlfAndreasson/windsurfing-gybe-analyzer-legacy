# Changelog

## 0.4.0 - 2026-10-14

- Persist uploaded FIT/ZIP files and analysis JSON under `data/sessions/`.
- Add previous-session picker and re-analysis of saved source files.
- Add optional true wind-from direction.
- Classify turns as Gipp/Tack when wind direction is known.
- Add wind arrow to the detailed GPS arc.
- Rename turn direction to Vänster/BB and Höger/SB.
- Add keyboard navigation between turns with ↑/↓.
- Add keyboard navigation through second-by-second turn points with ↑/↓.
- Highlight selected second in GPS arc and speed graph.
- Color detailed GPS arc continuously by speed: blue → green → yellow → red.
- Improve near-180° turn direction using measured turn-rate sign.
- Keep local default port at 8776.

## 0.3.1 - 2026-10-14

- Change default local port from 8765 to 8776 to avoid collision with Portfolio Local.
- Allow overriding the port with `GYBE_PORT`.
- Suppress pip version-check notice in `run.sh`.

## 0.3.0 - 2026-10-13

- Initial local Garmin FIT/ZIP analyzer.
- Track rendering, turn detection and turn table.
- Per-turn entry/min/exit speed, retention, course change, time and estimated radius.
- Second-by-second speed and GPS arc detail.
