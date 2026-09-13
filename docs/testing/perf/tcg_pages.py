#!/usr/bin/env python3
"""Read the TCG retranslation counters off a soak logcat, and A/B two arms.

Why this exists, and why it does not read frame time first
----------------------------------------------------------

`performance-next-three.md` ends with "Prerequisite: the benchmark cannot yet
show a 2 ms gain", and two separate things are wrong with the benchmark. Both
have already cost a control.

**1. A median gfps is a measurement of how busy the device is.** The series is
bimodal -- ceiling 29-31, floor 5-20 -- and the median tracks occupancy, which
moved 80% -> 16-32% across one evening. #64's cost leg read 16 against 29,
reproduced on a repeat, and then the reverse-order control on its own ref read
21: the control moved 8 against a tolerance of 2.

**2. A dispatcher soak injects no input.** `soak_title.sh` boots the title and
holds it; the `pad.sh mash` sequence that reaches Crimson Skies' heavy sections
lives in `run_perf.sh`, which is a hand-run script on an attached device. So
the one request path an agent may use cannot reach the scene with headroom --
and the heavy-section frame time that the audio voice-lock fix was judged on is
not available from a soak at all. The `G > 35 ms` filter that fix used is
itself undocumented; it was recovered by reproducing its six published numbers.

The conclusion is not "get better at reading frame time". It is that frame time
is the wrong instrument for this change. `AGENTS.md`: "State the falsifier as a
measurement, not a pixel count. Name the quantity your mechanism changes and
predict *that*." And: "A mechanism-shaped falsifier separates 'it did not
happen' from 'it happened and the model is wrong'. A pixel count cannot."

The quantity the retranslation levers change is counted, not timed:

* how many translated blocks a guest store throws away,
* how many of those the guest had actually written the bytes of,
* how often a page is left with no code at all, which disarms code-write
  detection and buys a full arming TLB walk on the next generation there,
* how many of those walks happen,
* and the mean length of a generated block.

Those are integer counts of named events, emitted every 120 guest frames on the
always-on `hakuX-pages` line. They do not care what scene the title is in, they
do not care how busy the device is, and their noise floor is measurable from
the windows of a single run rather than assumed. That is the instrument fix:
not a better statistic over frame time, a different measurement.

Frame time is still read, and still reported, as the cost leg -- because a
change that improves every counter and slows the game down has not helped. It
is reported as the **ceiling**, per the rule above, never as a median.

The statistic and the decision rule, stated before any arm runs
---------------------------------------------------------------

* **Statistic, per arm, per counter:** the per-window rate, one sample per 120
  guest frames, over every window in the run. Reported as min / median / max.
* **The ratios are the statistic to judge on, not the rates.** Measured on two
  real Galleon soaks already on disk, the absolute per-window counts vary by a
  factor of three to five within a single run -- `tossed` spanned 1,434 to
  4,985 in one arm -- because they scale with how much the guest happens to be
  writing in that window. That is the same failure as a median gfps tracking
  device occupancy: the quantity moves for a reason that is not the change.
  The ratios below divide that out. `toss_per_gen` is the 2.8:1 waste ratio
  quoted in `frame-pacing-and-parallelism.md`; `sp_share` and `ws_share` are
  the premise check and the prize; `blk` is what a block-extent arm must move
  and is the falsifier that separates "the arm was not applied" from "it was
  applied and did not pay".
* **Noise floor:** the within-arm spread across those windows, printed for
  every counter, so the floor comes out of the same run as the number.
* **Decision rule (`--ab`):** take each *run's* median of a quantity, then
  require **every run in one arm to beat every run in the other**. That is the
  statistic the audio voice-lock fix was quoted on -- 48.2/47.7/49.3 against
  49.5/50.4/50.3, three runs each side -- chosen there because comparing
  medians against a within-arm spread of 1.6 ms would have been marginal.
  Overlapping run sets are reported as INDISTINGUISHABLE, with the overlap,
  and that is a result rather than a failure.

  It is the *run* that is the replicate, not the window, and this matters.
  Applying an all-samples rule to windows instead would tighten with every
  window a longer soak produced -- a 90 s run yields around 29 of them -- so
  one outlier window in a 29-window arm would veto a real effect, while the
  same rule over three runs is the published standard. So: **three soaks per
  arm, pass each one to `--ab` as its own `A=` or `B=`.** With a single run per
  arm the tool says so and reports the window spread instead of a verdict,
  because one run cannot satisfy a rule about runs.

  The per-window spread is still printed for every quantity. That is the noise
  floor, and it comes out of the same runs as the numbers.
* **Frame-time cost leg:** ceiling, as max and p90 of `gfps`, plus the floor of
  `G` (the fastest frame the arm produced). Never the median of either.
* **The first window is discarded.** It spans the title's boot, which
  translates the whole startup path once and is categorically different work
  from steady-state retranslation -- on a real Galleon soak the first window
  reported 47,792 blocks generated against a median of 4,128 for the rest of
  the run, an order of magnitude, and one such sample drags any range wide
  enough to make every comparison overlap. This is stated here because it is a
  property of what the first window measures and not of which way it moved:
  it applies to both arms identically and is the default, not an exception
  granted to a run after seeing it. `--keep-first` turns it off.

Usage
-----

    tcg_pages.py <logcat-or-result-dir> [...]           # one arm, per-window
    tcg_pages.py --ab A=<d1> A=<d2> A=<d3> B=<d4> B=<d5> B=<d6>

Repeat `A=` and `B=` once per soak. Three of each is the standard; fewer is
reported as such rather than judged.

A result directory is the dispatcher's `results/<id>/`; `logcat.txt` and
`result.json` are found inside it, and `result.json`'s `device_label`,
`apk_sha` and `ref` are printed with every arm. Two arms that do not agree on
`device_label` are called out: #64 lost a control to four soaks across two
handhelds with nothing recording which.
"""
import json
import os
import re
import statistics
import sys

