#!/usr/bin/env python3
"""Score one soak result directory's frame dump for #77's stipple rate.

    score_arms.py [--region X0,Y0,X1,Y1] [--json OUT] RESULT_DIR [RESULT_DIR...]

WHAT THIS ADDS TO `stipple_classify.py`, which does the actual classifying and
is imported rather than re-implemented:

  * IT READS THE DRIVER OFF THE RUN ITSELF.  The frame dump's session header
    line carries `"driver": "..."` -- the string the emulator got from the
    Vulkan implementation it actually loaded.  A driver A/B whose arm label is
    a note in a lane's head is one fat-fingered `swap_driver.sh` away from
    measuring the same driver twice and reporting it as a difference, so the
    arm label here is DERIVED from that header and never typed.  Pass
    `--expect-driver SUBSTRING` and a run whose header does not carry it is
    marked **VOID (driver)** -- the rule P2 registered, made machine-checked
    rather than left to a human comparing a column.  Without the flag the
    driver is printed for comparison and nothing is voided.

  * IT FIXES THE FRAME ORDER, AND FLAGS A SAMPLING HOLE.  The PPMs are pulled
    by glob and a lexical sort of `..._f004.ppm` happens to be correct only
    while the zero padding holds, so frames are ordered by the integer in the
    name.  What is then reported is NOT "these frames are not adjacent" --
    a `cap200` dump keeps roughly one image every 9-10 frames, so
    non-adjacency is true of nearly every pair in every run and a warning on
    it fires always and says nothing.  What is reported is the run's own
    cadence: median gap, max gap, and the LARGEST holes when the max exceeds
    `ANOMALY_RATIO` x the median.  `stipple_classify.py`'s local baseline is a
    window over NEIGHBOURS, and a hole makes those neighbours span more wall
    time than the rest of the run does.  See `NOTES.md` R8 for what that is
    measured to be worth on these ten runs.

  * IT REPORTS THE DENOMINATOR.  A `cap_mb` dump keeps images for only the
    first ~73 of its 600 frames, so the rate's denominator is the number of
    IMAGES, not the number of frames the spec asked for.  Both are printed.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "diagsoak77"))
# `galleon_flash_rate` lives in docs/testing.  Inserted explicitly: it used to
# arrive only because importing `stipple_classify` inserts that directory as a
# side effect, so any reorder of the two imports below broke this file.
sys.path.insert(0, os.path.join(_HERE, "..", "..", "testing"))
from stipple_classify import classify  # noqa: E402
from galleon_flash_rate import load_frames  # noqa: E402

FRAME_RE = re.compile(r"_f(\d+)\.ppm$")


MAX_HEADER_LINES = 12

# A gap this many times the run's OWN median gap is a hole rather than the
# dump's normal cadence.  Measured, not picked: over the ten runs in NOTES.md
# the four band runs top out at 1.5-1.7x their median and every run with a
# visible hole is 2.1x or more, so 2.0 sits in the gap between the two
# populations.  It is a REPORTING bar -- nothing here voids a run on it, and
# no verdict in this lane is gated on it.
ANOMALY_RATIO = 2.0


def session_header(pulled):
    """The dump's own account of the run: driver, spec, prefs.

    THE HEADER IS NOT ALWAYS ONE LINE, AND THE ARM THAT BREAKS IT IS THE ONE
    THIS WHOLE FILE EXISTS FOR. `readline()` plus a strict `json.loads` reads
    both Turnip arms perfectly and returns None for the **stock** arm, because
    Adreno's own `VkPhysicalDeviceProperties.driverName`-ish blob is five
    lines with embedded newlines:

        Qualcomm Technologies Inc. Adreno Vulkan Driver (Driver Build: ...
        Date: 12/27/23
        Compiler Version: E031.41.03.47
        Driver Branch:
        )

    The emulator writes that straight into the JSONL, so line 1 of a stock
    dump is an unterminated string and the record continues over the next
    four. Both stock runs of #77's driver A/B came back with `driver: ?` for
    exactly this reason -- and this lane's OWN registered guard G2 voids a run
    with an unparseable header, so a reader bug was one step from being
    reported as "the stock arm did not produce a readable run". The arm whose
    label cannot be derived is the arm whose label matters most: it is the
    only one of the three that is not a PurpleVK string, i.e. the only one
    where "the swap did not take" and "the swap took" look different.

    So: accumulate physical lines until the record parses, and parse with
    `strict=False` so a control character inside a string is data rather than
    a syntax error.

    THIS MUST NOT TURN "NO HEADER" INTO A HEADER. The accumulation is bounded
    (`MAX_HEADER_LINES`) and still requires `t == "session"`, so a dump whose
    first record is a draw, or a truncated dump with no session line at all,
    returns None exactly as before -- which is what G2 is entitled to void on.
    `tests_session_header.py` next to this file asserts both directions.
    """
    for p in sorted(glob.glob(os.path.join(pulled, "framedump_*.jsonl"))):
        buf = ""
        with open(p, errors="replace") as fh:
            for n, line in enumerate(fh):
                if n >= MAX_HEADER_LINES:
                    break
                buf += line
                try:
                    rec = json.loads(buf, strict=False)
                except ValueError:
                    continue
                if rec.get("t") == "session":
                    rec["_jsonl"] = os.path.basename(p)
                    rec["_header_lines"] = n + 1
                    return rec
                break  # a parsed record that is not the session record
    return None


def one_line(s):
    """A driver string for a table cell. Adreno's spans five lines."""
    return " ".join((s or "?").split())


