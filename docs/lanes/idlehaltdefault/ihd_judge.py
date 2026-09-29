#!/usr/bin/env python3
"""Judge #525's default question: idle halt on (B) vs off (A), what a player sees.

    ihd_judge.py [--json OUT] [--copies DIR] --a RESULT [RESULT ...] --b RESULT [RESULT ...]

Every number is over ONE window per run: the route's first `mark gameplay`
(else the survey route's `mark play`) to `soak end` -- title_verdict.py's
scored window, so fps, pacing, audio and power are read over the same span.

Per run:
  - title_verdict.judge() on a COPY of the result dir (it writes verdict.json
    and contact.png beside its input, so never on dispatch/results): the
    per-60-flip windows (60 / dt, exact), audio starve share, power.net_w and
    power.j_per_frame, thermal pause, void.
  - from the same windows: fps median, and the TIME share of windows at or
    above 0.95 x 30 and 0.95 x 60 (both printed; which one a title's leg reads
    is the prediction's business, not this file's).
  - hakuX-pace (60-flip lines, f > 60): sum of vK, the flip-time p99 in
    VBLANKs (v4 = 4 or more, so a p99 of 4 is a floor), the late share for
    nominal 1 and 2 VBLANKs, and the median of the per-line `max` (ms).
  - [pace526] (every 10 s): held frames (`waited`), late_gt1ms and its share
    of held frames, the late p99 bin median.
  - [idlehalt] (every 2 s): the `on` values seen and total `halts`. A run whose
    `on` is not the arm's (B: 1, A: 0) is WRONG-ARM, not a measurement.

SILENCE IS VOID: a run with no window, or a verdict void, prints VOID with
the reason and no number. Nothing here reads a prediction file.
"""
import argparse, json, os, re, shutil, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTING = os.path.normpath(os.path.join(HERE, "..", "..", "testing"))
sys.path.insert(0, TESTING)
import title_verdict as tv  # noqa: E402

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
SHARE_AT = []      # extra fps thresholds (exact, no 0.95), from --share-at


def kv(msg):
    return {k: v for k, v in re.findall(r"(\w+)=([^\s\[\],]+)", msg)}


