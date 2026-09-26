#!/usr/bin/env python3
"""#79 / #44 falsifier: is the Stencil flake observable still ALIVE on the
runs we have, or has it gone the way of the Texture border one?

#79 says Stencil is nondeterministic -- 9 of 16 captures change value between
runs of the SAME binary -- and that #44's skew bound fixes it (7 wrong of 64
observations -> 0 of 64).  #44 then carries the caveat that both #79 arm refs
are 292 commits behind the tip, and separately records that the OTHER disc
observable it was relying on (`2D_BorderTex_SZ` stale_px) went DEAD: 6 of 10
runs non-zero at a 128-commit-old floor, 2 of 10 at a fresh arm, 0 of 10 at
the tip, while the race was still live on a real title.

That is the trap this script exists to avoid repeating.  A shipping decision
that cites "7 of 64 Stencil captures rendered wrong" needs to know whether
that rate is a property of the defect or a property of a stale binary.

FALSIFIER SHAPE.  If the Stencil observable were still live at recent refs,
then grouping every Stencil run on disk by ref and comparing same-ref runs
pairwise would show captures whose differing-pixel count changes between runs
of one binary.  If every recent same-ref pair agrees exactly, the observable
is dead there -- and a future arm B reading "0 of 64 wrong" would be passed by
luck, exactly as #44's V1 was.

This is not forced true by anything here: the script reads scores written by
the device before the question was asked, and it reports the negative outcome
(no same-ref pairs available) as a failure of the instrument rather than as
evidence of stability.
"""
import csv, glob, json, os, sys, collections

R = "/home/justin/hakux-work/dispatch/results"


def main():
    # Group Stencil scores by (ref, apk_sha) -- a same-binary replicate is the
    # only pair in which a difference means nondeterminism rather than a code
    # change.  apk_sha is included because ref alone has been wrong before:
    # after a rebase the sha is not the patch.
    groups = collections.defaultdict(dict)
    for f in sorted(glob.glob(R + "/*/scores*.tsv")):
        d = os.path.dirname(f)
        run = os.path.basename(d)
        rj = os.path.join(d, "result.json")
        ref = apk = None
        if os.path.exists(rj):
            try:
                j = json.load(open(rj))
                ref, apk = j.get("ref"), j.get("apk_sha")
            except Exception:
                pass
        rows = {}
        for r in csv.DictReader(open(f), delimiter="\t"):
            if r["suite"] == "Stencil":
                rows[r["test"]] = int(r["differing"])
        if rows:
            groups[(str(ref), str(apk))][run + ":" + os.path.basename(f)] = rows

    print("=== STENCIL SCORE SETS ON DISK, GROUPED BY (ref, apk_sha)")
    live, dead, single = [], [], []
    for (ref, apk), runs in sorted(groups.items()):
        names = sorted(runs)
        if len(names) < 2:
            single.append((ref, apk, names[0], len(runs[names[0]])))
            continue
        keys = set(runs[names[0]])
        for n in names[1:]:
            keys &= set(runs[n])
        unstable = []
        for k in sorted(keys):
            vals = [runs[n][k] for n in names]
            if len(set(vals)) > 1:
                unstable.append((k, vals))
        entry = (ref, apk, len(names), len(keys), unstable)
        (live if unstable else dead).append(entry)

    def show(title, entries):
        print()
        print(title)
        if not entries:
            print("  (none)")
        for ref, apk, nruns, ncaps, unstable in entries:
            print("  ref %-12s apk %-14s runs=%d caps=%d  UNSTABLE=%d"
                  % (str(ref)[:12], str(apk)[:14], nruns, ncaps, len(unstable)))
            for k, vals in unstable[:16]:
                print("       %-34s %s" % (k, vals))

    show("=== OBSERVABLE ALIVE (same binary, captures disagree between runs)", live)
    show("=== OBSERVABLE DEAD HERE (same binary, every capture identical)", dead)

    print()
    print("=== REFS WITH ONLY ONE STENCIL RUN (cannot say either way)")
    print("count: %d" % len(single))
    for ref, apk, run, n in single[:20]:
        print("  ref %-12s %-46s caps=%d" % (str(ref)[:12], run[:46], n))
    if len(single) > 20:
        print("  ... %d more" % (len(single) - 20))

    print()
    print("=== WHAT THIS DOES AND DOES NOT ESTABLISH")
    print("A ref in the DEAD list is a ref at which a future arm B reading")
    print("'0 of N wrong' proves nothing, because arm A would read 0 too.")
    print("A ref in the SINGLE list is not evidence of stability: one run")
    print("cannot disagree with itself.  That distinction is the whole point;")
    print("#44's V1 leg was passed by luck for exactly the missing-control")
    print("reason, and was recorded as DEAD only after a paired re-score.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
