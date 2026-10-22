#!/usr/bin/env python3
"""playprobe_report.py <result-dir|logcat.txt> [--bar FPS] [--lookback S] [--targets FILE] [--json]

Lay a play run's frame-rate dips against the inputs that preceded them (playprobe1021, #433).

The owner (2026-10-21): the game must hold 30 fps in gameplay whatever path the dispatcher's
driver takes, "if falling into water craters the framerate, we need to know that". drive.py
writes every input it sends, and every play-probe it makes, to logcat (tag hakuX-route:
`input t=<route s> <what> why=<why>`, `play-probe won|missed <input> ...`), on the same
clock as the `hakuX-perf gfps=` lines. This reads both and says, for each stretch of play
that ran under the bar, what was held and what had just been pressed.

READS ONLY. It sends nothing and writes nothing; it takes title_verdict.py's own logcat
parser, its gfps pattern and its bar (targets.toml [defaults]: playable_fps x fps_tolerance,
30 x 0.95 = 28.5), so a dip here is a dip there.

WHAT IT SCORES. Only seconds the driver called `play` (the last `hakuX-route: state=` line
before the sample). A below-bar second in a menu or a load is not gameplay and is counted
apart, never as a dip. `gfps=` is a trailing ~1 s rate (memory gfps-is-last-second-not-window),
so a sample at time t covers [t-1, t] and is placed by its midpoint.

WHAT IT CLAIMS. Attribution is by time, not cause: "held LY min RT max, last tap A 1.2 s
before" is what the run was doing, and the by-input table says whether the same input
recurs across dips. One dip under one input is a candidate; the same input under many dips
and not under the good seconds is a finding. Neither is a diagnosis -- the scene (water,
a crowd, a cut) is in the frame, and the nearest route frame is named for a human to look at.

A run with no `input` markers (drive.py from before playprobe1021) is reported as
"not attributable", never as "no cause found"."""
import argparse
import bisect
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import title_verdict as tv  # noqa: E402

INPUT = re.compile(r"^input t=([\d.]+) (.*) why=(.*)$")
FRAME = re.compile(r"^(\d\d)(\d\d)(\d\d)-\d+-")
STATE = re.compile(r"^state=(\S+) t=(\d+)")
MERGE_GAP_S = 2.5            # two samples this close are one stretch (they are 1 s apart)
LOOKBACK_S = 4.0


def clock(t):
    return dt.datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-5]


def is_hold(what):
    return what.startswith(("hold ", "probe hold "))


def read_events(lines):
    """(states, inputs, probes, perf), each sorted by time. states: (t, state); inputs:
    (t, what, why); probes: (t, text); perf: (t, gfps)."""
    states, inputs, probes, perf = [], [], [], []
    for t, _lv, tag, msg in lines:
        if tag == "hakuX-route":
            m = STATE.match(msg)
            if m:
                states.append((t, m.group(1)))
                continue
            m = INPUT.match(msg)
            if m:
                inputs.append((t, m.group(2), m.group(3)))
            elif msg.startswith("play-probe "):
                probes.append((t, msg[len("play-probe "):]))
        elif tag == "hakuX-perf":
            m = tv.PERF.search(msg)
            if m:
                perf.append((t, int(m.group(1))))
    for seq in (states, inputs, probes, perf):
        seq.sort(key=lambda e: e[0])
    return states, inputs, probes, perf


def frames_of(rdir):
    """[(device seconds-of-day, name)] from route-frames/HHMMSS-NNN-state.png."""
    out = []
    d = os.path.join(rdir, "route-frames")
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            m = FRAME.match(name)
            if m:
                h, mi, s = (int(x) for x in m.groups())
                out.append((h * 3600 + mi * 60 + s, name))
    return out


def analyse(lines, bar, lookback=LOOKBACK_S, frames=()):
    states, inputs, probes, perf = read_events(lines)
    st_t = [t for t, _ in states]
    in_t = [t for t, _, _ in inputs]
    pr_t = [t for t, _ in probes]

    def state_at(t):
        i = bisect.bisect_right(st_t, t) - 1
        return states[i][1] if i >= 0 else None

    def hold_at(t):
        """The last hold input sent at or before t. drive.py logs a fresh `hold` whenever it
        puts one back after a release (a menu, a load), so the latest marker is what was down."""
        i = bisect.bisect_right(in_t, t) - 1
        while i >= 0:
            if is_hold(inputs[i][1]):
                return inputs[i]
            i -= 1
        return None

    play, outside, dips = [], 0, []
    for t, g in perf:
        mid = t - 0.5
        if state_at(mid) != "play":
            if g < bar:
                outside += 1
            continue
        play.append((t, g))

    by_input = {}
    for t, g in play:
        h = hold_at(t - 0.5)
        key = h[1] if h else "(no hold logged)"
        row = by_input.setdefault(key, dict(seconds=0, gfps_sum=0, dip_seconds=0))
        row["seconds"] += 1
        row["gfps_sum"] += g
        if g < bar:
            row["dip_seconds"] += 1

    run = []
    for t, g in play:
        if g >= bar:
            continue
        if run and t - run[-1][0] > MERGE_GAP_S:
            dips.append(run)
            run = []
        run.append((t, g))
    if run:
        dips.append(run)

    episodes = []
    for run in dips:
        start, end = run[0][0] - 1.0, run[-1][0]
        h = hold_at(start)
        lo, hi = start - lookback, end
        recent = [(t, w, y) for t, w, y in inputs if lo <= t <= hi]
        pmarks = [(t, x) for t, x in probes if lo <= t <= hi]
        ep = dict(start=start, end=end, seconds=len(run), min_gfps=min(g for _, g in run),
                  mean_gfps=round(sum(g for _, g in run) / len(run), 1),
                  holding=h[1] if h else None, held_since=h[0] if h else None,
                  recent_inputs=[dict(t=t, what=w, why=y) for t, w, y in recent],
                  probes=[dict(t=t, text=x) for t, x in pmarks])
        if frames:
            sod = (dt.datetime.fromtimestamp(start).hour * 3600 + dt.datetime.fromtimestamp(start).minute * 60
                   + dt.datetime.fromtimestamp(start).second)
            before = [f for f in frames if f[0] <= sod]
            if before:
                ep["frame"] = before[-1][1]
                ep["frame_age_s"] = sod - before[-1][0]
        episodes.append(ep)

    ok = sum(1 for _, g in play if g >= bar)
    return dict(bar=bar, lookback=lookback, play_seconds=len(play), play_ok_seconds=ok,
                play_ok_share=(ok / len(play)) if play else None,
                below_bar_outside_play=outside, inputs_logged=len(inputs), probes_logged=len(probes),
                perf_samples=len(perf), dips=episodes,
                by_input={k: dict(seconds=v["seconds"], mean_gfps=round(v["gfps_sum"] / v["seconds"], 1),
                                  dip_seconds=v["dip_seconds"]) for k, v in by_input.items()})


