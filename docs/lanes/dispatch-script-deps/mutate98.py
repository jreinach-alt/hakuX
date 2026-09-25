#!/usr/bin/env python3
"""Run selftest.d/98 against one mutant of fleet.py per invariant.

    mutate98.py [mutant ...]        # all of them by default

Each mutant is a copy of fleet.py and affinity.py in a temp directory with
one invariant removed; 98 runs against it through SELFTEST_FLEET_SRC. Every
mutant must turn exactly the checks written for its invariant red. A mutant
whose pattern no longer matches exactly once is REFUSED, never scored.
"""
import os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
S = tempfile.mkdtemp(prefix="mutate98-")
src = os.path.join(WT, "docs/testing")
MUT = {
  "order":    [("if x > name and claimed > changed and", "if claimed > changed and")],
  "stale":    [("if x > name and claimed > changed and", "if x > name and")],
  "sibling":  [("changed = max(epoch, sib.get(key, 0.0))", "changed = epoch")],
  "between":  [("elif lane not in between and now - quiet_since", "elif now - quiet_since")],
  "lastact":  [("quiet_since = max(written, last, epoch)", "quiet_since = max(written, epoch)")],
  "agegate":  [("if not written or age <= settle_s:", "if not written:")],
  "liveness": [("live = set(affinity.serving(D))",
                "live = {l for l in os.listdir(os.path.join(D, 'lanes')) if '.' not in l}")],
  "pooled":   [("pooled_unheld = set(affinity.pooled(D)) - held",
                "pooled_unheld = {l for l in os.listdir(os.path.join(D, 'lanes')) if '.' not in l} - held - set(affinity.OFFPOOL)")],
  "holdall":  [("elif handhelds_held and not pooled_unheld:", "elif False:")],
  "pinheld":  [("            if pin in held:\n", "            if False:\n")],
  "nocall":   [("    stalled, on_hold, qblind = queue_stall()\n", "    stalled, on_hold, qblind = [], [], None\n")],
}
names = sys.argv[1:] or list(MUT)
for name in names:
    d = os.path.join(S, "mut-" + name)
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for f in ("fleet.py", "affinity.py"):
        shutil.copy(os.path.join(src, f), d)
    p = os.path.join(d, "fleet.py"); s = open(p).read()
    for a, b in MUT[name]:
        n = s.count(a)
        if n != 1:
            print("%-9s REFUSED: pattern matched %d times: %r" % (name, n, a[:60])); break
        s = s.replace(a, b)
    else:
        open(p, "w").write(s)
        out = subprocess.run([os.path.join(HERE, "runfrag.sh"), WT, "98-fleet-queue-stall.sh"],
                             env=dict(os.environ, SELFTEST_FLEET_SRC=d),
                             capture_output=True, text=True).stdout
        red = [l.strip()[5:] for l in out.splitlines() if l.strip().startswith("FAIL ")]
        print("%-9s %d red: %s" % (name, len(red), " | ".join(r[:70] for r in red) or "NONE -- inert"))
shutil.rmtree(S, ignore_errors=True)
