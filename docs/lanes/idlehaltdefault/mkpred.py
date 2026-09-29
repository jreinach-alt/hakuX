#!/usr/bin/env python3
"""Writes lane.idlehaltdefault's six soak predictions (#525), one per title.
Hand-read: the arms job skips a titled env A/B (a_ref == b_ref), and this lane
queues the requests itself. Kept as the provenance of their text; run once,
before any run. The bounds come from the same-arm pairs in NOTES.md
("Bounds"), read with ihd_judge.py before registration."""
import datetime
import json
import os

now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
Z = '3a5d79e3ea225fd1a7673de28657b6eb14cc058c'   # origin/master when registered
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'testing', 'predictions')

JUDGE = ("python3 docs/lanes/idlehaltdefault/ihd_judge.py --a <A1> [<A2>] --b <B1> [<B2>]  "
         "(copies each result dir into docs/lanes/idlehaltdefault/.copies and runs title_verdict.judge "
         "there; never inside dispatch/results)")
WINDOW = ("the route's first `mark gameplay` (survey route: `mark play`) to `soak end`, "
          "title_verdict.py's scored window; every leg is read over it")

V = ("Per run: not VOID (title_verdict: display, foreground, thermal pause in the window), a "
     "window of >= 120 s holding >= 20 fps windows, audio and power measured. Both arms on the "
     "Nova with one apk_sha. B's [idlehalt] lines read on=1 with halts > 0 in the window; A's "
     "read on=0. A run that fails V is re-queued, never scored as a zero.")
P1 = ("Display lateness: [pace526] late_gt1ms / waited (limiter-held display frames released "
      "more than 1 ms after their deadline) over the window, B <= A + 0.002. Bound: lane.pacing's "
      "sleep-limiter arm measured 0.0008 pooled over two Kabuki runs, one of them 1 in 12612, so "
      "the two runs spread by ~0.0015; 0.002 covers that. Judged only when both arms hold >= 1000 "
      "frames (a render-bound title's limiter never holds one, and the leg is then BLIND, "
      "reported as such, not as a pass).")
P2 = ("Frame-time p99: the median over the window's hakuX-pace lines of each line's `max` (the "
      "worst flip of 60), which estimates the 98.85th percentile of flip time (0.5^(1/60)) if "
      "flips are independent; an estimator, labelled. B <= 1.5 x A. Bound: the same-arm pairs "
      "spread by up to 46% (Kabuki 30.8 vs 45.0 ms), and 7 of 9 DOA1U pairs by <= 20%; the two "
      "DOA1U pairs past 1.5x each hold one run that was not in the fight (lane.pacing: 2.35 flips "
      "a second). Reported, not judged: vK p99 in VBLANKs, and the share of flips over nominal.")
A = ("Audio: title_verdict's audio_starve_share (short sink callbacks after mark + 10 s). Holds "
     "when B <= 0.001 (the verdict's bar). If A itself is over 0.001, B <= A + 0.0031, the "
     "largest same-arm spread measured (DOA1U notify488 9f80bc887a: 0 vs 0.0031). Fails in the "
     "world where the halt's late wake starves the APU feed while the halt-off arm plays clean.")
E = ("J/frame (title_verdict power.j_per_frame = net_w x scored s / flips; net_w includes the "
     "USB input, so a charging run compares fairly): B < A in at least 4 of the 6 titles, first "
     "pairs. Fails in the world where the halt's saving belongs to AUF and Blinx (idle-heavy) and "
     "the pgraph-bound titles, which idle less, pay the wake cost in power instead.")
SECOND = ("A second pair (same order, same ref) is queued for this title only if a leg fails on "
          "the first, or if B is worse than A by more than half the H bound or half the P2 "
          "margin. Scored pooled: H on the mean of the two runs' medians per arm, P on each pair.")
VERDICT = ("Across the six titles: the halt stays opt-in if any title fails H or P on both of its "
           "pairs; the PR proposes default-on if H, P and A hold on every title and E holds. "
           "Controls, cited not re-run: AUF 1-1790582079-idlehalt-2124199 (off) / "
           "1-1790582078-idlehalt-2124125 (on), Blinx 1-1790582080-idlehalt-2124441 / "
           "-2124356, at 40fabbaacc.")

