#!/usr/bin/env python3
"""The #462 signal-timing table: the console against hakuX, per signal, from the suite's .txt files.

    signal_timing_table.py --console DIR --hakux DIR [--device NAME]

Each DIR is a run's output with the `Signal timing` suite's ST_*.txt files somewhere below it (pgraph_run.py's fetch,
or a dispatcher result's captures dir). Prints the instrument legs (signal-timing-run.md), then one markdown table.
Times are recomputed from the raw samples, not copied from the summaries, so a summary line cannot disagree with its
own data unnoticed.
"""
import argparse
import glob
import os
import statistics
import sys

TESTS = ("ST_Calibrate", "ST_VBlank_Spin", "ST_VBlank_Event", "ST_Done_Tiny", "ST_Done_DOA", "ST_Done_DOA_Read",
         "ST_Flip")


def load(root, test):
    """(freq, summary dict, columns, rows) for one test's file, or None if the run did not write it."""
    found = glob.glob(os.path.join(root, "**", test + ".txt"), recursive=True)
    if not found:
        return None
    freq, summary, cols, rows = None, {}, [], []
    lines = open(found[0], errors="replace").read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("freq_hz "):
            freq = int(line.split()[1])
        elif line.startswith("# raw"):
            cols = lines[i + 1].split("\t") if i + 1 < len(lines) and lines[i + 1] else []
            rows = [[int(x) for x in l.split("\t")] for l in lines[i + 2:] if l.strip()]
            break
        elif not line.startswith("#") and " " in line:
            key, _, val = line.partition(" ")
            summary[key] = val
        i += 1
    return freq, summary, cols, rows


def pct(values, p):
    v = sorted(values)
    return v[int(p * (len(v) - 1) + 0.5)]


def stats(values):
    if not values:
        return None
    return dict(n=len(values), median=statistics.median(values), p95=pct(values, 0.95), p5=pct(values, 0.05),
                min=min(values), max=max(values))


def us(ticks, freq):
    return ticks * 1e6 / freq


def signals(root):
    """{signal name: stats in microseconds} from one run's raw samples."""
    out = {}
    for test in ("ST_VBlank_Spin", "ST_VBlank_Event"):
        d = load(root, test)
        if not d or not d[2]:
            continue
        freq, _, cols, rows = d
        t, c = cols.index(cols[0]), cols.index("vbl_count")
        iv = [us(b[t] - a[t], freq) for a, b in zip(rows, rows[1:]) if b[c] - a[c] == 1]
        out["vblank interval, " + ("ISR/DPC counter (spin)" if test.endswith("Spin") else "event wake")] = stats(iv)
        if len(iv) > 2:
            med = statistics.median(iv)
            out["vblank jitter |interval - median|, " + ("spin" if test.endswith("Spin") else "event")] = stats(
                [abs(x - med) for x in iv])
    for test, label in (("ST_Done_Tiny", "1 quad"), ("ST_Done_DOA", "500 quads + RT switch"),
                        ("ST_Done_DOA_Read", "500 quads + RT switch + CPU read")):
        d = load(root, test)
        if not d or not d[2]:
            continue
        freq, _, cols, rows = d
        k, s, n = cols.index("kick"), cols.index("semaphore_seen"), cols.index("notify_seen")
        out["last kick -> semaphore visible, " + label] = stats([us(r[s] - r[k], freq) for r in rows if r[s]])
        out["last kick -> NOTIFY write visible, " + label] = stats([us(r[n] - r[k], freq) for r in rows if r[n]])
        st = cols.index("start")
        out["submit (first draw -> kick), " + label] = stats([us(r[k] - r[st], freq) for r in rows])
        if "read_ticks" in cols and test.endswith("Read"):
            rt = cols.index("read_ticks")
            out["CPU read of the back buffer, after the semaphore"] = stats([us(r[rt], freq) for r in rows if r[rt]])
    d = load(root, "ST_Flip")
    if d and d[2]:
        freq, _, cols, rows = d
        rq, ss, cs = cols.index("request"), cols.index("start_seen"), cols.index("count_seen")
        out["flip: pb_finished -> NV_PCRTC_START written (vblank ISR)"] = stats(
            [us(r[ss] - r[rq], freq) for r in rows if r[ss]])
        out["flip: NV_PCRTC_START written -> vblank DPC counter"] = stats(
            [us(r[cs] - r[ss], freq) for r in rows if r[ss] and r[cs]])
    return out


def legs(root, console):
    """The instrument legs. Returns [(leg, holds, detail)]."""
    res = []
    d = load(root, "ST_Calibrate")
    if not d:
        return [("I1 clock", False, "no ST_Calibrate.txt")]
    s = d[1]
    ratio = float(s.get("counter_over_interrupt", "0"))
    res.append(("I1 clock: counter / interrupt time over 2 s in 0.995..1.005", 0.995 <= ratio <= 1.005,
                "%.6f" % ratio))
    if console:
        hz = float(s.get("vblank_hz", "0"))
        res.append(("I2 vblank rate 59.94 +/- 0.05 Hz", abs(hz - 59.94) <= 0.05, "%.4f Hz" % hz))
        sp = load(root, "ST_VBlank_Spin")
        if sp:
            freq, summ, cols, rows = sp
            iv = [us(b[0] - a[0], freq) for a, b in zip(rows, rows[1:]) if b[1] - a[1] == 1]
            med = statistics.median(iv) if iv else 0
            res.append(("I3 spin: 0 timeouts, median 16683 +/- 20 us",
                        summ.get("timeouts") == "0" and abs(med - 16683) <= 20,
                        "timeouts %s, median %.1f us" % (summ.get("timeouts"), med)))
        else:
            res.append(("I3 spin", False, "no ST_VBlank_Spin.txt"))
        dt = load(root, "ST_Done_Tiny")
        res.append(("I4 tiny: 0 semaphore timeouts", bool(dt) and dt[1].get("semaphore_timeouts") == "0",
                    dt[1].get("semaphore_timeouts") if dt else "no file"))
        fl = load(root, "ST_Flip")
        res.append(("I5 flip: 0 PCRTC_START timeouts", bool(fl) and fl[1].get("start_timeouts") == "0",
                    fl[1].get("start_timeouts") if fl else "no file"))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--console", required=True)
    ap.add_argument("--hakux", required=True)
    ap.add_argument("--device", default="handheld")
    a = ap.parse_args(argv)
    ok = True
    for name, root, console in (("console", a.console, True), ("hakuX " + a.device, a.hakux, False)):
        for leg, holds, detail in legs(root, console):
            print("%s %s: %s (%s)" % (name, leg, "holds" if holds else "FAILS", detail))
            ok = ok and holds
    c, h = signals(a.console), signals(a.hakux)
    fmt = lambda s: "%.1f / %.1f (n=%d)" % (s["median"], s["p95"], s["n"]) if s else "no data"
    print()
    print("| signal | console median / p95 (us) | hakuX %s median / p95 (us) | hakuX / console (median) |" % a.device)
    print("|---|---:|---:|---:|")
    for k in list(c) + [k for k in h if k not in c]:
        cs, hs = c.get(k), h.get(k)
        ratio = "%.2f" % (hs["median"] / cs["median"]) if cs and hs and cs["median"] else ""
        print("| %s | %s | %s | %s |" % (k, fmt(cs), fmt(hs), ratio))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
