#!/usr/bin/env python3
"""#43: the signed blend fold IS expressible in ordinary blend state, in TWO
passes -- no framebuffer fetch, no float intermediate surface, no extension.

WHAT THIS REFUTES

`vk/draw.c` records the fold as inexpressible, on a proof that is correct:

    silicon's output steps 254 -> 0 between adjacent source bytes at D=127,
    every Vulkan blend op is a continuous map of the source, and no
    composition of continuous maps is discontinuous.

The proof carries a qualifier that its list of remedies then drops -- "no
multi-pass arrangement of blend states driving *the same fragment output*".
Two passes driving TWO DIFFERENT fragment outputs are outside it, because the
discontinuity is then created in the SHADER, which may branch for free, and
the blend unit only ever sees a continuous map of what it is handed.

    f1 = S        if S < 128 else 0
    f2 = 0        if S < 128 else 256 - S

    FUNC_ADD_SIGNED               pass1 ADD(f1)      then pass2 REVSUB(f2)
    FUNC_REVERSE_SUBTRACT_SIGNED  pass1 REVSUB(f1)   then pass2 ADD(f2)

Both passes are ONE/ONE, which the landed factor half (ab4a829316) already
programs. Exactly one of f1,f2 is non-zero for any S, so the other pass is an
exact identity and the intermediate UNORM clamp cannot bite -- which is also
why the two passes COMMUTE (checked below as a control, not assumed).

draw.c prices the multi-pass option at "six to eight passes per draw", for one
pass per (channel, sign) with a colorWriteMask and a discard. Masking the
source to zero in the shader instead makes the off-sign channels identities, so
all four channels ride one pass and the cost is TWO, not six to eight.

WHAT THIS DOES NOT CLAIM

Two passes are exact only where a draw does not overlap ITSELF: the pass order
becomes p1(all prims), p2(all prims), so a pixel covered twice within one draw
blends in the wrong order. Every quad in blend_tests.cpp is its own
Begin/End -- DrawAlphaStack's four nested quads are four separate draws -- so
the corpus has no self-overlap and this is exact on it. Framebuffer fetch with
VK_EXT_rasterization_order_attachment_access would handle self-overlap; two
passes do not. See the issue for the depth/stencil/alpha-test conditions.

Run: python3 docs/testing/signed_blend_twopass.py [--goldens DIR]
"""
import argparse
import glob
import os
import sys

LABEL_ROWS = 64  # TestSpot prints its own test name into rows 0-63


def clamp(v):
    return 0 if v < 0 else (255 if v > 255 else v)


def sgn(S):
    return S - 256 if S >= 128 else S


def rule_sadd(S, D):
    return clamp(sgn(S) + D)


def rule_srevsub(S, D):
    return clamp(D - sgn(S))


def f1(S):
    return S if S < 128 else 0


def f2(S):
    return 0 if S < 128 else 256 - S


def two_sadd(S, D):
    return clamp(clamp(D + f1(S)) - f2(S))


def two_srevsub(S, D):
    return clamp(clamp(D - f1(S)) + f2(S))


def landed_sadd(S, D):
    """The factor half alone: clamp(D + S), unsigned source."""
    return clamp(D + S)


def landed_srevsub(S, D):
    return clamp(D - S)


# ---------------------------------------------------------------- exhaustive

def exhaustive():
    print("== exhaustive over all 256 x 256 (S, D) ==")
    ok = True
    for name, rule, cand, landed in (
            ("FUNC_ADD_SIGNED", rule_sadd, two_sadd, landed_sadd),
            ("FUNC_REVERSE_SUBTRACT_SIGNED", rule_srevsub, two_srevsub,
             landed_srevsub)):
        bad = badlo = badhi = 0
        lbad = lbadlo = lbadhi = 0
        for S in range(256):
            for D in range(256):
                r = rule(S, D)
                if cand(S, D) != r:
                    bad += 1
                    if S >= 128:
                        badhi += 1
                    else:
                        badlo += 1
                if landed(S, D) != r:
                    lbad += 1
                    if S >= 128:
                        lbadhi += 1
                    else:
                        lbadlo += 1
        print("  %s" % name)
        print("    landed (factor half) wrong %6d  [S<128 %6d  S>=128 %6d]"
              % (lbad, lbadlo, lbadhi))
        print("    TWO-PASS             wrong %6d  [S<128 %6d  S>=128 %6d]"
              % (bad, badlo, badhi))
        ok = ok and bad == 0
    return ok


# ------------------------------------------------------------------ controls

def controls():
    """A checker that only ever prints 0 is not a checker."""
    print("== negative controls (these MUST fail) ==")
    variants = [
        ("CORRECT two-pass", two_sadd, True),
        ("commuted pass order", lambda S, D: clamp(clamp(D - f2(S)) + f1(S)),
         True),
        ("S-128 instead of 256-S",
         lambda S, D: clamp(clamp(D + f1(S)) - (0 if S < 128 else S - 128)),
         False),
        ("unmasked f1 (f1 = S)",
         lambda S, D: clamp(clamp(D + S) - f2(S)), False),
        ("unmasked f2",
         lambda S, D: clamp(clamp(D + f1(S)) - (256 - S)), False),
        ("both passes ADD",
         lambda S, D: clamp(clamp(D + f1(S)) + f2(S)), False),
        ("single pass only", lambda S, D: clamp(D + f1(S)), False),
    ]
    ok = True
    for name, fn, expect_zero in variants:
        bad = sum(1 for S in range(256) for D in range(256)
                  if fn(S, D) != rule_sadd(S, D))
        verdict = "ok" if (bad == 0) == expect_zero else "INSTRUMENT FAULT"
        if verdict != "ok":
            ok = False
        print("  %-24s wrong %6d   %s" % (name, bad, verdict))
    both = [S for S in range(256) if f1(S) and f2(S)]
    print("  S where BOTH passes contribute: %d  (why the clamp is an "
          "identity, and why the passes commute)" % len(both))
    return ok and not both


