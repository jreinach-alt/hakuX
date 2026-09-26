#!/usr/bin/env python3
"""Score the retired 1,568-test `Blend tests` oracle against a closed-form model.

`BlendTests::TestDetailed` (still in nxdk_pgraph_tests as an interactive-only
test) draws one capture per `<sfactor>_<eqn>_<dfactor>` triple: three
render-to-texture blocks, each over a 16 pixel checkerboard of 0x33333333 and
opaque black, each blitted to the 640x480 screen through an A8B8G8R8 texture
stage over a 24 texel screen checkerboard.

    left    x[16,80)   y[112,368)   64x256   RGB blended, alpha written straight
    center  x[192,448) y[112,368)   256x256  RGB written straight, alpha blended
                                             through four nested quads in turn
    right   x[560,624) y[112,368)   64x256   all four channels blended

This walks blend -> 8 bit store -> byte reinterpretation -> alpha blit -> 8 bit
store for every pixel of all three blocks and compares whole REGIONS against
the goldens, never point samples.  The 1,120 captures using the five unsigned
equations are the control: the model has to reproduce silicon on them before
any claim about the two signed equations means anything.

    blend_detailed_oracle.py --control          score the 1,120 unsigned captures
    blend_detailed_oracle.py --signed           score the 448 signed captures
    blend_detailed_oracle.py --fifth-quad DIR   locate our own residual

Goldens default to /home/justin/goldens/results/Blend_tests.
"""
import numpy as np
from fractions import Fraction as F
from PIL import Image
import os, sys, functools

FACTORS = ["0","1","srcRGB","1-srcRGB","srcA","1-srcA","dstA","1-dstA",
           "dstRGB","1-dstRGB","srcAsat","cRGB","1-cRGB","cA","1-cA"]
CONST = (85,85,85,85)
W,H = 640,480

def q(x):  # round-half-up store to 8 bit, saturating
    return min(255, max(0, int(x*255 + F(1,2))))

def factor(name, s, d, ch):
    return {
      "0": lambda: F(0), "1": lambda: F(1),
      "srcRGB": lambda: F(s[ch],255), "1-srcRGB": lambda: 1-F(s[ch],255),
      "srcA": lambda: F(s[3],255),    "1-srcA":   lambda: 1-F(s[3],255),
      "dstA": lambda: F(d[3],255),    "1-dstA":   lambda: 1-F(d[3],255),
      "dstRGB": lambda: F(d[ch],255), "1-dstRGB": lambda: 1-F(d[ch],255),
      "srcAsat": lambda: F(1) if ch==3 else F(min(s[3],255-d[3]),255),
      "cRGB": lambda: F(CONST[ch],255), "1-cRGB": lambda: 1-F(CONST[ch],255),
      "cA": lambda: F(CONST[3],255),    "1-cA":   lambda: 1-F(CONST[3],255),
    }[name]()

def signed(v):
    return v-256 if v >= 128 else v

def blend(eqn, src, dst, sf, df, ch, signed_rule=True):
    """Blend result as a Fraction in [0,1]."""
    if eqn == "MIN": return min(F(src[ch],255), F(dst[ch],255))
    if eqn == "MAX": return max(F(src[ch],255), F(dst[ch],255))
    if eqn in ("SADD","SREVSUB"):
        if signed_rule:
            # both factors ignored; source read as a signed byte; saturate
            s = signed(src[ch]); d = dst[ch]
            v = F(s+d,255) if eqn=="SADD" else F(d-s,255)
            return min(F(1), max(F(0), v))
        eqn = {"SADD":"ADD","SREVSUB":"REVSUB"}[eqn]   # what we do today
    a = F(src[ch],255)*factor(sf,src,dst,ch)
    b = F(dst[ch],255)*factor(df,src,dst,ch)
    v = {"ADD":a+b,"SUB":a-b,"REVSUB":b-a}[eqn]
    return min(F(1), max(F(0), v))

# ---- scene ------------------------------------------------------------------
# NV097_SET_DIFFUSE_COLOR4I packs ABGR, so 0xDDDD0000 is blue.  (The reversal
# at the blit undoes this; the pair is unobservable here -- see write-up.)
def abgr(c):
    return ((c)&0xFF, (c>>8)&0xFF, (c>>16)&0xFF, (c>>24)&0xFF)

