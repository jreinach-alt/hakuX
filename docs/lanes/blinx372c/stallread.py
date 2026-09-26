#!/usr/bin/env python3
"""Read the perflog `hakuX-stall` line of a Blinx soak over a window and name
the SURFACE_DOWN site. Judges docs/testing/predictions/blinx372c-demo-soak.json.

    stallread.py <logcat.txt> [--window 135,265] [--spec <result.json>]
                 [--prediction <json>]
    stallread.py --selftest

Time zero is the first hakuX line (the boot), as in blinx372/soakread.py.

What a line is (vk/draw.c, opt_stats_log_and_reset): g_opt_stats summed over 60
FLIP_STALL/PRESENTING finishes, then zeroed. So `fl + pres` on a line is 60 when
the window is intact, and counters / 60 is per presented frame.

Sites (docs/lanes/blinx372b/NOTES.md section 2, re-read on 6c25a829ef):
  dl    surface.c download_surface_to_buffer        (sync download_surface)
  cDef  surface.c complete_deferred                 (deferred downloads now needed)
  pDl   surface.c process_pending_downloads         (display wait OR the CPU-access
                                                     watch, surface_access_callback)
  dDl   surface.c download_dirty_surfaces           (guest-wide flush)
`dif` has no counter for texture.c's incompatible-shape download (the
`!surface_to_texture && surface->draw_dirty` branch in texture_bind); it is
dirtyIf minus the named dif fields, printed here as `tex`.
"""
import json
import math
import re
import sys
from datetime import datetime

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\s+\w/([\w-]+)\(\s*\d+\):\s?(.*)$")
STALL = re.compile(
    r"RPBreaks:(\d+) Finish:(\d+)\(vtx(\d+) sc(\d+) sd(\d+) buf(\d+) fb(\d+) "
    r"pres(\d+) flip(\d+) flu(\d+) stl(\d+) stlDef(\d+) stlBat(\d+)\).*?"
    r"sd\[ev(\d+) noCb(\d+) dl(\d+) cDef(\d+) cDefC(\d+) pDl(\d+) dDl(\d+)\] "
    r"dlSrc\[defFb(\d+) ppdFb(\d+) dirtyIf(\d+)\] "
    r"dif\[ovl(\d+) ovlSh(\d+) exp(\d+) expSh(\d+) blt(\d+) flu(\d+) dds(\d+) oth(\d+)\]")
FIELDS = ("rpb fin vtx sc sd buf fb pres flip flu stl stlDef stlBat "
          "ev noCb dl cDef cDefC pDl dDl defFb ppdFb dirtyIf "
          "ovl ovlSh exp expSh blt dflu dds oth").split()
PHASE_FEN = re.compile(r"Fin:([\d.]+)\(Sub:([\d.]+) Fen:([\d.]+)\)")
SITES = ("dl", "cDef", "pDl", "dDl")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def read(path, lo, hi):
    t0, stall, gfps, phase = None, [], [], []
    for line in open(path, errors="replace"):
        m = TS.match(line)
        if not m:
            continue
        t, tag, body = ts(m.group(1)), m.group(2), m.group(3)
        if t0 is None and tag.startswith("hakuX"):
            t0 = t
        if t0 is None:
            continue
        t -= t0
        if not lo <= t < hi:
            continue
        if tag == "hakuX-stall":
            s = STALL.search(body)
            if s:
                stall.append((t, dict(zip(FIELDS, map(int, s.groups())))))
        elif tag == "hakuX-perf" and body.startswith("gfps="):
            gfps.append(t)
        elif tag == "hakuX-phase":
            p = PHASE_FEN.search(body)
            if p:
                phase.append(tuple(float(x) for x in p.groups()))
    return stall, gfps, phase


def line_fps(ts_):
    fr, sp = 0, 0.0
    for a, b in zip(ts_, ts_[1:]):
        if 0 < b - a < 30:
            fr += 60
            sp += b - a
    return fr / sp if sp else float("nan")


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def summarize(stall, gfps, phase, spec_ok):
    tot = {k: sum(r[k] for _, r in stall) for k in FIELDS}
    frames = tot["pres"] + tot["flip"]
    out = {"lines": len(stall), "frames": frames, "fps": line_fps(gfps),
           "spec_has_stall": spec_ok}
    out["window_intact"] = bool(stall) and all(r["pres"] + r["flip"] == 60 for _, r in stall)
    out["p1_bad_lines"] = sum(1 for _, r in stall if r["sd"] != sum(r[s] for s in SITES))
    sd = tot["sd"]
    out["sd_per_frame"] = sd / frames if frames else float("nan")
    out["share"] = {s: (tot[s] / sd if sd else float("nan")) for s in SITES}
    out["per_frame"] = {s: (tot[s] / frames if frames else float("nan")) for s in SITES}
    named = sum(tot[k] for k in ("ovl", "ovlSh", "exp", "expSh", "blt", "dflu", "dds"))
    out["dlsrc"] = {"defFb": tot["defFb"], "ppdFb": tot["ppdFb"], "dirtyIf": tot["dirtyIf"]}
    out["dif"] = {k: tot[k] for k in ("ovl", "ovlSh", "exp", "expSh", "blt", "dflu", "dds", "oth")}
    out["dif"]["tex"] = tot["dirtyIf"] - named
    out["stl_per_frame"] = tot["stl"] / frames if frames else float("nan")
    fen = med([p[2] for p in phase])
    out["fen_ms_median"] = fen
    waits = out["sd_per_frame"] + out["stl_per_frame"]
    # Fen is every fence wait in the frame, not only Sd's: a bound, not a value.
    out["ms_per_wait_upper"] = fen / waits if waits and waits == waits else float("nan")
    top = max(SITES, key=lambda s: out["share"][s] if out["share"][s] == out["share"][s] else -1)
    out["top_site"] = top
    out["top_share"] = out["share"][top]
    return out


