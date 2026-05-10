import json, re

baseline = json.loads(open('data/baseline_results.json').read())

bad = [r for r in baseline if r['time_sec'] == 86400]
print(f'Rows with time_sec=86400: {len(bad)}')
for r in bad:
    print(f"  {r['division']:12} {r['event_id']:35} {r['time_str']:12} rank={r['rank']}")

def parse_time_str(s):
    """Parse 'm:ss.cc' or 'mm:ss.cc' into seconds."""
    if not s:
        return None
    m = re.match(r'^(\d+):(\d+\.\d+)$', s.strip())
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    return None

fixed = 0
for r in baseline:
    if r['time_sec'] == 86400:
        parsed = parse_time_str(r.get('time_str'))
        if parsed:
            r['time_sec'] = parsed
            fixed += 1
        else:
            print(f"  Could not parse: {r['time_str']}")

print(f'\nFixed {fixed} rows.')
open('data/baseline_results.json', 'w').write(json.dumps(baseline, indent=2))
print('Written.')