def spacing(idx):
    """The run's sampling cadence, and the holes that are anomalous IN IT.

    A hole matters because `stipple_classify.py`'s baseline for a frame is the
    median over its +-W NEIGHBOURING IMAGES; across a hole those neighbours
    are drawn from a longer stretch of wall time, so the smooth animation
    trend the local median exists to remove is removed less well.  The
    quantity that says whether that happened is max gap against the run's own
    median gap -- NOT `b != a + 1`, which is true of nearly every pair of a
    sampled dump and therefore flags every run ever taken.

    Returns None for a run with fewer than two images (there is no gap to
    measure; `images` already reports that case).
    """
    if len(idx) < 2:
        return None
    deltas = [b - a for a, b in zip(idx, idx[1:])]
    med = float(statistics.median(deltas))
    holes = sorted(((d, a, b) for (a, b), d in zip(zip(idx, idx[1:]), deltas)
                    if med and d > ANOMALY_RATIO * med), reverse=True)
    return dict(median_delta=med, max_delta=max(deltas),
                max_over_median=(max(deltas) / med) if med else float("nan"),
                n_holes=len(holes), holes=holes)


def ordered_frames(pulled):
    """PPM paths in frame order, the frame indices, and the spacing profile."""
    pairs = []
    for p in glob.glob(os.path.join(pulled, "framedump_*_f*.ppm")):
        m = FRAME_RE.search(p)
        if m:
            pairs.append((int(m.group(1)), p))
    pairs.sort()
    idx = [i for i, _ in pairs]
    return [p for _, p in pairs], idx, spacing(idx)


def score(rdir, region=None, expect_driver=None):
    pulled = os.path.join(rdir, "pulled")
    hdr = session_header(pulled)
    paths, idx, space = ordered_frames(pulled)
    res = {}
    rj = os.path.join(rdir, "result.json")
    if os.path.exists(rj):
        res = json.load(open(rj))
    out = dict(run=os.path.basename(rdir),
               device=res.get("device_label"), ref=res.get("ref"),
               apk_sha=res.get("apk_sha"), env=res.get("env"),
               driver=(hdr or {}).get("driver"),
               spec=(hdr or {}).get("spec"),
               session=(hdr or {}).get("id"),
               frames_asked=(hdr or {}).get("frames"),
               images=len(paths), spacing=space)
    if expect_driver:
        # P2's rule, machine-checked: a run whose header does not name the
        # driver the caller asked for is VOID, not relabelled -- a swap that
        # silently did not take also means the device was in an unknown state.
        # The rate is still computed and printed; what is asserted is that the
        # run may not be used as evidence about `expect_driver`.
        got = one_line(out["driver"])
        if expect_driver.lower() not in got.lower():
            out["void_driver"] = "header says %r, caller asked for %r" % (
                got, expect_driver)
    if not paths:
        out["error"] = "no PPMs in %s" % pulled
        return out
    frames = load_frames(sorted(paths, key=lambda p: int(FRAME_RE.search(p).group(1))),
                         None, region)
    rows = classify(frames)
    flagged = [r for r in rows if r["stipple"]]
    out["stipple"] = len(flagged)
    out["rate_per_100"] = 100.0 * len(flagged) / len(rows)
    out["flagged_frames"] = [idx[r["frame"]] for r in flagged]
    out["rows"] = rows
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--region", metavar="X0,Y0,X1,Y1")
    ap.add_argument("--json", metavar="OUT")
    ap.add_argument("--expect-driver", metavar="SUBSTRING",
                    help="void any run whose header driver string does not "
                         "contain SUBSTRING (case-insensitive); exit 1 if any "
                         "run is void")
    args = ap.parse_args(argv)
    region = tuple(int(x) for x in args.region.split(",")) if args.region else None
    if region and len(region) != 4:
        sys.exit("--region takes X0,Y0,X1,Y1")

    outs = []
    # str() first: a 4-tuple in a %s would be unpacked as four arguments.
    print("region %s" % str(region or "whole frame"))
    print("%-42s %-46s %5s %6s %7s" %
          ("run", "driver (read from the dump, not typed)", "imgs", "stip", "per100"))
    void = 0
    for d in args.dirs:
        o = score(d, region, args.expect_driver)
        outs.append(o)
        if "void_driver" in o:
            void += 1
        if "error" in o:
            print("%-42s %s" % (o["run"], o["error"]))
        else:
            print("%-42s %-46s %5d %6d %7.1f" %
                  (o["run"], one_line(o["driver"])[:46], o["images"],
                   o["stipple"], o["rate_per_100"]))
        if "void_driver" in o:
            print("    VOID (driver): %s -- this run is not evidence about "
                  "the arm it was filed under" % o["void_driver"])
        s = o.get("spacing")
        if s:
            print("    spacing: median gap %.0f frames, max %d (%.1fx median)"
                  % (s["median_delta"], s["max_delta"], s["max_over_median"]))
            if s["n_holes"]:
                print("    SPACING ANOMALY: %d hole(s) over %.1fx the median "
                      "gap -- largest %s" %
                      (s["n_holes"], ANOMALY_RATIO,
                       ", ".join("f%d->f%d (%d)" % (a, b, dl)
                                 for dl, a, b in s["holes"][:4])))
                print("        a frame beside one of these is classified "
                      "against a local baseline drawn from a wider stretch "
                      "of wall time than the rest of the run")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(dict(region=list(region) if region else None, runs=outs),
                      fh, indent=1)
        print("wrote %s" % args.json)
    if void:
        print("%d run(s) VOID on --expect-driver %r" % (void, args.expect_driver))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
