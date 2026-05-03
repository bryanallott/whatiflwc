"""Loads JSON data and validates schema."""

import json
import math
from pathlib import Path
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"

DIVISIONS = ["Youth Men", "Youth Women", "Open Men", "Open Women"]

@st.cache_data
def load_events():
    return json.loads((DATA_DIR / "events.json").read_text())

@st.cache_data
def load_athletes():
    return json.loads((DATA_DIR / "athletes.json").read_text())

@st.cache_data
def load_baseline_results():
    return json.loads((DATA_DIR / "baseline_results.json").read_text())

@st.cache_data
def load_points_scheme():
    return json.loads((DATA_DIR / "points_scheme.json").read_text())

@st.cache_data
def compute_baseline_leaderboards():
    from simulator import Entry, simulate_event, recompute_country_totals

    baseline = load_baseline_results()
    leaderboards = {}

    for division in DIVISIONS:
        sim_events = {r["event_id"] for r in baseline if r["division"] == division and r["is_simulated"]}
        sim_outputs = {}
        for event_id in sim_events:
            finals, bfinals = [], []
            for r in baseline:
                if r["division"] != division or r["event_id"] != event_id:
                    continue
                t = r["time_sec"] if r["time_sec"] is not None else math.inf
                e = Entry(athlete=r["athlete"], club_code=r["club_code"], time_sec=t,
                          prev_round=r["round"],
                          prev_rank=r["rank"] if isinstance(r["rank"], int) else None)
                (finals if r["round"] == "Final" else bfinals).append(e)
            sim_outputs[event_id] = simulate_event(finals, bfinals, [])

        totals = recompute_country_totals(division, baseline, sim_outputs)

        club_names = {}
        for r in baseline:
            if r["division"] == division:
                club_names[r["club_code"]] = r["club"]

        ranked = sorted(
            [{"club_code": cc, "club": club_names.get(cc, cc), "points": pts}
             for cc, pts in totals.items() if cc in club_names],
            key=lambda x: -x["points"],
        )
        leaderboards[division] = [{"rank": i + 1, **row} for i, row in enumerate(ranked)]

    return leaderboards
