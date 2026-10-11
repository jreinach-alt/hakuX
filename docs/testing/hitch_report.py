#!/usr/bin/env python3
"""hitch_report.py <result-dir> -- stand-alone hitch report, for a human.

Judges nothing: `title_verdict.py` calls `hitches()` and `static_window()`
below and decides pass/fail. This file lists and explains hitches found in
an already-scored window, and is runnable by itself to look at one result.

THE OWNER'S FINDING (2026-10-01 ~18:35 PDT, #433). Sonic Heroes on the Nova
showed brief (< 1 s) delays during real play that the sustained-fps rule
cannot see: one stall is a rounding error in a 600 s window scored by
TIME-weighted share. This module finds every such stall and says what the
engine was doing in the same window, from counters hakuX-perf already
prints every 60 guest flips (profile.c):
  hakuX-pace: f=<flips> ... max=<ms> ms=<window ms>   -- the window's worst
    single flip-to-flip interval, and the window's own wall time.
  hakuX-perf [shd413] f=<flips> ... dsm=<n> ... dpc_ms=<ms> ... dvs_ms=<ms>
    dgs_ms=<ms> dfs_ms=<ms> ...                        -- that SAME window's
    shader-cache misses and pipeline/shader-stage compile time (deltas).
  hakuX-perf [rdc] ... tex=<n>/<us>/<pages>/<hits>      -- texture-dirty-bit
    clears (system/physmem.c RDC_TCD_TEX), on the probe's own clock, not
    tied to the flip count; a texture re-upload needs one of these first,
    so microseconds spent here over the hitch's span is the texture-work
    proxy.
A window is a HITCH at max >= HITCH_MS. It is classified SHADER when the
same window's shd413 line shows a cache miss or real compile time, TEXTURE
when [rdc]'s tex microseconds (summed over rdc lines inside the hitch's own
span) exceed a bound, BOTH when it shows both, else UNEXPLAINED -- the
classifier must not guess a cause neither counter supports.

VERDICT RULE (title_verdict.py): more than HITCHES_PER_MIN_BAR hitches per
minute after the first WARMUP_S of the scored window (shader caches
legitimately still fill early on), or any hitch >= BIG_HITCH_MS after that,
fails as "hitches" -- unless the title carries `hitch_allowance` in
targets.toml. These are the owner's proposed numbers, not numbers this
module fit to data: see NOTES.md ("the thresholds do not separate") for the
survey that found them wanting, and why it did not change them anyway.

WHOLE-WINDOW LIVENESS (a second owner finding, same day): Super Monkey Ball
and Castlevania scored PASS on a Stage Select / Name Entry menu because
`reached_gameplay` only reads the mark frame. `static_window()` answers "did
the scored window ever move on," independent of fps or hitches -- a menu can
hold a rock-steady 59 fps with no stall at all and still never be gameplay.
A plain frame-to-frame pixel diff does NOT separate the two real cases: Super
Monkey Ball's Stage Select has an animated background (flowing water, an
idle character) that moves a river's worth of pixels every frame while the
menu itself never advances, and the survey (NOTES.md) found its consecutive-
frame diff indistinguishable from real gameplay's. What does separate them is
whether the window ever departs far from its OWN FIRST FRAME: real gameplay's
camera and HUD drift the whole frame over a 600 s window; a looping menu
animation returns near its starting values the whole time. `static_window()`
measures the fraction of (downsampled, grayscale) pixels that never stray
more than FROZEN_TOL from their value in the window's first sampled frame,
across every sampled frame -- FROZEN_FRAC_BAR or more of them, and the window
is static, whether the cause is a literal freeze (near 100%, Sonic Heroes's
withdrawn capture, a true pause-menu hang) or a looping menu (Super Monkey
Ball, ~32%, still well above a real-gameplay run's ~3%).
"""
import datetime as dt
import glob
import os
import re
import sys


def ts(stamp):
    # Same convention as title_verdict.ts: year 2000 is a leap year, so a
    # 02-29 stamp parses; only differences between two of these are used.
    return dt.datetime.strptime("2000-" + stamp, "%Y-%m-%d %H:%M:%S.%f").timestamp()

LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\s+([VDIWEF])/([^(\s]+)\s*\(\s*\d+\):\s?(.*)$")
PACE = re.compile(r"f=(\d+) v0=\d+ v1=\d+ v2=\d+ v3=\d+ v4=\d+ vb=\d+ max=([\d.]+) ms=([\d.]+)")
SHD = re.compile(r"\[shd413\] f=(\d+).*? dsm=(\d+).*? dpc_ms=([\d.]+) dpn=\d+ dfb=\d+ dfbh=\d+ "
                  r"dfb_ms=[\d.]+ dvs_ms=([\d.]+) dgs_ms=([\d.]+) dfs_ms=([\d.]+)")
RDC = re.compile(r"\[rdc\].*?tex=(\d+)/(\d+)/(\d+)/(\d+)")
FRAME_NAME = re.compile(r"^(\d\d)(\d\d)(\d\d)-")

HITCH_MS = 100.0
WARMUP_S = 60.0
HITCHES_PER_MIN_BAR = 6.0
BIG_HITCH_MS = 500.0
SHADER_COMPILE_MS_BAR = 20.0
TEXTURE_US_BAR = 20000.0

FROZEN_RESIZE = (160, 90)
FROZEN_TOL = 10          # 0-255 grayscale levels a pixel may drift and still count "unchanged"
FROZEN_FRAC_BAR = 0.20   # this share of pixels frozen all window long calls it static
FROZEN_MIN_FRAMES = 3    # fewer post-mark frames: unmeasured, not judged


def classify(h):
    shader = h["dsm"] > 0 or h["dpc_ms"] > SHADER_COMPILE_MS_BAR or h["shader_stage_ms"] > SHADER_COMPILE_MS_BAR
    texture = h["tex_us"] > TEXTURE_US_BAR
    if shader and texture:
        return "both"
    if shader:
        return "shader"
    if texture:
        return "texture"
    return "unexplained"


def find_hitches(lines, mark_t, end_t):
    """lines: parse_logcat's (t, level, tag, msg) tuples. One dict per window
    whose hakuX-pace `max=` is >= HITCH_MS, in [mark_t, end_t]."""
    if mark_t is None or end_t is None:
        return []
    shd_by_f = {}
    rdc = []   # (t, tex_us), kept in order; rdc's own clock, not the flip count
    for t, lv, tag, msg in lines:
        if tag != "hakuX-perf" or t < mark_t or t > end_t:
            continue
        m = SHD.search(msg)
        if m:
            f = int(m.group(1))
            shd_by_f[f] = dict(dsm=int(m.group(2)), dpc_ms=float(m.group(3)),
                                shader_stage_ms=float(m.group(4)) + float(m.group(5)) + float(m.group(6)))
            continue
        m = RDC.search(msg)
        if m:
            rdc.append((t, int(m.group(2))))

    out = []
    for t, lv, tag, msg in lines:
        if tag != "hakuX-pace" or t < mark_t or t > end_t:
            continue
        m = PACE.search(msg)
        if not m:
            continue
        f, max_ms, window_ms = int(m.group(1)), float(m.group(2)), float(m.group(3))
        if max_ms < HITCH_MS:
            continue
        win_lo = t - window_ms / 1000.0
        tex_us = sum(u for rt, u in rdc if win_lo <= rt <= t)
        shd = shd_by_f.get(f, dict(dsm=0, dpc_ms=0.0, shader_stage_ms=0.0))
        h = dict(f=f, t=t, off_s=round(t - mark_t, 1), max_ms=max_ms, window_ms=window_ms,
                 tex_us=tex_us, **shd)
        h["class"] = classify(h)
        out.append(h)
    return out


def report(hitches, scored_s):
    """Summary dict for title_verdict.py and for a human: counts, rate,
    worst, classification, and the 5 worst (with enough to print a line)."""
    after = [h for h in hitches if h["off_s"] >= WARMUP_S]
    minutes_after = max(0.0, (scored_s - WARMUP_S) / 60.0)
    per_min = round(len(after) / minutes_after, 3) if minutes_after > 0 else None
    cls = {"shader": 0, "texture": 0, "both": 0, "unexplained": 0}
    for h in hitches:
        cls[h["class"]] += 1
    worst = sorted(hitches, key=lambda h: -h["max_ms"])[:5]
    big_after_warmup = [h for h in after if h["max_ms"] >= BIG_HITCH_MS]
    return dict(n=len(hitches), n_after_warmup=len(after), per_min_after_warmup=per_min,
                worst_ms=max((h["max_ms"] for h in hitches), default=0.0),
                n_big_after_warmup=len(big_after_warmup), classification=cls,
                worst5=[dict(off_s=h["off_s"], max_ms=h["max_ms"], dsm=h["dsm"],
                              dpc_ms=h["dpc_ms"], shader_stage_ms=h["shader_stage_ms"],
                              tex_us=h["tex_us"], cls=h["class"]) for h in worst])


def hitch_fail(rep, allowance=None):
    """(bool, reason|None). `allowance` is a title's own hitch_allowance
    entry in targets.toml (None/falsy: the default bars apply)."""
    if allowance:
        return False, None
    if rep["per_min_after_warmup"] is not None and rep["per_min_after_warmup"] > HITCHES_PER_MIN_BAR:
        return True, ("hitches: %.2f/min after the first %.0f s (bar %.0f/min)"
                       % (rep["per_min_after_warmup"], WARMUP_S, HITCHES_PER_MIN_BAR))
    if rep["n_big_after_warmup"] > 0:
        return True, ("hitches: a %.0f ms stall after the first %.0f s (bar %.0f ms)"
                       % (max(h["max_ms"] for h in rep["worst5"] if h["off_s"] >= WARMUP_S),
                          WARMUP_S, BIG_HITCH_MS))
    return False, None


def _frame_time(name, date_prefix):
    m = FRAME_NAME.match(os.path.basename(name))
    if not m:
        return None
    return ts("%s %s:%s:%s.000" % (date_prefix, *m.groups()))


def _post_mark(rdir, sub, mark_t, end_t, date_prefix):
    """(t, name) for each frame in rdir/sub taken inside [mark_t, end_t], in time order."""
    out = []
    for name in sorted(glob.glob(os.path.join(rdir, sub, "*.png"))):
        t = _frame_time(name, date_prefix)
        if t is not None and mark_t <= t <= (end_t if end_t is not None else t):
            out.append((t, name))
    out.sort()
    return out


def window_frames(rdir, mark_t, end_t):
    """The scored window's samples, shared by the liveness and position tests
    so they cannot disagree about what was seen. (source, [(t, name)], None),
    or (None, [], reason) when the window has too few frames to read.

    The post-mark route-frames when there are at least FROZEN_MIN_FRAMES of
    them (most routes take none at all: `--frames-every 0`); otherwise the
    post-mark `frames/` samples."""
    if mark_t is None:
        return None, [], "no mark"
    try:
        with open(os.path.join(rdir, "logcat.txt"), errors="replace") as f:
            date_prefix = None
            for raw in f:
                m = LINE.match(raw.rstrip("\n"))
                if m:
                    date_prefix = m.group(1).split(" ")[0]
                    break
    except OSError:
        date_prefix = None
    if date_prefix is None:
        return None, [], "no logcat lines"
    route = _post_mark(rdir, "route-frames", mark_t, end_t, date_prefix)
    boot = _post_mark(rdir, "frames", mark_t, end_t, date_prefix)
    if len(route) >= FROZEN_MIN_FRAMES:
        return "route-frames", route, None
    if len(boot) >= FROZEN_MIN_FRAMES:
        return "frames", boot, None
    return None, [], ("%d post-mark route-frame(s) and %d post-mark frames/ sample(s), need %d of one"
                      % (len(route), len(boot), FROZEN_MIN_FRAMES))


def static_window(rdir, mark_t, end_t):
    """Whole-window liveness: the fraction of pixels that never move far
    from the window's first sampled frame, across every frame in
    window_frames(). See the module doc for why this, not a frame-to-frame
    diff. With too few frames, or no PIL on this host, the window is
    {measured: False}. An unmeasured window is not judged by its pixels, and
    static_window_unmeasured() fails it outright: it is not Playable-eligible."""
    source, after, why = window_frames(rdir, mark_t, end_t)
    if source is None:
        return dict(measured=False, reason=why, frozen_frac=None, n=0, source=None)
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return dict(measured=False, reason="PIL/numpy unavailable", frozen_frac=None, n=len(after), source=None)

    arrs = [np.asarray(Image.open(name).convert("L").resize(FROZEN_RESIZE), dtype=np.int16)
            for _, name in after]
    base = arrs[0]
    maxdev = base * 0  # same shape/dtype, all zero
    for a in arrs[1:]:
        maxdev = np.maximum(maxdev, np.abs(a - base))
    frozen_frac = float((maxdev <= FROZEN_TOL).mean())
    return dict(measured=True, frozen_frac=round(frozen_frac, 4), n=len(after), source=source)


def static_window_fail(sw):
    """(bool, reason|None) from static_window()'s dict. Unmeasured never fails
    here: static_window_unmeasured() is the verdict's rule for that."""
    if not sw.get("measured"):
        return False, None
    if sw["frozen_frac"] >= FROZEN_FRAC_BAR:
        return True, ("static window: %.0f%% of pixels never moved more than %d/255 "
                      "from the window's first frame, over %d sampled frames from %s (bar %.0f%%)"
                      % (100 * sw["frozen_frac"], FROZEN_TOL, sw["n"], sw.get("source") or "?",
                         100 * FROZEN_FRAC_BAR))
    return False, None


def static_window_unmeasured(sw):
    """(bool, reason|None): an unmeasured scored window fails the run as
    `window unmeasured`, naming why. A window with no pixels to read is not a
    Playable window (#433: Castlevania and Black Stone passed unmeasured)."""
    if sw.get("measured"):
        return False, None
    return True, "window unmeasured: %s (a scored window the verdict cannot read is not Playable)" \
        % sw.get("reason", "no reason recorded")


POSITION_STILL_BAR = 0.5   # more than this share of consecutive sample pairs with no scene change: not gameplay


def position_change(rdir, mark_t, end_t):
    """Did the scene change across the scored window? Two zero-model checks on
    the same samples as static_window(): the first and last sample differ, and
    most consecutive pairs differ. The change is titles/classify.py's motion()
    (the share of pixels that moved, FPS corner and motion masks blacked out)
    against its own STATIC_BAR, the bar its classifier names a frame still.

    This names still vs moving, not menu vs gameplay: classify names a menu
    only through a title's drive profile, and most titles have none. A still
    window is a menu, a pause or a load in all but name, which is what the
    owner needs the verdict to say (#433: a Name Entry at 60 fps passed)."""
    source, after, why = window_frames(rdir, mark_t, end_t)
    if source is None:
        return dict(measured=False, reason=why, source=None, samples=0, pairs=0, still=0,
                    still_frac=None, first_last=None)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "titles"))
    try:
        import classify
    except ImportError:
        return dict(measured=False, reason="classify unavailable (PIL/numpy)", source=None,
                    samples=len(after), pairs=0, still=0, still_frac=None, first_last=None)
    greys = [classify.open_grey(name) for _, name in after]
    pairs = [classify.motion(greys[i], greys[i + 1])[0] for i in range(len(greys) - 1)]
    still = sum(1 for c in pairs if c <= classify.STATIC_BAR)
    return dict(measured=True, reason=None, source=source, samples=len(after), pairs=len(pairs),
                still=still, still_frac=round(still / len(pairs), 4) if pairs else None,
                first_last=round(classify.motion(greys[0], greys[-1])[0], 4), bar=classify.STATIC_BAR)