def render(r, path):
    out = ["playprobe_report: %s" % path,
           "bar: gfps >= %.1f (playable_fps x fps_tolerance, targets.toml)" % r["bar"]]
    if not r["perf_samples"]:
        out.append("not measured: no hakuX-perf gfps= line in this logcat")
        return out
    if not r["play_seconds"]:
        out.append("not measured: no perf second fell in a `play` span "
                   "(no `hakuX-route: state=play` marker, or a run that never reached play)")
        return out
    out.append("play: %d perf seconds, %d at the bar (%.1f%%; the verdict needs >= 90%%), %d below"
               % (r["play_seconds"], r["play_ok_seconds"], 100 * r["play_ok_share"],
                  r["play_seconds"] - r["play_ok_seconds"]))
    if r["below_bar_outside_play"]:
        out.append("outside play: %d below-bar seconds in a menu, load or cutscene (not scored)"
                   % r["below_bar_outside_play"])
    if not r["inputs_logged"]:
        out.append("inputs: none logged -- this run predates the input markers; dips are NOT attributable")
    else:
        out.append("inputs: %d logged, %d play-probe lines" % (r["inputs_logged"], r["probes_logged"]))
    if not r["dips"]:
        out.append("dips: none -- every play second held the bar")
    for ep in r["dips"]:
        out.append("dip %s - %s  %d s  min %d  mean %.1f"
                   % (clock(ep["start"]), clock(ep["end"]), ep["seconds"], ep["min_gfps"], ep["mean_gfps"]))
        if r["inputs_logged"]:
            out.append("    holding: %s" % (("%s (since %s)" % (ep["holding"], clock(ep["held_since"])))
                                            if ep["holding"] else "nothing logged"))
            for e in ep["recent_inputs"]:
                out.append("    %s input %s  [%s]" % (clock(e["t"]), e["what"], e["why"]))
            for e in ep["probes"]:
                out.append("    %s play-probe %s" % (clock(e["t"]), e["text"]))
            if not ep["recent_inputs"] and not ep["probes"]:
                out.append("    no input or probe in the %.0f s before it" % r["lookback"])
        if ep.get("frame"):
            out.append("    nearest route frame before it: %s (%d s earlier)" % (ep["frame"], ep["frame_age_s"]))
    if r["inputs_logged"] and r["by_input"]:
        out.append("by input held (play seconds):")
        for k, v in sorted(r["by_input"].items(), key=lambda kv: -kv[1]["seconds"]):
            out.append("    %-44s %4d s  mean %5.1f  below bar %d s" % (k[:44], v["seconds"], v["mean_gfps"], v["dip_seconds"]))
    out.append("playprobe_report: %d dip(s) in %d play s" % (len(r["dips"]), r["play_seconds"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", help="a result dir (logcat.txt, route-frames/) or a logcat file")
    ap.add_argument("--bar", type=float, help="gfps bar; default playable_fps x fps_tolerance from targets.toml")
    ap.add_argument("--lookback", type=float, default=LOOKBACK_S, help="seconds of inputs shown before a dip")
    ap.add_argument("--targets", default=tv.DEFAULT_TARGETS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rdir = a.path if os.path.isdir(a.path) else os.path.dirname(os.path.abspath(a.path))
    lc = os.path.join(a.path, "logcat.txt") if os.path.isdir(a.path) else a.path
    if not os.path.isfile(lc):
        print("playprobe_report: no logcat at %s" % lc)
        return 2
    if a.bar is not None:
        bar = a.bar
    else:
        d = tv.load_targets(a.targets).get("defaults") or {}
        bar = float(d.get("playable_fps", 30)) * float(d.get("fps_tolerance", 0.95))
    lines, _gaps, _open = tv.parse_logcat(lc)
    r = analyse(lines, bar, a.lookback, frames_of(rdir))
    if a.json:
        print(json.dumps(r, indent=1, default=str))
    else:
        print("\n".join(render(r, a.path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
