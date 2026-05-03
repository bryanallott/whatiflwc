"""Streamlit app — start here."""

import math
import streamlit as st
import pandas as pd

from data_loader import (load_events, load_athletes, load_baseline_results,
                         compute_baseline_leaderboards)
from simulator import Entry, simulate_event, recompute_country_totals

st.set_page_config(page_title="Lifesaving What-If Simulator", layout="wide")
st.title("Lifesaving Championship What-If Simulator")

events = load_events()
athletes = load_athletes()
baseline = load_baseline_results()
leaderboards = compute_baseline_leaderboards()

division = st.selectbox("Division", ["Youth Men", "Youth Women", "Open Men", "Open Women"])

# NOTE: athletes.json currently lacks club_code. For v1, we look it up from baseline_results
# (an athlete with the same name in the same division usually has competed somewhere).
# If not found, candidate is rejected with a warning. Alternative: add club_code to athletes.json.
def lookup_club(athlete_name, division):
    for r in baseline:
        if r["division"] == division and r["athlete"] == athlete_name:
            return r["club_code"]
    return None

if "toggled" not in st.session_state:
    st.session_state.toggled = set()

div_athletes = [a for a in athletes if a["division"] == division]
div_events_sim = sorted({(a["event_id"], a["event_name"]) for a in div_athletes})

with st.sidebar:
    st.header("Toggle candidates")
    for event_id, event_name in div_events_sim:
        cands = sorted([a for a in div_athletes if a["event_id"] == event_id],
                       key=lambda a: a["best_time_sec"])
        with st.expander(f"{event_name} ({len(cands)})"):
            for a in cands:
                checked = a["id"] in st.session_state.toggled
                new = st.checkbox(f'{a["athlete"]} — {a["best_time_str"]}',
                                  value=checked, key=f"chk_{a['id']}")
                if new and not checked: st.session_state.toggled.add(a["id"])
                elif not new and checked: st.session_state.toggled.discard(a["id"])
    st.divider()
    replacement_mode = st.checkbox(
        "Replacement mode",
        value=True,
        help="Remove existing athletes from the same country as each toggled candidate before simulating",
    )
    if st.button("Reset all"):
        st.session_state.toggled = set()
        st.rerun()

def real_pools(division, event_id):
    finals, bfinals = [], []
    for r in baseline:
        if r["division"] != division or r["event_id"] != event_id: continue
        t = r["time_sec"] if r["time_sec"] is not None else math.inf
        e = Entry(athlete=r["athlete"], club_code=r["club_code"], time_sec=t,
                  prev_round=r["round"],
                  prev_rank=r["rank"] if isinstance(r["rank"], int) else None)
        (finals if r["round"] == "Final" else bfinals).append(e)
    return finals, bfinals

active = {a["id"]: a for a in div_athletes if a["id"] in st.session_state.toggled}
sim_outputs = {}
for event_id, event_name in div_events_sim:
    finals, bfinals = real_pools(division, event_id)
    cands = []
    for a in active.values():
        if a["event_id"] != event_id: continue
        cc = lookup_club(a["athlete"], division) or "RSA"
        cands.append(Entry(athlete=a["athlete"], club_code=cc,
                            time_sec=a["best_time_sec"], is_candidate=True))
    if replacement_mode and cands:
        cand_clubs = {c.club_code for c in cands}
        finals  = [e for e in finals  if e.club_code not in cand_clubs]
        bfinals = [e for e in bfinals if e.club_code not in cand_clubs]
    sim_outputs[event_id] = simulate_event(finals, bfinals, cands)

sim_totals = recompute_country_totals(division, baseline, sim_outputs)
lb_rows = []
for row in leaderboards[division]:
    cc = row["club_code"]
    base = row["points"]
    sim = sim_totals.get(cc, 0)
    lb_rows.append({"Club": row["club"], "Code": cc, "Baseline": base, "Simulated": sim, "Δ": sim - base})

st.subheader("Country leaderboard")
df = pd.DataFrame(lb_rows).sort_values("Simulated", ascending=False).reset_index(drop=True)
df.insert(0, "Rank", range(1, len(df) + 1))

def _highlight_delta(row):
    delta = row["Δ"]
    if delta > 0:
        color = "background-color: #1a3a2a"
    elif delta < 0:
        color = "background-color: #3a2e00"
    else:
        color = ""
    return [color] * len(row)

styled = df.style.apply(_highlight_delta, axis=1)
st.dataframe(styled, hide_index=True, use_container_width=True)

st.subheader("Event results")
for event_id, event_name in div_events_sim:
    out = sim_outputs[event_id]
    rows = [{"Round": "Final", **r} for r in out["final"]]
    rows += [{"Round": "B Final", **r} for r in out["bfinal"]]
    rdf = pd.DataFrame(rows)
    with st.expander(event_name, expanded=False):
        st.dataframe(rdf, hide_index=True, use_container_width=True)
