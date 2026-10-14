# Changelog

## 0.5.1 - 2026-10-14

- Add display-only `Min ingång` slider for filtering detected turns by entry speed.
- Keep the filter separate from the analyzer's `Ingång minst` detection threshold: moving the slider never re-runs analysis.
- Apply the filter consistently to map markers, turn table and ↑/↓ turn navigation.
- Automatically move selection to the first visible turn when the current turn is filtered out.
- Show a clear empty state when no detected turns match the display filter.

## 0.5.0 - 2026-10-14

- Add post-turn recovery analysis: time/distance back to sustained planing, time to 90% of entry speed and speed at +5/+10 seconds.
- Extend detailed per-second data through the recovery phase.
- Estimate wind direction automatically from dominant stable planing course clusters when no manual wind direction is supplied.
- Use turn quality to help resolve the 180° wind-axis ambiguity and expose estimate confidence.
- Keep manual wind direction as an override for Gipp/Tack classification and wind-arrow display.

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
