# Changelog

## v0.53 - 2026-10-14

- Increase session metadata readability and keep responsive wrapping.
- Move `Vänd vind 180°` into `Analysinställningar` and remove the visible `Sparad i molnet` badge without changing cloud-save behavior.
- Keep the rich `Detekterade svängar` table at one maneuver per row while narrowing the status icon column and distributing remaining columns more evenly.
- Balance the compact `Svänglista` column widths and padding while preserving synchronized selection, keyboard navigation and status markers.
- Rename the maneuver-path view from `Svängens GPS-ark` to `Svängspår`.
- Add maneuver-focused initial framing plus `+`, `−`, wheel/trackpad zoom, pan and `Återställ` for `Svängspår`; zoom is display-only and preserves speed colours, wind overlay and second navigation.
- Verify 57/57 cloud regression tests and saved-session browser checks at 1440 and 1280 px without page-level horizontal overflow.

## v0.52 - 2026-10-14

- Bump the cloud app and README to `v0.52` so each published build has a distinct visible version.
- Restore the rich `Detekterade svängar` table to one body row per maneuver with all 18 values; only header labels wrap onto two lines for compactness.
- Keep the compact synchronized `Svänglista` and selected-turn detail layout unchanged.
- Move the zero-match `Min ingång` hint onto the same row as the slider and `0 / N svängar` count instead of showing it as a separate block below.
- Add a separate view-only `Stallad/långsam vändning` coaching flag: planing entry, at least two consecutive samples ≤4 kt with at least one ≤3 kt, followed by sustained planing recovery within 20 s. `Misstänkt bad/fall` takes precedence.
- Preserve the warning triangle for suspected bad/fall and use a separate amber `S` marker for stalled/slow turns.

## v0.51 - 2026-10-14

- Add display-only `Min ingång` slider for filtering detected turns by entry speed without re-running analysis.
- Extend cloud recovery detail beyond 30 seconds using the saved full session track, bounded by the next maneuver or session end.
- Show truthful recovery status: exact planing time, `Ej före nästa sväng` or `Ej före passets slut`.
- Add time from turn end to planing and preserve detail through the recovery/failed-recovery period.
- Make maneuver metric cards more compact and enlarge the selected-session miniature.
- Add wind arrows to the session miniature and full session view.
- Add a geographic Leaflet/OpenStreetMap session map with speed-coloured track, clickable maneuver markers and SVG fallback.
- Improve cloud Gipp/Tack display classification using course samples through the turn instead of midpoint alone; ignore very-low-speed noisy COG.
- Show uncertain classifications as `Gipp?`, `Tack?` or `Okänd` with classification confidence.
- Show the alternative 180° wind direction for non-strong GPS estimates and add `Vänd vind 180°` to re-run the active session with the opposite manual wind direction.
- Add conservative `Misstänkt bad/fall` display flag.
- Rename visible `Lovable mörkt` theme to `Custom mörkt` while preserving the stored `lovable-dark` preference.
- Set visible cloud version to `v0.51` and standardize README heading.
- Keep map privacy explicit: FIT/ZIP and full track are not sent to the tile provider; normal OpenStreetMap tile requests reveal the viewed area/IP as with a normal web map.
- Cloud regression suite: 38 tests passing after the recovery-boundary correction.

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
