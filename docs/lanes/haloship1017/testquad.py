#!/usr/bin/env python3
"""Where each light's test quad is, frame by frame: can a cut be seen in it? (#1039)

usage: testquad.py DUMP.jsonl ZREP.txt F0 F1 [--lo HEX --hi HEX] [--jump]

Halo's visibility test for a light is one inline_buffer quad (prim 7, count 4,
zpass on) followed by GET_REPORT at 0x60000 + 16 k. Replaying gd "va" (as
flares.py does) gives the quad's LAST vertex: attribute 0 (position) and the
rest. REPORT_EARLY answers a report from the offset's previous count; if the
light's test quad jumps at a camera cut by more than it moves within a shot,
the report path can see the cut and refuse the early answer there.

Default: one line per test in [F0, F1]: f off own pos(x,y,z,w).
--jump: per frame, over the tests whose offset was also tested the frame
before, the median and max |dx|+|dy| of the position (screen units) and of
|dz|/max(|z|,1e-6), so the within-shot spread and the cut's jump can be read
side by side.
--guard T[,T...]: what a guard "no early answer when the offset's test quad
moved more than T since its last test" would cost and catch. The guest waits
in a frame if any of the frame's reports is not answered early (it spins on
each in turn, and the late ones land together), so the cost is the frames
that wait. Per T: frames that already wait under EARLY (some report not
early: a new offset), frames the guard adds, and the early answers it
refuses, split by whether the refused early answer differed from the
report's own count in visibility (0 vs nonzero: the defect class) or not.
--poskey T[,T...]: the other key. Answer each test early with the own count of
the previous frame's test whose quad was nearest (|dx|+|dy| <= T, any offset),
and make it wait when there is none. Per T: frames that wait, tests that wait,
early answers whose visibility differs from the test's own count (flips), and
for comparison the offset key's flips over the same tests. With --frame F,
one line per test of frame F: off, own, offset-key answer, position-key answer.
--nzguard T:N[,T:N...]: refuse an early answer only when the offset's quad
moved more than T AND the answer is at least N samples (the direction that
draws a hidden flare). Cost and catch per T:N, hidden answers caught/missed.
"""
import json
import statistics
import struct
import sys


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def main():
    a = sys.argv[1:]
    jump = "--jump" in a
    if jump:
        a.remove("--jump")
    guard = None
    if "--guard" in a:
        i = a.index("--guard")
        guard = [float(x) for x in a[i + 1].split(",")]
        del a[i:i + 2]
    poskey = None
    if "--poskey" in a:
        i = a.index("--poskey")
        poskey = [float(x) for x in a[i + 1].split(",")]
        del a[i:i + 2]
    # --sim: treat every report whose offset has a previous count as answered
    # early (EARLY's gap-1 case), so a run with EARLY off can be scored too.
    sim = "--sim" in a
    if sim:
        a.remove("--sim")
    nzguard = None
    if "--nzguard" in a:
        i = a.index("--nzguard")
        nzguard = [(float(t), int(n)) for t, n in
                   (x.split(":") for x in a[i + 1].split(","))]
        del a[i:i + 2]
    show = None
    if "--frame" in a:
        i = a.index("--frame")
        show = int(a[i + 1])
        del a[i:i + 2]

    def opt(k, d):
        if k in a:
            i = a.index(k)
            v = int(a[i + 1], 16)
            del a[i:i + 2]
            return v
        return d

    lo = opt("--lo", 0x60000)
    hi = opt("--hi", 0x70000)
    dump, zrep, f0, f1 = a[0], a[1], int(a[2]), int(a[3])

    own = {}
    early = {}
    prev_v = {}
    last = {}
    for line in open(zrep, errors="replace"):
        p = line.split()
        if len(p) == 6 and p[0] == "r":
            rs, off = int(p[1]), int(p[3], 16)
            own[rs] = int(p[4])
            early[rs] = int(p[5]) or (sim and off in last)
            prev_v[rs] = last.get(off)
            last[off] = int(p[4])

    va = [0] * 64
    pos = None
    tests = {}
    for line in open(dump, errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        t = rec.get("t")
        if t == "draw":
            d = (rec.get("gd") or {}).get("va") or []
            for i in range(0, len(d) - 1, 2):
                va[d[i]] = d[i + 1]
            pos = tuple(f32(va[c]) for c in range(4)) if rec.get("zp") else None
        f = rec.get("f")
        if f is None or not (f0 <= f <= f1):
            continue
        if t == "rep" and not rec.get("clr") and pos is not None:
            off = int(rec["off"], 16)
            if lo <= off < hi:
                rs = rec["rs"]
                tests.setdefault(f, {})[off] = (pos, own.get(rs),
                                                early.get(rs), prev_v.get(rs))

    if poskey:
        frames = sorted(tests)
        print("T frames wait_frames wait_tests answered flips "
              "offset_key_flips cold_offset")
        for T in poskey:
            wf = wt = ans = fl = ofl = cold = 0
            for k, f in enumerate(frames):
                if not k or frames[k - 1] != f - 1:
                    continue
                prev = tests[frames[k - 1]]
                waits = False
                for off, (p, v, e, pv) in sorted(tests[f].items()):
                    best = None
                    for qoff, (q, qv, *_) in prev.items():
                        d = abs(p[0] - q[0]) + abs(p[1] - q[1])
                        if d <= T and (best is None or d < best[0]):
                            best = (d, qv, qoff)
                    oans = prev[off][1] if off in prev else None
                    cold += oans is None
                    if oans is not None and v is not None:
                        ofl += (oans == 0) != (v == 0)
                    if best is None or best[1] is None:
                        wt += 1
                        waits = True
                        pans = None
                    else:
                        ans += 1
                        pans = best[1]
                        if v is not None:
                            fl += (pans == 0) != (v == 0)
                    if show == f and T == poskey[0]:
                        print(f"  f{f} {off:#x} own={v} offkey={oans} "
                              f"poskey={pans} d={best[0] if best else '-'}"
                              f" from={best[2] if best else '-':}")
                wf += waits
            print(f"{T:g} {len(frames)} {wf} {wt} {ans} {fl} {ofl} {cold}")
        return

    if guard:
        frames = sorted(tests)
        print("T frames wait_early wait_added refused refused_flip "
              "flips_kept flips_all")
        for T in guard:
            wait0 = added = refused = rflip = kept = allflip = 0
            for k, f in enumerate(frames):
                prev = tests[frames[k - 1]] if k else {}
                waits = any(not e for _, _, e, _ in tests[f].values())
                wait0 += waits
                extra = False
                for off, (p, v, e, pv) in tests[f].items():
                    if not e:
                        continue
                    flip = pv is not None and v is not None and \
                        (pv == 0) != (v == 0)
                    allflip += flip
                    q = prev.get(off)
                    moved = q is None or \
                        abs(p[0] - q[0][0]) + abs(p[1] - q[0][1]) > T
                    if moved:
                        refused += 1
                        rflip += flip
                        extra = True
                    else:
                        kept += flip
                added += extra and not waits
            print(f"{T:g} {len(frames)} {wait0} {added} {refused} {rflip} "
                  f"{kept} {allflip}")
        return

    if nzguard:
        # Refuse an early answer only when the offset's quad moved more than
        # T since its last test AND that answer is >= N samples: the one
        # direction that draws a hidden flare (a stale 0 for a light now in
        # view only starts its fade-in a frame later, which the guest's own
        # reset at a cut makes moot). hid_* = early answers >= N whose own
        # count is 0 (the defect), split caught/missed.
        frames = sorted(tests)
        print("T N frames wait_early wait_added refused hid_caught "
              "hid_missed hid_missed_max")
        for T, N in nzguard:
            wait0 = added = refused = hc = hm = 0
            hmax = 0
            for k, f in enumerate(frames):
                prev = tests[frames[k - 1]] if k else {}
                waits = any(not e for _, _, e, _ in tests[f].values())
                wait0 += waits
                extra = False
                fr = fh = 0
                for off, (p, v, e, pv) in tests[f].items():
                    if not e or pv is None:
                        continue
                    q = prev.get(off)
                    moved = q is None or \
                        abs(p[0] - q[0][0]) + abs(p[1] - q[0][1]) > T
                    hid = pv >= N and v == 0
                    if moved and pv >= N:
                        refused += 1
                        extra = True
                        hc += hid
                        fr += 1
                        fh += hid
                    elif hid:
                        hm += 1
                        hmax = max(hmax, pv)
                added += extra and not waits
                if fr and show == -1:
                    print(f"  T{T:g} N{N} f{f} refused={fr} hidden={fh} "
                          f"already_waits={int(waits)}")
            print(f"{T:g} {N} {len(frames)} {wait0} {added} {refused} {hc} "
                  f"{hm} {hmax}")
        return

    if not jump:
        for f in sorted(tests):
            for off, (p, v, *_) in sorted(tests[f].items()):
                print(f"{f} {off:#x} {v} " + ",".join(f"{x:.4g}" for x in p))
        return

    print("f ntests nmatched dxy_med dxy_max dzrel_med dzrel_max")
    prev = None
    for f in sorted(tests):
        cur = tests[f]
        if prev is not None:
            dxy, dz = [], []
            for off, (p, *_) in cur.items():
                if off in prev:
                    q = prev[off][0]
                    dxy.append(abs(p[0] - q[0]) + abs(p[1] - q[1]))
                    dz.append(abs(p[2] - q[2]) / max(abs(q[2]), 1e-6))
            if dxy:
                print(f"{f} {len(cur)} {len(dxy)} {statistics.median(dxy):.2f} "
                      f"{max(dxy):.2f} {statistics.median(dz):.4f} {max(dz):.4f}")
            else:
                print(f"{f} {len(cur)} 0")
        prev = cur


if __name__ == "__main__":
    main()