def judge(out, pred):
    """Each leg returns (got, ok). Rules in pred['expect']."""
    e = pred["expect"]
    legs = {}
    legs["M0/spec_has_stall_is"] = (out["spec_has_stall"], out["spec_has_stall"] is e["M0/spec_has_stall_is"])
    legs["M0/stall_lines_min"] = (out["lines"], out["lines"] >= e["M0/stall_lines_min"])
    legs["M0/window_intact_is"] = (out["window_intact"], out["window_intact"] is e["M0/window_intact_is"])
    legs["P1/sum_mismatch_lines_max"] = (out["p1_bad_lines"], out["p1_bad_lines"] <= e["P1/sum_mismatch_lines_max"])
    r = out["sd_per_frame"]
    legs["P2/sd_per_frame_range"] = (r, e["P2/sd_per_frame_range"][0] <= r <= e["P2/sd_per_frame_range"][1])
    legs["P3/top_site_share_min"] = ((out["top_site"], out["top_share"]),
                                    out["top_share"] >= e["P3/top_site_share_min"])
    legs["P4/top_site_is"] = (out["top_site"], out["top_site"] == e["P4/top_site_is"])
    f = out["fps"]
    legs["P5/demo_fps_range"] = (f, e["P5/demo_fps_range"][0] <= f <= e["P5/demo_fps_range"][1])
    void = not all(ok for k, (_, ok) in legs.items() if k.startswith("M0/"))
    return legs, void


def selftest():
    # A line built from draw.c's own format string, sd = 2 per frame via pDl.
    body = ("RPBreaks:900 Finish:420(vtx0 sc3 sd120 buf0 fb0 pres60 flip0 flu0 stl60 "
            "stlDef0 stlBat0) InlClr:0/0 PreDL:0 sd[ev0 noCb0 dl0 cDef0 cDefC0 pDl120 dDl0] "
            "dlSrc[defFb0 ppdFb0 dirtyIf0] dif[ovl0 ovlSh0 exp0 expSh0 blt0 flu0 dds0 oth0]")
    s = STALL.search(body)
    assert s, "STALL regex does not match draw.c's format"
    r = dict(zip(FIELDS, map(int, s.groups())))
    out = summarize([(140.0, r), (144.0, r)], [140.0, 144.0, 148.0],
                    [(33.0, 1.0, 30.0)], True)
    assert out["p1_bad_lines"] == 0 and out["window_intact"], out
    assert out["top_site"] == "pDl" and out["top_share"] == 1.0, out
    assert abs(out["sd_per_frame"] - 2.0) < 1e-9, out
    assert abs(out["fps"] - 15.0) < 1e-9, out
    # The impossible row: a fifth site must show up as a P1 mismatch.
    bad = dict(r, sd=121)
    assert summarize([(140.0, bad)], [], [], True)["p1_bad_lines"] == 1
    print("selftest ok")


def main(a):
    if a[:1] == ["--selftest"]:
        return selftest()
    path = a[0]
    lo, hi = 135.0, 265.0
    if "--window" in a:
        lo, hi = map(float, a[a.index("--window") + 1].split(","))
    spec_ok = None
    if "--spec" in a:
        meta = json.load(open(a[a.index("--spec") + 1]))
        spec_ok = "hakuX-stall" in (meta.get("logcat") or {}).get("spec", "")
    stall, gfps, phase = read(path, lo, hi)
    out = summarize(stall, gfps, phase, spec_ok)
    print(json.dumps(out, indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else x))
    if "--prediction" in a:
        pred = json.load(open(a[a.index("--prediction") + 1]))
        legs, void = judge(out, pred)
        for k, (got, ok) in legs.items():
            print("%-30s %-5s %s" % (k, "PASS" if ok else "FAIL", got))
        print("VERDICT", "VOID" if void else ("PASS" if all(ok for _, ok in legs.values()) else "FAIL"))


if __name__ == "__main__":
    main(sys.argv[1:])