COLORSTACK = [abgr(x) for x in (0xDD00DD00,0xDDDD0000,0xDD0000DD,0xDDFFFFFF)]
CASTACK    = [abgr(x) for x in (0xDDFFFFFF,0xDD0000DD,0xDDDD0000,0xDD00DD00)]
ALPHAQUADS = [((0,0,256,256),  abgr(0x7F00CC00)),
              ((24,24,232,232),abgr(0xFFCC0000)),
              ((48,48,208,208),abgr(0x800000FF)),
              ((72,72,184,184),abgr(0x00FFFFFF))]
# blits: (name, screen x0, y0, rt w, rt h)
BLITS = [("left",16,112,64,256), ("center",192,112,256,256), ("right",560,112,64,256)]
CHECK = 16

def rt_bg(rx,ry):
    return (51,51,51,51) if ((rx//CHECK)+(ry//CHECK))%2==0 else (0,0,0,255)

def screen_bg(x,y):
    """24 texel checkers of 0xFF202020 / black in a 256x256 texture over 640x480."""
    u,v = (x*256)//640, (y*256)//480
    return 32 if ((u//24)+(v//24))%2==0 else 0

# ---- render-target prediction ----------------------------------------------
def rt_left(eqn,sf,df,sr,stack):
    """64x256 RT: RGB blended, alpha written straight."""
    out = np.zeros((256,64,4),dtype=int)
    for sw in range(4):
        for ph in (0,1):
            src = stack[sw]; dst = (51,51,51,51) if ph==0 else (0,0,0,255)
            px = [q(blend(eqn,src,dst,sf,df,ch,sr)) for ch in range(3)] + [src[3]]
            ys,xs = np.mgrid[sw*64:sw*64+64, 0:64]
            m = (((xs//CHECK)+(ys//CHECK))%2 == (0 if ph==0 else 1))
            out[ys[m],xs[m]] = px
    return out

def rt_right(eqn,sf,df,sr):
    """64x256 RT: all four channels blended in one pass."""
    out = np.zeros((256,64,4),dtype=int)
    for sw in range(4):
        for ph in (0,1):
            src = CASTACK[sw]; dst = (51,51,51,51) if ph==0 else (0,0,0,255)
            px = [q(blend(eqn,src,dst,sf,df,ch,sr)) for ch in range(4)]
            ys,xs = np.mgrid[sw*64:sw*64+64, 0:64]
            m = (((xs//CHECK)+(ys//CHECK))%2 == (0 if ph==0 else 1))
            out[ys[m],xs[m]] = px
    return out

def rt_center(eqn,sf,df,sr):
    """256x256 RT: RGB written straight, alpha blended, quad after quad."""
    out = np.zeros((256,256,4),dtype=int)
    chain = {}
    for k in range(1,5):
        for ph in (0,1):
            cur = list((51,51,51,51) if ph==0 else (0,0,0,255))
            for j in range(k):
                src = ALPHAQUADS[j][1]
                cur[0:3] = list(src[0:3])                     # RGB, blending off
                cur[3] = q(blend(eqn,src,tuple(cur),sf,df,3,sr))
            chain[(k,ph)] = list(cur)
    ys,xs = np.mgrid[0:256,0:256]
    kk = np.ones((256,256),dtype=int)
    for (l,t,r,b),_ in ALPHAQUADS[1:]:
        kk += ((xs>=l)&(xs<r)&(ys>=t)&(ys<b)).astype(int)
    ph = ((xs//CHECK)+(ys//CHECK))%2
    for k in range(1,5):
        for p in (0,1):
            m = (kk==k)&(ph==p)
            out[ys[m],xs[m]] = chain[(k,p)]
    return out

@functools.lru_cache(maxsize=None)
def bg_arrays():
    ys,xs = np.mgrid[0:H,0:W]
    u,v = (xs*256)//640, (ys*256)//480
    return np.where(((u//24)+(v//24))%2==0, 32, 0)

def blit(rt, x0, y0):
    """A8R8G8B8 surface sampled as A8B8G8R8 (RGB reversed), alpha blended over
    the screen checkerboard with SRC_ALPHA / ONE_MINUS_SRC_ALPHA."""
    h,w,_ = rt.shape
    samp = rt[:,:,[2,1,0,3]]
    a = samp[:,:,3].astype(np.int64)
    bg = bg_arrays()[y0:y0+h, x0:x0+w].astype(np.int64)
    out = np.zeros((h,w,4),dtype=np.int64)
    for c in range(3):
        # round((samp*a + bg*(255-a)) / 255)
        out[:,:,c] = (samp[:,:,c].astype(np.int64)*a + bg*(255-a) + 127)//255
    out[:,:,3] = (a*a + 255*(255-a) + 127)//255
    return np.clip(out,0,255)

def predict(eqn,sf,df,signed_rule=True):
    """Full 640x480 screen prediction; NaN-free, with a validity mask."""
    img = np.zeros((H,W,4),dtype=np.int64)
    valid = np.zeros((H,W),dtype=bool)
    img[:,:,0] = img[:,:,1] = img[:,:,2] = bg_arrays()
    img[:,:,3] = 255
    valid[:,:] = True
    for name,x0,y0,w,h in BLITS:
        rt = {"left":  lambda: rt_left(eqn,sf,df,signed_rule,COLORSTACK),
              "right": lambda: rt_right(eqn,sf,df,signed_rule),
              "center":lambda: rt_center(eqn,sf,df,signed_rule)}[name]()
        img[y0:y0+h, x0:x0+w] = blit(rt,x0,y0)
    return img

# ---- scoring ----------------------------------------------------------------
UNSIGNED = ["ADD","SUB","REVSUB","MIN","MAX"]
SIGNED   = ["SADD","SREVSUB"]
GOLDENS  = "/home/justin/goldens/results/Blend_tests"
CHANNELS = "RGBA"


def tests(eqns):
    """Every TestDetailed name, in suite order.  0_<eqn>_0 is never generated."""
    for eqn in eqns:
        for sf in FACTORS:
            for df in FACTORS:
                if sf == "0" and df == "0":
                    continue
                yield f"{sf}_{eqn}_{df}", eqn, sf, df


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.int64)


def region_scores(gold, pred):
    """Per-block, per-channel matching channel counts, plus the outside-blit
    residual (which carries the pb_print text overlay and nothing else)."""
    out = {}
    for name, x0, y0, w, h in BLITS:
        g = gold[y0:y0+h, x0:x0+w]
        p = pred[y0:y0+h, x0:x0+w]
        out[name] = [(int((g[:, :, c] == p[:, :, c]).sum()), w*h) for c in range(4)]
    mask = np.ones(gold.shape[:2], dtype=bool)
    for _, x0, y0, w, h in BLITS:
        mask[y0:y0+h, x0:x0+w] = False
    out["outside"] = [(int((gold[:, :, c][mask] == pred[:, :, c][mask]).sum()),
                       int(mask.sum())) for c in range(4)]
    return out


def run(eqns, goldens, signed_rule=True, verbose=False):
    per_block = {n: [[0, 0] for _ in range(4)] for n in
                 [b[0] for b in BLITS] + ["outside"]}
    failures = []          # (test, block, channel, bad channel count)
    n_caps = n_exact = 0
    for name, eqn, sf, df in tests(eqns):
        path = os.path.join(goldens, name + ".png")
        if not os.path.exists(path):
            continue
        n_caps += 1
        sc = region_scores(load(path), predict(eqn, sf, df, signed_rule))
        clean = True
        for block, chans in sc.items():
            for c, (hit, tot) in enumerate(chans):
                per_block[block][c][0] += hit
                per_block[block][c][1] += tot
                if hit != tot and block != "outside":
                    failures.append((name, eqn, sf, df, block, CHANNELS[c], tot - hit))
                    clean = False
        n_exact += clean
        if verbose:
            blocks = " ".join(f"{b}:{sum(h for h,_ in sc[b])}/{sum(t for _,t in sc[b])}"
                              for b, _, _, _, _ in BLITS)
            print(f"  {name:28} {blocks}")
    return n_caps, n_exact, per_block, failures


def report(label, n_caps, n_exact, per_block, failures):
    print(f"\n== {label}: {n_caps} captures, {n_exact} exact on all three blocks")
    for block in [b[0] for b in BLITS] + ["outside"]:
        chans = per_block[block]
        tot_h, tot_t = sum(h for h, _ in chans), sum(t for _, t in chans)
        if not tot_t:
            continue
        per_ch = "  ".join(f"{CHANNELS[c]} {chans[c][0]}/{chans[c][1]}" for c in range(4))
        print(f"  {block:8} {tot_h}/{tot_t} channels   {per_ch}")
    if failures:
        import collections
        print(f"  {len(failures)} (capture, block, channel) failures")
        by = collections.Counter((f[4], f[5]) for f in failures)
        for (block, ch), n in sorted(by.items()):
            print(f"    {block:8} {ch}: {n} captures")
        by_eqn = collections.Counter((f[1], f[4], f[5]) for f in failures)
        for k, n in sorted(by_eqn.items()):
            print(f"    eqn {k[0]:8} {k[1]:8} {k[2]}: {n}")
        sf_set = collections.Counter(f[2] for f in failures)
        df_set = collections.Counter(f[3] for f in failures)
        print(f"    sfactors involved: {dict(sf_set)}")
        print(f"    dfactors involved: {dict(df_set)}")
        print("    worst 12 by deviating channels:")
        for f in sorted(failures, key=lambda f: -f[6])[:12]:
            print(f"      {f[0]:28} {f[4]:8} {f[5]} {f[6]} of region")


def fifth_quad(captures, goldens, eqns):
    """Where OUR renders differ from silicon, by block.  This cannot move the
    verdict above, which is model-against-golden and never reads a capture.
    Stack A and stack B are bit-exact on all 1,120 unsigned captures, so a
    residual there is attributable; stack C differs on 1,567 of 1,568 including
    every unsigned one and belongs to #50, so it is reported and not
    attributed."""
    import collections
    tally = collections.Counter()
    shapes = collections.Counter()
    n = 0
    for name, eqn, sf, df in tests(eqns):
        gp = os.path.join(goldens, name + ".png")
        cp = os.path.join(captures, "Blend_tests::" + name + ".png")
        if not (os.path.exists(gp) and os.path.exists(cp)):
            continue
        n += 1
        g, c = load(gp), load(cp)
        bad = (g != c).any(axis=2)
        for bname, x0, y0, w, h in BLITS:
            k = int(bad[y0:y0+h, x0:x0+w].sum())
            if k:
                tally[bname] += 1
                shapes[(bname, k)] += 1
        mask = np.ones(bad.shape, dtype=bool)
        for _, x0, y0, w, h in BLITS:
            mask[y0:y0+h, x0:x0+w] = False
        if bad[mask].any():
            tally["outside"] += 1
    print(f"\n== our renders vs silicon, {n} captures")
    for k, v in sorted(tally.items()):
        print(f"  {k:8} differs on {v} captures")
    print("  differing pixel counts per block:")
    for k, v in sorted(shapes.items(), key=lambda kv: -kv[1])[:10]:
        print(f"    {k[0]:8} {k[1]:6} px on {v} captures")


def layout_gate(goldens, eqns):
    """Separate "the rule is wrong here" from "this capture is a different test
    revision than its golden".

    A revision difference shows up as content in the wrong PLACE -- the order,
    position or extent of the swatch stacks -- while a blend-rule failure shows
    up as the right geometry carrying wrong values.  So for each golden this
    re-predicts the left and right swatch blocks under all 24 permutations of
    the four source colours and asks which ones the golden accepts.  A golden
    that accepts the current source's order and rejects the other 23 has its
    layout PINNED: it cannot be a capture of a revision that reordered the
    stack.  A golden that accepts more than one order is degenerate for this
    question (the source contributes nothing there, e.g. sfactor=0) and is
    counted separately rather than claimed as evidence.
    """
    import collections, itertools
    perms = list(itertools.permutations(range(4)))
    tally = collections.Counter()
    unpinned = []
    for name, eqn, sf, df in tests(eqns):
        path = os.path.join(goldens, name + ".png")
        if not os.path.exists(path):
            continue
        gold = load(path)
        tally["captures"] += 1
        accepted = {}
        for block, x0, y0, w, h in [b for b in BLITS if b[0] != "center"]:
            g = gold[y0:y0+h, x0:x0+w]
            base = COLORSTACK if block == "left" else CASTACK
            ok = []
            for pi, perm in enumerate(perms):
                stack = [base[i] for i in perm]
                if block == "left":
                    rt = rt_left(eqn, sf, df, True, stack)
                else:
                    saved = globals()["CASTACK"]
                    globals()["CASTACK"] = stack
                    rt = rt_right(eqn, sf, df, True)
                    globals()["CASTACK"] = saved
                if (blit(rt, x0, y0) == g).all():
                    ok.append(perm)
            accepted[block] = ok
            identity = tuple(range(4))
            if identity not in ok:
                tally[block + ":REJECTS current order"] += 1
            elif len(ok) == 1:
                tally[block + ":pinned to current order"] += 1
            else:
                tally[block + ":degenerate (accepts %d orders)" % len(ok)] += 1
        if any(tuple(range(4)) not in v for v in accepted.values()):
            unpinned.append(name)
    print(f"\n== layout gate: {tally['captures']} goldens, 24 swatch orders each")
    for k, v in sorted(tally.items()):
        if k != "captures":
            print(f"  {k:44} {v}")
    if unpinned:
        print(f"  QUARANTINE: {len(unpinned)} goldens reject the current source order")
        for n in unpinned[:20]:
            print(f"    {n}")
    else:
        print("  no golden rejects the current source order: layout agrees everywhere")
    return unpinned


VARIANTS = {
    "signed byte, saturate (the #43 rule)": {},
    "sign threshold 127 not 128":           {"thresh": 127},
    "sign threshold 129 not 128":           {"thresh": 129},
    "wrap at 256 instead of saturate":      {"wrap": True},
    "signed source AND signed destination": {"signed_dst": True},
    "factors honoured, source still signed":{"honour": True},
    "0.5 bias on the signed source":        {"bias": True},
    "destination signed, source unsigned":  {"only_dst": True},
}


def falsify(goldens):
    """A fit nobody can fail is not evidence.  Each rival below is the #43 rule
    with one thing changed; each must be rejected by the same goldens.  The
    scene constants get the same treatment -- if the geometry were wrong the
    arithmetic fit would be meaningless.
    """
    import copy
    global _VAR
    base_blend = blend

    def make(opts):
        def b(eqn, src, dst, sf, df, ch, sr=True):
            if eqn in ("SADD", "SREVSUB") and sr:
                t = opts.get("thresh", 128)
                s = src[ch] - 256 if src[ch] >= t else src[ch]
                d = dst[ch]
                if opts.get("signed_dst") or opts.get("only_dst"):
                    d = d - 256 if d >= 128 else d
                if opts.get("only_dst"):
                    s = src[ch]
                if opts.get("bias"):
                    s += 128
                if opts.get("honour"):
                    fs = factor(sf, src, dst, ch)
                    fd = factor(df, src, dst, ch)
                    v = (F(s, 255) * fs + F(d, 255) * fd) if eqn == "SADD" \
                        else (F(d, 255) * fd - F(s, 255) * fs)
                else:
                    v = F(s + d, 255) if eqn == "SADD" else F(d - s, 255)
                if opts.get("wrap"):
                    return F(int(v * 255) % 256, 255)
                return min(F(1), max(F(0), v))
            return base_blend(eqn, src, dst, sf, df, ch, sr)
        return b

    print("\n== falsifiability: each rival must be REJECTED by the same goldens")
    for label, opts in VARIANTS.items():
        globals()["blend"] = make(opts)
        n, exact, per, fails = run(SIGNED, goldens, True, False)
        h = sum(x[0] for b in ("left", "center", "right") for x in per[b])
        t = sum(x[1] for b in ("left", "center", "right") for x in per[b])
        verdict = "FITS" if h == t else "rejected"
        print(f"  {label:40} {h}/{t} channels, {exact}/{n} captures exact  [{verdict}]")
    globals()["blend"] = base_blend

    print("\n== falsifiability of the scene constants (control, unsigned equations)")
    for label, setter, restore in [
        ("nested-quad increment 23 not 24",
         lambda: globals().__setitem__("ALPHAQUADS",
             [((0,0,256,256),abgr(0x7F00CC00)), ((23,23,233,233),abgr(0xFFCC0000)),
              ((46,46,210,210),abgr(0x800000FF)), ((69,69,187,187),abgr(0x00FFFFFF))]),
         lambda: globals().__setitem__("ALPHAQUADS",
             [((0,0,256,256),abgr(0x7F00CC00)), ((24,24,232,232),abgr(0xFFCC0000)),
              ((48,48,208,208),abgr(0x800000FF)), ((72,72,184,184),abgr(0x00FFFFFF))])),
        ("render-target checker 8 not 16",
         lambda: globals().__setitem__("CHECK", 8),
         lambda: globals().__setitem__("CHECK", 16)),
    ]:
        setter()
        n, exact, per, _ = run(["ADD", "MAX"], goldens, True, False)
        h = sum(x[0] for b in ("left","center","right") for x in per[b])
        t = sum(x[1] for b in ("left","center","right") for x in per[b])
        restore()
        print(f"  {label:40} {h}/{t} channels, {exact}/{n} captures exact  "
              f"[{'FITS' if h==t else 'rejected'}]")


def stack_a(goldens):
    """The verdict region.  `DrawColorStack` (cols 16-79, rows 112-368) is
    bit-exact against silicon under all five unsigned equations and wrong under
    both signed ones, so a residual there is the signed-equation defect alone:
    no #50 contamination, no revision question, no text overlay.  RGB is
    blended with a known source and a known checkerboard destination; alpha is
    written with blending off, so all three colour channels are pure blend-unit
    output.

    Reported per equation and per factor pair, at channel level.  The band
    order here (source order 0xDD00DD00, 0xDDDD0000, 0xDD0000DD, 0xDDFFFFFF) is
    the OPPOSITE of DrawColorAndAlphaStack's; the two stacks keep separate
    colour lists and no band index is carried between them.
    """
    import collections
    x0, y0, w, h = 16, 112, 64, 256
    print("\n== stack A, cols 16-79 rows 112-368: 16,384 px, 65,536 channels per capture")
    for eqns, rule, label in ((UNSIGNED, True, "unsigned control"),
                              (SIGNED, True, "signed-byte rule (#43)"),
                              (SIGNED, False, "as we render today")):
        per_eqn = collections.Counter()
        cap_eqn = collections.Counter()
        tot_eqn = collections.Counter()
        bad_pairs = collections.Counter()
        worst = []
        for name, eqn, sf, df in tests(eqns):
            path = os.path.join(goldens, name + ".png")
            if not os.path.exists(path):
                continue
            g = load(path)[y0:y0+h, x0:x0+w]
            p_ = blit(rt_left(eqn, sf, df, rule, COLORSTACK), x0, y0)
            hit = int((g == p_).sum())
            per_eqn[eqn] += hit
            tot_eqn[eqn] += g.size
            cap_eqn[eqn] += (hit == g.size)
            if hit != g.size:
                bad_pairs[(sf, df)] += 1
                worst.append((g.size - hit, name))
        print(f"\n  -- {label}")
        for eqn in eqns:
            n = sum(1 for _ in tests([eqn]))
            print(f"     {eqn:8} {cap_eqn[eqn]:3}/{n} captures exact, "
                  f"{per_eqn[eqn]:,}/{tot_eqn[eqn]:,} channels")
        if bad_pairs:
            print(f"     {len(bad_pairs)} of 224 factor pairs deviate; "
                  f"worst: {sorted(worst, reverse=True)[:3]}")
        else:
            print("     every factor pair exact: 0 of 224 deviate")


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default=GOLDENS)
    ap.add_argument("--control", action="store_true",
                    help="score the 1,120 unsigned captures (the harness control)")
    ap.add_argument("--signed", action="store_true",
                    help="score the 448 signed captures against the signed-byte rule")
    ap.add_argument("--naive", action="store_true",
                    help="also score them the way we render today (plain add/revsub)")
    ap.add_argument("--stack-a", action="store_true",
                    help="the verdict: DrawColorStack alone, per equation and factor pair")
    ap.add_argument("--falsify", action="store_true",
                    help="check that rival rules and wrong scene constants are rejected")
    ap.add_argument("--layout", action="store_true",
                    help="gate the goldens' swatch layout against the current source")
    ap.add_argument("--fifth-quad", metavar="DIR",
                    help="directory of Blend_tests::<test>.png to localise our residual")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    if not (a.control or a.signed or a.fifth_quad or a.layout or a.falsify or a.stack_a):
        a.control = a.signed = True
    if a.control:
        report("CONTROL, five unsigned equations",
               *run(UNSIGNED, a.goldens, True, a.verbose))
    if a.signed:
        report("SIGNED, signed-byte rule (both factors ignored, saturate)",
               *run(SIGNED, a.goldens, True, a.verbose))
        if a.naive:
            report("SIGNED, as we render today (plain ADD / REVSUB, factors honoured)",
                   *run(SIGNED, a.goldens, False, False))
    if a.stack_a:
        stack_a(a.goldens)
    if a.falsify:
        falsify(a.goldens)
    if a.layout:
        layout_gate(a.goldens, SIGNED)
    if a.fifth_quad:
        fifth_quad(a.fifth_quad, a.goldens, UNSIGNED + SIGNED)
    return 0


if __name__ == "__main__":
    sys.exit(main())
