#!/usr/bin/env python3
"""Selftest for leg_verdict.py.

The rule it applies is the lane's whole defence against a single run's
coincidence, so the two ways of getting it wrong are pinned directly:

  - counting two ANALYSES of one dump as two replicates, which would let one
    soak analysed at two regions satisfy "two independent dumps";
  - letting a sign flip through, which is what actually refuted six of this
    lane's seven legs.

Run:  python3 docs/lanes/diagsoak77/leg_verdict_selftest.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import leg_verdict as lv  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("%-60s %s%s" % (name, "ok" if ok else "FAIL",
                          "" if ok else "   " + detail))
    if not ok:
        fails.append(name)


def dump(path, session, legs, confounded=False, stipple=3, imaged=40):
    json.dump(dict(session=session, imaged=imaged,
                   stipple=list(range(stipple)),
                   confound=dict(confounded=confounded),
                   legs=legs), open(path, "w"))
    return path


def run(args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        lv.main(["leg_verdict.py"] + args)
    return buf.getvalue()


def leg(obs, p, mdd):
    return dict(observed=obs, p=p, mdd=mdd)


tmp = tempfile.mkdtemp(prefix="legv-")
try:
    # Two REGIONS of ONE session, both significant, same sign.  Under a
    # label-counting rule this reads as replicated; it is one soak.
    a = dump(os.path.join(tmp, "a.json"), 111,
             {"x": leg(+0.01, 0.01, 0.005)})
    b = dump(os.path.join(tmp, "b.json"), 111,
             {"x": leg(+0.02, 0.02, 0.008)})
    txt = run(["full=" + a, "lower=" + b])
    check("one session analysed twice does NOT meet the rule",
          "only 1 dump session" in txt, txt.splitlines()[-1])

    # Two genuinely distinct sessions, same sign, both significant.
    c = dump(os.path.join(tmp, "c.json"), 222,
             {"x": leg(+0.02, 0.02, 0.008)})
    txt = run(["s1=" + a, "s2=" + c])
    check("two distinct sessions, same sign, both p<0.05: meets the rule",
          "MEETS THE RULE" in txt)

    # Sign flip must refute regardless of p.
    d = dump(os.path.join(tmp, "d.json"), 333,
             {"x": leg(-0.02, 0.01, 0.008)})
    txt = run(["s1=" + a, "s2=" + d])
    check("a sign flip refutes even when both are significant",
          "REFUTED: the sign flips" in txt)

    # Same sign and BOTH resolved, but only one significant.  The second
    # observation has to clear its own mdd or the noise-floor rule below takes
    # it out of the sign test and this stops testing what it names: mdd is the
    # 95th percentile of |null|, so "resolved but not significant" lives in a
    # narrow band just above it.
    e = dump(os.path.join(tmp, "e.json"), 444,
             {"x": leg(+0.016, 0.060, 0.015)})
    txt = run(["s1=" + a, "s2=" + e])
    check("same sign, both resolved, one significant: not implicated",
          "not implicated" in txt and "MEETS THE RULE" not in txt,
          " | ".join(l.strip() for l in txt.splitlines()
                     if l.strip().startswith("x ")))

    # A confounded dump must not contribute at all.
    f = dump(os.path.join(tmp, "f.json"), 555,
             {"x": leg(+0.02, 0.001, 0.008)}, confounded=True)
    txt = run(["s1=" + a, "bad=" + f])
    check("a scene-confounded dump is excluded from the verdict",
          "DESCRIPTIVE ONLY" in txt and "only 1 dump session" in txt)

    # The power-inconsistency flag: significant only where the mdd is worst,
    # and less than half that size where it is best.
    g = dump(os.path.join(tmp, "g.json"), 666,
             {"x": leg(+0.0137, 0.011, 0.0103)}, stipple=5)
    h = dump(os.path.join(tmp, "h.json"), 777,
             {"x": leg(+0.0032, 0.286, 0.0058)}, stipple=22)
    txt = run(["few=" + g, "many=" + h])
    check("flags a small-sample overestimate",
          "SMALL-SAMPLE OVERESTIMATE" in txt)

    # ...and does not flag one when the better-powered arm agrees.
    i = dump(os.path.join(tmp, "i.json"), 888,
             {"x": leg(+0.0130, 0.001, 0.0058)}, stipple=22)
    txt = run(["few=" + g, "many=" + i])
    check("does not flag one when the better-powered arm agrees",
          "SMALL-SAMPLE OVERESTIMATE" not in txt)

    # THE NOISE-FLOOR RULE, both ways.  A near-zero observation must not be
    # allowed to refute by its sign; and it must not be allowed to PASS a leg
    # either, since p<0.05 in two sessions is still required.
    j = dump(os.path.join(tmp, "j.json"), 999,
             {"x": leg(-0.0008, 0.815, 0.0066)})
    k_ = dump(os.path.join(tmp, "k.json"), 1010,
              {"x": leg(+0.0104, 0.031, 0.0095)})
    txt = run(["s1=" + a, "s2=" + c, "noise=" + j, "s3=" + k_])
    check("a near-zero observation does not refute by its sign",
          "MEETS THE RULE" in txt and "resolved no direction" in txt,
          " | ".join(l.strip() for l in txt.splitlines()
                     if l.strip().startswith("x ")))
    # Two near-zero sessions and nothing significant must NOT pass.
    l_ = dump(os.path.join(tmp, "l.json"), 1111,
              {"x": leg(+0.0008, 0.700, 0.0066)})
    txt = run(["n1=" + j, "n2=" + l_])
    check("two near-zero sessions do not pass on an unresolved sign",
          "MEETS THE RULE" not in txt and "resolved a direction" in txt)

    # The expected-by-chance line must scale with the number of tests.
    txt = run(["s1=" + a, "s2=" + c])
    check("reports how many p<0.05 hits chance alone would produce",
          "expected by chance alone" in txt)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if fails:
    print("FAILED: %d check(s): %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("all checks passed")
