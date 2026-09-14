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

# "inval ev=N ov=N sp=N em=N ws=N pr=N ai=N di=N cg=N xx=N ins=N bytes=N
#  blk=N.NN".  ai/di/cg/xx are each optional, because a build from before the
# counter existed emits no field for it and a missing field is not a zero.
INVAL_RE = re.compile(
    r"inval ev=(\d+) ov=(\d+) sp=(\d+) em=(\d+) ws=(\d+) pr=(\d+) "
    r"(?:ai=(\d+) )?(?:di=(\d+) cg=(\d+) )?(?:xx=(\d+) )?"
    r"ins=(\d+) bytes=(\d+) blk=(\d+)\.(\d+)"
    r"(?: iv=(\d+) ic=(\d+) ib=(\d+) ih=(\d+) ix=(\d+)"
    r" hd=(\d+)/(\d+)/(\d+)/(\d+)/(\d+))?")

# The M5 group above is APPENDED and optional, in one piece. Appended because
# a field inserted in the middle would stop this regex matching every log
# already on disk; optional in one piece because these six counters arrive
# together in one commit, so a build either has all of them or none, and
# splitting them into six optional groups would model a state that cannot
# exist. As everywhere in this file: a missing field is not a zero.

# "slow stores N (M reached the invalidator) ... [blocks ...]"
STORES_RE = re.compile(
    r"slow stores (\d+) \((\d+) reached the invalidator\)")

# The current form, as of the #69 rename. Every field names its own event.
BLOCKS_RE = re.compile(
    r"blocks discarded (\d+) of (\d+) visited, generated (\d+) of (\d+) calls")

# The form before it, which printed a VISIT count labelled "tossed" and a CALL
# count labelled "generated" -- the numerator and denominator of the retracted
# 2.8:1 waste ratio. It is read, but into `visited` and `calls`, because that
# is what those two numbers are. The mapping is safe because it is a statement
# about the code at those refs and not an inference from the values: the
# increments sat at the top of tb_gen_code and before
# tb_phys_invalidate__locked respectively. A log in this form is NOT a source
# of a discard count or a generation count; those come from di=/cg= on the
# inval line, and if that line is absent so is the waste ratio.
LEGACY_RE = re.compile(r"blocks tossed (\d+), generated (\d+)")

# The always-on pacing line.
PERF_RE = re.compile(
    r"gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\).*?Vpf:([\d.]+)")

