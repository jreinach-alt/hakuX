#!/usr/bin/env python3
"""Score the audio1016-cutscene legs (docs/testing/predictions/audio1016-cutscene.json).

  judge_cutscene.py RESULTS_DIR A=<id> B=<id> D=<id> C1=<id> C0=<id>

MKSM runs (A, B, D): windows are the level meter's 5 s intervals, stamped at
their end on the logcat clock. route-frames/ names each frame HHMMSS-<shot>
on the same clock. A window is "cutscene" when it starts at or after the
first `cutscene` frame and ends no later than 10 s after the last one; "pre"
when it ends at or before the first `cutscene` frame and its level is above
-50 dBFS. Medians are of the mean of L and R in dB.

Crimson runs (C1, C0): the meter's run totals (clipped samples, acrms).

Prints each leg's numbers and pass/fail against the registered bounds.
"""
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mixlog_read  # noqa: E402

TS = r"^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.\d+ "
METER = re.compile(TS + r".*hakuX-audio\(\s*\d+\): level ([LR]): ([\d.]+) s\s+peak (\d+) "
                   r".*?acrms (-?[\d.]+|-inf) dBFS.*?clipped (\d+)")
APUMIX = re.compile(TS + r".*" + mixlog_read.LINE.pattern)
APUDSP = re.compile(TS + r".*apudsp w=(\d+) rt=(\d)(\d) gp_cyc=(\d+)/(\d+) ep_cyc=(\d+)/(\d+) "
                    r"gp_us=(\d+)/(\d+) ep_us=(\d+)/(\d+) vp_us=(\d+)/(\d+) "
                    r"util=([\d.-]+)/([\d.-]+)")
# Per 30 s interval, not cumulative: "starve: a/b callbacks short (c empty), z/t bytes zero-filled".
STARVE = re.compile(TS + r".*hakuX-audiocap.*starve: .*?, (\d+)/(\d+) bytes zero-filled")
DOWNMIX = re.compile(r"monvp_downmix: (on|off)")
USEDSP = re.compile(r"use_dsp: forced on")


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def meter_windows(path):
    """[(end_s, dt, level_db_mean_LR)] and the last totals per channel."""
    prev, rows, last = {}, {}, {}
    for line in open(path, errors="replace"):
        m = METER.match(line)
        if not m:
            continue
        h, mi, s, ch, t, peak, a, clipped = m.groups()
        t = float(t)
        e = 0.0 if a == "-inf" else t * 10 ** (float(a) / 10)
        end = secs(h, mi, s)
        if ch in prev:
            pt, pe = prev[ch]
            dt, de = t - pt, e - pe
            if dt > 0 and de > 0:
                rows.setdefault(end, {})[ch] = (dt, 10 * math.log10(de / dt))
            else:
                rows.setdefault(end, {})[ch] = (dt, -120.0)
        prev[ch] = (t, e)
        last[ch] = (t, float(a) if a != "-inf" else -120.0, int(clipped))
    out = []
    for end in sorted(rows):
        r = rows[end]
        if "L" in r and "R" in r:
            out.append((end, r["L"][0], (r["L"][1] + r["R"][1]) / 2))
    return out, last


def frames(res):
    d = os.path.join(res, "route-frames")
    cs = []
    if not os.path.isdir(d):
        return cs
    for f in sorted(os.listdir(d)):
        m = re.match(r"(\d\d)(\d\d)(\d\d)-(.*)\.png$", f)
        if m and "cutscene" in m.group(4):
            cs.append(secs(*m.groups()[:3]))
    return cs


def mksm(res):
    lc = os.path.join(res, "logcat.txt")
    text = open(lc, errors="replace").read().splitlines()
    wins, _ = meter_windows(lc)
    cs = frames(res)
    r = {"cs_frames": len(cs), "cs_span": (cs[-1] - cs[0]) if cs else 0}
    if cs:
        c0, c1 = cs[0], cs[-1] + 10
        r["cut"] = [lv for end, dt, lv in wins if end - dt >= c0 and end <= c1]
        r["pre"] = [lv for end, dt, lv in wins if end <= c0 and lv > -50]
    else:
        r["cut"], r["pre"] = [], []
    r["downmix"] = [m.group(1) for ln in text for m in [DOWNMIX.search(ln)] if m]
    r["use_dsp"] = any(USEDSP.search(ln) for ln in text)
    dsp, mix, starve = [], [], []
    for ln in text:
        m = APUDSP.match(ln)
        if m:
            g = m.groups()
            dsp.append((secs(*g[:3]), g[4] + g[5], [int(x) for x in g[6:16]],
                        float(g[16]), float(g[17])))
            continue
        m = APUMIX.match(ln)
        if m:
            g = m.groups()
            mix.append((secs(*g[:3]), int(g[3]), int(g[4]), int(g[5]), g[8]))
            continue
        m = STARVE.match(ln)
        if m:
            g = m.groups()
            starve.append((secs(*g[:3]), int(g[3]), int(g[4])))
    r["rt"] = sorted({x[1] for x in dsp})
    r["mix_windows"] = len({x[1] for x in mix})
    if cs:
        cd = [x for x in dsp if x[0] - 5 >= c0 and x[0] <= c1]
        cm = [x for x in mix if x[0] - 5 >= c0 and x[0] <= c1]
        cz = [x for x in starve if x[0] - 30 >= c0 and x[0] <= c1]
    else:
        cd, cm, cz = [], [], []
    tot = sum(x[2] for x in cz)
    r["starve"] = 100.0 * sum(x[1] for x in cz) / tot if tot else None
    if cd:
        # gp_cyc, ep_cyc, gp_us, ep_us, vp_us are mean/max pairs in that order.
        r["gp_us"] = statistics.mean(x[2][4] for x in cd)
        r["ep_us"] = statistics.mean(x[2][6] for x in cd)
        r["vp_us"] = statistics.mean(x[2][8] for x in cd)
        r["gp_cyc"] = statistics.mean(x[2][0] for x in cd)
        r["util"] = statistics.mean(x[3] for x in cd)
        r["util_max"] = max(x[4] for x in cd)
    spread = []
    for t, w, v, n, bins in cm:
        slots = [tuple(int(y) for y in s.split(":")) for s in bins.split(",")]
        spk = [(b, vol) for b, vol in slots if b < 10 and b != 3 and vol < 4095]
        if len(spk) >= 4 and len({vol for _, vol in spk}) == 1:
            gmax, gl, gr = mixlog_read.side_gains(slots, False)
            ex = min(mixlog_read.db(gl), mixlog_read.db(gr)) - mixlog_read.db(gmax)
            spread.append((w, v, n, round(ex, 2), " ".join(
                f"{mixlog_read.NAMES.get(b, b)}:{-vol / 64:.1f}" for b, vol in spk)))
    r["spread"] = spread
    return r


