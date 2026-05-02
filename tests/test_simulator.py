"""Tests against validated Excel reference. Run: pytest tests/"""

import json, math
from pathlib import Path
from simulator import Entry, simulate_event, recompute_country_totals

DATA = Path(__file__).parent.parent / "data"

def load_baseline():
    return json.loads((DATA / "baseline_results.json").read_text())

def load_leaderboards():
    return json.loads((DATA / "baseline_leaderboards.json").read_text())

def real_pools(division, event_id, baseline):
    finals, bfinals = [], []
    for r in baseline:
        if r["division"] != division or r["event_id"] != event_id: continue
        t = r["time_sec"] if r["time_sec"] is not None else math.inf
        e = Entry(athlete=r["athlete"], country_code=r["country_code"],
                  time_sec=t, is_candidate=False,
                  prev_round=r["round"],
                  prev_rank=r["rank"] if isinstance(r["rank"], int) else None)
        if r["round"] == "Final": finals.append(e)
        elif r["round"] == "B Final": bfinals.append(e)
    return finals, bfinals

def test_identity_no_candidates_matches_baseline():
    """With nothing toggled, simulated leaderboard == baseline leaderboard for every division."""
    baseline = load_baseline()
    leaderboards = load_leaderboards()
    for division, lb in leaderboards.items():
        sim_outputs = {}
        events_in_div = {r["event_id"] for r in baseline if r["division"] == division and r["is_simulated"]}
        for ev in events_in_div:
            f, b = real_pools(division, ev, baseline)
            sim_outputs[ev] = simulate_event(f, b, [])
        sim_totals = recompute_country_totals(division, baseline, sim_outputs)
        baseline_totals = {row["country_code"]: row["points"] for row in lb}
        for cc, base_pts in baseline_totals.items():
            assert sim_totals.get(cc, 0) == base_pts, (
                f"{division}/{cc}: baseline {base_pts}, sim {sim_totals.get(cc, 0)}")

def test_youth_men_50m_pincente_displaces_staszkiewicz():
    """Toggle Pincente into Youth Men 50m Manikin Carry -> Final rank 4."""
    baseline = load_baseline()
    finals, bfinals = real_pools("Youth Men", "50m_manikin_carry", baseline)
    candidate = Entry(athlete="Matthew Pincente", country_code="RSA",
                      time_sec=30.63, is_candidate=True)
    out = simulate_event(finals, bfinals, [candidate])
    assert out["final"][3]["athlete"] == "Matthew Pincente"
    assert out["final"][3]["rank"] == 4
    assert out["bfinal"][0]["athlete"] == "Tobiasz Staszkiewicz"
    assert out["bfinal"][0]["rank"] == 9