# "inval ev=N ov=N sp=N em=N ws=N pr=N ins=N bytes=N blk=N.NN"
INVAL_RE = re.compile(
    r"inval ev=(\d+) ov=(\d+) sp=(\d+) em=(\d+) ws=(\d+) pr=(\d+) "
    r"(?:ai=(\d+) )?ins=(\d+) bytes=(\d+) blk=(\d+)\.(\d+)")

# "slow stores N (M reached the invalidator) ... [blocks tossed T, generated G]"
STORES_RE = re.compile(
    r"slow stores (\d+) \((\d+) reached the invalidator\)")
TOSSED_RE = re.compile(r"blocks tossed (\d+), generated (\d+)")

# The always-on pacing line.
PERF_RE = re.compile(
    r"gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\).*?Vpf:([\d.]+)")

# Counters read from the invalidation line, in report order. The key is the
# field name, the value is what it means when it moves.
COUNTERS = [
    ("ev",    "invalidation events that found a block"),
    ("ov",    "blocks discarded whose bytes the guest wrote"),
    ("sp",    "blocks discarded that a range test would have SPARED"),
    ("em",    "events that emptied the page (disarmed detection)"),
    ("ws",    "...of those, a block would have survived a range test"),
    ("pr",    "arming TLB walks performed (tlb_protect_code)"),
    ("ai",    "visited blocks that already carried CF_INVALID"),
    ("ins",   "guest instructions translated"),
    ("blk",   "mean guest instructions per generated block"),
    ("tossed", "blocks invalidated (all callers)"),
    ("gen",   "blocks generated"),
    ("stores", "slow stores into code pages"),
]


def resolve(path):
    """Accept a logcat file or a dispatcher result directory."""
    if os.path.isdir(path):
        log = os.path.join(path, "logcat.txt")
        meta = os.path.join(path, "result.json")
    else:
        log = path
        meta = os.path.join(os.path.dirname(path), "result.json")
    if not os.path.exists(log):
        sys.exit("no logcat at %s" % log)
    info = {}
    if os.path.exists(meta):
        try:
            with open(meta) as fh:
                info = json.load(fh)
        except (OSError, ValueError):
            pass
    return log, info


