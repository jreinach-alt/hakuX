#!/usr/bin/env python3
"""Selftest for framedump_correlate.py.

Every check here is built so that the interesting verdict is NOT free.

  - A leg that reports "no separation" is only worth printing if the same code
    reports SEPARATES on a dump where the counter really is tied to the label.
    So each null case has a planted twin.
  - F0's exclusion is the whole design, so it gets the mutant it deserves: a
    dump whose counters are all constant must reach NOT VISIBLE TO THIS
    INSTRUMENT and must score no leg at all.  A version that scored a constant
    would report a beautiful null.
  - The stale-binding leg is checked in both directions: a planted stale
    binding must be found, and an unplanted dump must report none.

Run:  python3 docs/lanes/diagsoak77/framedump_correlate_selftest.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import framedump_correlate as fc  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("%-62s %s%s" % (name, "ok" if ok else "FAIL",
                          "" if ok else "   " + detail))
    if not ok:
        fails.append(name)


def write_dump(d, n_frames=60, stipple_every=7, schema=3,
               submits_of=None, constant=False, stale_img_on_stipple=False,
               image_every=1, busy_from=None, rng=None):
    """Synthesise a dump whose frames are known to be stipple or clean.

    The images are noise at one amplitude for clean frames and a higher one for
    stipple frames, so the classifier's own 1.45x bar is what decides -- the
    label is planted in the PIXELS and recovered through the real classifier,
    not handed to the correlator directly.
    """
    rng = rng or np.random.default_rng(7)
    base = rng.normal(0, 1, (64, 64))
    path = os.path.join(d, "framedump_1.jsonl")
    out = [dict(t="session", schema=schema, id=1, spec="test", armed_by="test",
                draw_merge=False, draw_reorder=False, driver="test")]
    truth = []
    for f in range(n_frames):
        is_stip = (stipple_every is not None
                   and f % stipple_every == 0 and f % image_every == 0)
        imaged = (f % image_every == 0)
        busy = busy_from is not None and f >= busy_from
        if imaged:
            # `busy` is the second scene: more high-frequency content AND more
            # draws, the way a real one is, so the confound is built from the
            # same fact rather than planted twice.
            amp = 24.0 if (is_stip or busy) else 12.0
            arr = np.clip(128 + base * amp, 0, 255).astype(np.uint8)
            name = "framedump_1_f%03d.ppm" % f
            Image.fromarray(arr, "L").convert("RGB").save(
                os.path.join(d, name))
            truth.append((f, is_stip))

        if constant:
            submits, resets = 1, 0
        elif submits_of is not None:
            submits, resets = submits_of(f, is_stip)
        else:
            submits, resets = (1 + rng.integers(0, 3)), 0

        ndraws = 60 if busy else 20
        for i in range(ndraws):
            cbd = i + 1
            img = "0xAA"
            if stale_img_on_stipple and is_stip and i == 5:
                img = "0xBB"
            out.append(dict(t="draw", f=f, n=i, kind="arrays", count=3,
                            cb=1, cb_draws=cbd, submits=1000 + f, vkframe=0,
                            in_rp=1, dq=0, dq_active=0, rw=0, rw_active=0,
                            prim=4, shader="0", pipeline="0x1",
                            color=dict(addr="0x1", w=8, h=8, pitch=8, fmt=1,
                                       swizzle=0, dirty=1),
                            tex=[dict(s=0, en=1, fmt="0x1", off="0x2",
                                      addr="0x3", ctl0="0x4", ctl1="0x5",
                                      fil="0x6", img=img,
                                      submit_time=1000 + f)]))
        out.append(dict(t="frame", f=f, draws=ndraws,
                        submits_in_frame=submits, submits=1000 + f,
                        nv2a_frame=5000 + f,
                        image=("framedump_1_f%03d.ppm" % f) if imaged else None,
                        w=64, h=64, img_sync=0 if imaged else fc.IMG_STALE,
                        diag_active=0, wall=0))
    out.append(dict(t="end", why="test", frames=n_frames, draws=0, bytes=0,
                    images_stale=0))
    with open(path, "w") as fh:
        for r in out:
            fh.write(json.dumps(r) + "\n")
    return path, truth


def run(path, extra=()):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fc.main([path, "--perms", "2000"] + list(extra))
    return rc, buf.getvalue()


tmp = tempfile.mkdtemp(prefix="fdcorr-")
try:
    # ---------------------------------------------------- F0: all constant
    d = os.path.join(tmp, "const")
    os.makedirs(d)
    p, _ = write_dump(d, constant=True)
    rc, txt = run(p)
    check("all counters constant: reaches NOT VISIBLE TO THIS INSTRUMENT",
          "NOT VISIBLE TO THIS INSTRUMENT" in txt)
    check("all counters constant: scores no leg at all",
          "permutation null" not in txt and "SEPARATES" not in txt)
    check("all counters constant: names draw_merge gating explicitly",
          "CONSTANT BY CONSTRUCTION" in txt)

    # ------------------------------------------- planted correlation (F1)
    d = os.path.join(tmp, "planted")
    os.makedirs(d)
    p, truth = write_dump(
        d, submits_of=lambda f, s: (4 if s else 1, 0))
    rc, txt = run(p)
    n_stip = sum(1 for _, s in truth if s)
    check("planted: the classifier recovers the planted stipple frames",
          ("STIPPLE %d / " % n_stip) in txt, txt.split("region")[-1][:120])
    line = [l for l in txt.splitlines() if l.strip().startswith("submits_in_frame")]
    check("planted: submits_in_frame SEPARATES",
          bool(line) and "SEPARATES" in line[0], line[0] if line else "absent")

    # ---------------------------------------------- unplanted (the null)
    d = os.path.join(tmp, "null")
    os.makedirs(d)
    p, _ = write_dump(d, submits_of=lambda f, s: (1 + (f % 3), 0))
    rc, txt = run(p)
    line = [l for l in txt.splitlines()
            if l.strip().startswith("submits_in_frame")]
    check("unplanted: submits_in_frame does NOT separate",
          bool(line) and "no separation" in line[0], line[0] if line else "absent")
    check("unplanted: a minimum detectable difference is printed with it",
          "minimum detectable difference" in txt)

    # ------------------------------------------- the scene confound guard
    #
    # The case this guard exists for, reproduced: a dump spanning two scenes,
    # where the busier one has more draws AND more high-frequency content.  The
    # classifier flags the busier scene, every leg separates at once, and the
    # permutation test is powerless because the scene rides along with the
    # label.  Two arms of this lane produced exactly this before the window was
    # moved, and both replicated, which is what makes it dangerous.
    d = os.path.join(tmp, "twoscene")
    os.makedirs(d)
    # The busy scene must be a MINORITY of the dump, as it was in the real
    # arms (9 demo frames among 115): that is what leaves the local baseline
    # made of quiet frames, so the busy ones clear the ratio bar.  A dump that
    # is half one scene and half the other hides the confound instead of
    # showing it, which is itself worth knowing.
    p, _ = write_dump(d, n_frames=70, stipple_every=None,
                      submits_of=lambda f, s: (3 if f >= 64 else 1, 0),
                      busy_from=64)
    rc, txt = run(p)
    check("two scenes: the confound is named before any leg is read",
          "CONFOUNDED WITH SCENE" in txt)
    check("two scenes: the legs are marked descriptive only",
          "DESCRIPTIVE ONLY" in txt)
    idx_c = txt.find("CONFOUNDED WITH SCENE")
    idx_l = txt.find("== legs,")
    check("two scenes: the warning precedes the legs in the output",
          idx_c != -1 and idx_l != -1 and idx_c < idx_l)

    # ...and the converse, or the warning is free: one regime, no warning.
    d = os.path.join(tmp, "onescene")
    os.makedirs(d)
    p, _ = write_dump(d, submits_of=lambda f, s: (4 if s else 1, 0))
    rc, txt = run(p)
    check("one scene: no confound warning, legs are read normally",
          "CONFOUNDED WITH SCENE" not in txt and "SEPARATES" in txt,
          " | ".join(l.strip() for l in txt.splitlines()
                     if "spearman" in l or "draws " in l))

    # The tie bug this caught, pinned directly: `argsort(argsort(x))` ranks a
    # constant column 0..n-1 in frame order, so it correlates with anything
    # that trends.  A constant column must score exactly 0.
    check("spearman: a constant column scores 0, not an index correlation",
          fc.spearman(list(range(50)), [7.0] * 50) == 0.0,
          "got %.3f" % fc.spearman(list(range(50)), [7.0] * 50))
    check("spearman: ties are averaged, not broken by index",
          abs(fc.spearman([1, 1, 2, 2, 3, 3], [1, 1, 2, 2, 3, 3]) - 1.0) < 1e-9
          and abs(fc.spearman([1, 1, 2, 2], [9, 9, 9, 9])) < 1e-9)

    # ------------------------------------------------------ F2 both ways
    d = os.path.join(tmp, "stale")
    os.makedirs(d)
    p, _ = write_dump(d, submits_of=lambda f, s: (1 + (f % 3), 0),
                      stale_img_on_stipple=True)
    rc, txt = run(p)
    check("planted stale binding: F2 finds a guest state with two host images",
          "more than one host image on a stipple frame: 1" in txt
          or "answered by a DIFFERENT host image: 1" in txt,
          " | ".join(l.strip() for l in txt.splitlines()
                     if "host image" in l))

    d = os.path.join(tmp, "nostale")
    os.makedirs(d)
    p, _ = write_dump(d, submits_of=lambda f, s: (4 if s else 1, 0))
    rc, txt = run(p)
    check("no planted stale binding: F2 reports no stale-binding signature",
          "no stale-binding signature" in txt)

    # ------------------------------------------------ schema 2 is refused
    d = os.path.join(tmp, "schema2")
    os.makedirs(d)
    p, _ = write_dump(d, schema=2, submits_of=lambda f, s: (4 if s else 1, 0))
    rc, txt = run(p)
    check("schema 2: refused before any classification, exit 1",
          rc == 1 and "not pairable" in txt)
    check("schema 2: F0 is still reported, because it reads only records",
          "F0: which candidate counters can vary" in txt)

    # -------------------------------------- no stipple frame in the dump
    d = os.path.join(tmp, "clean")
    os.makedirs(d)
    p, _ = write_dump(d, stipple_every=None,
                      submits_of=lambda f, s: (1 + (f % 3), 0))
    rc, txt = run(p)
    check("no stipple frame: says so, and does not score a leg",
          "NO STIPPLE FRAME IN THIS DUMP" in txt and "SEPARATES" not in txt)
    check("no stipple frame: refuses to read it as evidence about the "
          "hypothesis",
          "not evidence for or against" in txt)
    # A null with no power attached is not a result, and the zero-flagged case
    # is the one where it is easiest to forget: there is no observed class size
    # to compute a minimum detectable difference from.
    check("no stipple frame: still states what it COULD have separated",
          "could have separated" in txt
          and "documented 12 per 100" in txt)

    # ------------------------- sparse images, the shape arm A1 came back in
    d = os.path.join(tmp, "sparse")
    os.makedirs(d)
    p, _ = write_dump(d, n_frames=120, image_every=10, stipple_every=20,
                      submits_of=lambda f, s: (1 + (f % 3), 0))
    rc, txt = run(p)
    check("sparse images: reports the gap and widens no claim silently",
          "median gap" in txt and "not consecutive ones" in txt)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if fails:
    print("FAILED: %d check(s): %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("all checks passed")
