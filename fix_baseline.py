"""Fix two data quality issues in baseline_results.json:
1. time_sec truncated to minutes-only for 2:xx.xx events (should be ~128s, stored as 2)
2. numeric club_code/club on line_throw rows (throw distance stored instead of country code)
"""
import json, re

baseline = json.loads(open('data/baseline_results.json').read())

def parse_time_str(s):
    """'M:SS.cc' or 'MM:SS.cc' -> float seconds."""
    if not s:
        return None
    m = re.match(r'^(\d+):(\d+\.\d+)$', s.strip())
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    return None

def extract_club_from_athlete(athlete_str):
    """'ESP - Spain Team A' -> ('ESP', 'ESP - Spain')"""
    m = re.match(r'^([A-Z]{2,3}) - (.+?)(?:\s+Team\s.*)?$', athlete_str.strip())
    if m:
        code = m.group(1)
        # rebuild full club name without " Team A/B/..."
        full = re.sub(r'\s+Team\s+.*$', '', athlete_str.strip())
        return code, full
    return None, None

time_fixes = 0
club_fixes = 0

for r in baseline:
    # Fix 1: time_sec way off from what time_str says
    parsed = parse_time_str(r.get('time_str'))
    if parsed is not None and r.get('time_sec') is not None:
        stored = r['time_sec']
        # Fix if stored value is more than 50% off from parsed (covers both the =2 and =86400 cases)
        if stored != parsed and (stored < parsed * 0.5 or stored > parsed * 1.5):
            r['time_sec'] = round(parsed, 3)
            time_fixes += 1

    # Fix 2: any club_code that isn't a 2-3 letter country code
    club_code = str(r.get('club_code', ''))
    if not re.match(r'^[A-Z]{2,3}$', club_code):
        code, full = extract_club_from_athlete(r.get('athlete', ''))
        if code:
            r['club_code'] = code
            r['club'] = full
            club_fixes += 1
        else:
            print(f"  Could not extract club from: {r['athlete']}")

print(f"Time fixes: {time_fixes}")
print(f"Club fixes: {club_fixes}")

open('data/baseline_results.json', 'w').write(json.dumps(baseline, indent=2))
print("Written.")
