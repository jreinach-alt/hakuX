"""Align the perflog tags of one hold to its hakuX-pace windows.

A pace line closes a 60-frame window at its own timestamp T. The tagged lines
that belong to it are the ones stamped in (T - 2.6 s, T + 0.05 s]; the 2 s
tags close within a few ms of the pace line, so one lookback covers them.

Stdlib only. Usage: python3 hitchwin.py <logcat.txt> [--all]
Prints one row per window with max >= 100 ms (or every window with --all).
"""
import re
import sys

LINE = re.compile(r"^10-04 (\d\d):(\d\d):(\d\d\.\d+) \w/(.+?)\(\s*\d+\): (.*)$")
KV = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)=(-?[0-9.]+)")
SPAN = 2.6


def kv(text):
    out = {}
    for k, v in KV.findall(text):
        try:
            out[k] = float(v)
        except ValueError:
            pass
    return out


def key_of(tag, body):
    """Return the window slot a tagged line fills, or None."""
    if tag == "hakuX-pace":
        return "pace"
    if body.startswith("gfps="):
        return "gfps"
    if body.startswith("fifoskew"):
        return "fifoskew"
    if body.startswith("cblat"):
        return "cblat"
    if body.startswith("[rdc]"):
        return "rdc"
    if body.startswith("[shd413]"):
        return "shd413"
    if body.startswith("[lock474]"):
        return "lock474"
    if body.startswith("[idlehalt]"):
        return "idlehalt"
    if body.startswith("[tlb68]"):
        return "tlb68"
    if body.startswith("[tcg787]"):
        return "tcg787"
    if body.startswith("[jc425]"):
        return "jc425"
    if body.startswith("[rr425] "):
        return "rr425"
    if body.startswith("[rr425w]"):
        return "rr425w"
    if body.startswith("[mf0]"):
        return "mf0"
    if body.startswith("slow stores"):
        return "pages_slow"
    if body.startswith("inval ev="):
        return "pages_inval"
    if body.startswith("starve:"):
        return "audiocap"
    if body.startswith("voice_headroom"):
        return "audio_voice"
    if body.startswith("vbl n="):
        return "vbl"
    return None


def parse_extras(slot, body):
    d = kv(body)
    if slot == "gfps":
        m = re.search(r"G:([0-9.]+)\(([0-9.]+)-([0-9.]+)\)", body)
        if m:
            d["G_mean"], d["G_lo"], d["G_hi"] = map(float, m.groups())
        d["Ul"] = 1.0 if " Ul:Y" in body else 0.0
    elif slot == "fifoskew":
        m = re.search(r"drain\(n=(\d+) mean=(\d+) p50=(\d+) p90=(\d+) p99=(\d+) max=(\d+)", body)
        if m:
            n, mean, p50, p90, p99, mx = map(float, m.groups())
            d.update(dr_mean=mean / 1e6, dr_p99=p99 / 1e6, dr_max=mx / 1e6)
        m = re.search(r"backlog\(mean=(\d+) max=(\d+)\)", body)
        if m:
            d.update(bl_mean=float(m.group(1)), bl_max=float(m.group(2)))
    elif slot == "lock474":
        m = re.search(r"rd_wait_ms=([0-9.]+) wr_wait_ms=([0-9.]+)", body)
        if m:
            d["rd_wait"], d["wr_wait"] = map(float, m.groups())
    elif slot == "pages_slow":
        m = re.match(r"slow stores (\d+)", body)
        if m:
            d["slow"] = float(m.group(1))
    elif slot == "audiocap":
        m = re.search(r"(\d+)/(\d+) callbacks short", body)
        if m:
            d["short"] = float(m.group(1))
    elif slot == "idlehalt":
        m = re.search(r"span_us=(\d+) run_us=(\d+) rq_us=(\d+) halts=(\d+)", body)
        if m:
            sp, run, rq, halts = map(float, m.groups())
            d.update(ih_span=sp, ih_run=run, ih_rq=rq, ih_halts=halts)
    elif slot == "rr425w":
        m = re.search(r"idle_us=(\d+) busy_us=(\d+)", body)
        if m:
            d.update(idle_us=float(m.group(1)), busy_us=float(m.group(2)))
    return d


def tod(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    path = sys.argv[1]
    show_all = "--all" in sys.argv
    lines = []  # (t, slot, dict)
    with open(path, errors="replace") as fh:
        for raw in fh:
            m = LINE.match(raw.rstrip("\n"))
            if not m:
                continue
            h, mi, s, tag, body = m.groups()
            slot = key_of(tag.strip(), body)
            if slot is None:
                continue
            lines.append((tod(h, mi, s), slot, parse_extras(slot, body), body))
    lines.sort(key=lambda x: x[0])
    times = [x[0] for x in lines]

    import bisect
    for t, slot, d, body in lines:
        if slot != "pace" or d.get("max", 0.0) < 100 and not show_all:
            continue
        lo = bisect.bisect_right(times, t - SPAN)
        hi = bisect.bisect_right(times, t + 0.05)
        win = {}
        for t2, s2, d2, b2 in lines[lo:hi]:
            if s2 != "pace":
                win[s2] = d2  # the latest line of each slot in the window
        ih = win.get("idlehalt", {})
        g = win.get("gfps", {})
        sk = win.get("fifoskew", {})
        rd = win.get("rdc", {})
        tc = win.get("tcg787", {})
        tb = win.get("tlb68", {})
        lk = win.get("lock474", {})
        pg = win.get("pages_slow", {})
        rw = win.get("rr425w", {})
        busy = rw.get("busy_us", 0)
        idle = rw.get("idle_us", 0)
        busy_pct = 100.0 * busy / (busy + idle) if busy + idle else float("nan")
        run_pct = 100.0 * ih["ih_run"] / ih["ih_span"] if ih.get("ih_span") else float("nan")
        hh, rem = divmod(int(t), 3600)
        mm, ss = divmod(rem, 60)
        print("%02d:%02d:%05.2f max=%6.1f f=%-6d vb=%-4d v4=%-2d | G=%5.1f(%4.1f-%5.1f) Ul=%d | "
              "dr=%5.2f/%5.1f/%5.1f bl=%-6.0f | run=%5.1f%% rq=%5.1fms busy=%5.1f%% | "
              "tcpu=%-6.0f v=%-5.0f | gc=%-5.0f cg=%-4.0f gus=%-6.0f disc=%-5.0f | "
              "ff=%-4.0f pf=%-6.0f jcus=%-5.0f | slow=%-6.0f | rdw=%-5.1f wrw=%-5.1f" % (
                  hh, mm, ss + (t % 1),
                  d["max"], d.get("f", 0), d.get("vb", 0), d.get("v4", 0),
                  g.get("G_mean", float("nan")), g.get("G_lo", float("nan")),
                  g.get("G_hi", float("nan")), g.get("Ul", -1),
                  sk.get("dr_mean", float("nan")), sk.get("dr_p99", float("nan")),
                  sk.get("dr_max", float("nan")), sk.get("bl_max", float("nan")),
                  run_pct, ih.get("ih_rq", float("nan")) / 1000.0, busy_pct,
                  rd.get("tcpu", float("nan")), rd.get("v", float("nan")),
                  tc.get("gc", float("nan")), tc.get("cg", float("nan")),
                  tc.get("gus", float("nan")), tc.get("disc", float("nan")),
                  tb.get("ff", float("nan")), tb.get("pf", float("nan")),
                  tb.get("jcus", float("nan")), pg.get("slow", float("nan")),
                  lk.get("rd_wait", float("nan")), lk.get("wr_wait", float("nan"))))


if __name__ == "__main__":
    main()
