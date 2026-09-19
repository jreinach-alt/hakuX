#!/usr/bin/env python3
"""Apply the registered decision rule across dumps, instead of by eye.

    leg_verdict.py LABEL=dump1.json LABEL=dump2.json ...

NOTES.md registers one rule for F1-F4 and it is deliberately not "p < 0.05":

    each leg requires the SAME SIGN in at least two independent dumps -- two
    separate soaks, two separate app launches, two separate dump sessions --
    before it counts.

That rule is doing the multiple-comparison work as well as the replication
work, and this prints both so neither is taken on trust:

  - per leg, the observed difference and its p in every dump, so a sign flip is
    visible rather than averaged away;
  - the count of legs x dumps tested, and how many p < 0.05 results that many
    tests produces by chance, so a single hit is read against the right
    expectation;
  - THE POWER INCONSISTENCY CHECK, which is the one this lane needed. A real
    effect should be LARGER, or at least not much smaller, where the analysis
    has more power.  When a leg separates only in the arm with the fewest
    flagged frames, and the better-powered arm of the SAME dump measures it at
    a fraction of the size with a minimum detectable difference well below the
    claimed effect, that is a small-sample overestimate and is reported as one.

Exit status is 0 always: this prints a verdict, it does not gate anything.
"""
import json
import sys
from collections import defaultdict


def load(args):
    dumps = []
    for a in args:
        label, _, path = a.partition("=")
        if not path:
            label, path = path or a, a
        dumps.append((label or path, json.load(open(path))))
    return dumps


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 0
    dumps = load(argv[1:])

    legs = defaultdict(dict)
    for label, d in dumps:
        for k, v in (d.get("legs") or {}).items():
            if isinstance(v, dict) and v.get("p") is not None:
                legs[k][label] = v

    print("dumps: %s" % ", ".join(
        "%s (%d flagged of %d)" % (lab, len(d.get("stipple") or []),
                                   d.get("imaged", 0))
        for lab, d in dumps))
    conf = [lab for lab, d in dumps if (d.get("confound") or {}).get("confounded")]
    if conf:
        print("CONFOUNDED WITH SCENE and therefore DESCRIPTIVE ONLY: %s.  Legs "
              "from these dumps take no part in the verdicts below."
              % ", ".join(conf))
    usable = [lab for lab, d in dumps
              if not (d.get("confound") or {}).get("confounded")]

    n_tests = sum(len(v) for k, v in legs.items()
                  if any(lab in usable for lab in v))
    print("\n%d leg x dump tests over the %d unconfounded dump(s); at p<0.05 "
          "that is %.1f hits expected by chance alone."
          % (n_tests, len(usable), 0.05 * n_tests))

    # INDEPENDENCE IS PER DUMP SESSION, NOT PER ANALYSIS.  Two regions of one
    # dump are two tests of the same pixels from the same soak, and counting
    # them as two replicates is how "same sign in two independent dumps" gets
    # satisfied by one run analysed twice.  The registration says two separate
    # soaks, two separate app launches, two separate dump sessions -- so group
    # by the session id the dump itself carries, and require the SIGN to agree
    # across sessions and the hits to land in two DIFFERENT ones.
    session_of = {lab: d.get("session") for lab, d in dumps}
    print("\nindependence: %d analysis label(s) over %d distinct dump "
          "session(s) -- %s"
          % (len(usable), len({session_of[lab] for lab in usable}),
             ", ".join("%s=%s" % (lab, session_of[lab]) for lab in usable)))

    print("\n%-22s %s" % ("leg", "  ".join("%-22s" % lab for lab in usable)))
    verdicts = {}
    for k in sorted(legs):
        cells, signs, hit_sessions, sessions = [], [], set(), set()
        for lab in usable:
            v = legs[k].get(lab)
            if v is None:
                cells.append("%-22s" % "--")
                continue
            star = "*" if v["p"] < 0.05 else " "
            cells.append("%-22s" % ("%+.4f p%.3f%s" % (v["observed"], v["p"],
                                                       star)))
            signs.append(1 if v["observed"] > 0 else -1)
            sessions.add(session_of[lab])
            if v["p"] < 0.05:
                hit_sessions.add(session_of[lab])
        print("%-22s %s" % (k, "  ".join(cells)))
        verdicts[k] = dict(same_sign=len(set(signs)) == 1 and len(signs) >= 2,
                           hit_sessions=len(hit_sessions),
                           sessions=len(sessions))

    print("\n== the registered rule: same sign in >=2 independent DUMP "
          "SESSIONS ==")
    for k in sorted(verdicts):
        v = verdicts[k]
        if v["sessions"] < 2:
            print("  %-22s only %d dump session -- not eligible"
                  % (k, v["sessions"]))
        elif not v["same_sign"]:
            print("  %-22s REFUTED: the sign flips" % k)
        elif v["hit_sessions"] >= 2:
            print("  %-22s MEETS THE RULE: same sign, and p<0.05 in %d of %d "
                  "distinct sessions" % (k, v["hit_sessions"], v["sessions"]))
        else:
            print("  %-22s same sign but p<0.05 in only %d of %d sessions -- "
                  "not implicated" % (k, v["hit_sessions"], v["sessions"]))

    # ------------------------------------------------- the power check
    print("\n== power inconsistency ==")
    print("A leg that separates ONLY where the flagged class is smallest, while "
          "a better-powered analysis of the same dumps measures it far lower, "
          "is a small-sample overestimate.  Listed per leg where both are "
          "available:")
    for k in sorted(legs):
        rows = [(lab, legs[k][lab]) for lab in usable if lab in legs[k]]
        if len(rows) < 2:
            continue
        best = min(rows, key=lambda r: r[1]["mdd"])
        worst = max(rows, key=lambda r: r[1]["mdd"])
        if best[0] == worst[0]:
            continue
        b, w = best[1], worst[1]
        flag = ""
        if w["p"] < 0.05 and b["p"] >= 0.05 and abs(b["observed"]) < \
                0.5 * abs(w["observed"]):
            flag = "   <-- SMALL-SAMPLE OVERESTIMATE"
        print("  %-22s best-powered %s: %+.4f (mdd %.4f, p %.3f) | "
              "least-powered %s: %+.4f (mdd %.4f, p %.3f)%s"
              % (k, best[0], b["observed"], b["mdd"], b["p"],
                 worst[0], w["observed"], w["mdd"], w["p"], flag))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