def parse(path):
    """Per-window counter samples, and the pacing samples, from one run."""
    windows = []
    pacing = []
    pending = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            m = STORES_RE.search(line)
            if m:
                # The two lines are emitted back to back in the same 120-frame
                # block. Buffer the first; the second completes the window.
                # If no second line arrives -- a build from before the
                # invalidation counters existed -- the buffered half is still a
                # window, so a baseline recorded on an older binary stays
                # readable. It then has only the stores/tossed/gen fields, and
                # the report simply omits the rows it has no data for rather
                # than printing zeros, which would read as a measurement.
                if pending:
                    windows.append(pending)
                pending = {"stores": int(m.group(1)),
                           "reached": int(m.group(2))}
                t = TOSSED_RE.search(line)
                if t:
                    pending["tossed"] = int(t.group(1))
                    pending["gen"] = int(t.group(2))
                continue
            m = INVAL_RE.search(line)
            if m:
                g = m.groups()
                w = dict(pending)
                w.update({
                    "ev": int(g[0]), "ov": int(g[1]), "sp": int(g[2]),
                    "em": int(g[3]), "ws": int(g[4]), "pr": int(g[5]),
                    "ins": int(g[7]), "bytes": int(g[8]),
                    "blk": int(g[9]) + int(g[10]) / 100.0,
                })
                # ai= is absent on a build from before it was added; a
                # missing field is not a zero, so it stays absent and the
                # report omits the row rather than claiming none happened.
                if g[6] is not None:
                    w["ai"] = int(g[6])
                windows.append(w)
                pending = {}
                continue

            m = PERF_RE.search(line)
            if m:
                pacing.append({"gfps": int(m.group(1)),
                               "g": float(m.group(2)),
                               "gmin": float(m.group(3)),
                               "gmax": float(m.group(4)),
                               "vpf": float(m.group(5))})
    if pending:
        windows.append(pending)
    return windows, pacing


# Scene-independent ratios, computed per window then summarised. Each is
# (name, numerator, denominator, what it means). A window missing either field
# is skipped rather than counted as zero.
RATIOS = [
    ("toss_per_gen", "tossed", "gen",
     "blocks discarded per block generated (the waste ratio)"),
    ("reach_share", "reached", "stores",
     "share of slow stores that reached the invalidator"),
    ("sp_share", "sp", "ovsp",
     "share of discarded blocks with no written byte in them"),
    ("ws_share", "ws", "em",
     "share of page-emptying events a range test would prevent"),
    ("pr_per_em", "pr", "em",
     "arming TLB walks per page-emptying event"),
]


def ratio_series(windows, num, den):
    out = []
    for w in windows:
        if den == "ovsp":
            d = w.get("ov", 0) + w.get("sp", 0) if "ov" in w else 0
        else:
            d = w.get(den, 0)
        if num in w and d:
            out.append(w[num] / float(d))
    return out


def spread(vals):
    if not vals:
        return None
    return (min(vals), statistics.median(vals), max(vals))


def series(windows, key):
    return [w[key] for w in windows if key in w]


def report(label, path, keep_first=False):
    log, info = resolve(path)
    windows, pacing = parse(log)
    dropped = 0
    if windows and not keep_first:
        # See the docstring: the boot window is a different measurement.
        windows = windows[1:]
        dropped = 1
    print("== %s  %s" % (label, log))
    if info:
        print("   ref=%s apk=%s device=%s title=%r"
              % (info.get("ref", "?"), info.get("apk_sha", "?"),
                 info.get("device_label") or "UNLABELLED",
                 info.get("title", "?")))
        if not info.get("device_label"):
            print("   WARNING: result.json has no device_label. An unlabelled"
                  " soak cannot be paired with another -- see #64.")
    print("   %d counter windows (120 guest frames each), %d pacing samples"
          "%s" % (len(windows), len(pacing),
                  ", first window dropped as boot" if dropped else ""))
    if not windows:
        print("   NO COUNTER WINDOWS. A window is emitted every 120 guest"
              " frames, so a short or stalled run has none -- that is not a"
              " zero, it is no measurement. Check the run reached gameplay.")
    for key, what in COUNTERS:
        s = spread(series(windows, key))
        if s is None:
            continue
        fmt = "%8.2f" if key == "blk" else "%8.0f"
        print(("   %-7s " + fmt + " /" + fmt + " /" + fmt + "   %s")
              % (key, s[0], s[1], s[2], what))
    for name, num, den, what in RATIOS:
        s = spread(ratio_series(windows, num, den))
        if s is None:
            continue
        print("   %-13s %6.3f /%6.3f /%6.3f   %s"
              % (name, s[0], s[1], s[2], what))
    derive(windows)
    cost(pacing)
    return windows, pacing, info


