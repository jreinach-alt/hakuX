#!/usr/bin/env python3
"""Count validation messages per message id in a dispatcher logcat produced by
the vklayer34 instrumentation ref (tag hakuX-lane, `vkval id=<id> | <msg>`),
and check the positive-control lines.  lane.vklayer34, #34.

usage: count_vuids.py <result dir>
"""
import collections
import glob
import json
import os
import re
import sys

rdir = sys.argv[1]
CONTROL = [
    "vkval GPU driver: forced system driver",
    "vkval validation_layers forced on",
    "layer[0]: VK_LAYER_KHRONOS_validation",
    "Validation layers ENABLED",
    "vkval debug_utils enabled = 1",
]
res = json.load(open(os.path.join(rdir, "result.json")))
print("request", os.path.basename(rdir))
for k in ("ref", "apk_sha", "device", "serial", "runs"):
    if k in res:
        print(f"  {k}: {res[k]}")
for lc in sorted(glob.glob(os.path.join(rdir, "logcat*.txt"))):
    t = open(lc, errors="replace").read()
    print(f"\n{os.path.basename(lc)}: {len(t.splitlines())} lines")
    ok = True
    for c in CONTROL:
        hit = c in t
        ok &= hit
        print(f"  control {'OK  ' if hit else 'MISS'} {c}")
    print("  control:", "PASS" if ok else "FAIL -- count is VOID, not 0")
    ids = collections.Counter()
    first = {}
    pids = set()
    for m in re.finditer(r"^\S+ \S+ ([VDIWEF])/hakuX-lane\((\d+)\): vkval id=(\S+) \| (.*)$",
                         t, re.M):
        prio, pid, mid, msg = m.groups()
        ids[(prio, mid)] += 1
        pids.add(pid)
        first.setdefault((prio, mid), msg[:220])
    print(f"  messages {sum(ids.values())}, distinct ids {len(ids)}, pids {sorted(pids)}")
    for (prio, mid), n in ids.most_common():
        print(f"  {n:6d}  {prio}  {mid}\n          {first[(prio, mid)]}")
