#!/usr/bin/env python3
"""Read #54's VRAM race probe off every soak that ever carried it.

The probe (`vk/draw.c`, `-DHAKUX_VRAM_RACE_PROBE=1`) appends one cumulative
field group to the `hakuX-perf` pacing line:

    Vr:<vtx_raced>/<vtx_copies>  Tr:<tex_raced>/<tex_uploads>/<tex_windows>  Xd:<impossible>

so the answer for a run is the LAST such line in its logcat and needs no
series reassembly.  This script finds every result directory on disk whose
logcat carries that group, groups the runs by title and by whether the ref
carries #44's skew bound, and judges #54's two registered legs against each
group rather than against a pool.

Three things it checks before it prints a number, because each is a way a
zero from this probe means nothing:

  * **The flip gate.**  `profile.c:600` gates the pacing line on
    `(frame_count % 60) == 0` in the flip path, so the probe cannot be read
    off a run that does not flip -- an absent `Vr:` reads exactly like "no
    races".  The `pace` column is the number of pacing lines seen, i.e. the
    run's guest frames / 60.  A run with a handful of them has no power and
    is flagged.
  * **The impossible row.**  `Xd` counts a range seen dirty and then seen
    clean by a second scan with nothing in between.  Nothing in the process
    clears those bits off this thread, so `Xd` must be exactly 0; non-zero
    indicts the instrument.  See `vram_range_dirty_checked()`.
  * **The denominators.**  `Vr` is per vertex-range copy and `Tr` is per
    upload -- both per-EVENT, not per-second, so neither is diluted by how
    busy the device was.  `tex_windows` is begin_pre_draw windows and is
    reported but never used as a denominator: a window in which no dirty
    bits were consumed is not a read.

Usage:
    docs/testing/vram_race_probe_sweep.py [--results DIR] [--csv OUT]

Exit 0 if every group agrees with #54's registered figures, 1 if any group
puts a leg outside them.  The exit code is the point: a leg that cannot fail
is not a leg.
"""

import argparse
import collections
import glob
import json
import math
import os
import re
import sys

PACE = re.compile(r"Vr:(\d+)/(\d+) Tr:(\d+)/(\d+)/(\d+) Xd:(\d+)")

# #54's registered figures, from 6 Galleon runs over 4 refs on both devices.
# Reproduced exactly by this script's `galleon / unbounded` group restricted
# to those refs, which is how the population behind them was identified.
REG_VR = 55 / 1009270          # 5.45e-05 per instrumented vertex-range copy
REG_TR_BOUND = 3 / 56131       # 5.35e-05, the rule-of-three bound on Tr = 0

# Refs that carry #44's selective skew bound.  The probe and the bound are
# independent knobs and pooling across them mixes two populations: the bound
# removes the very window the probe measures.  territory.toml records the
# three tip-based arm refs as "probe-on, bound 0/1/2".
BOUNDED_REFS = {
    "d879e6e03b": "mode 2",
    "7349193309": "mode 1",
    "3b7fe5f5fa": "mode 2",
}

# A run with fewer pacing lines than this has too few flips for its zeros to
# mean anything.  Every run on disk today clears it by a wide margin; the
# check exists so that a future short run is not read as a clean result.
MIN_PACE_LINES = 10


def pois_le(k, lam):
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def pois_ge(k, lam):
    return 1.0 - (pois_le(k - 1, lam) if k > 0 else 0.0)


def pois_p(k, lam):
    """One-sided tail probability of k on the side it actually fell."""
    if lam <= 0:
        return float("nan")
    return pois_le(k, lam) if k < lam else pois_ge(k, lam)


def short_title(t):
    if not t:
        return "?"
    return re.split(r"[ (]", t)[0]


