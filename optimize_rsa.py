"""
RSA Optimal 2-Athlete-per-Division Selector
Finds the best 8 athletes (2 per division) to maximise RSA points gain.

Rules:
- Each selected athlete competes in ALL their events within the chosen division.
- Replacement mode: strip all existing RSA athletes from those event pools before simulating.
- An athlete may only compete in ONE division total.
- Youth Male can be assigned to Open Men; Youth Female to Open Women.
- Select exactly 2 athletes per division, 8 total, no athlete used twice.
"""

from __future__ import annotations
import csv
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).parent
DATA = REPO / "data"

sys.path.insert(0, str(REPO))
from simulator import Entry, simulate_event, recompute_country_totals, POINTS_FINAL, POINTS_BFINAL

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DIVISIONS = ["Youth Men", "Youth Women", "Open Men", "Open Women"]

_AGE_TO_DIVISION = {
    "Youth Female": "Youth Women",
    "Youth Male":   "Youth Men",
    "Open Female":  "Open Women",
    "Open Male":    "Open Men",
}

# Youth → Open cross-division mapping
_YOUTH_TO_OPEN = {
    "Youth Men":   "Open Men",
    "Youth Women": "Open Women",
}


def _event_name_to_id(csv_event: str, division: str) -> str:
    normalized = csv_event.lower().replace(" ", "_")
    aliases = {
        ("Youth Men",   "100m_manikin_tow_with_fins"): "100m_manikin_tow",
        ("Youth Women", "100m_manikin_tow_with_fins"): "100m_manikin_tow",
        ("Open Men",    "100m_manikin_tow_with_fins"): "100m_manikin_tow",
    }
    return aliases.get((division, normalized), normalized)


def _ms_to_str(ms: int) -> str:
    return f"{ms // 60000:02d}:{(ms % 60000) // 1000:02d}.{ms % 1000:03d}"


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def load_events() -> list[dict]:
    return json.loads((DATA / "events.json").read_text())


def load_baseline_results() -> list[dict]:
    return json.loads((DATA / "baseline_results.json").read_text())


