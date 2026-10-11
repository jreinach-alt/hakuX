#!/usr/bin/env python3
"""Score screen-state answers against eval_set.tsv.

    score.py answers/haiku.jsonl [answers/sonnet.jsonl ...]

eval_set.tsv: frame, primary state, other states also accepted, title, device, source frame under
$WORK/dispatch/results/, note. A note starting "FP:" is a frame an older pipeline passed as gameplay;
"AMBIG:" frames are not scored. An answers file is one JSON object per line with "frame" and "state".
make_frames.py rebuilds the 640 px JPEGs the answers were given.
"""
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(paths):
    rows = {r['frame']: r for r in csv.DictReader(open(os.path.join(HERE, 'eval_set.tsv')), delimiter='\t')}
    for path in paths:
        ans = {}
        for ln in open(path):
            if ln.strip():
                j = json.loads(ln)
                ans[j['frame']] = j
        per = collections.defaultdict(lambda: [0, 0])
        fps = [0, 0]
        said_play, missed_play = [], []
        for fr, r in rows.items():
            if fr not in ans or r['note'].startswith('AMBIG:'):
                continue
            ok_set = {r['primary']} | set(filter(None, r['accepted'].split(',')))
            st = ans[fr].get('state')
            ok = st in ok_set
            per[r['primary']][0] += ok
            per[r['primary']][1] += 1
            if r['note'].startswith('FP:'):
                fps[0] += ok
                fps[1] += 1
            if st == 'gameplay' and 'gameplay' not in ok_set:
                said_play.append(f"{fr} ({r['primary']}: {r['note']})")
            if r['primary'] == 'gameplay' and st != 'gameplay':
                missed_play.append(f"{fr} (said {st}: {r['note']})")
        n = sum(v[1] for v in per.values())
        c = sum(v[0] for v in per.values())
        print(f'## {os.path.basename(path)}: {c}/{n} correct; known false passes named correctly {fps[0]}/{fps[1]}')
        print(' '.join(f'{k}={v[0]}/{v[1]}' for k, v in sorted(per.items())))
        print(f'said gameplay on a non-gameplay frame ({len(said_play)}):', '; '.join(said_play) or '-')
        print(f'said not-gameplay on a gameplay frame ({len(missed_play)}):', '; '.join(missed_play) or '-')
        print()


if __name__ == '__main__':
    main(sys.argv[1:] or [os.path.join(HERE, 'answers', f) for f in sorted(os.listdir(os.path.join(HERE, 'answers')))])
