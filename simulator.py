"""Pure simulation logic — no UI dependencies."""

from __future__ import annotations
from dataclasses import dataclass
import math

POINTS_FINAL  = {1: 20, 2: 19, 3: 18, 4: 17, 5: 16, 6: 15, 7: 14, 8: 13}
POINTS_BFINAL = {1: 8,  2: 7,  3: 6,  4: 5,  5: 4,  6: 3,  7: 2,  8: 1}

@dataclass
class Entry:
    athlete: str
    country_code: str
    time_sec: float       # math.inf for DSQ/DNS/DNF
    is_candidate: bool = False
    prev_round: str | None = None     # "Final" | "B Final" | None
    prev_rank: int | None = None

def _sort_key(e):
    return e.time_sec if e.time_sec is not None else math.inf

def simulate_event(real_finalists, real_bfinalists, candidates):
    """Lock-Final hierarchy: candidates compete for Final spots first.
    Displaced finalists drop into the B-Final pool. Slowest B-finalists fall out.
    """
    final_pool = sorted([*real_finalists, *candidates], key=_sort_key)
    new_final = final_pool[:8]
    pushed_down = final_pool[8:]

    bfinal_pool = sorted([*pushed_down, *real_bfinalists], key=_sort_key)
    new_bfinal = bfinal_pool[:8]
    fell_out = bfinal_pool[8:]

    final_out = []
    for i, e in enumerate(new_final, start=1):
        pts = 0 if math.isinf(e.time_sec) else POINTS_FINAL.get(i, 0)
        final_out.append({
            "rank": i, "athlete": e.athlete, "country_code": e.country_code,
            "time_sec": e.time_sec, "points": pts,
            "is_candidate": e.is_candidate,
        })
    bfinal_out = []
    for i, e in enumerate(new_bfinal, start=1):
        pts = 0 if math.isinf(e.time_sec) else POINTS_BFINAL.get(i, 0)
        bfinal_out.append({
            "rank": 8 + i, "athlete": e.athlete, "country_code": e.country_code,
            "time_sec": e.time_sec, "points": pts,
            "is_candidate": e.is_candidate,
        })
    dropped = [
        {"athlete": e.athlete, "country_code": e.country_code,
         "time_sec": e.time_sec, "prev_round": e.prev_round, "prev_rank": e.prev_rank}
        for e in fell_out if not e.is_candidate
    ]
    return {"final": final_out, "bfinal": bfinal_out, "dropped": dropped}

def recompute_country_totals(division, baseline_results, simulated_event_outputs):
    """Sum points per country across all events."""
    totals = {}
    # Non-simulated events carry through from baseline
    for r in baseline_results:
        if r["division"] != division: continue
        if r["is_simulated"]: continue
        cc = r["country_code"]
        totals[cc] = totals.get(cc, 0) + r["points"]
    # Simulated events: use simulated outputs
    for event_id, sim in simulated_event_outputs.items():
        for entry in sim["final"] + sim["bfinal"]:
            cc = entry["country_code"]
            totals[cc] = totals.get(cc, 0) + entry["points"]
    return totals