def read_run(rid, copies, arm):
    src = rid if os.path.isdir(rid) else os.path.join(D, "results", rid)
    rid = os.path.basename(src.rstrip("/"))
    out = dict(id=rid, arm=arm)
    if not os.path.isfile(os.path.join(src, "result.json")):
        return dict(out, void="no result.json")
    dst = os.path.join(copies, rid)
    if not os.path.isdir(dst):
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("route-frames", "frames"))
    v = tv.judge(dst)
    out.update(device=v.get("device"), ref=v.get("ref"), apk=v.get("apk_sha"),
               title=(v.get("name") or v.get("title") or "")[:32])
    res = json.load(open(os.path.join(dst, "result.json")))
    out["env"] = ",".join(res.get("env") or [])
    if v.get("void"):
        return dict(out, void=v["void"])

    lc, gaps, _ = tv.parse_logcat(os.path.join(dst, "logcat.txt"))
    marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.startswith("mark ")]
    gp = [t for t, m in marks if m == "gameplay"] or [t for t, m in marks if m == "play"]
    end = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
    if not gp:
        return dict(out, void="no mark gameplay/play")
    lo, hi = gp[0], (end[-1] if end else lc[-1][0])
    out["mark"] = [m for t, m in marks if t == lo][0]

    perf = [(t, tv.PERF.search(msg)) for t, lv, tag, msg in lc if tag == "hakuX-perf"]
    after = [t for t, p in perf if p and lo <= t <= hi]
    win = [(b - a, tv.FRAMES_PER_LINE / (b - a)) for a, b in zip(after, after[1:])
           if b > a and not tv.lost_in(a, b, gaps)]
    if not win:
        return dict(out, void="no fps window after the mark")
    tot = sum(w for w, _ in win)
    fs = sorted(f for _, f in win)
    out.update(window_s=round(hi - lo, 1), fps_windows=len(win), fps_median=round(fs[len(fs) // 2], 2),
               share30=round(sum(w for w, f in win if f >= 30 * 0.95) / tot, 4),
               share60=round(sum(w for w, f in win if f >= 60 * 0.95) / tot, 4),
               share_at={str(x): round(sum(w for w, f in win if f >= x) / tot, 4) for x in SHARE_AT})

    vk, mx = [0] * 5, []
    p526 = dict(waited=0, rel=0, late=0, p99=[])
    ih_on, halts = set(), 0
    for t, lv, tag, msg in lc:
        if not (lo <= t <= hi):
            continue
        if tag == "hakuX-pace":
            k = kv(msg)
            if all("v%d" % i in k for i in range(5)) and float(k.get("f", 0)) > 60:
                for i in range(5):
                    vk[i] += int(k["v%d" % i])
                if "max" in k:
                    mx.append(float(k["max"]))
        elif tag == "hakuX-lane" and "[pace526]" in msg and "rel=" in msg:
            k = kv(msg)
            p526["waited"] += int(k.get("waited", 0))
            p526["rel"] += int(k.get("rel", 0))
            p526["late"] += int(k.get("late_gt1ms", 0))
            if "late_p99_us" in k:
                p526["p99"].append(float(k["late_p99_us"]))
        elif tag == "hakuX" and "[idlehalt]" in msg:
            k = kv(msg)
            if "on" in k:
                ih_on.add(k["on"])
            halts += int(k.get("halts", 0) or 0)
    n = sum(vk)
    if n:
        c, p99 = 0, None
        for i in range(5):
            c += vk[i]
            if p99 is None and c >= 0.99 * n:
                p99 = i
        out.update(flips_paced=n, vk=vk, flip_p99_vbl=p99,
                   late1_share=round(sum(vk[2:]) / n, 4), late2_share=round(sum(vk[3:]) / n, 4),
                   max60_median_ms=round(statistics.median(mx), 1) if mx else None)
    else:
        out["flips_paced"] = 0
    out.update(held=p526["waited"], display_frames=p526["rel"], late_gt1ms=p526["late"],
               late_gt1ms_share=round(p526["late"] / p526["waited"], 5) if p526["waited"] else None,
               late_p99_us_median=statistics.median(p526["p99"]) if p526["p99"] else None)
    out["idlehalt_on"] = ",".join(sorted(ih_on)) or None
    out["halts"] = halts
    want = "1" if arm == "B" else "0"
    if out["idlehalt_on"] != want:
        out["wrong_arm"] = "idlehalt on=%s, arm %s wants %s" % (out["idlehalt_on"], arm, want)
    pw = v.get("power") or {}
    th = v.get("thermal") or {}
    out.update(audio_starve_share=v.get("audio_starve_share"), audio_measured=v.get("audio_measured"),
               net_w=pw.get("net_w"), battery_w=pw.get("battery_w"), usb_w=pw.get("usb_w"),
               j_per_frame=pw.get("j_per_frame"), power_samples=pw.get("samples"),
               pause_in_window=th.get("in_window"), hang=v.get("hang"), crash=v.get("crash"))
    return out


KEYS = ["mark", "window_s", "fps_windows", "fps_median", "share30", "share60", "share_at", "flips_paced", "vk",
        "flip_p99_vbl", "late1_share", "late2_share", "max60_median_ms", "held", "late_gt1ms",
        "late_gt1ms_share", "late_p99_us_median", "audio_measured", "audio_starve_share", "net_w",
        "battery_w", "usb_w", "power_samples", "j_per_frame", "idlehalt_on", "halts",
        "pause_in_window", "hang", "crash"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", nargs="+", required=True)
    ap.add_argument("--b", nargs="+", required=True)
    ap.add_argument("--copies", default=os.path.join(HERE, ".copies"))
    ap.add_argument("--json")
    ap.add_argument("--share-at", default="", help="comma-separated fps thresholds for share_at")
    o = ap.parse_args()
    SHARE_AT.extend(float(x) for x in o.share_at.split(",") if x)
    os.makedirs(o.copies, exist_ok=True)
    runs = [read_run(r, o.copies, "A") for r in o.a] + [read_run(r, o.copies, "B") for r in o.b]
    for r in runs:
        print("%s %s dev=%s ref=%s apk=%s env=[%s] %s" % (r["arm"], r["id"], r.get("device"), r.get("ref"),
                                                        r.get("apk"), r.get("env"), r.get("title")))
        if r.get("void"):
            print("   VOID: %s" % r["void"])
            continue
        if r.get("wrong_arm"):
            print("   WRONG-ARM: %s" % r["wrong_arm"])
        for k in KEYS:
            print("   %-20s %s" % (k, r.get(k)))
    if o.json:
        with open(o.json, "w") as f:
            json.dump(runs, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
