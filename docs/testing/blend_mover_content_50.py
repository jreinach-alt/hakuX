#!/usr/bin/env python3
"""#50: WHAT is in the pixels that move, and where does that content come from?

`fulldisc_instability_50.py` says WHICH captures move and splits them into a
device difference and a race.  This says what the moved pixels contain, and
kills two mechanisms for them.

THE OBSERVATION THIS STARTS FROM.  In all five movers, the run that is out on
its own writes GREY (R==G==B) over content the golden has in colour, and it is
always the run that does NOT match hardware:

  - four captures: nova is the odd one, thor matches the golden;
  - one capture (1-srcRGB_SADD_0): thor-B is the odd one, and nova and thor-2
    both match the golden and each other to the byte.

So the device difference and the race deposit the SAME KIND of wrong pixel.
That is the reason to look for one mechanism rather than two.

THREE READINGS, each with its own refutation
--------------------------------------------
(1) The grey is the ALPHA CHANNEL, i.e. an alpha-stack render landing where a
    colour-stack render belongs.  DrawAlphaStack draws alpha as greyscale, so
    this is the obvious first guess for grey in a Blend capture.
    REFUTED: 0 of every grey pixel equals the golden's alpha there, and 0
    equals the capture's own alpha.  It also cannot be a function of the
    golden pixel at all -- golden (0,102,0) and golden (41,0,0) both map to
    grey 10.

(2) The grey is ANOTHER TEST'S HARDWARE IMAGE.
    REFUTED: flat.  Best golden reproduces 24-33% of the moved pixels, with
    many exact ties -- the signature of several goldens being black in that
    region, not of a source.

(3) The grey is ANOTHER CAPTURE FROM THIS RUN -- a predecessor's framebuffer
    surviving, the RenderTextureLoop class make_test_iso.py documents.  This
    is the one reading (2) cannot settle, because our output differs from the
    goldens on 1,672 of 1,673 captures: content leaking from an earlier test
    would be OUR render of it, not hardware's.
    REFUTED: also flat, and the immediate predecessor scores 0.0% in four of
    the five.

WHAT IS LEFT, stated as the limit it is: the moved pixels hold structured grey
content that is not this capture's alpha, not any golden, and not any other
capture this run produced.  This file names no site.  It closes three doors.

THE CONTROL, and the two ways it was wrong first.  The search ranks candidate
images by how many of the moved pixels they reproduce.

  * The capture's OWN image from the odd run is not a control -- it scores
    100% by construction, since the moved pixels are read out of it.  The
    control is the AGREEING run's image of the same capture, which must score
    0% for the same reason.
  * It did not, first time: 1,024 px on 1-dstRGB_MIN_1.  The mask was built
    over RGBA while the search compared RGB, so pixels that move ONLY IN
    ALPHA landed in the mask with identical RGB and the control scored them.
    The mask is RGB now and the alpha-only movers are counted separately --
    they are a real part of the signal (see `alpha-only` below) and were
    being silently folded into the colour one.

A non-zero agreeing-run score still means the mask is not what this file
thinks it is, and it is printed on every row rather than asserted once.
"""
import os, re, sys, collections
import numpy as np
from PIL import Image

R = os.environ.get("HAKUX_RESULTS", "/home/justin/hakux-work/dispatch/results")
G = os.environ.get("GOLDENS", "/home/justin/goldens/results")
RUNS = {"nova-A": "1789318910-blendstack-A-63953",
        "thor-B": "1789318915-blendstack-B-64031",
        "thor-2": "1789326864-blendstack-thor2-889257"}
# capture, the run that is out on its own, a run that agrees with the golden
CASES = [("cA_MIN_srcRGB", "nova-A", "thor-B"),
         ("1-dstRGB_MIN_1", "nova-A", "thor-B"),
         ("srcA_REVSUB_1-cA", "nova-A", "thor-B"),
         ("1-dstA_SUB_1-cRGB", "nova-A", "thor-B"),
         ("1-srcRGB_SADD_0", "thor-B", "thor-2")]


def rgba(p):
    return np.asarray(Image.open(p).convert("RGBA"), dtype=np.uint8)


def cap(run, t):
    return rgba(os.path.join(R, RUNS[run], "captures1", "Blend_tests::%s.png" % t))


def golden(t):
    p = os.path.join(G, "Blend_tests/%s.png" % t)
    return rgba(p) if os.path.exists(p) else None


def run_order():
    p = os.path.join(R, RUNS["thor-B"], "captures1", "pgraph_progress_log.txt")
    out = []
    for line in open(p, errors="replace"):
        m = re.match(r"Starting \[\d+/\d+\] Blend tests::(.*)", line.strip())
        if m:
            out.append(m.group(1))
    return out


