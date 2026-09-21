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
    arm label here is DERIVED from that header and never typed.  A run whose
    header names a driver the caller did not ask for is void, not renamed.

  * IT FIXES THE FRAME ORDER.  The PPMs are pulled by glob and a lexical sort
    of `..._f004.ppm` happens to be correct only while the zero padding holds.
    Frames are ordered by the integer in the name, and a gap is reported --
    `stipple_classify.py`'s local baseline is a window over NEIGHBOURS, and
    neighbours that are 90 frames apart are not a baseline.

  * IT REPORTS THE DENOMINATOR.  A `cap_mb` dump keeps images for only the
    first ~73 of its 600 frames, so the rate's denominator is the number of
    IMAGES, not the number of frames the spec asked for.  Both are printed.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "diagsoak77"))
from stipple_classify import classify  # noqa: E402
from galleon_flash_rate import load_frames  # noqa: E402

FRAME_RE = re.compile(r"_f(\d+)\.ppm$")


MAX_HEADER_LINES = 12


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


def ordered_frames(pulled):
    """PPM paths in frame order, plus the frame indices, plus any gap."""
    pairs = []
    for p in glob.glob(os.path.join(pulled, "framedump_*_f*.ppm")):
        m = FRAME_RE.search(p)
        if m:
            pairs.append((int(m.group(1)), p))
    pairs.sort()
    idx = [i for i, _ in pairs]
    gaps = [(a, b) for a, b in zip(idx, idx[1:]) if b != a + 1]
    return [p for _, p in pairs], idx, gaps


def score(rdir, region=None):
    pulled = os.path.join(rdir, "pulled")
    hdr = session_header(pulled)
    paths, idx, gaps = ordered_frames(pulled)
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
               images=len(paths), gaps=gaps)
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
    args = ap.parse_args(argv)
    region = tuple(int(x) for x in args.region.split(",")) if args.region else None
    if region and len(region) != 4:
        sys.exit("--region takes X0,Y0,X1,Y1")

    outs = []
    # str() first: a 4-tuple in a %s would be unpacked as four arguments.
    print("region %s" % str(region or "whole frame"))
    print("%-42s %-46s %5s %6s %7s" %
          ("run", "driver (read from the dump, not typed)", "imgs", "stip", "per100"))
    for d in args.dirs:
        o = score(d, region)
        outs.append(o)
        if "error" in o:
            print("%-42s %s" % (o["run"], o["error"]))
            continue
        print("%-42s %-46s %5d %6d %7.1f" %
              (o["run"], one_line(o["driver"])[:46], o["images"], o["stipple"],
               o["rate_per_100"]))
        if o["gaps"]:
            print("    GAP in frame numbering: %s -- neighbours in the local "
                  "baseline are not adjacent frames" % (o["gaps"][:4],))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(dict(region=list(region) if region else None, runs=outs),
                      fh, indent=1)
        print("wrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
