#!/usr/bin/env python3
"""Writes lane.idlehalt's two soak predictions (hand-read; the arms job skips
titled predictions). Kept as the provenance of their text."""
import datetime
import json

now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
Z = '6554f0617589a81dac70890a6c99fe910e78eb6c'
V = ("Per run: >= 20 [idlehalt] windows inside the window and ihread.py's checks ok "
     "(span within 5% of the wall clock, schedstat read in every window); every line on=1 "
     "in B and on=0 in A; the route's play shots in the window show level play. A run whose "
     "hakuX-cpu or thermal record shows cpu3-7 paused inside the window is VOID for fps and "
     "on-CPU share (#507), not a zero.")
C = ("B: halts > 0 in every window after `[idlehalt] armed`, tp (timeouts with work pending "
     "and no kick: a missed wake) = 0 over the window, and xpc = 0 (the idiom halts only at "
     "the idle loop's pc; a guess, labelled). A: halts = 0.")
L = ("B: the pg raise-to-run histogram (the PGRAPH ERROR push-buffer callback, kick to the "
     "vCPU leaving the wait) has <= 1% of wakes at >= 50 us, i.e. p99 < 50 us. The same for "
     "lall is reported, not judged.")
F = ("gfps (1000 / mean G of the hakuX-perf lines) in the window: B >= 0.9 x A. The noise "
     "band is not measured for this build; 10% is wider than the 17.82 vs 17.76 pair "
     "retreason425 measured on one binary, and narrower than the 15-17.8 spread across "
     "builds. B runs first, on the shader cache A's apk install cleared, so any cache bias is "
     "against B.")
BOOTS = ("5 of 5 B runs (B1 and four boot runs B2-B5 of 300 s, same route) reach level play "
         "in the route's play shots, with `[idlehalt] armed` logged in each.")
HEAT = ("J/frame for both arms when the verdict reports power.measured: true (#523); until "
        "then the host leg is the on-CPU share and J/frame is reported as pending.")
FALS = ("The halt is refuted, and stays default off, in any of these worlds: a B boot that "
        "wedges (no hakuX-perf gfps lines, or flip=0 / no nv2a fb for the rest of the run); "
        "B's gfps below 0.9 x A's; tp > 0 (the wait missed a wake the bounded timeout had to "
        "recover); pg raise-to-run p99 >= 50 us. A B whose run% does not fall below A's by at "
        "least 25 points refutes the heat claim (the halt does not free the core) even if "
        "every other leg passes.")

PREDS = {
    'idlehalt-auf.json': dict(
        title="4541000D-007_Agent_Under_Fire.xiso.iso",
        window="299-420 s since the logcat's first line (mission play, as retreason425 read it)",
        judge=("python3 docs/lanes/idlehalt/ihread.py --from 299 --to 420 <B1> <A1>; "
               "boots: the route's play shots of B1..B5"),
        host=("A: run% >= 85 (retreason425 measured the vCPU ~94% on-CPU with the guest idle "
              "65.1% here). B: run% <= (1 - guest idle) + 15 points, about <= 50%, where guest "
              "idle is B's own [rr425w] idle share; and slept% within 10 points of guest idle "
              "(a guess, labelled)."),
        extra="AUF is Nova-only; every run on the Nova."),
    'idlehalt-blinx.json': dict(
        title="4D530013-Blinx_The_Time_Sweeper.xiso.iso",
        window=("`mark play` + 10 s to 10 s before the log ends (ihread.py --play), as "
                "retreason425 read Blinx"),
        judge=("python3 docs/lanes/idlehalt/ihread.py --play <B1> <A1>; "
               "boots: the route's play shots of B1..B5"),
        host=("A: run% >= 85. B: run% <= (1 - guest idle) + 15 points, about <= 62% "
              "(retreason425: guest idle 52.5% here), where guest idle is B's own [rr425w] "
              "idle share; and slept% within 10 points of guest idle (a guess, labelled)."),
        extra=("Blinx takes 14.66 callbacks a frame against AUF's 1.97 (retreason425), so the "
               "callback latency leg is loaded hardest here. Every run on the Nova, the device "
               "its copy and retreason425's baseline are on.")),
}

for fn, p in PREDS.items():
    d = {
        "registered_utc": now, "who": "lane.idlehalt", "issue": "525",
        "title": p['title'], "device": "nova", "seconds": 420, "route": "survey",
        "perflog": True, "frames_every": 0, "runs_per_arm": 1,
        "a_ref": Z, "b_ref": Z, "a_env": [], "b_env": ["HAKUX_IDLE_HALT=1"],
        "queue_order": ("B1 (--env HAKUX_IDLE_HALT=1) then A1, each request.sh --title "
                        "<title> --route survey --seconds 420 --perflog --device nova --ref "
                        "%s; then B2-B5 the same as B1 with --seconds 300. One binary."
                        % Z[:10]),
        "window": p['window'],
        "judge": p['judge'],
        "prediction": (
            "#525 idle halt on %s. %s (default off, identical tree to 056eea9aaf) with "
            "HAKUX_IDLE_HALT=1 turns the guest kernel's idle idiom (sti; nop; nop; cli) into a "
            "halt bounded at 1 ms, armed at the first PIT. The guest was idle 52-66%% of wall "
            "time in these titles while the vCPU thread stayed ~94%% on-CPU (retreason425 "
            "sections 6-8), so with the halt the vCPU's on-CPU share falls toward the guest's "
            "busy share, gfps does not move beyond noise, and the push-buffer callback that "
            "starts each frame's work reaches the guest within 50 us of its raise. %s"
            % (p['title'], Z[:10], p['extra'])),
        "legs": {
            "V (validity)": V,
            "H (host: the point)": p['host'],
            "C (counters)": C,
            "L (callback latency)": L,
            "F (fps)": F,
            "B (boots)": BOOTS,
            "Heat": HEAT,
            "Falsifier": FALS,
        },
        "expect": {}, "expect_counts": {},
        "expect_note": ("EMPTY ON PURPOSE: a soak writes no captures. The legs are read off "
                        "[idlehalt], [rr425w] and hakuX-perf lines by ihread.py, and the shots "
                        "by eye."),
    }
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    with open('docs/testing/predictions/' + fn, 'w') as f:
        f.write(s)
    print(fn, len(s))
