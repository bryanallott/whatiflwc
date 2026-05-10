import json, re, csv

print("=== baseline_results.json ===")
baseline = json.loads(open('data/baseline_results.json').read())

small_times = [r for r in baseline if r['time_sec'] is not None and r['time_sec'] < 10]
print(f"Rows with time_sec < 10s: {len(small_times)}")
for r in small_times:
    print(f"  {r['division']:12} {r['event_id']:30} time_sec={r['time_sec']} time_str={r['time_str']} club={r['club_code']}")

weird_club = [r for r in baseline if re.match(r'^[\d.]+$', str(r.get('club_code', '')))]
print(f"\nRows with numeric club_code: {len(weird_club)}")
for r in weird_club[:10]:
    print(f"  {r}")

print("\n=== rankings-source.csv (first 5 rows + any suspicious) ===")
with open('data/rankings-source.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total rows: {len(rows)}")
print(f"Headers: {reader.fieldnames}")
print("First 3 rows:")
for r in rows[:3]:
    print(f"  {dict(r)}")

# Find rows where Time(ms) is unexpectedly small or non-integer
print("\nSuspicious Time(ms) values:")
for r in rows:
    try:
        t = int(r['Time(ms)'])
        if t < 5000:  # under 5 seconds
            print(f"  {r}")
    except (ValueError, KeyError):
        print(f"  NON-INT: {r}")