def main():
    order = run_order()
    idx = {t: i + 1 for i, t in enumerate(order)}

    print("=== WHAT THE MOVED PIXELS CONTAIN")
    for t, bad, good in CASES:
        b, g = cap(bad, t), cap(good, t)
        gl = golden(t)
        mask = np.any(b[:, :, :3] != g[:, :, :3], axis=2)
        anymask = np.any(b != g, axis=2)
        alpha_only = int(anymask.sum()) - int(mask.sum())
        n = int(mask.sum())
        bs = b[mask]
        grey = (bs[:, 0] == bs[:, 1]) & (bs[:, 1] == bs[:, 2])
        ng = int(grey.sum())
        line = ("  %-20s #%-5d moved %6d px (RGB) + %4d alpha-only   grey %6d (%.1f%%)"
                % (t, idx.get(t, -1), n, alpha_only, ng, 100.0 * ng / max(1, n)))
        if gl is not None:
            ga = gl[mask][:, 3]
            eq = int((grey & (bs[:, 0] == ga)).sum())
            oa = b[mask][:, 3]
            eqo = int((grey & (bs[:, 0] == oa)).sum())
            line += "   ==golden alpha %d   ==own alpha %d" % (eq, eqo)
            # which run agrees with hardware on the moved pixels
            gm = int(np.all(g[mask][:, :3] == gl[mask][:, :3], axis=1).sum())
            bm = int(np.all(bs[:, :3] == gl[mask][:, :3], axis=1).sum())
            line += "\n      of the moved px, %-7s matches golden RGB on %d, %-7s on %d" % (
                good, gm, bad, bm)
        print(line)

    # ---- the two searches -------------------------------------------------
    gdir = os.path.join(G, "Blend_tests")
    goldens = {}
    if os.path.isdir(gdir):
        for f in sorted(os.listdir(gdir)):
            if f.endswith(".png"):
                goldens[f[:-4]] = rgba(os.path.join(gdir, f))[:, :, :3]

    owncache = {}
    for _, bad, _ in CASES:
        if bad in owncache:
            continue
        cdir = os.path.join(R, RUNS[bad], "captures1")
        owncache[bad] = {f[len("Blend_tests::"):-4]: rgba(os.path.join(cdir, f))[:, :, :3]
                         for f in sorted(os.listdir(cdir)) if f.endswith(".png")}

    for label, pool_for in (("GOLDENS (hardware)", lambda bad: goldens),
                            ("THIS RUN'S OWN CAPTURES", lambda bad: owncache[bad])):
        print()
        print("=== SEARCH: does any image in %s reproduce the moved content?" % label)
        for t, bad, good in CASES:
            b, g = cap(bad, t), cap(good, t)
            mask = np.any(b[:, :, :3] != g[:, :, :3], axis=2)
            n = int(mask.sum())
            bs = b[mask][:, :3]
            pool = pool_for(bad)
            scores = []
            for nm, im in pool.items():
                if nm == t:
                    continue            # scores 100% by construction, not a control
                if im.shape[:2] != b.shape[:2]:
                    continue
                scores.append((int(np.all(im[mask] == bs, axis=1).sum()), nm))
            scores.sort(reverse=True)
            # the real control: the agreeing run's own image, which must be 0
            ctrl = int(np.all(g[mask][:, :3] == bs, axis=1).sum())
            print("  == %-20s odd=%-7s moved=%d" % (t, bad, n))
            print("     CONTROL: the agreeing run (%s) scores %d px -- must be 0"
                  % (good, ctrl))
            for sc, nm in scores[:4]:
                tag = ""
                if abs(idx.get(nm, -999) - idx.get(t, 0)) <= 3:
                    tag = "  <-- NEIGHBOUR in run order"
                print("     %6d px (%5.1f%%)  %-28s #%-5s%s"
                      % (sc, 100.0 * sc / max(1, n), nm, idx.get(nm, "?"), tag))
            prev = order[idx[t] - 2] if idx.get(t, 0) > 1 else None
            if prev and prev in pool:
                ps = int(np.all(pool[prev][mask] == bs, axis=1).sum())
                print("     immediate predecessor %-24s #%-5d %6d px (%.1f%%)"
                      % (prev, idx[prev], ps, 100.0 * ps / max(1, n)))
            top = scores[0][0] if scores else 0
            # THE TOP SCORE MEANS NOTHING WITHOUT THE POOL IT CAME FROM.
            # These captures are highly similar to each other and largely
            # black outside the swatches, so a candidate can reproduce a
            # large share of the moved pixels by agreeing on black. Print the
            # distribution so "81%" can be read against what an arbitrary
            # candidate already scores, rather than as a hit on its own.
            vals = sorted(s for s, _ in scores)
            if vals:
                med = vals[len(vals) // 2]
                p99 = vals[int(len(vals) * 0.99)]
                print("     -> best non-self %.1f%%  | pool median %.1f%%  p99 %.1f%%"
                      % (100.0 * top / max(1, n), 100.0 * med / max(1, n),
                         100.0 * p99 / max(1, n)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
