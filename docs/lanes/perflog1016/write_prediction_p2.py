#!/usr/bin/env python3
"""perflog1016 (#433): write docs/testing/predictions/perflog1016-postlend.json.

P2, the default path with every hunk of the PR (the three granted files
applied), plus the ON leg. Hand-read like P1 (it has a title, so the arms job
skips it). Written once, before any run; refuses to overwrite. Judged by
docs/lanes/perflog1016/abread.py --judge, which reads P2/<name> before
P1/<name>.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(ROOT, 'docs', 'testing', 'predictions',
                   'perflog1016-postlend.json')

PRED = {
    "registered_utc": datetime.datetime.now(datetime.timezone.utc)
    .strftime("%Y-%m-%dT%H:%M:%SZ"),
    "who": "lane.perflog1016",
    "issue": "433",
    "title": "5454000F-Grand_Theft_Auto_Vice_City.xiso.iso",
    "device": "nova",
    "seconds": 330,
    "route_name": "gta-vc",
    "runs_per_arm": {"A": 3, "B": 2, "ON": 1},
    "order": "ON A B A B A",
    "a_ref": "7e00c7cf73",
    "b_ref": "ce91b11b74",
    "env_a": [],
    "env_b": [],
    "env_on": ["XEMU_PERFLOG_RT=1"],
    "prediction": (
        "#433 perflog1016 P2, after the lend. HAND-READ: queued by the lane with "
        "request.sh --title, judged by docs/lanes/perflog1016/abread.py --judge this file "
        "--on <the ON run>. A = origin/master 7e00c7cf73. B = lane/perflog1016 ce91b11b74: "
        "A merged plus every emulator hunk of the PR: debug.h's switch (every "
        "NV2A_PHASE_TIMER_* and counter site reads one relaxed flag), the [tcg787] hooks in "
        "cputlb.c/translate-all.c, pfifo.c (one relaxed flag load per method command in "
        "pfifo_run_puller beside its four atomics, one per pusher pass, the idle split "
        "behind it), profile.c (one flag check per flip for its every-60-frames block) and "
        "renderer.c (one access() of perflog.on a second, at the flip). Not in B: "
        "vk/surface.c (dropped; its timers print 0 under the switch). "
        "ON = B with --env XEMU_PERFLOG_RT=1 (the app's env_vars pref, setenv in "
        "xemu_android.cpp, read once at the first poll). "
        "Scene: GTA Vice City, gta-vc route, Nova, 330 s, one run per request. Order ON A1 "
        "B1 A2 B2 A3: each run's APK differs from the one before, so the dispatcher clears "
        "the shader cache before every run (it clears only on an APK change); A is last so "
        "the request after A3 finds no env of ours to clear. "
        "Window: mark gameplay +20 s to +180 s (run.log ROUTE clock = logcat clock). "
        "Per run: median of [rdc] tcpu ms/s (tcpu*1000/dt), median gfps, median Ri. Per arm: "
        "mean of its cold-cache runs (a warm run is listed and left out). Band: "
        "max(within-arm max-min, prior) with prior 14 ms/s tcpu, 0.2 ms Ri. P1 on 10-16 "
        "measured a same-build cold spread of 28.8 ms/s tcpu (A1-A2), so the band will "
        "likely be near 30 ms/s: this pair can see a slowdown of that size, not the point "
        "estimate. "
        "Point estimate: B-A tcpu 0 to +3 ms/s (P1's 0.3 ms/s for the debug.h sites, plus "
        "one load per method command, ~30k a second at ~1 ns, 0.03 ms/s, plus one access() "
        "a second, ~10 us). gfps B-A 0. Ri B-A within 0.2 ms. "
        "SLOWDOWN (fail): B-A tcpu > +15 ms/s and outside the band, or B-A Ri < -0.3 ms and "
        "outside the band, or every B run's gfps median at least 1 below every A run's. "
        "CLEARED (pass): none of those; a pass bounds the cost under max(15, band), not zero. "
        "VOID: a run with no mark gameplay or fewer than 60 [rdc] lines in the window; an "
        "arm with fewer than 2 cold-cache runs; a B run with a '[perflog] runtime tier ON', "
        "'[tcg787]' or hakuX-phase line (B is the OFF path; on 10-16 the four P1 runs had "
        "none of the three). "
        "ON leg, M2 (HIT/MISS, separate from the A/B verdict): exactly one 'hakuX-perf: "
        "[perflog] runtime tier ON (frame N, by env)' and no other tier line; from it on, "
        "at least 50 hakuX-phase lines carrying TxH, Sfp, Mfp and FTx with a median Draw of "
        "at least 0.1 ms (the debug.h timers booked; one line per 60 frames, ~150 in the "
        "run); hakuX-cpu medians Pull and Push at least 0.1 ms (pfifo.c's timers booked); "
        "at least 20 [tcg787] lines (one per 2 s window on at both ends, ~150). "
        "ON cost: tcpu, gfps, Ri over the window against the B mean, printed, not judged "
        "(one run). Expected +5 to +60 ms/s tcpu (a perflog build costs +74 ms/s; the "
        "callback-latency split at pfifo.c:785, a clock read per method dispatch and per "
        "park, stays compile-time, so the switch pays less than the build)."),
    "expect": {
        "M0/b_runtime_tier_on_lines": 0,
        "M0/b_tcg787_lines": 0,
        "M0/b_phase_lines": 0,
        "M1/rdc_lines_min": 60,
        "M1/cold_runs_only": True,
        "M1/cold_runs_min_per_arm": 2,
        "P2/tcpu_b_minus_a_max_ms_per_s": 15.0,
        "P2/ri_b_minus_a_min_ms": -0.3,
        "P2/gfps_both_b_below_both_a_by": 1,
        "P2/prior_band_tcpu_ms_per_s": 14.0,
        "P2/prior_band_ri_ms": 0.2,
        "P2/window_from_mark_s": [20, 180],
        "M2/on_tier_lines": 1,
        "M2/on_phase_lines_min": 50,
        "M2/on_phase_draw_median_min_ms": 0.1,
        "M2/on_cpu_pull_median_min_ms": 0.1,
        "M2/on_cpu_push_median_min_ms": 0.1,
        "M2/on_tcg787_lines_min": 20,
    },
    "expect_counts": {},
    "expect_note": ("Named rules read by docs/lanes/perflog1016/abread.py --judge "
                    "(P2/<name> before P1/<name>), not golden keys."),
}


def main():
    if os.path.exists(OUT):
        print('refusing: %s exists (a prediction is written once)' % OUT)
        return 1
    text = json.dumps(PRED, indent=2) + '\n'
    json.loads(text)
    with open(OUT, 'w') as f:
        f.write(text)
    print(OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
