#!/usr/bin/env python3
"""Correlate a frame dump's per-draw schedule against its stipple frames (#77).

    framedump_correlate.py DUMP.jsonl [--images DIR] [--region X0,Y0,X1,Y1]
                           [--window 10] [--ratio 1.45] [--perms 10000]
                           [--json OUT]

#77 is left suspecting the SCHEDULE -- draw merging, deferred submission, a
missing barrier -- because the instrument it had destroyed exactly that
behaviour.  PR #143 built one that does not.  This asks the question that was
then left: within one dump, does any schedule counter read differently on a
stipple frame than on a clean one?

THE PRECONDITION COMES FIRST AND IT IS NOT A FORMALITY.  A counter that takes
one value across every frame of the dump cannot correlate with anything, and
reporting "no difference found" from it would be reporting an inert control --
a leg that could not have come out the interesting way.  So F0 partitions the
candidate counters into VARYING and CONSTANT before any comparison is made,
names every constant one with the value it is stuck at, and refuses to score
it.  If every candidate is constant the verdict is NOT VISIBLE TO THIS
INSTRUMENT, and that is a measured verdict rather than a shrug.

Two of the constants are constant BY CONSTRUCTION rather than by observation,
and the difference matters: `dq`/`dq_active`/`rw`/`rw_active` are the draw
queue and reorder window, which `draw_merge` and `draw_reorder` gate, and both
prefs default false.  The session header records them and this refuses to
describe any merging verdict as measured when they are off.

EVERY LEG IS TESTED AGAINST A PERMUTATION NULL.  With ~50 classified frames
and a handful of them flagged, some statistic will separate some subset; the
guard is to recompute each statistic over many random relabellings holding the
class sizes fixed, and report the observed separation against that.  And every
null result is published WITH THE SMALLEST DIFFERENCE IT COULD HAVE DETECTED,
computed from the same null -- "we found nothing" is not a result without it.

Exit status:
    0   ran, and reported a verdict (positive, negative, or not-visible)
    1   the dump cannot be read, or its images cannot be paired with its
        records (schema < 3)
    2   usage
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))

import stipple_classify as sc  # noqa: E402

SCHEMA_IMAGES_PAIRABLE = 3
IMG_STALE = -2

# Counters gated by a pref this lane cannot set.  Named so a flat reading of
# them is never published as "measured and no difference found".
MERGE_GATED = {"max_dq", "max_dq_active", "max_rw", "max_rw_active"}


def load(path):
    session, draws, frames, end, bad = None, [], [], None, 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            k = rec.get("t")
            if k == "session":
                session = rec
            elif k == "draw":
                draws.append(rec)
            elif k == "frame":
                frames.append(rec)
            elif k == "end":
                end = rec
    return session, draws, frames, end, bad


def frame_counters(frame, draws):
    """The per-frame candidate set, fixed in NOTES.md before any dump existed.

    One dict per frame, one key per counter.  Derived quantities only where the
    raw column would be dominated by something else: `cb_reset_count` rather
    than max(cb_draws), because max(cb_draws) is essentially the frame's draw
    count and would correlate with scene complexity rather than with schedule.
    """
    n = len(draws) or 1
    cb = [d.get("cb_draws") for d in draws if isinstance(d.get("cb_draws"), int)]
    # A command buffer reset mid-frame: cb_draws goes down instead of up.
    resets = sum(1 for a, b in zip(cb, cb[1:]) if b <= a)
    lag = [d["submits"] - t["submit_time"]
           for d in draws for t in d.get("tex", [])
           if t.get("en") and t.get("submit_time") is not None
           and isinstance(d.get("submits"), int)]
    return dict(
        submits_in_frame=float(frame.get("submits_in_frame") or 0),
        cb_resets=float(resets),
        cb_resets_per_draw=resets / n,
        frac_not_in_rp=sum(1 for d in draws if d.get("in_rp") == 0) / n,
        frac_color_clean=sum(1 for d in draws
                             if (d.get("color") or {}).get("dirty") == 0) / n,
        max_dq=float(max((d.get("dq", 0) for d in draws), default=0)),
        max_dq_active=float(max((d.get("dq_active", 0) for d in draws),
                                default=0)),
        max_rw=float(max((d.get("rw", 0) for d in draws), default=0)),
        max_rw_active=float(max((d.get("rw_active", 0) for d in draws),
                                default=0)),
        mean_submit_lag=float(np.mean(lag)) if lag else 0.0,
        max_submit_lag=float(max(lag)) if lag else 0.0,
        draws=float(len(draws)),
    )


def permutation_test(values, labels, perms, rng):
    """Difference in means, against a null that reshuffles the labels.

    Returns (observed, p_two_sided, mdd) where mdd -- the minimum detectable
    difference -- is the 95th percentile of |null|: the smallest observed
    separation this many frames in these class sizes could have distinguished
    from chance at p < 0.05.  It is what makes a null result reportable.
    """
    values = np.asarray(values, dtype=float)
    labels = np.asarray(labels, dtype=bool)
    k = int(labels.sum())
    if k == 0 or k == len(labels):
        return float("nan"), float("nan"), float("nan")
    obs = float(values[labels].mean() - values[~labels].mean())
    idx = np.arange(len(values))
    null = np.empty(perms)
    for i in range(perms):
        pick = rng.permutation(idx)[:k]
        m = np.zeros(len(values), dtype=bool)
        m[pick] = True
        null[i] = values[m].mean() - values[~m].mean()
    p = float((np.abs(null) >= abs(obs) - 1e-12).mean())
    mdd = float(np.percentile(np.abs(null), 95))
    return obs, p, mdd


def texture_state_map(draws):
    """guest texture state -> set of host VkImage handles, over enabled stages.

    F2's observable.  A stale binding is the same guest request answered with a
    different host image, or the same host image behind a changed request.
    """
    m = {}
    for d in draws:
        for t in d.get("tex", []):
            if not t.get("en"):
                continue
            key = (t.get("fmt"), t.get("off"), t.get("addr"),
                   t.get("ctl0"), t.get("ctl1"), t.get("fil"))
            m.setdefault(key, set()).add(t.get("img"))
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump")
    ap.add_argument("--images", help="directory holding the dump's PPMs "
                                     "(default: the dump's own directory)")
    ap.add_argument("--region", metavar="X0,Y0,X1,Y1")
    ap.add_argument("--window", type=int, default=sc.DEFAULT_WINDOW)
    ap.add_argument("--ratio", type=float, default=sc.DEFAULT_RATIO)
    ap.add_argument("--perms", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260919)
    ap.add_argument("--json", metavar="OUT")
    args = ap.parse_args(argv)

    session, draws, frames, end, bad = load(args.dump)
    if session is None:
        print("no session header: this is not a frame dump")
        return 1
    schema = session.get("schema")
    print("session   id=%s spec=%r schema=%s draw_merge=%s draw_reorder=%s"
          % (session.get("id"), session.get("spec"), schema,
             session.get("draw_merge"), session.get("draw_reorder")))
    print("          driver=%s" % session.get("driver"))
    print("frames    %d recorded, %d draws%s"
          % (len(frames), len(draws),
             "" if not bad else ", %d unparseable line(s)" % bad))

    by_f = {}
    for d in draws:
        by_f.setdefault(d.get("f"), []).append(d)
    counters = {f.get("f"): frame_counters(f, by_f.get(f.get("f"), []))
                for f in frames}
    keys = sorted(next(iter(counters.values())).keys()) if counters else []

    # ------------------------------------------------------------------ F0
    print("\n== F0: which candidate counters can vary at all ==")
    varying, constant = [], []
    for k in keys:
        vals = {counters[f][k] for f in counters}
        (varying if len(vals) > 1 else constant).append(
            (k, sorted(vals)[:6], len(vals)))
    for k, vals, n in constant:
        why = ("CONSTANT BY CONSTRUCTION: draw_merge/draw_reorder are off, so "
               "this counter is gated shut" if k in MERGE_GATED
               else "constant over every frame of this dump")
        print("  EXCLUDED  %-22s = %-10s  %s" % (k, vals[0], why))
    for k, vals, n in varying:
        print("  scored    %-22s %d distinct values, %s%s"
              % (k, n, vals, " ..." if n > 6 else ""))
    if not varying:
        print("\nVERDICT: NOT VISIBLE TO THIS INSTRUMENT.  Every candidate "
              "counter is constant across all %d frames, so no correlation "
              "with any frame classification is possible -- the merge/barrier "
              "hypothesis has no observable attached to it in this build, "
              "which is a different finding from 'looked and found nothing'."
              % len(frames))
        return 0

    # ------------------------------------------------- the classification
    if not isinstance(schema, int) or schema < SCHEMA_IMAGES_PAIRABLE:
        print("\nREFUSED: schema %s images are not pairable with the draw "
              "records they are filed under (see framedump_check.py).  F0 "
              "above is sound -- it reads only records -- but no frame "
              "classification from this dump may be joined to them." % schema)
        return 1

    idir = args.images or os.path.dirname(os.path.abspath(args.dump))
    imaged = [f for f in frames
              if f.get("image") and f.get("img_sync") != IMG_STALE]
    stale = [f for f in frames if f.get("img_sync") == IMG_STALE]
    print("\n== classification ==")
    print("  %d of %d frames wrote a pairable image; %d were refused as stale"
          % (len(imaged), len(frames), len(stale)))
    if len(imaged) < 4:
        print("\nNO CLASSIFICATION POSSIBLE: %d usable image(s).  F0's varying "
              "counters are real and are reported above, but nothing can be "
              "correlated against them from this dump." % len(imaged))
        return 0
    gaps = np.diff([f["f"] for f in imaged])
    print("  image frames span f%d..f%d, median gap %.0f frames"
          % (imaged[0]["f"], imaged[-1]["f"], float(np.median(gaps))))
    if float(np.median(gaps)) > 1:
        print("  NOTE the local baseline below is over IMAGED frames, not "
              "consecutive ones: a +-%d-image window spans about %.0f guest "
              "frames.  That is a wider baseline than the classifier was "
              "validated at, and it is the right way round -- a wider window "
              "is a more robust median -- but a scene change inside it would "
              "not be removed by it."
              % (args.window, args.window * 2 * float(np.median(gaps))))

    from galleon_flash_rate import load_frames  # noqa: E402
    region = tuple(int(x) for x in args.region.split(",")) if args.region \
        else None
    paths = [os.path.join(idir, f["image"]) for f in imaged]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        print("\nREFUSED: %d image(s) named in the records are not on disk "
              "(first: %s).  A partial pull classified as a whole one is how "
              "a rate gets measured against the wrong denominator."
              % (len(missing), os.path.basename(missing[0])))
        return 1
    pix = load_frames(paths, None, region)
    rows = sc.classify(pix, args.window, args.ratio)
    for r, f in zip(rows, imaged):
        r["dump_frame"] = f["f"]
    flagged = [r for r in rows if r["stipple"]]
    print("  region %s: STIPPLE %d / %d = %.1f per 100  frames %s"
          % (region or "whole frame", len(flagged), len(rows),
             100.0 * len(flagged) / len(rows),
             [r["dump_frame"] for r in flagged]))
    for r in flagged:
        print("    f%-4d HF %6.2f  base %6.2f  ratio %5.2f  d1/d2 %5.2f "
              "(local %5.2f, dev %5.2f)"
              % (r["dump_frame"], r["hf"], r["base"], r["ratio"],
                 r["d_ratio"], r["d_base"], r["d_dev"]))

    labels = np.array([r["stipple"] for r in rows], dtype=bool)
    out = dict(dump=os.path.basename(args.dump), session=session.get("id"),
               schema=schema, frames=len(frames), draws=len(draws),
               region=list(region) if region else None,
               imaged=len(imaged), stale=len(stale),
               constant=[k for k, _, _ in constant],
               varying=[k for k, _, _ in varying],
               stipple=[r["dump_frame"] for r in flagged],
               rows=rows, legs={})

    if not flagged:
        print("\nNO STIPPLE FRAME IN THIS DUMP at the founding magnitude "
              "(%.2fx a local median).  The correlation is not computable, "
              "and that is a statement about what an unattended soak RENDERS "
              "-- not evidence for or against the merge/barrier hypothesis.  "
              "F0's varying counters stand and are reported above."
              % args.ratio)
        if args.json:
            json.dump(out, open(args.json, "w"), indent=1)
        return 0

    # --------------------------------------------------------- F1 .. F4
    print("\n== legs, against a %d-permutation null (class sizes held) =="
          % args.perms)
    rng = np.random.default_rng(args.seed)
    order = [r["dump_frame"] for r in rows]
    for k, _, _ in varying:
        vals = [counters[f][k] for f in order]
        obs, p, mdd = permutation_test(vals, labels, args.perms, rng)
        verdict = "SEPARATES" if p < 0.05 else "no separation"
        print("  %-22s stipple-clean %+8.4f   p %.4f   %s"
              % (k, obs, p, verdict))
        print("  %-22s   minimum detectable difference at these class sizes "
              "(%d vs %d): %.4f" % ("", len(flagged), len(rows) - len(flagged),
                                    mdd))
        out["legs"][k] = dict(observed=obs, p=p, mdd=mdd)

    # ------------------------------------------------------------- F2
    print("\n== F2: guest texture state -> host VkImage, per class ==")
    hot = texture_state_map([d for r in flagged
                             for d in by_f.get(r["dump_frame"], [])])
    cold = texture_state_map([d for r in rows if not r["stipple"]
                              for d in by_f.get(r["dump_frame"], [])])
    shared = set(hot) & set(cold)
    differing = [k for k in shared if hot[k] != cold[k]]
    multi = [k for k in hot if len(hot[k]) > 1]
    print("  %d guest texture states on stipple frames, %d on clean, %d shared"
          % (len(hot), len(cold), len(shared)))
    print("  shared states answered by a DIFFERENT host image: %d"
          % len(differing))
    print("  guest states answered by more than one host image on a stipple "
          "frame: %d" % len(multi))
    if not differing and not multi:
        print("  -> no stale-binding signature: every guest texture state that "
              "appears in both classes was answered by the same host image.")
    else:
        for k in differing[:5]:
            print("     state %s: stipple %s, clean %s" % (k, hot[k], cold[k]))
    out["legs"]["f2_states_differing"] = len(differing)
    out["legs"]["f2_states_multi_image_on_stipple"] = len(multi)

    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)
        print("\nwrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
