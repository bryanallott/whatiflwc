"""Tests against validated Excel reference. Run: pytest tests/"""

import json, math
from pathlib import Path
from simulator import Entry, simulate_event, recompute_country_totals

DATA = Path(__file__).parent.parent / "data"

def load_baseline():
    return json.loads((DATA / "baseline_results.json").read_text())

def real_pools(division, event_id, baseline):
    finals, bfinals = [], []
    for r in baseline:
        if r["division"] != division or r["event_id"] != event_id: continue
        t = r["time_sec"] if r["time_sec"] is not None else math.inf
        e = Entry(athlete=r["athlete"], club_code=r["club_code"],
                  time_sec=t, is_candidate=False,
                  prev_round=r["round"],
                  prev_rank=r["rank"] if isinstance(r["rank"], int) else None)
        if r["round"] == "Final": finals.append(e)
        elif r["round"] == "B Final": bfinals.append(e)
    return finals, bfinals

def _compute_totals(division, baseline):
    events_in_div = {r["event_id"] for r in baseline if r["division"] == division and r["is_simulated"]}
    sim_outputs = {}
    for ev in events_in_div:
        f, b = real_pools(division, ev, baseline)
        sim_outputs[ev] = simulate_event(f, b, [])
    return recompute_country_totals(division, baseline, sim_outputs)

def test_identity_no_candidates_matches_baseline():
    """With nothing toggled, running the simulator twice gives identical totals (Δ=0 for all clubs)."""
    baseline = load_baseline()
    for division in ["Youth Men", "Youth Women", "Open Men", "Open Women"]:
        first  = _compute_totals(division, baseline)
        second = _compute_totals(division, baseline)
        assert first == second, f"{division}: non-deterministic output"
        all_clubs = {r["club_code"] for r in baseline if r["division"] == division}
        for cc in all_clubs:
            assert first.get(cc, 0) == second.get(cc, 0), f"{division}/{cc}: delta is non-zero"

def test_youth_men_50m_pincente_displaces_staszkiewicz():
    """Toggle Pincente into Youth Men 50m Manikin Carry -> Final rank 4."""
    baseline = load_baseline()
    finals, bfinals = real_pools("Youth Men", "50m_manikin_carry", baseline)
    candidate = Entry(athlete="Matthew Pincente", club_code="RSA",
                      time_sec=30.63, is_candidate=True)
    out = simulate_event(finals, bfinals, [candidate])
    assert out["final"][3]["athlete"] == "Matthew Pincente"
    assert out["final"][3]["rank"] == 4
    # Staszkiewicz (31.68s) is displaced from Final but ranks behind Halasz (31.28s) in B Final
    assert out["bfinal"][0]["athlete"] == "Michal Halasz"
    assert out["bfinal"][0]["rank"] == 9
    assert out["bfinal"][1]["athlete"] == "Tobiasz Staszkiewicz"
    assert out["bfinal"][1]["rank"] == 10
