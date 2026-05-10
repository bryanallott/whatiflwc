"""Loads JSON data and validates schema."""

import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"

DIVISIONS = ["Youth Men", "Youth Women", "Open Men", "Open Women"]

_AGE_TO_DIVISION = {
    "Youth Female": "Youth Women",
    "Youth Male":   "Youth Men",
    "Open Female":  "Open Women",
    "Open Male":    "Open Men",
}

def _event_name_to_id(csv_event, division):
    normalized = csv_event.lower().replace(' ', '_')
    aliases = {
        ("Youth Men",  "100m_manikin_tow_with_fins"): "100m_manikin_tow",
        ("Youth Women","100m_manikin_tow_with_fins"): "100m_manikin_tow",
        ("Open Men",   "100m_manikin_tow_with_fins"): "100m_manikin_tow",
    }
    return aliases.get((division, normalized), normalized)

def _excel_serial_to_date(serial):
    try:
        return (datetime(1899, 12, 30) + timedelta(days=int(float(serial)))).strftime('%d %b %Y').lstrip('0')
    except (ValueError, TypeError):
        return ""

def _ms_to_str(ms):
    ms = int(ms)
    return f"{ms // 60000:02d}:{(ms % 60000) // 1000:02d}.{ms % 1000:03d}"

@st.cache_data
def load_events():
    return json.loads((DATA_DIR / "events.json").read_text())

@st.cache_data
def load_athletes():
    events = load_events()
    simulated_ids = {(e["division"], e["event_id"]) for e in events if e["simulated"]}
    event_names   = {(e["division"], e["event_id"]): e["name"] for e in events}

    buckets = {}
    with (DATA_DIR / "rankings-source.csv").open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            division = _AGE_TO_DIVISION.get(row["Age"])
            if division is None:
                continue
            event_id = _event_name_to_id(row["Event"], division)
            if (division, event_id) not in simulated_ids:
                continue
            buckets.setdefault((division, event_id), []).append({
                "athlete":      row["Athlete"].strip(),
                "time_ms":      int(row["Time(ms)"]),
                "date_serial":  row["Date"],
            })

    result = []
    for (division, event_id), entries in buckets.items():
        entries.sort(key=lambda x: x["time_ms"])
        seen = {}
        deduped = []
        for e in entries:
            name = e["athlete"]
            if name not in seen:
                seen[name] = True
                deduped.append(e)
        for entry in deduped[:15]:
            athlete  = entry["athlete"]
            time_ms  = entry["time_ms"]
            result.append({
                "id":             f"{division.replace(' ', '_')}::{event_id}::{athlete.replace(' ', '_')}",
                "division":       division,
                "event_id":       event_id,
                "event_name":     event_names[(division, event_id)],
                "athlete":        athlete,
                "best_time_str":  _ms_to_str(time_ms),
                "best_time_sec":  round(time_ms / 1000, 3),
                "best_time_date": _excel_serial_to_date(entry["date_serial"]),
                "club_code":      "RSA",
            })
    return result

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
