#!/usr/bin/env python3
"""Score a whole isolation sweep against the hardware goldens.

    score_sweep.py --out sweep.state/out --goldens goldens/results \
                   --tsv scores.tsv

Each directory under ``--out`` is one guest run: a progress log naming the
test(s) that actually executed, and the framebuffer(s) they captured. The
sweep exists so that every test runs alone, which is the only way a result
means what it says -- 328 of 864 tests were previously rendering a *previous*
test's image. The progress log is the proof: ``[1/1]`` is a solo run, anything
else is a shared disc and is reported as such rather than quietly trusted.

What it reports, per test:

  * differing pixels, as a count and a share of the frame
  * max delta over R, G and B, and separately over A
  * whether the capture's on-screen label matches the golden's. Every capture
    carries the test's own parameters printed over it in white. If those pixels
    differ, the golden was produced by a *different build of the test suite*,
    which may have uploaded different source data -- the comparison is then not
    measuring this emulator at all. TexFmt_R6G5B5 was chased for hours as a
    decode defect before anyone read the label: hardware prints "C: 0" and we
    print "C: 1", the suite's own require_conversion flag, which selects
    between two completely different upload paths.
  * whether the capture is *blank* -- one colour over more than 90% of a frame
    whose golden is richer than that. A blank frame is a different failure from
    a wrong one: nothing drew, or the capture beat the draw to it. Mixed into a
    pixel-difference average it reads as dozens of subtly broken tests instead
    of one thing that did not run, so it is counted separately.
  * for a depth capture (``*_ZB.png``), how many of the differing pixels are
    off by exactly one in the stored depth value. The PNG holds the zeta
    surface as it sits in memory: for z24 the 24-bit depth is spread over the
    A, R and G bytes with the stencil in B, for z16 it is packed as R5G6B5. A
    byte-wise comparison cannot see that 0x0100 and 0x00ff are neighbours, so
    the depth is decoded and compared as an integer, and a capture whose only
    differences are +-1 is reported as its own category, "exact (+-1)". It is
    never folded into bit-identical: +-1 in the last bit of the depth is where
    the emulated transform rounds differently from the hardware, which is a
    real difference and a small one, and the score should say both. The
    tolerance is exactly one, and it applies to depth captures only; colour is
    compared as before (issue #32).

The split matters. A mean cannot tell "this format is not decoded at all"
(max 255) from "rounding" (max 8), and that is the whole triage decision; and
comparing RGB alone once hid 1,279 differing alpha pixels behind a clean score.
Suites are ranked by the share of their tests that are bit-identical, because
that is the only claim that needs no threshold to defend.

The per-test TSV has one row per test: suite, test, solo, status, differing,
max_rgb, max_a, pixels, off_by_one. For a colour capture ``off_by_one``
counts differing pixels no channel of which is more than one step out. For a
depth capture ``differing`` counts
pixels whose decoded depth or stencil differs and ``off_by_one`` those whose
depth is off by exactly one with the stencil equal; ``max_rgb`` and ``max_a``
stay the raw channel maxima. 
"""

import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs numpy and pillow: pip install numpy pillow")

STARTING = re.compile(r"Starting \[(\d+)/(\d+)\] (.+?)::(.+)")

# Test names carry the zeta format the capture was taken with: Depth_buffer
# (DepthFmt_z16_*), Depth_buffer_fixed_function (z16_*) and W_buffering
# (WBuf16D_*, ZBuf16F_*, ...). Everything else that saves a depth buffer
# (Clear, Color_Zeta_Disable, Color_zeta_overlap, Depth_function, Stencil,
# Stencil_func, ZPass_pixel_count) runs with the default z24s8 surface.
Z16_NAME = re.compile(r"(^|_)z16_|^[WZ]Buf16[DF]_")


def depth_bits(test):
    """16 or 24: the width of the depth value stored in a ``_ZB`` capture."""
    return 16 if Z16_NAME.search(test) else 24