# -------------------------------------------------------------- golden solve

def recover(path_a, path_b, skip_rows):
    """Closed-form (S, D) from a SADD/SREVSUB golden pair.

    a = clamp(sgn(S)+D), b = clamp(D-sgn(S)); where neither saturated,
    D = (a+b)/2 and sgn(S) = (a-b)/2. A different instrument from the prior
    lane's exhaustive (S,D) sweep, so agreement validates both.

    BLIND SPOT, stated because a zero from a blind instrument is not evidence:
    any channel where either equation saturated is unrecoverable, so a
    destination of 0 or 255 contributes nothing at all. On
    Texture_signed_component_tests that leaves only D=127. The Blend_tests
    pairs are what supply the other destinations.
    """
    from PIL import Image
    A = Image.open(path_a).convert("RGBA")
    B = Image.open(path_b).convert("RGBA")
    W, H = A.size
    la, lb = A.load(), B.load()
    out = dict(solved=0, lo=0, hi=0, bad_a=0, bad_b=0,
               landed_lo=0, landed_hi=0, dvals={})
    for y in range(skip_rows, H):
        for x in range(W):
            ca, cb = la[x, y], lb[x, y]
            for ch in range(4):
                av, bv = ca[ch], cb[ch]
                if av in (0, 255) or bv in (0, 255) or (av + bv) % 2:
                    continue
                D = (av + bv) // 2
                sg = (av - bv) // 2
                if not (-128 <= sg <= 127):
                    continue
                S = sg + 256 if sg < 0 else sg
                out["solved"] += 1
                out["dvals"][D] = out["dvals"].get(D, 0) + 1
                if S >= 128:
                    out["hi"] += 1
                else:
                    out["lo"] += 1
                if two_sadd(S, D) != av:
                    out["bad_a"] += 1
                if two_srevsub(S, D) != bv:
                    out["bad_b"] += 1
                if landed_sadd(S, D) != av:
                    if S >= 128:
                        out["landed_hi"] += 1
                    else:
                        out["landed_lo"] += 1
    return out


def goldens(root):
    print("== against silicon's goldens ==")
    groups = [
        ("Texture_signed_component_tests",
         [(os.path.join(root, "Texture_signed_component_tests",
                        "txt_A8R8G8B8_SADD.png"),
           os.path.join(root, "Texture_signed_component_tests",
                        "txt_A8R8G8B8_SREVSUB.png"))], 0),
        ("Blend_tests (render target + blit, label band skipped)",
         [(p, p.replace("_SADD.png", "_SREVSUB.png"))
          for p in sorted(glob.glob(os.path.join(root, "Blend_tests",
                                                 "#spot_*_SADD.png")))],
         LABEL_ROWS),
    ]
    grand = dict(solved=0, bad_a=0, bad_b=0, lo=0, hi=0,
                 landed_lo=0, landed_hi=0)
    alld = {}
    ok = True
    for label, pairs, skip in groups:
        pairs = [(a, b) for a, b in pairs
                 if os.path.exists(a) and os.path.exists(b)]
        if not pairs:
            print("  %s: NO GOLDEN PAIRS FOUND -- not a pass" % label)
            ok = False
            continue
        tot = dict(solved=0, bad_a=0, bad_b=0, lo=0, hi=0,
                   landed_lo=0, landed_hi=0)
        for a, b in pairs:
            r = recover(a, b, skip)
            for k in tot:
                tot[k] += r[k]
            for d, c in r["dvals"].items():
                alld[d] = alld.get(d, 0) + c
        print("  %s" % label)
        print("    pairs %d   channels recovered %d  [S<128 %d  S>=128 %d]"
              % (len(pairs), tot["solved"], tot["lo"], tot["hi"]))
        print("    TWO-PASS mismatches vs silicon: SADD %d   SREVSUB %d"
              % (tot["bad_a"], tot["bad_b"]))
        print("    landed factor half wrong: S<128 %d   S>=128 %d   "
              "(the published signature: 0 low, all high)"
              % (tot["landed_lo"], tot["landed_hi"]))
        if tot["bad_a"] or tot["bad_b"] or tot["landed_lo"]:
            ok = False
        for k in grand:
            grand[k] += tot[k]
    print("")
    print("  TOTAL golden channels %d   TWO-PASS mismatches %d"
          % (grand["solved"], grand["bad_a"] + grand["bad_b"]))
    print("  distinct destinations recovered: %d  %s"
          % (len(alld), sorted(alld)))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    args = ap.parse_args()
    a = exhaustive()
    print("")
    b = controls()
    print("")
    try:
        c = goldens(args.goldens)
    except ImportError:
        print("== against silicon's goldens ==")
        print("  Pillow not available -- golden half SKIPPED, not passed")
        c = False
    print("")
    if a and b and c:
        print("VERDICT: two-pass reproduces silicon exactly, exhaustively and "
              "on the goldens, with controls discriminating.")
        return 0
    print("VERDICT: INCOMPLETE -- see above. A skipped half is not a pass.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
