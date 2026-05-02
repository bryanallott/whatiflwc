# Lifesaving Championship What-If Simulator

## Project goal

An interactive web app that lets users toggle ""candidate"" athletes (who didn't compete in the real championship Final/B-Final) into individual swimming events and see:
1. How they would have placed (which round, which rank, what time)
2. Who they displaced from the Final/B-Final
3. How the country medal-table standings change

The simulator currently exists as an Excel spreadsheet (""What-If Simulator"" tab in the source workbook) for the Youth Men division only. We're rebuilding it as a Python web app to (a) cover all four divisions cleanly, (b) make it shareable via URL, and (c) allow richer interaction than spreadsheet checkboxes.

## Tech stack

- **Frontend + backend:** Streamlit (single-file Python app, fastest path to working prototype)
- **Data:** Static JSON files in `data/` directory (no database needed)
- **Charts:** Plotly (interactive bar/dot charts, comes with Streamlit)
- **Deploy:** Streamlit Community Cloud (free) or Hugging Face Spaces

If Streamlit's UX is too limiting, the next step up is **Dash** (also Plotly-based) or **FastAPI + Vue/React**. Don't start there — Streamlit is faster to iterate on.

## Domain background

**Lifesaving sport** is competitive aquatic rescue — events combine swimming with manikin tows, fins, and obstacles. The IRB World Lifesaving Championships are held annually with four divisions: Youth Men, Youth Women, Open Men, Open Women.

**Event format:** Each individual event runs Heats → B Final (places 9–16) → Final (places 1–8). Only Final and B-Final results score points.

**Points scheme:**
- Final: 1st = 20 pts, 2nd = 19 pts ... 8th = 13 pts
- B Final: 1st = 8 pts, 2nd = 7 pts ... 8th = 1 pt
- DSQ / DNS / DNF / ""-"" = 0 pts
- Country total = sum of points across all athletes from that country, across all events

**The ""what-if"" question:** Some federations send strong athletes who don't qualify for the Final or B-Final because their event was over-subscribed in heats. We have those athletes' personal best times. If we slot their best time into the result list, where would they have placed, and how does it change the medal table?

## Simulation rules: ""Lock Final"" hierarchy model

This is the model the user picked. Implement exactly this — don't deviate.

For each individual swimming event:
1. Take the **8 real Final times** + any **toggled candidate times**.
2. Sort that combined pool by time ascending.
3. **Top 8 → new Final** (ranks 1–8, points 20–13).
4. The 9th-fastest from that pool falls down. Combine with the **8 real B-Final times**.
5. Sort that combined pool by time ascending. **Top 8 → new B Final** (ranks 9–16, points 8–1).
6. Anyone outside the top 16 is unranked, scores 0.

DSQ/DNS/DNF athletes from the real Final/B-Final: treat them as having time = infinity so they fall to the bottom of their pool.

Events that are **not simulated** (line throw, relays): the candidate-toggle UI doesn't show them. Their points carry through unchanged from `baseline_results.json`.

## Data files

All in `data/`:

### `events.json` — event catalog
Schema: array of objects with fields `division`, `event_id`, `name`, `simulated` (bool).

### `athletes.json` — candidate pool (athletes with best times, eligible for toggling)
Schema: array of objects with fields `id`, `division`, `event_id`, `event_name`, `athlete`, `best_time_str`, `best_time_sec`.

### `baseline_results.json` — actual championship Final/B-Final results
Schema: array of objects with fields `division`, `event_id`, `event_name`, `is_simulated`, `round` (""Final""/""B Final""), `rank` (1-8 or ""DSQ""/""DNS""/""DNF""), `points`, `athlete`, `country`, `country_code`, `time_sec` (null if DSQ), `time_str`, `status`.

### `baseline_leaderboards.json` — country totals as actually scored
Schema: object keyed by division name, value is array of `{rank, country_code, country, points}`.

### `points_scheme.json` — scoring constants
Object with `Final` and `B Final` maps from rank-string to points.

## Counts

- 4 divisions: Youth Men, Youth Women, Open Men, Open Women
- 37 distinct (division, event) pairs total
- 575 baseline result rows
- 341 candidate athlete-event entries
- 83 unique countries across the four leaderboards

Note: Open Men and Open Women have only partial candidate data (~few events each) — fewer projections than Youth divisions. This is fine; the sim still works, there are just fewer toggles available.

## App design

### Layout (Streamlit single-page)

- Top: title + division selector (Youth Men / Youth Women / Open Men / Open Women)
- Left sidebar: candidate toggles grouped by event, sorted by best time. ""Reset all"" button.
- Main panel: country leaderboard table (Country | Baseline | Simulated | Δ) with delta bar chart, then per-event result tables (Final 1-8 + B Final 9-16) with ★ marker on toggled-in athletes.

### Key behaviors

- **Default state:** No toggles active → everything matches baseline (deltas all 0).
- **Toggle a candidate:** Recompute that event's Final + B Final, recompute country totals, update leaderboard ranks.
- **Multi-toggle:** All active toggles apply simultaneously. Multiple candidates competing for the same event slot battle each other on time.
- **Persistence:** Toggle state lives in `st.session_state`. URL query params (`?toggled=id1,id2,id3`) for shareable scenarios — bonus, not required for v1.
- **""Select all RSA team"" preset:** Optional QoL — buttons that toggle on every candidate from a chosen country.

### File layout

```
lifesaving-simulator/
├── app.py                    # Streamlit entry point
├── simulator.py              # Pure simulation logic (no UI deps)
├── data_loader.py            # Loads + validates JSONs, caches with @st.cache_data
├── data/                     # all 5 JSON files
├── tests/test_simulator.py   # pytest — see required tests below
├── requirements.txt
└── README.md
```

## Required tests (write these FIRST, before the UI)

1. **Identity test:** With zero candidates toggled, simulated leaderboard equals baseline leaderboard for every division. Every country: Δ = 0. **This is the most important test — if it fails, the model is wrong.**
2. **Single insertion (Youth Men, 50m Manikin Carry):** Toggle Matthew Pincente (best 30.63s). He places at Final rank 4. Tobiasz Staszkiewicz (real Final rank 8 at 31.68s) is displaced to B-Final rank 9. The slowest real B-finalist falls out (no points). RSA gains +16, POL loses 7, the displaced B-finalist's country loses 1.
3. **Multi-insertion same event:** Toggling 3 candidates into one event causes correct cascading displacement.
4. **Cross-event independence:** Toggling someone in 50m Manikin doesn't affect 100m Medley results.
5. **Non-simulated events untouched:** Line Throw and relay points stay constant in the leaderboard regardless of toggle state.
6. **DSQ/DNS handling:** A real finalist with status ""DSQ"" shouldn't block a candidate (treat their time as infinity).

These cases come from validated behavior in the source Excel spreadsheet — match it exactly.

## Build sequence

1. `data_loader.py` + load all 5 JSONs, validate counts match the spec.
2. `simulator.py` + the 6 tests in `tests/test_simulator.py`. Get all tests green before touching UI.
3. `app.py` v1: division dropdown, sidebar with toggle checkboxes, main panel with leaderboard + per-event results.
4. v2: Plotly charts (Δ-bar chart for leaderboard).
5. v3: URL query param sharing, country presets, CSV export.

## Things to ask the user before building

- For Open Men / Open Women, only some events have candidate data. Should the UI hide events with no candidates, or show them dimmed? (Default: show, dimmed.)
- Should the user be able to **add** new candidates (athletes not in the JSON) via a manual-entry form? (Probably v3.)
- Country code mapping for candidates: athletes.json doesn't currently include country_code. Either (a) add a `country_code` field to athletes.json by cross-referencing a country lookup, or (b) require the user to pick which country a candidate represents. Recommend (a) — extract country from athlete's federation registry.