def med(x):
    return statistics.median(x) if x else float("nan")


def crimson(res):
    _, last = meter_windows(os.path.join(res, "logcat.txt"))
    return last


def verdict(ok):
    return "PASS" if ok else "FAIL"


def main():
    res = sys.argv[1]
    ids = dict(kv.split("=", 1) for kv in sys.argv[2:])
    runs = {k: mksm(os.path.join(res, ids[k])) for k in ("A", "B", "D") if k in ids}
    for k, r in runs.items():
        print(f"== {k} {ids[k]}")
        print(f"  V: downmix {r['downmix']} use_dsp {r['use_dsp']} rt {r['rt']} "
              f"apumix windows {r['mix_windows']} cutscene frames {r['cs_frames']} "
              f"span {r['cs_span']} s")
        print(f"  cutscene windows {len(r['cut'])} median {med(r['cut']):.2f}; "
              f"pre windows {len(r['pre'])} median {med(r['pre']):.2f}")
        if "gp_us" in r:
            print(f"  cost (cutscene): gp_us {r['gp_us']:.0f} ep_us {r['ep_us']:.0f} "
                  f"vp_us {r['vp_us']:.0f} gp_cyc {r['gp_cyc']:.0f} util {r['util']:.2f} "
                  f"(max {r['util_max']:.2f})")
        print(f"  starve over the cutscene: {r['starve']}% of output")
    if "A" in runs:
        a = runs["A"]
        q = med(a["pre"]) - med(a["cut"])
        print(f"Q: A pre - cutscene = {q:+.2f} dB (>= 6): {verdict(q >= 6)}")
        best = max(a["spread"], key=lambda x: x[3]) if a["spread"] else None
        print(f"L: spread voices in A's cutscene: {len(a['spread'])}; best {best}: "
              f"{verdict(bool(best) and best[3] >= 5)}")
    if "A" in runs and "B" in runs:
        a, b = runs["A"], runs["B"]
        u = med(b["cut"]) - med(a["cut"])
        s = med(b["pre"]) - med(a["pre"])
        print(f"U: cutscene B - A = {u:+.2f} dB ([+3.0, +8.5]): {verdict(3.0 <= u <= 8.5)}")
        print(f"S: pre B - A = {s:+.2f} dB (|x| <= 1.5): {verdict(abs(s) <= 1.5)}")
    if "A" in runs and "D" in runs:
        a, d = runs["A"], runs["D"]
        dp = med(d["pre"]) - med(a["pre"])
        dc = med(d["cut"]) - med(a["cut"])
        bal = dc - dp
        print(f"DL: pre D - A = {dp:+.2f} dB ([-8, -4]): {verdict(-8 <= dp <= -4)}")
        print(f"DL: cutscene D - A = {dc:+.2f} dB ([-4, +1]): {verdict(-4 <= dc <= 1)}")
        print(f"DL: balance gain D over A = {bal:+.2f} dB ([+2, +7]): {verdict(2 <= bal <= 7)}")
        if "gp_us" in d:
            per = d["gp_us"] + d["ep_us"] / 8
            print(f"DC: D gp_us + ep_us/8 = {per:.0f} us of 667 ([250, 700]): "
                  f"{verdict(250 <= per <= 700)}")
        sa, sd = a["starve"], d["starve"]
        if sa is not None and sd is not None:
            print(f"DC: starve D {sd:.4f}% vs A {sa:.4f}% (D - A >= 1 point): "
                  f"{verdict(sd - sa >= 1)}")
    if "C1" in ids and "C0" in ids:
        c1 = crimson(os.path.join(res, ids["C1"]))
        c0 = crimson(os.path.join(res, ids["C0"]))
        for ch in "LR":
            t1, a1, k1 = c1[ch]
            t0, a0, k0 = c0[ch]
            bound = 2 * k0 + 100 * (t1 / 5)
            print(f"C {ch}: clipped C1 {k1} vs C0 {k0} (<= {bound:.0f}): {verdict(k1 <= bound)}; "
                  f"acrms C1 {a1:.2f} C0 {a0:.2f} ({a1 - a0:+.2f}, |x| <= 1.5): "
                  f"{verdict(abs(a1 - a0) <= 1.5)}")


if __name__ == "__main__":
    main()
