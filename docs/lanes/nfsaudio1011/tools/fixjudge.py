#!/usr/bin/env python3
"""Judge the HAKUX_APU_PACE arms: legs S, T, L, F of docs/testing/predictions/nfsaudio1011-fix.json.

Usage: fixjudge.py [--ref <837057 dir>] [--psa a-b] [--other] LABEL:<result id or dir> [...]
--other judges a title that is not NFS: pass its OFF run as --ref, and S becomes 'no increase' on the lag-2400 and
any-lag shares (the PSA window and the phase lock mean nothing there).
LABEL is OFF or ON. Per run: the switch line the app logged, the lag-2400 share (whole capture and the PSA window),
the content slope against the reference (RANSAC over bit-exact 32-frame windows, so the attract loop's repeats do not
pull the fit), the output level (audio_measure.py), gfps (hakuX-perf lines past 20 s), and where replays start in the
drain cycle (mean resultant of start index mod 2048 and mod 256, starts past 12 s as in lane.local's phase.py).
Then the legs, ON against OFF.
"""
import glob, json, os, re, subprocess, sys
import numpy as np

R = "/home/justin/hakux-work/dispatch/results/"
HERE = os.path.dirname(os.path.abspath(__file__))
MEASURE = os.path.join(HERE, "../../../testing/audio_measure.py")
LAG, MIN_RUN, LOUD, SR, W = 2400, 16, 200, 48000, 32
NO_INCREASE = 1.0   # --other (a title that is not NFS): S is 'ON share no more than 1 point above OFF'


def pcm_of(d):
    p = sorted(q for q in glob.glob(d + "/pulled/**/apu_monitor.s16le48k2ch.pcm*", recursive=True)
               if not q.endswith(".json"))
    return p


def load(d):
    return np.concatenate([np.fromfile(p, dtype="<i2") for p in pcm_of(d)]).reshape(-1, 2).astype(np.int64)


def replays(x, loud):
    same = np.zeros(len(x), bool)
    same[LAG:] = np.all(x[LAG:] == x[:-LAG], axis=1)
    d = np.diff(np.concatenate(([0], (same & loud).astype(np.int8), [0])))
    s, e = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    k = (e - s) >= MIN_RUN
    m = np.zeros(len(x), bool)
    for a, b in zip(s[k], e[k]):
        m[a:b] = True
    return m, s[k]


def hashes(x):
    v = ((x[:, 0] + 32768) * 65536 + (x[:, 1] + 32768)).astype(np.uint64)
    Q = np.uint64(0x9E3779B97F4A7C15)
    with np.errstate(over="ignore"):
        pw = np.cumprod(np.full(len(v), Q, dtype=np.uint64))
        S = np.concatenate(([np.uint64(0)], np.cumsum(v * pw, dtype=np.uint64)))
        h = S[W:] - S[:-W]
        ipw = np.cumprod(np.full(len(h), np.uint64(pow(int(Q), -1, 1 << 64)), dtype=np.uint64))
        return h * ipw


