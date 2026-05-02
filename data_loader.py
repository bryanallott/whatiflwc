"""Loads JSON data and validates schema."""

import json
from pathlib import Path
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"

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
def load_baseline_leaderboards():
    return json.loads((DATA_DIR / "baseline_leaderboards.json").read_text())

@st.cache_data
def load_points_scheme():
    return json.loads((DATA_DIR / "points_scheme.json").read_text())