def position_fail(pc):
    """(bool, reason|None) from position_change()'s dict. Unmeasured never
    fails here: static_window_unmeasured() already fails an unreadable window."""
    if not pc.get("measured"):
        return False, None
    bar = pc["bar"]
    if pc["first_last"] is not None and pc["first_last"] <= bar:
        return True, ("position: the window's first and last of %d samples are the same picture "
                      "(changed %.3f, still bar %.3f): a menu, a pause, a load or a freeze"
                      % (pc["samples"], pc["first_last"], bar))
    if pc["still_frac"] is not None and pc["still_frac"] > POSITION_STILL_BAR:
        return True, ("position: %d of %d consecutive samples (%.0f%%) show no picture change "
                      "(bar %.0f%%): a menu, a pause, a load or a freeze"
                      % (pc["still"], pc["pairs"], 100 * pc["still_frac"], 100 * POSITION_STILL_BAR))
    return False, None


def main(argv=None):
    rdir = (argv or sys.argv[1:])[0]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import title_verdict as tv
    lc, _gaps, _open = tv.parse_logcat(os.path.join(rdir, "logcat.txt"))
    marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc
             if tag == "hakuX-route" and msg.startswith("mark ")]
    gp = [t for t, lab in marks if lab == "gameplay"]
    mark_t = gp[0] if gp else None
    soak_end = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
    end_t = soak_end[-1] if soak_end else (lc[-1][0] if lc else None)
    if mark_t is None or end_t is None:
        print("no scored window (no `mark gameplay` or nothing after it)")
        return 1
    scored_s = end_t - mark_t
    hs = find_hitches(lc, mark_t, end_t)
    rep = report(hs, scored_s)
    print("scored_s=%.1f hitches=%d after_warmup=%d per_min=%s worst_ms=%.1f classification=%s"
          % (scored_s, rep["n"], rep["n_after_warmup"], rep["per_min_after_warmup"],
             rep["worst_ms"], rep["classification"]))
    for h in rep["worst5"]:
        print("  off=%7.1fs max=%7.1fms dsm=%-3d dpc_ms=%7.1f shader_ms=%7.1f tex_us=%-8d class=%s"
              % (h["off_s"], h["max_ms"], h["dsm"], h["dpc_ms"], h["shader_stage_ms"],
                 h["tex_us"], h["cls"]))
    fail, why = hitch_fail(rep)
    print("hitch verdict:", "FAIL " + why if fail else "pass")
    sw = static_window(rdir, mark_t, end_t)
    print("static_window:", sw)
    fail, why = static_window_fail(sw)
    print("liveness verdict:", "FAIL " + why if fail else "pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