# Counters read from the invalidation line, in report order. The key is the
# field name, the value is what it means when it moves.
COUNTERS = [
    ("ev",    "invalidation events that found a block"),
    ("ov",    "LIVE blocks discarded whose bytes the guest wrote"),
    ("sp",    "LIVE blocks discarded that a range test would have SPARED"),
    ("em",    "events that emptied the page (disarmed detection)"),
    ("ws",    "...of those, a block would have survived a range test"),
    ("pr",    "arming TLB walks performed (tlb_protect_code)"),
    ("ai",    "visited blocks that already carried CF_INVALID"),
    ("di",    "DISCARDS: blocks really unlinked, past the early return"),
    ("cg",    "GENERATIONS: calls that really generated code"),
    ("xx",    "THE IMPOSSIBLE ROW -- must be 0, see derive()"),
    ("ins",   "guest instructions translated"),
    ("blk",   "mean guest instructions per generated block"),
    ("visited", "VISITS: TBs the invalidation loop walked over"),
    ("calls",  "CALLS to tb_gen_code, recycles included"),
    ("stores", "slow stores into code pages"),
    ("iv",    "CALLS to the inv_htable recycle probe (== calls; see M5)"),
    ("ic",    "CANDIDATES hashed: one guest-byte hash each. M5's cost"),
    ("ib",    "guest BYTES hashed by those, one cpu_ldub_code at a time"),
    ("ih",    "recycle HITS: lookups that returned a block"),
    ("ix",    "THE M5 IMPOSSIBLE ROW -- a hit that hashed nothing. Must be 0"),
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
                b = BLOCKS_RE.search(line)
                if b:
                    pending["discarded"] = int(b.group(1))
                    pending["visited"] = int(b.group(2))
                    pending["generated"] = int(b.group(3))
                    pending["calls"] = int(b.group(4))
                else:
                    t = LEGACY_RE.search(line)
                    if t:
                        # See LEGACY_RE: "tossed" was visits, "generated" was
                        # calls. Read into the names of the events they are.
                        pending["visited"] = int(t.group(1))
                        pending["calls"] = int(t.group(2))
                        pending["legacy_line"] = 1
                continue
            m = INVAL_RE.search(line)
            if m:
                g = m.groups()
                w = dict(pending)
                w.update({
                    "ev": int(g[0]), "ov": int(g[1]), "sp": int(g[2]),
                    "em": int(g[3]), "ws": int(g[4]), "pr": int(g[5]),
                    "ins": int(g[10]), "bytes": int(g[11]),
                })
                # Absent fields stay absent: a build from before a counter
                # existed reports no value, and a missing field is not a zero.
                if g[6] is not None:
                    w["ai"] = int(g[6])
                if g[7] is not None:
                    w["di"] = int(g[7])
                if g[8] is not None:
                    w["cg"] = int(g[8])
                if g[9] is not None:
                    w["xx"] = int(g[9])
                if g[14] is not None:
                    w["iv"] = int(g[14])
                    w["ic"] = int(g[15])
                    w["ib"] = int(g[16])
                    w["ih"] = int(g[17])
                    w["ix"] = int(g[18])
                    w["hd"] = [int(g[19 + i]) for i in range(5)]
                # blk is instructions per block that really generated code.
                # Divided by a CALL count instead -- which is what
                # hakux_tb_generated is -- it comes out below 1, which a block
                # cannot be. Such a row is void, not small, so it is dropped
                # rather than reported. That is how the defect was found.
                w["blk_raw"] = int(g[12]) + int(g[13]) / 100.0
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
    # blk is instructions per block that really generated code. Divided by a
    # CALL count instead -- which is what hakux_tb_generated is -- it comes out
    # below 1, and a block cannot hold less than one instruction. One such
    # window voids the whole column: keeping only the windows that happened to
    # land above 1.0 would be survivorship, not a measurement. That impossible
    # row is how the defect was found in the first place.
    raw = [w["blk_raw"] for w in windows if "blk_raw" in w]
    if raw and min(raw) >= 1.0:
        for w in windows:
            if "blk_raw" in w:
                w["blk"] = w["blk_raw"]
    elif raw:
        for w in windows:
            if "blk_raw" in w:
                w["blk_void"] = w["blk_raw"]
    return windows, pacing


# Scene-independent ratios, computed per window then summarised. Each is
# (name, numerator, denominator, what it means). A window missing either field
# is skipped rather than counted as zero.
RATIOS = [
    ("waste", "di", "cg",
     "THE WASTE RATIO: real discards per real generation"),
    ("waste_legacy", "visited", "calls",
     "what 2.8:1 was: visits over calls, kept only to show the gap"),
    ("recycle", "calls", "cg",
     "calls per generation, i.e. the inv_htable recycle rate"),
    ("clog", "ai", "visited",
     "share of visits that were already-dead blocks on the page list"),
    ("reach_share", "reached", "stores",
     "share of slow stores that reached the invalidator"),
    ("sp_share", "sp", "ovsp",
     "share of LIVE discarded blocks with no written byte in them"),
    ("ws_share", "ws", "em",
     "share of page-emptying events a range test would prevent"),
    ("pr_per_em", "pr", "em",
     "arming TLB walks per page-emptying event"),
    ("inv_cand", "ic", "iv",
     "M5: guest-byte hashes per recycle probe -- the unbounded chain"),
    ("inv_hit", "ih", "iv",
     "M5: recycle hit rate, same denominator as the cost above"),
    ("inv_bytes_per_cand", "ib", "ic",
     "M5: mean block hashed. Arithmetically confined to [1, 4096)"),
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


def discard_model(windows):
    """Which invalidation predicate this build carries, read off the counters.

    Returns (model, bad_page_windows, bad_range_windows). `model` is None when
    the log has no di= field at all.

    THE POINT OF DOING IT THIS WAY. `di` and the ov/sp/ai split are emitted on
    ONE log line, so each identity below is exact -- no sampling slack, no
    cross-thread term. But WHICH identity holds is a property of the build, and
    this tool is handed a logcat that does not say. Hard-coding one of them is
    what voided #68's arm: the pre-#68 form was asserted against an arm-B soak
    of a range-tested build and reported "sp+ov != di in 21 of 21 windows,
    two counts of the same live population", over counters that were coherent.

    So: test both, name the one that held, and VOID only a run that matches
    neither. A tool that cannot see which side of a fold it is on must not
    assert one side of it.

        WHOLE-PAGE (pre-#68):   di == ov + sp
        RANGE-TESTED (#68):     di == ov + ai

    Both carry do_tb_phys_invalidate()'s non-loop callers -- tb_check_watchpoint
    in a softmmu build -- as an error term. Measured 0 on all six 2026-09-14
    soaks, which is why exact equality is used; if that ever stops being true
    this is the first place it will show, as MIXED.
    """
    if not any("di" in w for w in windows):
        return None, [], []
    bad_page = [i for i, w in enumerate(windows)
                if "di" in w and w.get("sp", 0) + w.get("ov", 0) != w["di"]]
    bad_rng = [i for i, w in enumerate(windows)
               if "di" in w and w.get("ov", 0) + w.get("ai", 0) != w["di"]]
    if not bad_page and not bad_rng:
        return "DEGENERATE", bad_page, bad_rng
    if not bad_page:
        return "WHOLE-PAGE", bad_page, bad_rng
    if not bad_rng:
        return "RANGE-TESTED", bad_page, bad_rng
    return "MIXED", bad_page, bad_rng


def derive(windows):
    """The two ratios the levers turn on, plus the self-consistency check."""
    if not windows:
        return
    # THE IMPOSSIBLE ROW, and it is checked before anything is printed about
    # the numbers. A visit is live XOR discarded; xx counts the violations and
    # is zero by the model, not by construction of the patch. A nonzero value
    # means "visits = discards + already-invalid" is wrong, and then every
    # ratio below is a quotient of two quantities whose populations are not
    # known -- which is exactly the defect #69 is about.
    xx = series(windows, "xx")
    if xx and sum(xx) == 0:
        print("   -> CONTROL xx = 0 over %d windows: every visited block was"
              " live and discarded, or already invalid and not. The counters"
              " below are quotients of known populations." % len(xx))
    elif xx:
        print("   -> VOID: the impossible row fired. xx = %d over %d windows,"
              " and it cannot be nonzero if a live TB is findable in"
              " tb_ctx.htable and an already-CF_INVALID one is not. Read"
              " NOTHING below as a measurement until it is explained: the"
              " populations behind di, ai and visited are not what their"
              " comments in tb-maint.c say." % (sum(xx), len(xx)))
    else:
        print("   -> NO xx= FIELD. This build predates the control, so the"
              " visits/discards/already-invalid split below is asserted by a"
              " code reading rather than checked on the run.")
    void = [w["blk_void"] for w in windows if "blk_void" in w]
    if void:
        print("   -> VOID: mean block length came out at %.2f, and a block"
              " cannot hold less than one instruction. This build divides"
              " instructions by a CALL count to tb_gen_code -- a call that"
              " recycles a TB from inv_htable never generates code. Rebuild"
              " with the cg= counter before reading any block-length figure,"
              " and treat the published \"blocks generated\" numbers as call"
              " counts too." % (sum(void) / len(void)))
    if any("legacy_line" in w for w in windows):
        print("   -> This log's always-on line is the pre-#69 form, which"
              " printed visits labelled \"tossed\" and calls labelled"
              " \"generated\". They have been read into `visited` and"
              " `calls`. There is no discard or generation count on that"
              " line; di=/cg= on the inval line are the only source, and"
              " `waste` is absent if they are.")
    cg = sum(series(windows, "cg")) if any("cg" in w for w in windows) else None
    dis = sum(series(windows, "di")) if any("di" in w for w in windows) else None
    calls = sum(series(windows, "calls"))
    if cg and dis is not None:
        print("   -> WASTE RATIO %.2f discards per generation (%d / %d)."
              " This is the corrected figure. The retracted 2.8:1 was"
              " visits over calls." % (dis / float(cg), dis, cg))
        if calls:
            print("      Same run, the retracted pair: %.2f visits per call"
                  " (%d / %d), recycle rate %.2f calls per generation."
                  % (sum(series(windows, "visited")) / float(calls),
                     sum(series(windows, "visited")), calls,
                     calls / float(cg)))
        print("      And a discard is not a retranslation. A discarded block"
              " goes into inv_htable and can be recycled from it without"
              " codegen, which is what the recycle rate measures, so the"
              " cost of a discard is bounded by tb_link_page and the arming"
              " walk rather than by tb_gen_code.")
    vis = sum(series(windows, "visited"))
    di = sum(series(windows, "di")) if any("di" in w for w in windows) else None
    ai = sum(series(windows, "ai")) if any("ai" in w for w in windows) else None
    # THE POPULATION IDENTITY, and it is the one that survives #68.
    #
    # `visited == ov + sp + ai` holds on BOTH sides of the range-test
    # restoration, because tb-maint.c makes the live/dead split and the
    # overlap split BEFORE applying the discard predicate -- deliberately, so
    # that the predicate cannot select its own population.
    #
    # What this check used to be was `visits == discards + already`, and that
    # is a PRE-#68 statement wearing the words of a population check: with the
    # range test restored a visit can be a live block the test spared, which
    # is neither a discard nor an already-invalid block. Checking it against
    # arm B produced a residual of 160 million and read as a broken counter.
    # The counters were fine. See docs/investigations/issue68-arm-void.md and
    # the CROSS-COUNTER IDENTITIES block in accel/tcg/tb-maint.c.
    ov_t = sum(series(windows, "ov"))
    sp_t = sum(series(windows, "sp"))
    if ai is not None and vis:
        resid = vis - (ov_t + sp_t + ai)
        print("   -> POPULATION visits %d = ov %d + sp %d + already-invalid %d"
              " (run residual %d)." % (vis, ov_t, sp_t, ai, resid))
        # THE RESIDUAL IS PER WINDOW, NOT PER RUN, and checking the run total
        # is what made it look like a defect.
        #
        # `visited` is printed on the FIRST hakuX-pages line and ov/sp/ai on
        # the SECOND -- two separate __android_log_print calls from the nv2a
        # thread, with the guest CPU thread running in between. A visit in
        # flight at that moment lands on one side of the subtraction and not
        # the other, so it is MISSING from window k and PRESENT in window
        # k+1. The slips therefore come in cancelling pairs, which is visible
        # in the data: -30/+30, -100/+96, -164/+182 on the arm-B soaks.
        #
        # Two consequences, and both are properties of the logging and not of
        # which way a number moved:
        #
        #  * The tolerance scales with the window's OWN visit count, because
        #    what slips is however many visits happen in the gap between two
        #    log calls. Measured over six 2026-09-14 soaks the worst
        #    non-terminal slip is 1.9e-5 of its window; 1e-4 with a floor of
        #    8 covers every one of them with two decades of margin.
        #  * THE FINAL WINDOW'S SLIP IS UNCOMPENSATED BY CONSTRUCTION -- the
        #    run ends before the partner window is ever emitted -- so it is
        #    reported and not judged. It is the whole of the run residual.
        #    One soak's last window carried -3544 of a -3536 run total and it
        #    is not a finding. This exclusion is structural and applies to
        #    every run identically; it is not a case granted an exception
        #    after its number was seen.
        res = [w.get("visited", 0) - (w.get("ov", 0) + w.get("sp", 0)
                                      + w.get("ai", 0))
               for w in windows]
        bad = [(i, res[i], windows[i].get("visited", 0))
               for i in range(len(res) - 1)
               if abs(res[i]) > max(8, windows[i].get("visited", 0) * 1e-4)]
        print("      per window: max |residual| %d over %d windows; final"
              " window %+d, reported not judged (the run ends between the two"
              " log calls, so its slip has no partner window to cancel in)."
              % (max((abs(r) for r in res[:-1]), default=0),
                 max(len(res) - 1, 0), res[-1] if res else 0))
        if bad:
            print("      RESIDUAL EXCEEDS THE PER-WINDOW SLACK in %d window(s)"
                  " %s. That is not a log-boundary slip: a slip is bounded by"
                  " the visits in flight across one log call and cancels into"
                  " the next window. Treat every ratio here as void until it"
                  " is explained."
                  % (len(bad), [(i, r) for i, r, _ in bad[:5]]))
    # THE DISCARD IDENTITY, and WHICH ONE HOLDS DEPENDS ON THE PREDICATE.
    #
    # Both terms of each are on ONE log line, so both are exact -- no slack.
    # This used to hard-code the pre-#68 form and call it "two counts of the
    # same live population", which is what VOIDed #68's arm in 21 of 21
    # windows against counters that were coherent. So it now tests both and
    # reports WHICH MODEL the run matched, and VOIDs only a run that matches
    # neither. A tool that cannot see which side of a fold it is on must not
    # assert one of them.
    #
    #   WHOLE-PAGE (pre-#68):  di == ov + sp    every live visited block dies
    #   RANGE-TESTED (#68):    di == ov + ai    the spared population leaves
    #
    # The model is a property of the BUILD, so a run whose windows disagree
    # among themselves is itself a finding and is reported as MIXED.
    model, bad_page, bad_rng = discard_model(windows)
    if model:
        n_di = len([w for w in windows if "di" in w])
        if model == "DEGENERATE":
            # Only possible when sp == ai in every window, which in practice
            # means both are 0: a run that invalidated nothing. Say so rather
            # than picking a model off a degenerate run.
            print("   -> CONTROL both discard identities hold in every window,"
                  " which means sp == ai throughout (in practice both 0). This"
                  " run does not determine which invalidation predicate the"
                  " build carries; do not use it to date a build.")
        elif model == "WHOLE-PAGE":
            print("   -> CONTROL di == ov+sp in every window (%d): the build"
                  " discards every live block it visits, so this is a"
                  " WHOLE-PAGE invalidation build, pre-#68." % n_di)
        elif model == "RANGE-TESTED":
            print("   -> CONTROL di == ov+ai in every window (%d): discards are"
                  " the live-and-overlapping blocks plus the already-invalid"
                  " ones, so this is a RANGE-TESTED build, #68 applied. `sp`"
                  " is the SPARED population here and is not part of di."
                  % n_di)
        else:
            print("   -> VOID: neither discard identity holds. di != ov+sp in"
                  " %d window(s) %s AND di != ov+ai in %d window(s) %s. Both"
                  " sides of each are on ONE log line, so one of them must"
                  " hold exactly for any build this tool knows about. Read"
                  " NOTHING below as a measurement."
                  % (len(bad_page), bad_page[:5],
                     len(bad_rng), bad_rng[:5]))
    if any("di" in w for w in windows) and ai is not None and vis:
        if ai > vis * 0.5:
            print("      MOST VISITS ARE DEAD BLOCKS (%.0f%%). The page lists"
                  " are carrying already-invalidated TBs, so the visit count"
                  " is largely a re-visit count. sp/ov below are live-only as"
                  " of 02f04060e8 and are unaffected, but any figure derived"
                  " from `visited` is not -- including waste_legacy, which is"
                  " why it is printed beside `waste` rather than instead of"
                  " it." % (100.0 * ai / vis))
        elif model == "RANGE-TESTED":
            print("      already-invalid is %.1f%% of visits. Under a"
                  " range-tested build this is the SMALL number: #73's mask"
                  " makes a dead block findable and #68's `!tb_live` clause"
                  " discards it on its first visit, so a clogged page list"
                  " reads here as a defect rather than as the baseline."
                  % (100.0 * ai / vis))
        if ai > vis * 0.5:
            print("      A large already-invalid share means the page lists"
                  " carry dead TBs that do_tb_phys_invalidate's early return"
                  " refuses to unlink, every later store re-visits them, and"
                  " BOTH the discarded-blocks count and the sp/ov split are"
                  " measured over the wrong population.")
    ov = sum(series(windows, "ov"))
    sp = sum(series(windows, "sp"))
    em = sum(series(windows, "em"))
    ws = sum(series(windows, "ws"))
    if ov + sp:
        # The noun changes with the model and the number does not: sp+ov is
        # the LIVE VISITED population either way, which is why it is the
        # quantity the two arms of #68 are comparable on. Under whole-page
        # invalidation every one of them is discarded; under the restored
        # range test the sp half is spared, which is the change itself.
        noun = ("live blocks visited" if model == "RANGE-TESTED"
                else "discarded blocks")
        print("   -> %.1f%% of %s had no written byte in them"
              " (sp/(sp+ov) = %d/%d)."
              % (100.0 * sp / (ov + sp), noun, sp, ov + sp))
        if sp and ov * 100 < sp:
            # The standing caution, and it is about the DEAD share, not about
            # the value being near 100%. A page list clogged with
            # already-invalid TBs reports 100% spared while saying nothing
            # about live ones -- but sp/ov have been live-only since
            # 02f04060e8, so the caution only bites where `ai` is large.
            # Saying it on a run with ai == 0 taught readers to ignore it.
            if ai and ai > vis * 0.5:
                print("      CAUTION: that is at or near 100%%, and on THIS run"
                      " %.0f%% of visits were already-dead blocks, which is"
                      " exactly what a systematic instrument error looks"
                      " like. Check the population identity above before"
                      " reading this as the premise check."
                      % (100.0 * ai / vis))
            else:
                print("      At or near 100%%, with a dead-block share of"
                      " %.1f%%, so the standing clogged-page-list caution"
                      " does not apply: these are live blocks the guest"
                      " never wrote the bytes of. That is the premise check"
                      " passing, not an instrument artefact."
                      % (100.0 * ai / vis if vis else 0.0))
        print("      This is the premise check for"
              " performance-next-three.md section 2. Near 0% means the"
              " invalidation is already effectively range-precise and the"
              " block-extent lever has its mechanism. Large means it does"
              " not: a smaller block cannot be missed by a store that"
              " discards the whole page.")
    ev = sum(series(windows, "ev"))
    if ev and em < ev:
        ai = sum(series(windows, "ai")) if any("ai" in w for w in windows) \
            else None
        if model == "RANGE-TESTED":
            print("   -> em (%d) is BELOW ev (%d), and under a RANGE-TESTED"
                  " build that is the change working rather than a shortfall"
                  " to explain: a block the write missed is spared, so the"
                  " page keeps its code and does not empty. em/ev is the"
                  " measure of it. The paragraphs below are the whole-page"
                  " reading and do not apply." % (em, ev))
        else:
            print("   -> em (%d) is BELOW ev (%d). Under whole-page"
                  " invalidation every block on the page is discarded, so the"
                  " page should always empty." % (em, ev))
        if model == "RANGE-TESTED":
            pass
        elif ai is None:
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
    if em and model == "RANGE-TESTED":
        # `ws` is RETIRED on this side of the fold. 937848c9e7 removes the
        # increment and keeps the symbol only so this regex and profile.c's
        # format string keep parsing, because the counterfactual it measured
        # is what that commit makes actual -- any value it could carry would
        # be true by construction. Printing "0.0% of events would not have
        # emptied" here reads as a measured collapse of the prize and is not
        # a measurement at all.
        print("   -> ws is RETIRED on a range-tested build and reads 0 by"
              " construction (it counted the counterfactual this build makes"
              " actual). ws/em is NOT computed. The before-and-after lives in"
              " two ARMS, on em and pr, which mean the same thing on both"
              " sides.")
    elif em:
        print("   -> %.1f%% of page-emptying events would NOT have emptied the"
              " page under a range test (ws/em = %d/%d)."
              % (100.0 * ws / em, ws, em))
        print("      That is the arming TLB walk -- tlb_reset_dirty, 10.6%"
              " self of the bounding thread -- that the range test would"
              " remove. It is the prize, and it is not about discarded code.")


    m5(windows)


def m5(windows):
    """The inv_htable recycle cache: what it costs and what it buys.

    Audit pass 1 M5. `inv_htable` has no eviction path, so every distinct
    byte-content ever translated at a pc leaves a permanently resident entry,
    and each later tb_gen_code() for that pc pays one byte-at-a-time
    guest-memory hash per entry. The remediation the audit proposed -- evict on
    insert -- is REFUTED and must not be implemented; see the comment block at
    inv_tb_lookup_cmp() in accel/tcg/cpu-exec.c. The real fix bounds the chain,
    and N has to be sized against these numbers.
    """
    if not any("ic" in w for w in windows):
        print("   -> NO iv=/ic= FIELDS. This build predates the M5 counters,"
              " so the inv_htable chain is unmeasured here -- which is not the"
              " same as unmeasured cost. Nothing below is printed.")
        return
    iv = sum(series(windows, "iv"))
    ic = sum(series(windows, "ic"))
    ib = sum(series(windows, "ib"))
    ih = sum(series(windows, "ih"))
    ix = sum(series(windows, "ix"))
    hd = [0] * 5
    for w in windows:
        for i, v in enumerate(w.get("hd", [])):
            hd[i] += v
    # THE IMPOSSIBLE ROW FIRST, before anything is printed about the numbers.
    if ix:
        print("   -> VOID (M5): ix = %d. A recycle hit that hashed no"
              " candidate, which cannot happen -- a hit IS a candidate whose"
              " ihash matched, so the counter was incremented before the"
              " comparison that returned true. Read NOTHING in this section"
              " as a measurement: the depth histogram and ih/ic are over a"
              " population that is not what cpu-exec.c says." % ix)
    else:
        print("   -> CONTROL (M5) ix = 0: every recycle hit hashed at least"
              " one candidate, so hd and the ratios below are over the"
              " population inv_tb_lookup_cmp() names.")
    if sum(hd) + ix != ih:
        print("   -> VOID (M5): sum(hd) + ix != ih (%d + %d != %d). Every hit"
              " lands in exactly one depth bucket or in the impossible row."
              " All terms are on ONE log line, so there is no slack: this is"
              " a counter defect, not a sampling slip."
              % (sum(hd), ix, ih))
    else:
        print("   -> CONTROL (M5) sum(hd) + ix == ih exactly (%d)." % ih)
    # iv == calls is the check that the probe is still on every codegen call.
    # It crosses the two log lines, so it carries the same in-flight slip the
    # population identity does, and is judged with the same shape of bound.
    calls = sum(series(windows, "calls"))
    if calls:
        slack = max(8, int(calls * 1e-4) + 1)
        ok = abs(iv - calls) <= slack
        print("   -> %s (M5) iv %d vs calls %d (residual %d, slack +/-%d)."
              " tb_gen_code() reaches inv_tb_htable_lookup() unconditionally,"
              " so these count the same event across two log calls. A"
              " divergence beyond the slip means the probe is no longer on"
              " every codegen call -- a new early return, or a second caller"
              " -- and every ratio below is then over an unstated population."
              % ("CONTROL" if ok else "VOID", iv, calls, iv - calls, slack))
    if not ic:
        print("   -> M5: ic = 0 over %d windows. NOT 'the chain is short' --"
              " no lookup reached the guest-byte hash at all, so this run"
              " says nothing about chain length. Check ih and iv before"
              " concluding anything." % len(windows))
        return
    print("   -> M5 COST %.2f guest-byte hashes per recycle probe (%d / %d),"
          " %.0f guest bytes per probe (%d total), mean block hashed %.0f"
          " bytes." % (ic / float(iv) if iv else 0.0, ic, iv,
                       ib / float(iv) if iv else 0.0, ib, ib / float(ic)))
    if not (1.0 <= ib / float(ic) < 4096.0):
        print("      VOID: mean bytes per candidate is outside [1, 4096),"
              " which tb->size's own range and tb_code_hash_func's assert"
              " make arithmetically impossible. One of ib and ic is being"
              " summed over the wrong population.")
    print("   -> M5 BENEFIT %.3f recycle hits per probe (%d / %d). The cost"
          " and the benefit share a denominator on purpose: a chain bound"
          " trades the second against the first."
          % (ih / float(iv) if iv else 0.0, ih, iv))
    if ih:
        labels = ["1", "2", "3-4", "5-8", ">8"]
        print("   -> M5 HIT DEPTH (candidates hashed by a hit, itself"
              " included): " + ", ".join(
                  "%s: %d (%.1f%%)" % (labels[i], hd[i], 100.0 * hd[i] / ih)
                  for i in range(5)))
        cum = 0
        for i, k in enumerate([1, 2, 4, 8]):
            cum += hd[i]
            print("      capping the WALK at %d candidate(s) keeps %.2f%% of"
                  " hits and spends at most %d hashes per probe"
                  % (k, 100.0 * cum / ih, k))
        print("      AND THIS DOES NOT SIZE AN MRU-N BOUND. `hd` is the hit's"
              " ordinal in the WALK, and the walk is qht bucket-slot order:"
              " qht_insert__locked() fills the first empty slot and"
              " qht_remove__locked() leaves a hole, so every successful"
              " recycle -- the event being measured -- perturbs the order. It"
              " answers 'would capping the walk at K have kept this hit'. It"
              " does NOT answer 'would keeping the most recent N have kept"
              " it'; that needs a monotone insertion stamp on the"
              " TranslationBlock, which does not exist.")


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

    # Two arms whose always-on line has DIFFERENT FIELD NAMES is exactly the
    # situation #69 created, and it is comparable -- `visited` and `calls` are
    # the same two counters either side of the rename, read out of
    # differently-labelled fields. It is still worth saying out loud, because
    # "the arms agree on a quantity that is spelled differently in each" is
    # the kind of thing that hides a real mismatch, and because an arm in the
    # legacy form has no discard or generation count at all, so `waste` will
    # silently be missing from the verdict rather than judged.
    leg_a = any("legacy_line" in w for ws, _, _ in arm_a for w in ws)
    leg_b = any("legacy_line" in w for ws, _, _ in arm_b for w in ws)
    if leg_a != leg_b:
        print("   NOTE: the arms use different always-on line formats (%s"
              " pre-#69, %s post). `visited` and `calls` are the same"
              " counters either side of the rename and are comparable; but"
              " the pre-#69 arm carries no discard or generation count on"
              " that line, so any quantity it lacks is ABSENT from the"
              " verdict below rather than judged."
              % ("A" if leg_a else "B", "B" if leg_a else "A"))

    # TWO ARMS ON OPPOSITE SIDES OF #68 ARE NOT COMPARABLE ON `di`, and this
    # is the note that would have saved #68's arm. `visited`, `ov`, `sp`,
    # `ai`, `em`, `pr`, `cg`, `ins` and `stores` are counted identically on
    # both sides -- tb-maint.c makes the live/dead and overlap splits BEFORE
    # applying the discard predicate, deliberately, so the predicate cannot
    # select its own population. `di` is the one that moves population, and
    # every ratio built on it moves with it: waste (di/cg) and sp_share's
    # NOUN, though not its value.
    ma = {discard_model(ws)[0] for ws, _, _ in arm_a} - {None, "DEGENERATE"}
    mb = {discard_model(ws)[0] for ws, _, _ in arm_b} - {None, "DEGENERATE"}
    if len(ma) > 1 or len(mb) > 1:
        print("   REFUSED as a pair: an arm mixes invalidation models"
              " (A=%s B=%s). Each arm is one binary."
              % (sorted(ma), sorted(mb)))
    elif ma and mb and ma != mb:
        print("   CROSS-FOLD PAIR: arm A is a %s build and arm B is a %s one,"
              " so this A/B spans #68's predicate change. That is the intended"
              " comparison, and it makes `di` INCOMMENSURABLE between the"
              " arms: a spared live block is a visit on both sides and a"
              " discard on only one. Judge on visited/ov/sp/ai/em/pr/cg/"
              " stores, which are counted before the predicate and mean the"
              " same thing on both. `waste` (di/cg) below is a quotient of"
              " two different populations and must not be quoted."
              % (sorted(ma)[0], sorted(mb)[0]))

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