def load_candidates_from_csv(events: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """
    Returns {(division, event_id): [{"athlete": ..., "time_ms": ..., "time_sec": ...}, ...]}
    Top-15 per (division, event_id) by time ascending.
    All athletes are treated as RSA candidates.
    """
    simulated_ids = {(e["division"], e["event_id"]) for e in events if e["simulated"]}

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with (DATA / "rankings-source.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            division = _AGE_TO_DIVISION.get(row["Age"])
            if division is None:
                continue
            event_id = _event_name_to_id(row["Event"], division)
            if (division, event_id) not in simulated_ids:
                continue
            buckets[(division, event_id)].append({
                "athlete":   row["Athlete"].strip(),
                "time_ms":   int(row["Time(ms)"]),
                "time_sec":  round(int(row["Time(ms)"]) / 1000, 3),
                "native_div": division,  # their Age-based division
            })

    result = {}
    for key, entries in buckets.items():
        entries.sort(key=lambda x: x["time_ms"])
        result[key] = entries[:15]
    return result


# ---------------------------------------------------------------------------
# Build event pools from baseline
# ---------------------------------------------------------------------------
def build_event_pools(baseline: list[dict], division: str, event_id: str) -> tuple[list[Entry], list[Entry]]:
    """Return (finalists, bfinalists) Entry lists for a given division+event."""
    finalists, bfinalists = [], []
    for r in baseline:
        if r["division"] != division or r["event_id"] != event_id:
            continue
        t = r["time_sec"] if r["time_sec"] is not None else math.inf
        e = Entry(
            athlete=r["athlete"],
            club_code=r["club_code"],
            time_sec=t,
            is_candidate=False,
            prev_round=r["round"],
            prev_rank=r["rank"] if isinstance(r["rank"], int) else None,
        )
        if r["round"] == "Final":
            finalists.append(e)
        else:
            bfinalists.append(e)
    return finalists, bfinalists


def rsa_points_in_sim(sim_output: dict) -> int:
    """Sum RSA points from a simulate_event() output."""
    pts = 0
    for entry in sim_output["final"] + sim_output["bfinal"]:
        if entry["club_code"] == "RSA":
            pts += entry["points"]
    return pts


def rsa_baseline_points(baseline: list[dict], division: str, event_id: str) -> int:
    """Baseline RSA points for a specific (division, event_id)."""
    return sum(
        r["points"] for r in baseline
        if r["division"] == division
        and r["event_id"] == event_id
        and r["club_code"] == "RSA"
    )


# ---------------------------------------------------------------------------
# Score a single athlete (or pair) in replacement mode
# ---------------------------------------------------------------------------

def score_athlete_in_division(
    athlete_name: str,
    division: str,
    athlete_events: list[tuple[str, float]],  # [(event_id, time_sec), ...]
    baseline: list[dict],
) -> int:
    """
    Simulate all events for the given athlete in the given division using
    replacement mode (strip RSA from pools, add athlete as RSA candidate).
    Return NET RSA points gain vs baseline.
    """
    total_gain = 0
    for event_id, time_sec in athlete_events:
        finalists, bfinalists = build_event_pools(baseline, division, event_id)

        # Replacement mode: remove all existing RSA from both pools
        finalists  = [e for e in finalists  if e.club_code != "RSA"]
        bfinalists = [e for e in bfinalists if e.club_code != "RSA"]

        candidate = Entry(
            athlete=athlete_name,
            club_code="RSA",
            time_sec=time_sec,
            is_candidate=True,
        )
        sim = simulate_event(finalists, bfinalists, [candidate])
        sim_rsa  = rsa_points_in_sim(sim)
        base_rsa = rsa_baseline_points(baseline, division, event_id)
        total_gain += sim_rsa - base_rsa

    return total_gain


def score_pair_in_division(
    a1_name: str, a1_events: list[tuple[str, float]],
    a2_name: str, a2_events: list[tuple[str, float]],
    division: str,
    baseline: list[dict],
) -> int:
    """
    Score a pair of athletes together (they may share events).
    Replacement mode: strip all RSA from all touched events, add both candidates.
    """
    # Merge their events — if both share an event, both compete
    event_map: dict[str, list[Entry]] = {}  # event_id -> list of candidate Entries

    def add_events(name, events):
        for event_id, time_sec in events:
            if event_id not in event_map:
                event_map[event_id] = []
            event_map[event_id].append(Entry(
                athlete=name,
                club_code="RSA",
                time_sec=time_sec,
                is_candidate=True,
            ))

    add_events(a1_name, a1_events)
    add_events(a2_name, a2_events)

    total_gain = 0
    for event_id, candidates in event_map.items():
        finalists, bfinalists = build_event_pools(baseline, division, event_id)
        # Replacement mode
        finalists  = [e for e in finalists  if e.club_code != "RSA"]
        bfinalists = [e for e in bfinalists if e.club_code != "RSA"]

        sim = simulate_event(finalists, bfinalists, candidates)
        sim_rsa  = rsa_points_in_sim(sim)
        base_rsa = rsa_baseline_points(baseline, division, event_id)
        total_gain += sim_rsa - base_rsa

    return total_gain


# ---------------------------------------------------------------------------
# Build candidate roster per division
# ---------------------------------------------------------------------------

def build_athlete_roster(
    candidates_by_event: dict[tuple[str, str], list[dict]],
    division: str,
) -> dict[str, list[tuple[str, float]]]:
    """
    For a given division, return {athlete_name: [(event_id, time_sec), ...]}
    taking the best time per athlete per event (in case they appear multiple times).
    """
    # athlete -> {event_id -> best_time_sec}
    roster: dict[str, dict[str, float]] = defaultdict(dict)
    for (div, event_id), entries in candidates_by_event.items():
        if div != division:
            continue
        for entry in entries:
            name = entry["athlete"]
            t = entry["time_sec"]
            if event_id not in roster[name] or t < roster[name][event_id]:
                roster[name][event_id] = t

    return {
        name: list(events.items())
        for name, events in roster.items()
    }


# ---------------------------------------------------------------------------
# Main optimisation
# ---------------------------------------------------------------------------

def optimise():
    print("Loading data...")
    events_list  = load_events()
    baseline     = load_baseline_results()
    candidates_by_event = load_candidates_from_csv(events_list)

    simulated_ids = {(e["division"], e["event_id"]) for e in events_list if e["simulated"]}

    # -----------------------------------------------------------------------
    # Build rosters for native divisions + youth-in-open option
    # -----------------------------------------------------------------------
    # native_roster[division] = {athlete: [(event_id, time_sec), ...]}
    native_roster: dict[str, dict[str, list]] = {}
    for div in DIVISIONS:
        native_roster[div] = build_athlete_roster(candidates_by_event, div)

    # Cross-div roster: Youth Men athletes who could compete in Open Men,
    # but only for events that are simulated in Open Men.
    # They use their Youth Men event times for matching Open Men event_ids.
    cross_roster: dict[str, dict[str, list]] = {}  # cross_roster[open_div][athlete_name]
    for youth_div, open_div in _YOUTH_TO_OPEN.items():
        cross_roster[open_div] = {}
        open_simulated = {eid for (d, eid) in simulated_ids if d == open_div}
        youth_athletes = native_roster.get(youth_div, {})
        for name, events in youth_athletes.items():
            # Only include events that also exist in Open division
            open_events = [(eid, t) for (eid, t) in events if eid in open_simulated]
            if open_events:
                cross_roster[open_div][name] = open_events

    # -----------------------------------------------------------------------
    # Score every individual athlete in their division(s)
    # -----------------------------------------------------------------------
    print("\nScoring individual athletes per division...")
    # individual_scores[(athlete, division)] = gain
    individual_scores: dict[tuple[str, str], int] = {}
    # Track which athletes have cross-div options
    cross_div_candidates: dict[str, list[str]] = defaultdict(list)  # athlete -> [open_divs]

    for div in DIVISIONS:
        roster = native_roster[div]
        print(f"  {div}: {len(roster)} unique athletes")
        for name, events in roster.items():
            g = score_athlete_in_division(name, div, events, baseline)
            individual_scores[(name, div)] = g

    # Score youth-in-open
    for open_div, roster in cross_roster.items():
        for name, events in roster.items():
            g = score_athlete_in_division(name, open_div, events, baseline)
            individual_scores[(name, open_div)] = g
            cross_div_candidates[name].append(open_div)

    # -----------------------------------------------------------------------
    # Print youth-in-open comparison
    # -----------------------------------------------------------------------
    print("\n--- Youth Athletes who score better in Open division ---")
    found_any = False
    for name, open_divs in cross_div_candidates.items():
        for open_div in open_divs:
            youth_div = "Youth Men" if open_div == "Open Men" else "Youth Women"
            native_gain = individual_scores.get((name, youth_div), 0)
            open_gain   = individual_scores.get((name, open_div), 0)
            if open_gain > native_gain:
                found_any = True
                print(f"  {name}: {youth_div} gain={native_gain:+d}  |  {open_div} gain={open_gain:+d}  --> BETTER IN OPEN")
    if not found_any:
        print("  (none found)")

    # -----------------------------------------------------------------------
    # Per division: find top-10 candidates by individual gain, then brute-force pairs
    # -----------------------------------------------------------------------
    print("\nFinding optimal pairs per division (brute-force over top-10)...")

    best_pair_per_div: dict[str, tuple[str, str, int, dict]] = {}  # div -> (a1, a2, gain, detail)

    for div in DIVISIONS:
        # Include native athletes + cross-div youth athletes (if this is an open div)
        candidates_this_div: dict[str, list[tuple[str, float]]] = {}

        # Native athletes
        for name, events in native_roster[div].items():
            candidates_this_div[name] = events

        # Cross-div (youth in open)
        for name, events in cross_roster.get(div, {}).items():
            # Don't double-add if already native (shouldn't happen, but safety)
            if name not in candidates_this_div:
                candidates_this_div[name] = events

        if len(candidates_this_div) < 2:
            print(f"  {div}: too few candidates ({len(candidates_this_div)}), skipping")
            best_pair_per_div[div] = (None, None, 0, {})
            continue

        # Sort by individual gain, take top 10
        scored = sorted(
            [(name, individual_scores.get((name, div), 0)) for name in candidates_this_div],
            key=lambda x: -x[1]
        )
        top_n = scored[:10]
        print(f"  {div}: top-10 individuals: {[(n, g) for n, g in top_n]}")

        # Brute-force pairs
        best_gain = -99999
        best_a1 = best_a2 = None

        for (n1, _), (n2, _) in combinations(top_n, 2):
            e1 = candidates_this_div[n1]
            e2 = candidates_this_div[n2]
            pair_gain = score_pair_in_division(n1, e1, n2, e2, div, baseline)
            if pair_gain > best_gain:
                best_gain = pair_gain
                best_a1, best_a2 = n1, n2

        best_pair_per_div[div] = (best_a1, best_a2, best_gain, candidates_this_div)
        print(f"  {div}: best pair = {best_a1} + {best_a2}, gain = {best_gain:+d}")

    # -----------------------------------------------------------------------
    # Cross-division conflict resolution:
    # If a youth athlete appears as the best pick in both their native div AND
    # the open div, we need to resolve. We do this by finding which assignment
    # of conflicted athletes maximises TOTAL system gain.
    # -----------------------------------------------------------------------
    # For simplicity: collect all 8 chosen athletes across 4 divisions.
    # If any athlete appears twice, we need to substitute.
    chosen: dict[str, list[str]] = {}  # div -> [a1, a2]
    for div in DIVISIONS:
        a1, a2, _, _ = best_pair_per_div[div]
        chosen[div] = [a1, a2]

    # Detect conflicts (same name in multiple divisions)
    name_to_divs: dict[str, list[str]] = defaultdict(list)
    for div, names in chosen.items():
        for name in names:
            if name:
                name_to_divs[name].append(div)

    conflicts = {name: divs for name, divs in name_to_divs.items() if len(divs) > 1}
    if conflicts:
        print(f"\nConflicts detected: {conflicts}")
        print("Resolving by keeping athlete in division with higher individual gain...")
        for name, divs in conflicts.items():
            gains = [(div, individual_scores.get((name, div), 0)) for div in divs]
            gains.sort(key=lambda x: -x[1])
            keep_div = gains[0][0]
            print(f"  {name}: keep in {keep_div} (gain={gains[0][1]:+d})")
            for div, g in gains[1:]:
                print(f"    removing from {div} (gain={g:+d})")
                # Replace with next-best individual in that division
                _, _, _, cand_map = best_pair_per_div[div]
                scored_div = sorted(
                    [(n, individual_scores.get((n, div), 0)) for n in cand_map if n != name],
                    key=lambda x: -x[1]
                )
                replacement = scored_div[0][0] if scored_div else None
                chosen[div] = [n if n != name else replacement for n in chosen[div]]
                print(f"    replaced with {replacement} in {div}")

    # -----------------------------------------------------------------------
    # Final output: per division detail
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("OPTIMAL RSA TEAM SELECTION")
    print("=" * 80)

    total_rsa_gain = 0

    for div in DIVISIONS:
        a1_name, a2_name = chosen[div]
        if not a1_name or not a2_name:
            print(f"\n{div}: INSUFFICIENT CANDIDATES")
            continue

        _, _, _, cand_map = best_pair_per_div[div]
        a1_events = cand_map.get(a1_name, native_roster[div].get(a1_name, []))
        a2_events = cand_map.get(a2_name, native_roster[div].get(a2_name, []))

        # Compute final pair gain (may differ from earlier best if conflicts resolved)
        pair_gain = score_pair_in_division(a1_name, a1_events, a2_name, a2_events, div, baseline)
        total_rsa_gain += pair_gain

        # Per-event detail for each athlete
        def per_event_detail(name, events):
            rows = []
            for event_id, time_sec in sorted(events, key=lambda x: x[0]):
                # Score this athlete alone (to show their individual contribution)
                finalists, bfinalists = build_event_pools(baseline, div, event_id)
                finalists  = [e for e in finalists  if e.club_code != "RSA"]
                bfinalists = [e for e in bfinalists if e.club_code != "RSA"]
                cand = Entry(athlete=name, club_code="RSA", time_sec=time_sec, is_candidate=True)
                sim = simulate_event(finalists, bfinalists, [cand])
                base_rsa = rsa_baseline_points(baseline, div, event_id)
                sim_rsa  = rsa_points_in_sim(sim)
                # Find their rank
                rank_str = "DNQ"
                for entry in sim["final"] + sim["bfinal"]:
                    if entry["athlete"] == name and entry["club_code"] == "RSA":
                        rank_str = str(entry["rank"])
                        break
                rows.append((event_id, _ms_to_str(int(time_sec * 1000)), rank_str, sim_rsa - base_rsa))
            return rows

        print(f"\n{'-' * 80}")
        print(f"Division: {div}   | Net RSA gain (pair together): {pair_gain:+d} pts")
        print(f"{'-' * 80}")

        for ath_name, ath_events in [(a1_name, a1_events), (a2_name, a2_events)]:
            solo_gain = individual_scores.get((ath_name, div), 0)
            detail = per_event_detail(ath_name, ath_events)
            print(f"\n  Athlete: {ath_name}  (solo gain: {solo_gain:+d})")
            print(f"  {'Event':<40} {'Time':>10} {'Rank':>5} {'Gain':>6}")
            print(f"  {'-' * 65}")
            for event_id, time_str, rank, gain in detail:
                print(f"  {event_id:<40} {time_str:>10} {rank:>5} {gain:>+6}")

    print(f"\n{'=' * 80}")
    print(f"TOTAL RSA POINTS GAIN ACROSS ALL DIVISIONS: {total_rsa_gain:+d}")
    print(f"{'=' * 80}")

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    print("\n\nSUMMARY TABLE")
    print(f"{'Division':<15} {'Athlete':<35} {'Events':>6} {'Points Gained':>14}")
    print(f"{'-' * 75}")
    for div in DIVISIONS:
        a1_name, a2_name = chosen[div]
        if not a1_name:
            continue
        _, _, _, cand_map = best_pair_per_div[div]
        pair_gain = score_pair_in_division(
            a1_name, cand_map.get(a1_name, native_roster[div].get(a1_name, [])),
            a2_name, cand_map.get(a2_name, native_roster[div].get(a2_name, [])),
            div, baseline
        )
        for i, name in enumerate([a1_name, a2_name]):
            evts = cand_map.get(name, native_roster[div].get(name, []))
            n_events = len(evts)
            div_label = div if i == 0 else ""
            gain_str = f"{pair_gain:+d}" if i == 0 else ""
            print(f"{div_label:<15} {name:<35} {n_events:>6} {gain_str:>14}")
    print(f"{'-' * 75}")
    print(f"{'TOTAL':<15} {'':35} {'':>6} {total_rsa_gain:>+14}")


if __name__ == "__main__":
    optimise()
