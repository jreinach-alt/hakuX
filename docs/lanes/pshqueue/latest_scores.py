#!/usr/bin/env python3
"""Latest scored rows for the named captures across dispatch results.

    latest_scores.py SUITE_DIR[/TEST] ... [--n N]

For each result directory (newest first) that holds a row for any named key,
print the directory, its ref and device, and each matching row's differing
count and status. The TSV is read by header name, so a column added later
does not shift what is printed."""
import csv, fnmatch, glob, json, os, sys

R = '/home/justin/hakux-work/dispatch/results'
args = [a for a in sys.argv[1:] if not a.startswith('--')]
n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 4
args = [a for a in args if not a.isdigit()]
pats = [a if '/' in a else a + '/*' for a in args]

dirs = sorted(glob.glob(os.path.join(R, '*')), key=os.path.getmtime, reverse=True)
shown = 0
for d in dirs:
    tsvs = glob.glob(os.path.join(d, '*.tsv'))
    rows = []
    for t in tsvs:
        try:
            with open(t) as f:
                for row in csv.DictReader(f, delimiter='\t'):
                    key = '%s/%s' % (row.get('suite', ''), row.get('test', ''))
                    if any(fnmatch.fnmatch(key, p) for p in pats):
                        rows.append((key, row))
        except Exception:
            continue
    if not rows:
        continue
    req = {}
    try:
        req = json.load(open(os.path.join(d, 'request.json')))
    except Exception:
        pass
    print('==', os.path.basename(d), req.get('ref', '?'), req.get('device', '?'))
    for key, row in sorted(rows, key=lambda kr: kr[0]):
        print('   %-48s %9s %s' % (key, row.get('differing', '?'), row.get('status', '')))
    shown += 1
    if shown >= n:
        break
