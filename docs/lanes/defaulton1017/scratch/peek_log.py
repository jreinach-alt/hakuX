#!/usr/bin/env python3
"""What a result's logcat looks like at its ends: first/last line, first/last pace line, tag counts,
crash-ish lines, and the V lines this lane reads. usage: peek_log.py <result dir> ..."""
import collections
import os
import re
import sys

TAG = re.compile(r'^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+\d+\s+\d+ (\w) ([^:]+):')
for d in sys.argv[1:]:
    p = os.path.join(d, 'logcat.txt')
    lines = open(p, errors='replace').read().splitlines()
    tags = collections.Counter()
    pace = [l for l in lines if 'hakuX-pace' in l]
    crash = [l for l in lines if re.search(r'hakuX-crash|Fatal signal|SIGSEGV|SIGABRT|abort', l)]
    v = [l for l in lines if re.search(r'\[(s2tcvt|rearly1018|fldcw1018|ibc507)\] (on|off|early=|chain=|needs)', l)]
    for l in lines:
        m = TAG.match(l)
        if m:
            tags[m.group(1) + ' ' + m.group(2).strip()] += 1
    print('==', d)
    print('lines', len(lines))
    print('first', lines[0][:150] if lines else None)
    print('last ', lines[-1][:150] if lines else None)
    print('pace first', pace[0][:150] if pace else None)
    print('pace last ', pace[-1][:150] if pace else None)
    print('tags', tags.most_common(25))
    print('crash-ish', len(crash))
    for l in crash[:5]:
        print('  ', l[:200])
    for l in v[:8]:
        print('V ', l[:200])
    rw = [l for l in lines if '[rearly1018] w ' in l]
    print('rearly w lines', len(rw), rw[-1][:220] if rw else '')
    fl = [l for l in lines if '[fldcw1018] n=' in l]
    print('fldcw n lines', len(fl), fl[-1][:200] if fl else '')