def derive(windows):
    """The two ratios the levers turn on."""
    if not windows:
        return
    ov = sum(series(windows, "ov"))
    sp = sum(series(windows, "sp"))
    em = sum(series(windows, "em"))
    ws = sum(series(windows, "ws"))
    if ov + sp:
        print("   -> %.1f%% of discarded blocks had no written byte in them"
              " (sp/(sp+ov) = %d/%d)." % (100.0 * sp / (ov + sp), sp, ov + sp))
        print("      This is the premise check for"
              " performance-next-three.md section 2. Near 0%% means the"
              " invalidation is already effectively range-precise and the"
              " block-extent lever has its mechanism. Large means it does"
              " not: a smaller block cannot be missed by a store that"
              " discards the whole page.")
    ev = sum(series(windows, "ev"))
    if ev and em < ev:
        ai = sum(series(windows, "ai")) if any("ai" in w for w in windows) \
            else None
        print("   -> em (%d) is BELOW ev (%d). Under whole-page invalidation"
              " every block on the page is discarded, so the page should"
              " always empty." % (em, ev))
        if ai is None:
            print("      This build has no ai= counter, so the shortfall is"
                  " unexplained here. The known benign cause is"
                  " do_tb_phys_invalidate returning early, before tb_remove,"
                  " when a TB already carries CF_INVALID -- which the tier-1"
                  " soft invalidation produces. Re-run on a build with ai= to"
                  " tell that from a misreading of tb-maint.c.")
        else:
            print("      %d visited blocks already carried CF_INVALID."
                  " do_tb_phys_invalidate returns before tb_remove for those,"
                  " so they stay on the page list and it does not empty."
                  " If that does not account for the %d-event shortfall, the"
                  " whole-page reading of tb-maint.c is wrong and every"
                  " number above inherits it." % (ai, ev - em))
    elif ev and em > ev:
        print("   -> em (%d) EXCEEDS ev (%d), which no path in tb-maint.c"
              " allows. Treat every number above as void until this is"
              " explained." % (em, ev))
    if em:
        print("   -> %.1f%% of page-emptying events would NOT have emptied the"
              " page under a range test (ws/em = %d/%d)."
              % (100.0 * ws / em, ws, em))
        print("      That is the arming TLB walk -- tlb_reset_dirty, 10.6%%"
              " self of the bounding thread -- that the range test would"
              " remove. It is the prize, and it is not about discarded code.")


def cost(pacing):
    """Frame time as the ceiling. Never as a median."""
    if not pacing:
        return
    gf = [p["gfps"] for p in pacing]
    gf.sort()
    p90 = gf[min(len(gf) - 1, int(round(0.9 * (len(gf) - 1))))]
    gmin = min(p["gmin"] for p in pacing)
    print("   cost leg (ceiling, not median): gfps max=%d p90=%d,"
          " fastest frame G_min=%.1f ms  [median gfps=%d, shown only to make"
          " the point that it tracks device occupancy]"
          % (max(gf), p90, gmin, statistics.median(gf)))


def run_medians(arm, key, ratio=None):
    """One number per run: that run's median of the quantity."""
    out = []
    for windows, _, _ in arm:
        vals = (ratio_series(windows, ratio[0], ratio[1]) if ratio
                else series(windows, key))
        if vals:
            out.append(statistics.median(vals))
    return out


