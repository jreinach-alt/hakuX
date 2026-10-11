#!/usr/bin/env python3
"""[tlb68] windows where the jump cache was wiped by something other than a
TLB flush (jct) or a TB invalidation (jci): jc - jct - jci > 0. tb_flush()
wipes it (tcg_flush_jmp_cache), and its own hakuX-tb line is outside every
LOGCAT_SPEC, so this is the one trace a code-cache flush leaves in a run that
predates [tcg787]'s tbf.

usage: fs_jcx.py <logcat.txt>
"""
import re
import sys

t0 = None
for line in open(sys.argv[1], errors='replace'):
    if '[tlb68]' not in line:
        continue
    m = re.match(r'(\d\d-\d\d) (\d\d):(\d\d):(\d\d\.\d+)', line)
    t = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + float(m.group(4))
    t0 = t if t0 is None else t0
    d = dict(re.findall(r' (\w+)=(\d+)', line))
    other = int(d['jc']) - int(d['jct']) - int(d['jci'])
    if other:
        print('%7.1f w=%s jc=%s jct=%s jci=%s other=%d ff=%s' %
              (t - t0, d['w'], d['jc'], d['jct'], d['jci'], other, d['ff']))