def decode_depth(img, bits):
    """(depth, stencil) integer arrays from an RGBA capture of a zeta surface.

    The test saves the surface bytes as they are: a z24s8 pixel is the little
    endian word (depth << 8) | stencil, so B is the stencil and the depth is
    A:R:G high to low; a z16 pixel is the 16-bit depth read back as R5G6B5.
    """
    a = img.astype(np.int64)
    if bits == 24:
        return (a[..., 3] << 16) | (a[..., 0] << 8) | a[..., 1], a[..., 2]
    depth = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
    return depth, np.zeros_like(depth)


def read_log(path):
    """(solo, [test names]) for one run directory."""
    names, total = [], 1
    try:
        with open(path, errors="replace") as f:
            for line in f:
                m = STARTING.match(line.strip())
                if m:
                    total = int(m.group(2))
                    names.append(m.group(4).strip())
    except OSError:
        return False, []
    return total == 1, names


def score_dir(args):
    run_dir, goldens = args
    # A MISSING CAPTURE DIRECTORY IS AN EXPECTED OUTCOME, NOT A BUG HERE.
    #
    # It happens when the device disappears mid-run: on 2026-09-13 the thor
    # dropped off adb 604 s into a 1,673-capture arm, the pull failed, and
    # `captures1` was never created. `os.listdir` then raised
    # FileNotFoundError out of a ProcessPoolExecutor worker, so the log got a
    # two-frame `_RemoteTraceback` wrapping a one-line fact. The dispatcher
    # handled the outcome correctly -- it wrote "ran but produced 0 captures"
    # to ERROR -- but anyone reading the log met the traceback first and had to
    # work out that the tool was fine and the cable was not.
    #
    # An instrument that cannot see its input should say so in one line. The
    # empty list is the honest return: zero captures scored, which is what
    # happened.
    if not os.path.isdir(run_dir):
        sys.stderr.write("score_sweep: no capture directory at %s -- nothing "
                         "to score. The run produced no captures (a device "
                         "that vanished mid-run does this); this is not a "
                         "scoring failure.\n" % run_dir)
        return []
    solo, _ = read_log(os.path.join(run_dir, "pgraph_progress_log.txt"))
    rows = []
    for name in sorted(os.listdir(run_dir)):
        if not name.endswith(".png") or "::" not in name:
            continue
        suite, test = name[:-4].split("::", 1)
        gp = os.path.join(goldens, suite, test + ".png")
        if not os.path.exists(gp):
            rows.append((suite, test, solo, "no-golden", 0, 0, 0, 0, 0))
            continue
        try:
            g = np.asarray(Image.open(gp).convert("RGBA"), dtype=np.int16)
            o = np.asarray(Image.open(os.path.join(run_dir, name)).convert("RGBA"),
                           dtype=np.int16)
        except Exception:
            # A truncated capture is a finding of its own; count it.
            #
            # NINE fields, like every other append here. This had EIGHT --
            # missing `off_by_one` -- so an unreadable capture wrote an
            # 11-column row against a 12-column header, and csv.DictReader
            # fills the shortfall silently rather than raising. A malformed row
            # in the one status meaning "this capture could not be read" is the
            # worst place for one: the row reporting the instrument's failure
            # was itself misaligned.
            rows.append((suite, test, solo, "unreadable", 0, 0, 0, 0, 0))
            continue
        if g.shape != o.shape:
            rows.append((suite, test, solo, "size", 0, 0, 0,
                         g.shape[0] * g.shape[1], 0))
            continue
        d = np.abs(g - o)
        rgb = d[..., :3].max(axis=2)
        alpha = d[..., 3]
        off_by_one = 0
        if test.endswith("_ZB"):
            bits = depth_bits(test)
            gz, gs = decode_depth(g, bits)
            oz, os_ = decode_depth(o, bits)
            dz = np.abs(gz - oz)
            ds = np.abs(gs - os_)
            differing = int(((dz > 0) | (ds > 0)).sum())
            off_by_one = int(((dz == 1) & (ds == 0)).sum())
        else:
            differing = int(((rgb > 0) | (alpha > 0)).sum())
            # A colour capture's off-by-one bucket, for the same reason the
            # depth one exists. Measured across 727 captures, the pixels in
            # this bucket sit 0.01 to 0.04 of a step from the hardware's
            # value: two nearly identical computations landing either side
            # of a quantisation boundary, not a rounding rule, which would
            # put half of them across it. See docs/testing/
            # run-2026-09-11-residual-classes.tsv and issue #38.
            off_by_one = int(((rgb <= 1) & (alpha <= 1)
                              & ((rgb > 0) | (alpha > 0))).sum())

        # The overlay text is drawn pure white by the guest. Pixels that are
        # white on exactly one side mean the two runs printed different text,
        # so the goldens and the disc are different builds of the suite.
        #
        # SCOPED TO THE LABEL BAND, and that scoping is load-bearing. The test
        # harness prints via `pb_printat(0, 0, name)`, so the overlay occupies
        # the top rows and nothing else. Counting white mismatches over the
        # WHOLE image makes this a content test for any suite whose palette
        # contains white -- and `2D_BorderTex_SZ`'s `kColors` does. Measured:
        # when one of its swatches went stale, all 281 white-mismatch pixels
        # were INSIDE a swatch and ZERO were in the label, and the row was
        # flagged `label-differs` anyway. AGENTS.md says to void such a row,
        # which would have discarded the one capture #44 is about -- the
        # flakiest and most-studied capture in the corpus.
        #
        # So the band decides the status, and white mismatches outside it are
        # counted separately as what they are: content. A suite that really
        # does print different text differs in the band, because that is where
        # the text is.
        LABEL_ROWS = 64
        gw = (g[..., :3] >= 250).all(axis=2)
        ow = (o[..., :3] >= 250).all(axis=2)
        white_mismatch = gw ^ ow
        label_delta = int(white_mismatch[:LABEL_ROWS].sum())
        content_white_delta = int(white_mismatch[LABEL_ROWS:].sum())

        flat = o[..., :3].reshape(-1, 3)
        _, counts = np.unique(flat, axis=0, return_counts=True)
        gold_colours = len(np.unique(g[..., :3].reshape(-1, 3), axis=0))
        blank = (counts.max() / flat.shape[0] > 0.90 and len(counts) <= 4
                 and gold_colours > 4)

        status = "blank" if blank else "ok"
        # NEITHER CHECK APPLIES TO A DEPTH CAPTURE, which is the other half and
        # was missing. A `_ZB` capture has NO LABEL: the guest prints its
        # overlay into the COLOUR buffer, and the `_ZB` image is packed depth
        # (z24 = A<<16|R<<8|G with stencil in B; z16 = RGB565). So "all three
        # channels >= 250" there does not mean white text -- it means a depth
        # value near maximum, which is the CLEARED value and the most common
        # value in the buffer.
        #
        # Running it anyway files real depth defects under a white-pixel
        # heuristic. Measured: the two `Depth_buffer_fixed_function` z16 rows
        # at 2,840 px each are a genuine depth disagreement, called
        # `label-differs` (void) by the pre-06:20 scorer and `white-content`
        # after it, and neither is what they are. Five `ZPass_pixel_count`
        # `_ZB` rows and one instance of #39 went the same way.
        #
        # This is the mirror of the false positive the band above fixed: that
        # made the check narrower, this stops it running on a class of capture
        # the concept does not apply to. Same error twice -- a test for white
        # text applied where white is data.
        #
        # PLACED HERE, AFTER `status` IS ASSIGNED, and the first version of
        # this was not. Returning early above the assignment made every depth
        # row inherit the PREVIOUS capture's status from the loop variable --
        # Python keeps it across iterations, so there was no NameError to
        # notice, just plausible statuses on the wrong rows. Caught by running
        # it against the two captures it was written for and finding rows that
        # should have been skipped coming back changed.
        depth_capture = test.endswith("_ZB")
        # Report it, do not silently downgrade the row: a differing label makes
        # the pixel comparison untrustworthy, not automatically wrong.
        if depth_capture:
            pass
        elif label_delta > 8:
            status = "label-differs"
        elif content_white_delta > 8:
            # White pixels differ in the image BODY. That is a real
            # disagreement about content and the row stays scoreable -- it is
            # what a stale swatch looks like on a suite whose palette holds
            # white. Named rather than silently folded into `differing`, so
            # nobody re-derives the false positive above.
            status = "white-content"
        rows.append((suite, test, solo, status, differing,
                     int(rgb.max()), int(alpha.max()), g.shape[0] * g.shape[1],
                     off_by_one))
    return rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True,
                    help="sweep state's out/ directory, or with --flat a single "
                         "directory of Suite::Test.png captures")
    ap.add_argument("--flat", action="store_true",
                    help="--out is one directory of captures rather than a tree "
                         "of per-run directories. A whole-suite disc writes this "
                         "shape; there is no progress log, so nothing is solo and "
                         "contamination between tests is not ruled out.")
    ap.add_argument("--goldens", required=True)
    ap.add_argument("--tsv", help="write the per-test table here")
    # Provenance. Two results are only comparable if the binary differs and the
    # disc composition matches; a row that carries neither cannot be checked.
    # Comparing a shared-disc number against a per-suite one caused a working
    # fix to be reverted on 2026-09-12, and nothing in the file said they were
    # different runs. See docs/orchestration.md.
    ap.add_argument("--apk-sha", default="",
                    help="the binary that produced these captures")
    ap.add_argument("--disc-id", default="",
                    help="which suites were on the disc, e.g. 'Specular' or "
                         "'g0:23suites' -- results with different disc ids are "
                         "not comparable")
    ap.add_argument("--label", default="",
                    help="run label, e.g. baseline / published / nightly")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()

    if args.flat:
        dirs = [args.out]
    else:
        dirs = [os.path.join(args.out, d) for d in sorted(os.listdir(args.out))
                if os.path.isdir(os.path.join(args.out, d))]
    captures = []
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for got in ex.map(score_dir, [(d, args.goldens) for d in dirs],
                          chunksize=8):
            captures.extend(got)

    # A test can be captured more than once: the suites that could not be split
    # one-test-per-disc appear in every disc that carried them, and 2D_Lines
    # lands nine times. Counting captures instead of tests inflates every
    # total, so fold them here -- and report whether the repeats agreed, which
    # is the only determinism check this data can offer for free.
    rows, repeats, disagreed = [], 0, []
    first = {}
    for r in captures:
        k = (r[0], r[1])
        if k in first:
            repeats += 1
            if (first[k][3], first[k][4]) != (r[3], r[4]):
                disagreed.append(k)
            continue
        first[k] = r
        rows.append(r)

    if args.tsv:
        with open(args.tsv, "w") as f:
            # Provenance goes in columns, not a comment header: a leading
            # "#" line becomes the header row for csv.DictReader and silently
            # breaks every consumer. Per-row also means several runs can be
            # concatenated and still be told apart.
            f.write("suite\ttest\tsolo\tstatus\tdiffering\tmax_rgb\tmax_a"
                    "\tpixels\toff_by_one\tapk_sha\tdisc_id\tlabel\n")
            for r in sorted(rows):
                f.write("\t".join(str(x) for x in r) +
                        "\t%s\t%s\t%s\n" % (args.apk_sha or "unknown",
                                             args.disc_id or "unknown",
                                             args.label or "unlabelled"))

    scored = [r for r in rows if r[3] in ("ok", "blank", "label-differs",
                                          "white-content")]
    blanks = [r for r in rows if r[3] == "blank"]
    stale = [r for r in rows if r[3] == "label-differs"]
    exact = [r for r in scored if r[4] == 0]
    # Depth captures whose every differing pixel is one depth unit away from
    # the hardware's. A category of their own, on purpose: not bit-identical,
    # and not the same failure as a wrong depth either.
    within1 = [r for r in scored if r[3] == "ok" and 0 < r[4] == r[8]]
    nogold = [r for r in rows if r[3] == "no-golden"]
    sized = [r for r in rows if r[3] == "size"]
    shared = {r[0] for r in rows if not r[2]}

    print(f"{len(rows)} tests from {len(dirs)} runs "
          f"({len(captures)} captures, {repeats} repeated)\n")
    if repeats:
        if disagreed:
            print(f"  !! {len(disagreed)} test(s) scored differently on a repeat "
                  f"run -- the results are not deterministic:")
            for suite, test in disagreed[:5]:
                print(f"       {suite}::{test}")
        else:
            print(f"  every repeated test scored identically on each run\n")
    print(f"  bit-identical to hardware   : {len(exact):5d}  "
          f"({len(exact)/max(len(scored),1)*100:.1f}% of scored)")
    print(f"  within +-1 of hardware      : {len(within1):5d}  "
          f"(every differing pixel one step out; not counted above)")
    print(f"  differ                      : "
          f"{len(scored)-len(exact)-len(within1)-len(blanks):5d}")
    print(f"  blank -- nothing drew       : {len(blanks):5d}")
    if stale:
        print(f"  label differs from golden   : {len(stale):5d}  "
              f"<- goldens built from a different test suite; not comparable")
        for suite, test, *_ in stale[:8]:
            print(f"       {suite}::{test}")
    if sized:
        print(f"  wrong size                  : {len(sized):5d}")
    if nogold:
        print(f"  no golden to compare        : {len(nogold):5d}")

    suites = {}
    for suite, test, solo, status, differing, mrgb, ma, px, ob1 in scored:
        s = suites.setdefault(suite, {"n": 0, "exact": 0, "px": 0, "tot": 0,
                                      "mrgb": 0, "ma": 0, "blank": 0,
                                      "within1": 0})
        s["n"] += 1
        s["exact"] += differing == 0
        s["within1"] += status == "ok" and 0 < differing == ob1
        s["px"] += differing
        s["tot"] += px
        s["mrgb"] = max(s["mrgb"], mrgb)
        s["ma"] = max(s["ma"], ma)
        s["blank"] += status == "blank"

    order = sorted(suites.items(), key=lambda kv: (kv[1]["exact"] / kv[1]["n"],
                                                   -kv[1]["px"] / max(kv[1]["tot"], 1)))
    w = max(len(k) for k in suites) + 1
    print(f"\n{'suite':<{w}} {'exact':>11} {'+-1 only':>8} {'blank':>7} "
          f"{'px differing':>13} {'max RGB':>8} {'max A':>6}")
    print("-" * (w + 59))
    for name, s in order:
        share = s["px"] / max(s["tot"], 1) * 100
        mark = " *" if name in shared else ""
        blank = f"{s['blank']}" if s["blank"] else "-"
        within1 = f"{s['within1']}" if s["within1"] else "-"
        print(f"{name:<{w}} {s['exact']:>4}/{s['n']:<6} {within1:>8} {blank:>7} "
              f"{share:>12.2f}% {s['mrgb']:>8} {s['ma']:>6}{mark}")
    if shared:
        print("\n  * ran on a shared disc, not one test per run — these are the "
              "suites\n    the isolation build could not split, so contamination "
              "between their\n    own tests is not ruled out.")

    # Coverage against the oracle we own. A suite that runs fewer tests than it
    # has goldens is being scored on part of its oracle, and the score looks
    # respectable either way -- Depth_buffer read 28/144 exact on a ninth of
    # its masks and Blend_tests 16/105 on 6.7% of its tests, both for days,
    # because nothing compared these two numbers. The mismatch is the tell for
    # a suite whose tests were retired upstream; the 2025-03-14 disc still
    # emits them. docs/investigations/depth-full-oracle-2026-09-12.md
    partial = []
    for name, s in sorted(suites.items()):
        gdir = os.path.join(args.goldens, name)
        if not os.path.isdir(gdir):
            continue
        have = len([f for f in os.listdir(gdir) if f.endswith(".png")])
        if have > s["n"]:
            partial.append((name, s["n"], have))
    if partial:
        print("\n  PARTIAL COVERAGE — these suites have more goldens than the "
              "captures scored:")
        for name, got, have in sorted(partial, key=lambda r: r[1] / r[2]):
            print(f"    {name:<34} {got:>5} of {have:<5} "
                  f"({100.0 * got / have:>5.1f}%)")
        print("    A score over part of a suite is not the suite's score. If the "
              "gap is large,\n    the tests were probably retired upstream and "
              "need the 2025-03-14 disc.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