def anylag(x, loud, minlag=W, maxlag=SR // 2):
    """Share of loud output inside a 32-frame window that is a bit-exact copy of the window minlag..maxlag frames
    before it (its nearest earlier equal window), and the lags that carry the most. Another title's ring need not
    be 2400 frames, so 'no increase' at lag 2400 alone could not see its replays. Content that repeats on its own
    (a looped sample at pitch 1.0) counts here too, the same in both arms."""
    h = hashes(x)
    order = np.argsort(h, kind="stable")
    eq = h[order][1:] == h[order][:-1]
    prev = np.full(len(h), -1, np.int64)
    prev[order[1:][eq]] = order[:-1][eq]
    lag = np.arange(len(h)) - prev
    cl = np.concatenate(([0], np.cumsum(loud)))
    win_loud = (cl[W:] - cl[:-W]) == W
    hit = (prev >= 0) & (lag >= minlag) & (lag <= maxlag) & win_loud[:len(h)]
    cov = np.zeros(len(x) + 1, np.int64)
    np.add.at(cov, np.flatnonzero(hit), 1)
    np.add.at(cov, np.flatnonzero(hit) + W, -1)
    m = np.cumsum(cov)[:len(x)] > 0
    lags, cnt = np.unique(lag[hit], return_counts=True)
    top = [(int(l), round(float(100 * c / max(hit.sum(), 1)), 1)) for l, c in sorted(zip(lags, cnt), key=lambda t: -t[1])[:4]]
    return 100 * (m & loud).sum() / max(loud.sum(), 1), top


class Ref:
    def __init__(self, d):
        self.x = load(d)
        h = hashes(self.x)
        self.order = np.argsort(h, kind="stable")
        self.srt = h[self.order]

    def points(self, x, rep, loud):
        """(output s, reference s) for loud non-replay windows every 0.1 s, matched bit-exactly."""
        h = hashes(x)
        pts = []
        for i in range(LAG, len(x) - W, SR // 10):
            for j in range(i, min(i + SR // 10, len(x) - W), 37):
                if loud[j:j + W].all() and not rep[j:j + W].any():
                    lo = np.searchsorted(self.srt, h[j])
                    hi = np.searchsorted(self.srt, h[j], side="right")
                    for k in range(lo, min(hi, lo + 8)):   # every occurrence: the attract loop repeats
                        pos = self.order[k]
                        if np.array_equal(self.x[pos:pos + W], x[j:j + W]):
                            pts.append((j / SR, pos / SR))
                    break
        return np.array(pts)


def ransac(p, lo, hi, tol=0.05, it=400, seed=1):
    """Line ref = a*out + b through the points with out in [lo, hi), slope in 0.5..1.5; inliers within tol s."""
    if len(p) == 0:
        return None
    q = p[(p[:, 0] >= lo) & (p[:, 0] < hi)]
    if len(q) < 10:
        return None
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(it):
        i, j = rng.choice(len(q), 2, replace=False)
        if abs(q[j, 0] - q[i, 0]) < 1.0:
            continue
        a = (q[j, 1] - q[i, 1]) / (q[j, 0] - q[i, 0])
        if not 0.5 < a < 1.5:
            continue
        b = q[i, 1] - a * q[i, 0]
        inl = np.abs(q[:, 1] - (a * q[:, 0] + b)) < tol
        if best is None or inl.sum() > best.sum():
            best = inl
    if best is None or best.sum() < 10:
        return None
    a, b = np.polyfit(q[best, 0], q[best, 1], 1)
    return a, b, int(best.sum()), len(q)


def resultant(starts, period):
    if len(starts) < 5:
        return float("nan")
    ph = 2 * np.pi * (starts % period) / period
    return float(np.abs(np.exp(1j * ph).mean()))


def measure(d):
    out = subprocess.run([sys.executable, MEASURE, pcm_of(d)[0], "--json"], capture_output=True, text=True)
    j = json.loads(out.stdout)
    return float(np.mean([c["ac_rms_dbfs"] for c in j["per_channel"]]))


def gfps(d, after_s=20):
    lc = open(d + "/logcat.txt", errors="replace").read().splitlines()
    t0, v = None, []
    for l in lc:
        m = re.match(r"\d+-\d+ (\d+):(\d+):([\d.]+) .*hakuX-perf.*gfps=([\d.]+)", l)
        if m:
            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            t0 = t if t0 is None else t0
            if t - t0 >= after_s:
                v.append(float(m.group(4)))
    return (float(np.median(v)) if v else float("nan")), len(v)


def run(label, rid, ref, psa):
    d = rid if os.path.isdir(rid) else R + rid
    lc = open(d + "/logcat.txt", errors="replace").read()
    sw = re.findall(r"apu_pace: (on|off)", lc)
    try:
        env = json.load(open(d + "/request.json")).get("env")
    except OSError:
        env = None
    x = load(d)
    loud = np.abs(x).max(axis=1) > LOUD
    rep, starts = replays(x, loud)
    share = 100 * rep.sum() / max(loud.sum(), 1)
    any_share, any_top = anylag(x, loud)
    pts = ref.points(x, rep, loud)
    fit = ransac(pts, 0, 25)            # the intro: EA logo and the PSA
    fitw = ransac(pts, 12, 95)          # lane.local's window for the slope-1.000 runs
    psa_share = float("nan")
    if fit:
        a, b = fit[:2]
        lo, hi = int((psa[0] - b) / a * SR), int((psa[1] - b) / a * SR)
        psa_share = 100 * rep[lo:hi].sum() / max(loud[lo:hi].sum(), 1)
    g, gn = gfps(d)
    lev = measure(d)
    starve = [float(v) for v in re.findall(r"= ([\d.]+)% of output", lc)]
    r = dict(label=label, id=os.path.basename(d.rstrip("/")), switch=",".join(sw) or "NONE", env=env,
             starve_after_30s=max(starve[1:], default=float("nan")),
             secs=len(x) / SR, share=share, any_share=any_share, any_top=any_top, psa_share=psa_share, fit=fit, fitw=fitw, gfps=g, gfps_n=gn, level=lev,
             p2048=resultant(starts[starts >= 12 * SR], 2048), p256=resultant(starts[starts >= 12 * SR], 256),
             nstarts=len(starts))
    f = lambda t: "%.3f (%d/%d inliers)" % (t[0], t[2], t[3]) if t else "n/a"
    print(f"{label:3s} {r['id']}: switch={r['switch']} env={env} {r['secs']:.0f} s")
    print(f"    lag-2400 share {share:5.1f}%  PSA {psa_share:5.1f}%  slope 0-25 s {f(fit)}  12-95 s {f(fitw)}")
    print(f"    any-lag (32..24000) share {any_share:5.1f}%  top lags (lag, % of hit windows) {any_top}")
    print(f"    level {lev:6.2f} dBFS ac-rms (mean L/R)  gfps median {g:.1f} (n {gn})  "
          f"replay starts {len(starts)}: lock P2048 {r['p2048']:.2f} P256 {r['p256']:.2f}")
    print(f"    starvation per 30 s window: {' '.join('%g' % v for v in starve)} (worst past the first: "
          f"{r['starve_after_30s']:g}%)")
    return r


def main():
    args = sys.argv[1:]
    refd, psa = R + "0-1791764924-lane.local-837057", (2.27, 17.27)
    if "--ref" in args:
        i = args.index("--ref"); refd = args[i + 1]; del args[i:i + 2]
    if "--psa" in args:
        i = args.index("--psa"); psa = tuple(float(v) for v in args[i + 1].split("-")); del args[i:i + 2]
    other = "--other" in args
    if other:
        args.remove("--other")
    ref = Ref(refd)
    rows = [run(*a.split(":", 1), ref, psa) for a in args]
    on = [r for r in rows if r["label"] == "ON"]
    off = [r for r in rows if r["label"] == "OFF"]
    bad = [r["id"] for r in rows if r["switch"] != r["label"].lower()]
    print("V  switch reached the app as labelled:", "yes" if not bad else "NO: %s (VOID)" % bad)
    if other and on and off:
        mo = lambda k: max(r[k] for r in on) - max(r[k] for r in off)
        print("S  no increase, ON - OFF <= %.1f point: %s  (lag-2400 %+.1f, any-lag %+.1f)" % (
            NO_INCREASE, "PASS" if mo("share") <= NO_INCREASE and mo("any_share") <= NO_INCREASE else "FAIL",
            mo("share"), mo("any_share")))
    elif on:
        print("S  ON lag-2400 share <= 2%%: %s  (ON %s; OFF %s)" % (
            "PASS" if all(r["share"] <= 2.0 for r in on) else "FAIL",
            " ".join("%.1f" % r["share"] for r in on), " ".join("%.1f" % r["share"] for r in off)))
    sl = [(r["id"], r["fit"][0] if r["fit"] else float("nan")) for r in rows]
    print("T  slope 0-25 s within 1.00 +/- 0.02: %s  (%s)" % (
        "PASS" if all(abs(s - 1) <= 0.02 for _, s in sl) else "see runs",
        " ".join("%s %.3f" % (r["label"], s) for r, (_, s) in zip(rows, sl))))
    if on and off:
        dl = np.mean([r["level"] for r in on]) - np.mean([r["level"] for r in off])
        print("L  level ON - OFF %+.2f dB: %s" % (dl, "PASS" if abs(dl) < 0.5 else "FAIL"))
        go, gf = np.mean([r["gfps"] for r in on]), np.mean([r["gfps"] for r in off])
        print("F  gfps ON %.1f vs OFF %.1f: %s" % (go, gf, "PASS" if go >= gf - 1.0 else "FAIL"))
        zon = [r["starve_after_30s"] for r in on]
        zmax = max(r["starve_after_30s"] for r in off) if other else 0.0
        print("Z  ON starvation past the first window <= %g%%: %s  (ON %s; OFF %s)" % (
            zmax, "PASS" if all(z <= zmax for z in zon) else "FAIL", " ".join("%g" % z for z in zon),
            " ".join("%g" % r["starve_after_30s"] for r in off)))


if __name__ == "__main__":
    main()
