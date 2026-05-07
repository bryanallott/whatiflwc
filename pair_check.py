import sys, json, math, csv
sys.path.insert(0, '.')
from simulator import Entry, simulate_event

baseline = json.loads(open('data/baseline_results.json').read())
events   = json.loads(open('data/events.json').read())

simulated_ids = {(e['division'], e['event_id']) for e in events if e['simulated']}

AGE_TO_DIVISION = {
    'Youth Female': 'Youth Women', 'Youth Male': 'Youth Men',
    'Open Female': 'Open Women',   'Open Male':  'Open Men',
}
ALIASES = {
    ('Youth Men',  '100m_manikin_tow_with_fins'): '100m_manikin_tow',
    ('Youth Women','100m_manikin_tow_with_fins'): '100m_manikin_tow',
    ('Open Men',   '100m_manikin_tow_with_fins'): '100m_manikin_tow',
}

athletes = []
with open('data/rankings-source.csv', newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        div = AGE_TO_DIVISION.get(row['Age'])
        if not div:
            continue
        eid = row['Event'].lower().replace(' ', '_')
        eid = ALIASES.get((div, eid), eid)
        if (div, eid) not in simulated_ids:
            continue
        athletes.append({
            'name': row['Athlete'].strip(),
            'division': div,
            'event_id': eid,
            'time_sec': int(row['Time(ms)']) / 1000,
        })

# Also add youth athletes as open candidates
YOUTH_TO_OPEN = {'Youth Men': 'Open Men', 'Youth Women': 'Open Women'}
for a in list(athletes):
    open_div = YOUTH_TO_OPEN.get(a['division'])
    if open_div and (open_div, a['event_id']) in simulated_ids:
        athletes.append({**a, 'division': open_div})

def real_pools(division, event_id):
    finals, bfinals = [], []
    for r in baseline:
        if r['division'] != division or r['event_id'] != event_id:
            continue
        t = r['time_sec'] if r['time_sec'] is not None else math.inf
        e = Entry(athlete=r['athlete'], club_code=r['club_code'], time_sec=t,
                  prev_round=r['round'],
                  prev_rank=r['rank'] if isinstance(r['rank'], int) else None)
        (finals if r['round'] == 'Final' else bfinals).append(e)
    return finals, bfinals

def pair_gain(div, name_a, name_b, verbose=True):
    events_a = {a['event_id']: a['time_sec'] for a in athletes if a['name'] == name_a and a['division'] == div}
    events_b = {a['event_id']: a['time_sec'] for a in athletes if a['name'] == name_b and a['division'] == div}
    all_events = set(events_a) | set(events_b)

    total_sim_rsa  = 0
    total_base_rsa = 0
    if verbose:
        print(f"\nPair: {name_a} + {name_b}  |  {div}")
        print(f"  {'Event':<40} {'Athlete':<25} {'Time':>9}  {'Rank':>4}  {'Pts':>4}")
        print("  " + "-" * 85)

    for eid in sorted(all_events):
        f, b = real_pools(div, eid)
        f = [e for e in f if e.club_code != 'RSA']
        b = [e for e in b if e.club_code != 'RSA']
        cands = []
        if eid in events_a:
            cands.append(Entry(athlete=name_a, club_code='RSA', time_sec=events_a[eid], is_candidate=True))
        if eid in events_b:
            cands.append(Entry(athlete=name_b, club_code='RSA', time_sec=events_b[eid], is_candidate=True))
        out = simulate_event(f, b, cands)
        for entry in out['final'] + out['bfinal']:
            if entry['club_code'] == 'RSA':
                total_sim_rsa += entry['points']
                if verbose:
                    rank_str = str(entry['rank']) if not math.isinf(entry['time_sec']) else 'DNQ'
                    print(f"  {eid:<40} {entry['athlete']:<25} {entry['time_sec']:>9.3f}  {rank_str:>4}  {entry['points']:>4}")
        for r in baseline:
            if r['division'] == div and r['event_id'] == eid and r['club_code'] == 'RSA':
                total_base_rsa += r['points']

    gain = total_sim_rsa - total_base_rsa
    if verbose:
        print(f"\n  Simulated RSA: {total_sim_rsa}  Baseline RSA: {total_base_rsa}  Gain: {gain:+d}")
    return gain

nicola_divs = sorted({a['division'] for a in athletes if a['name'] == 'Nicola Harcus'})
print(f"Nicola Harcus found in divisions: {nicola_divs}")

gain_keira_nicola   = pair_gain('Open Women', 'Keira Van Heerden', 'Nicola Harcus')
gain_keira_savannah = pair_gain('Open Women', 'Keira Van Heerden', 'Savannah Voigt')

print(f"\n--- Open Women comparison ---")
print(f"  Keira + Savannah Voigt : {gain_keira_savannah:+d}")
print(f"  Keira + Nicola Harcus  : {gain_keira_nicola:+d}")
print(f"  Difference             : {gain_keira_nicola - gain_keira_savannah:+d}")