def collect(results_dir):
    runs = []
    skipped = []
    for lc in sorted(glob.glob(os.path.join(results_dir, "*", "logcat.txt"))):
        d = os.path.dirname(lc)
        with open(lc, errors="replace") as fh:
            hits = PACE.findall(fh.read())
        if not hits:
            continue
        # An in-flight run has a growing logcat and no result.json, so its
        # last pacing line is a truncated sample of a cumulative counter.
        # Pooling it understates every rate.  The dispatcher writes DONE when
        # the run completes; wait for it.
        if not os.path.exists(os.path.join(d, "DONE")):
            skipped.append(os.path.basename(d))
            continue

        def load(name):
            try:
                with open(os.path.join(d, name)) as fh:
                    return json.load(fh)
            except Exception:
                return {}

        res, req = load("result.json"), load("request.json")
        vr, vc, tr, tu, tw, xd = (int(x) for x in hits[-1])
        ref = (res.get("ref") or req.get("ref") or "?")[:10]
        runs.append(dict(
            id=os.path.basename(d),
            title=short_title(res.get("title") or req.get("title")),
            ref=ref,
            mode=BOUNDED_REFS.get(ref, "unbounded"),
            device=res.get("device_label", "?"),
            seconds=res.get("seconds", req.get("seconds", 0)),
            pace=len(hits),
            vr=vr, vc=vc, tr=tr, tu=tu, tw=tw, xd=xd,
        ))
    return runs, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results",
                    default=os.path.expanduser("~/hakux-work/dispatch/results"))
    ap.add_argument("--csv")
    args = ap.parse_args()

    runs, skipped = collect(args.results)
    if not runs:
        print("no probe-on soak found under %s" % args.results)
        return 1

    runs.sort(key=lambda r: (r["title"], r["mode"], r["ref"]))

    print("#54 VRAM RACE PROBE -- every probe-on run on disk (%d runs)" % len(runs))
    if skipped:
        print("  skipped %d in-flight run(s) with no DONE marker: %s"
              % (len(skipped), ", ".join(skipped)))
    print()
    hdr = ("%-9s %-10s %-11s %-5s %4s %5s   %5s/%-9s %9s   %7s/%-8s %8s  %3s"
           % ("title", "ref", "bound", "dev", "s", "pace",
              "Vr", "vtx_rd", "Vr rate", "Tr", "uploads", "Tr rate", "Xd"))
    print(hdr)
    print("-" * len(hdr))
    for r in runs:
        vrate = r["vr"] / r["vc"] if r["vc"] else float("nan")
        trate = r["tr"] / r["tu"] if r["tu"] else float("nan")
        print("%-9s %-10s %-11s %-5s %4s %5d   %5d/%-9d %9.2e   %7d/%-8d %8.5f  %3d"
              % (r["title"][:9], r["ref"], r["mode"], r["device"], r["seconds"],
                 r["pace"], r["vr"], r["vc"], vrate, r["tr"], r["tu"], trate,
                 r["xd"]))

    problems = []

    # --- instrument controls, before any number above is allowed to mean
    # anything ------------------------------------------------------------
    print()
    print("INSTRUMENT CONTROLS")
    bad_xd = [r for r in runs if r["xd"]]
    print("  impossible row Xd == 0 .......... %s (%d/%d runs)"
          % ("PASS" if not bad_xd else "FAIL", len(runs) - len(bad_xd), len(runs)))
    for r in bad_xd:
        problems.append("Xd=%d on %s -- the instrument, not the emulator"
                        % (r["xd"], r["id"]))
    thin = [r for r in runs if r["pace"] < MIN_PACE_LINES]
    print("  flip gate: >= %d pacing lines ... %s (min %d, max %d)"
          % (MIN_PACE_LINES, "PASS" if not thin else "FAIL",
             min(r["pace"] for r in runs), max(r["pace"] for r in runs)))
    for r in thin:
        problems.append("only %d pacing lines on %s -- too few flips to read a zero"
                        % (r["pace"], r["id"]))

    # --- the two legs, judged per (title, bound mode) --------------------
    groups = collections.OrderedDict()
    for r in runs:
        groups.setdefault((r["title"], r["mode"]), []).append(r)

    print()
    print("LEG 1 -- Vr against the registered 5.45e-05 per instrumented read")
    for (title, mode), rs in groups.items():
        vr = sum(r["vr"] for r in rs)
        vc = sum(r["vc"] for r in rs)
        if not vc:
            continue
        lam = REG_VR * vc
        p = pois_p(vr, lam)
        verdict = "consistent"
        if p < 0.01:
            verdict = "OUTSIDE"
            problems.append("Vr on %s/%s is %.2e against 5.45e-05 (p=%.1e)"
                            % (title, mode, vr / vc, p))
        print("  %-9s %-11s %2d run(s)  Vr=%3d/%-9d = %9.2e  expect %8.2f  p=%8.1e  %s"
              % (title, mode, len(rs), vr, vc, vr / vc, lam, p, verdict))

    print()
    print("LEG 2 -- Tr against the registered 5.35e-05 one-sided bound")
    for (title, mode), rs in groups.items():
        tr = sum(r["tr"] for r in rs)
        tu = sum(r["tu"] for r in rs)
        if not tu:
            continue
        rate = tr / tu
        note = "rule-of-3 <= %.2e" % (3 / tu)
        if rate > REG_TR_BOUND:
            note = "ABOVE the bound by %.0fx" % (rate / REG_TR_BOUND)
            problems.append("Tr on %s/%s is %.5f, %.0fx the 5.35e-05 bound"
                            % (title, mode, rate, rate / REG_TR_BOUND))
        print("  %-9s %-11s %2d run(s)  Tr=%6d/%-8d = %8.5f  %s"
              % (title, mode, len(rs), tr, tu, rate, note))

    if args.csv:
        import csv
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(runs[0].keys()))
            w.writeheader()
            w.writerows(runs)
        print("\nwrote %s" % args.csv)

    print()
    if problems:
        print("VERDICT: %d group(s) fall outside #54's registered figures." % len(problems))
        for p in problems:
            print("  - %s" % p)
        print()
        print("  The registered figures are GALLEON figures. Neither leg names a")
        print("  title, and the rate is a property of the workload -- so a leg")
        print("  read across titles fails for a reason that is not about the")
        print("  probe. See docs/investigations/vram-race-frequency-is-per-title.md.")
        return 1
    print("VERDICT: every group agrees with #54's registered figures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