T = {
    'kabuki': dict(
        title="43560001-Kabuki_Warriors.xiso.iso", route="kabuki-warriors", seconds=420, lead="A",
        why="a 60 fps budget: capped at 60 (gfps 59 from boot to the fight, lane.pacing)",
        H=("fps median of the per-60-flip windows (title_verdict's exact 60 / dt): B >= A - 2.0 fps. "
           "Bound: the Kabuki route's Nova runs at ead1086cb5 read 59.94 (1-1790559842-lane.pacing-"
           "2277012, only 3 windows), 57.97 (1-1790575939-lane.pacing-1078233, same arm) and 58.03 "
           "(-1078186, the spin limiter, which lane.pacing found fps-neutral): a 1.97 fps range. The "
           "time share at 57 fps is not used: in 2277012 one 60-flip window lasts 62.6 s of a 75 s "
           "window, and slow stretches of 11.4 s sit between rounds in 1078233, so the share read "
           "0.05 vs 0.38 within one arm."),
    ),
    'fuzion': dict(
        title="Fuzion Frenzy (USA).xiso.iso", route="fuzion-frenzy", seconds=420, lead="B",
        why="a 60 fps budget: asks for every VBLANK (targets.toml target 60; ran 30.6 median on the Nova)",
        H=("fps median of the per-60-flip windows: B >= A - 2.5 fps. Bound BORROWED: one Nova run "
           "exists (1-1790507407-titlebench-1059623, 30.58), so no same-arm spread; 2.5 is Forza's "
           "measured same-arm spread (2.23 of 27.7, 8%) applied to 30.6. Time share at 57 reported."),
    ),
    'forza': dict(
        title="4D53006E-Forza_Motorsport.xiso.iso", route="survey", seconds=420, lead="A",
        why="heavy on pgraph sync: downloads (#414)",
        H=("fps median of the per-60-flip windows: B >= A - 2.3 fps. Bound: the same-arm pair "
           "1-1790518618-forza414-1930404 / 0-0-x-1790525921-forza414-1054756 (4b22f2526b, survey, "
           "Nova) read 26.62 vs 28.85."),
    ),
    'doa1u': dict(
        title="54430006-Dead_or_Alive_1_Ultimate.xiso.iso", route="survey", seconds=420, lead="B",
        why="heavy on pgraph sync; lane.pacing's noisy title (9.5-15 gfps within one arm)",
        H=("fps median of the per-60-flip windows: B >= A - 4.0 fps. Bound: nine same-arm Nova pairs "
           "(NOTES.md, Bounds) spread by 0.4-4.0 fps in eight, and 12.8 in the ninth (lane.pacing's "
           "1078334-r2, a run mostly not in the fight). The brief asked for a time-share form here; "
           "on the same nine pairs the time share at 13.5 fps (0.9 x DOA1U's usual 15) spread by "
           "0.08-1.0, and at 28.5 it is 0 in most runs (a leg that cannot fail), so the median is "
           "the tighter instrument and the second pair carries the noise."),
    ),
    'blinx2': dict(
        title="4D530065-Blinx_2_Battle_of_Time_Space_Blinx_2_Masters_of_Time_Space.xiso.iso",
        route="survey", seconds=420, lead="A",
        why="near the 30 fps bar: capped at 30, 29.3 median on the Nova survey",
        H=("fps median of the per-60-flip windows: B >= A - 1.0 fps, and the time share at >= 28.5 "
           "fps: B >= A - 0.10. Bound: the two Nova runs are at different refs (e5db66fa37 29.28 / "
           "0.573, e156fcdf02 29.38 / 0.513), so the spread is BORROWED from Kabuki's capped pair "
           "(1.97 of 60, 3.3%, times 30 = 1.0) and, for the share, rounded up from these two (0.06)."),
    ),
    'ghoulies': dict(
        title="Grabbed by the Ghoulies (USA) (En,Fr,De,Es,It).xiso.iso", route="ghoulies",
        seconds=730, lead="B",
        why="near the 30 fps bar: swap interval 2 (targets.toml target 30); `mark gameplay` at ~430 s",
        H=("fps median of the per-60-flip windows: B >= A - 1.0 fps, and the time share at >= 28.5 "
           "fps: B >= A - 0.10. Bound BORROWED as for Blinx 2: the ghoulies route has never run on "
           "the Nova, and its one same-arm Thor pair (6bfce4a685: 7.74 vs 29.96) holds a run that "
           "decayed (#311 shape), so it measures a failure, not noise."),
    ),
}

for key, p in T.items():
    order = "A1 then B1" if p['lead'] == "A" else "B1 then A1"
    d = {
        "registered_utc": now, "who": "lane.idlehaltdefault", "issue": "525",
        "title": p['title'], "device": "nova", "seconds": p['seconds'], "route": p['route'],
        "perflog": True, "frames_every": 0, "runs_per_arm": 1,
        "a_ref": Z, "b_ref": Z, "a_env": [], "b_env": ["HAKUX_IDLE_HALT=1"],
        "queue_order": ("%s, each request.sh --who lane.idlehaltdefault --title <title> --route %s "
                        "--seconds %d --perflog --device nova --ref %s, B with --env HAKUX_IDLE_HALT=1. "
                        "Titles interleaved: Kabuki A B, Fuzion B A, Forza A B, DOA1U B A, Blinx 2 A B, "
                        "Ghoulies B A, so the Nova's drift falls on both arms. One binary."
                        % (order, p['route'], p['seconds'], Z[:10])),
        "window": WINDOW,
        "judge": JUDGE,
        "prediction": (
            "#525, should the idle halt default on. %s on the Nova, %s. One master binary (%s, "
            "the halt opt-in, spin 0), A without and B with HAKUX_IDLE_HALT=1. The halt's pg "
            "callback wake is slower (leg L failed: p99 raise-to-run 100-200 us on AUF), but at "
            "~1.6 pg wakes a frame that is well under 1%% of a 16.7-33 ms frame, so a player sees "
            "no fps, pacing or audio change beyond this title's same-arm spread, and J/frame "
            "falls." % (p['title'], p['why'], Z[:10])),
        "legs": {
            "V (validity)": V,
            "H (fps)": p['H'] + " Fails in the world where the slow wake stalls the guest behind "
                               "the push buffer each frame, so a pgraph-bound or 60-budget title "
                               "loses frames the halt-off arm keeps.",
            "P (pacing)": P1 + " " + P2 + " Fails in the world where the tail shows as frames "
                                          "that miss their VBLANK (hitching) with the mean fps intact.",
            "A (audio)": A,
            "E (energy, across titles)": E,
            "Second pair": SECOND,
            "Verdict": VERDICT,
        },
        "expect": {},
        "expect_counts": {},
        "expect_note": ("EMPTY ON PURPOSE: a soak writes no captures. The legs are read off "
                        "hakuX-perf, hakuX-pace, [pace526], hakuX-audiocap, [idlehalt] and "
                        "thermal.jsonl by ihd_judge.py."),
    }
    fn = os.path.join(OUT, 'idlehaltdefault-%s.json' % key)
    if os.path.exists(fn):
        raise SystemExit("%s exists: a registered prediction is not rewritten" % fn)
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    with open(fn, 'w') as f:
        f.write(s)
    print(fn)