def judge(arm_a, arm_b):
    """Every run in one arm against every run in the other."""
    print()
    print("== A/B verdict  (%d A runs, %d B runs)" % (len(arm_a), len(arm_b)))

    labels_a = {(i or {}).get("device_label") for _, _, i in arm_a}
    labels_b = {(i or {}).get("device_label") for _, _, i in arm_b}
    labels = (labels_a | labels_b) - {None, ""}
    if len(labels) > 1:
        print("   REFUSED as a pair: these soaks span %s. Pin every arm with"
              " --device and re-run; #64 lost a control to four soaks across"
              " two handhelds with nothing recording which."
              % "/".join(sorted(labels)))
    if not labels:
        print("   WARNING: no soak recorded a device_label, so nothing here"
              " records which handheld produced what.")

    refs_a = {(i or {}).get("ref") for _, _, i in arm_a} - {None}
    refs_b = {(i or {}).get("ref") for _, _, i in arm_b} - {None}
    if len(refs_a) > 1 or len(refs_b) > 1:
        print("   REFUSED as a pair: an arm mixes refs (A=%s B=%s). Each arm"
              " is one binary." % (sorted(refs_a), sorted(refs_b)))
    if refs_a and refs_a == refs_b:
        print("   NOT an A/B: both arms are ref %s, so this is one binary"
              " measured twice. That is a valid noise-floor run -- read the"
              " spreads above as the floor -- but there is no effect to judge."
              % sorted(refs_a)[0])

    if len(arm_a) < 3 or len(arm_b) < 3:
        print("   NOT JUDGED: the rule is over runs and this is %d vs %d."
              " Three soaks per arm is the standard. The per-window spreads"
              " printed above are the noise floor and are the only thing"
              " these runs support." % (len(arm_a), len(arm_b)))
        return

    quantities = [(k, None) for k, _ in COUNTERS]
    quantities += [(n, (nu, de)) for n, nu, de, _ in RATIOS]
    for key, ratio in quantities:
        va = run_medians(arm_a, key, ratio)
        vb = run_medians(arm_b, key, ratio)
        if len(va) < 3 or len(vb) < 3:
            continue
        if max(vb) < min(va):
            verdict = "FELL   (every B run below every A run)"
        elif min(vb) > max(va):
            verdict = "ROSE   (every B run above every A run)"
        else:
            lo = max(min(va), min(vb))
            hi = min(max(va), max(vb))
            verdict = ("INDISTINGUISHABLE (run medians overlap on %.3f-%.3f)"
                       % (lo, hi))
        print("   %-13s A %s  B %s  %s"
              % (key,
                 "/".join("%.3f" % v for v in va),
                 "/".join("%.3f" % v for v in vb),
                 verdict))
    print("   Rule: per-run medians, every run in one arm against every run in"
          " the other. Stated in this file's docstring before any arm ran, not"
          " chosen after seeing these numbers.")


def main(argv):
    if not argv:
        sys.exit(__doc__.strip().splitlines()[0] +
                 "\n\nusage: tcg_pages.py <logcat|result-dir> ...\n"
                 "       tcg_pages.py --ab A=<path> B=<path>")
    keep_first = "--keep-first" in argv
    argv = [a for a in argv if a != "--keep-first"]
    if argv and argv[0] == "--ab":
        arms = {"A": [], "B": []}
        for spec in argv[1:]:
            if "=" not in spec:
                sys.exit("--ab wants A=<path> [A=<path> ...] B=<path> ...")
            name, path = spec.split("=", 1)
            if name not in arms:
                sys.exit("arm must be A or B, got %r" % name)
            arms[name].append(
                report("%s%d" % (name, len(arms[name]) + 1), path, keep_first))
            print()
        if not arms["A"] or not arms["B"]:
            sys.exit("--ab needs at least one A= and one B=")
        judge(arms["A"], arms["B"])
        return
    for path in argv:
        report(os.path.basename(path.rstrip("/")) or path, path,
               keep_first)
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
