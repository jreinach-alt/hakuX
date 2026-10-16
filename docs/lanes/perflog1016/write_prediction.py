#!/usr/bin/env python3
"""perflog1016 (#433): write docs/testing/predictions/perflog1016-defaultpath.json.

A hand-read soak prediction (the arms job skips a prediction with a title), in
the shape uberspike569-doa-soak.json uses. Written once, before any run;
refuses to overwrite. Judged by docs/lanes/perflog1016/abread.py --judge.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(ROOT, 'docs', 'testing', 'predictions',
                   'perflog1016-defaultpath.json')

PRED = {
    "registered_utc": datetime.datetime.now(datetime.timezone.utc)
    .strftime("%Y-%m-%dT%H:%M:%SZ"),
    "who": "lane.perflog1016",
    "issue": "433",
    "title": "5454000F-Grand_Theft_Auto_Vice_City.xiso.iso",
    "device": "nova",
    "seconds": 330,
    "route_name": "gta-vc",
    "runs_per_arm": 2,
    "order": "A B B A",
    "a_ref": "4bf47129b1",
    "b_ref": "644877144a",
    "env_a": [],
    "env_b": [],
    "prediction": (
        "#433 perflog1016 P1, the default path with the run-time perflog switch OFF. "
        "HAND-READ: queued by the lane with request.sh --title, judged by "
        "docs/lanes/perflog1016/abread.py --judge this file. "
        "A = origin/master 4bf47129b1. B = lane/perflog1016 644877144a: the same tree plus "
        "debug.h's switch (every NV2A_PHASE_TIMER_* and nv2a_profile_inc_counter site reads "
        "one relaxed flag) and the [tcg787] hooks in cputlb.c/translate-all.c under it. B "
        "carries no poll (that is the renderer.c lend patch), so the switch cannot turn on: "
        "B is the OFF path. Not covered: the four lend patches' own hunks (pfifo.c flag read "
        "per puller call and pusher pass, surface.c timers, profile.c one check per frame, "
        "renderer.c one access() a second); they re-run after the lend. "
        "Scene: GTA Vice City, gta-vc route, Nova, 330 s, one run per request, order A B B A. "
        "Window: mark gameplay +20 s to +180 s (run.log ROUTE clock = logcat clock). "
        "Per run: median of [rdc] tcpu ms/s (tcpu*1000/dt), median gfps, median Ri. Per arm: "
        "mean of its two runs. Band: max(|A1-A2|, |B1-B2|, prior) with prior 14 ms/s tcpu, "
        "0.2 ms Ri (alwaystelemetry's plain-vs-plain, Castlevania). "
        "Point estimate: B-A tcpu 0 to +3 ms/s (about 10 timed phases a draw x 1000 draws x "
        "30 fps x ~1 ns load+branch = 0.3 ms/s; a perflog build's whole cost is +74 ms/s and "
        "OFF skips every clock read). "
        "SLOWDOWN (fail): B-A tcpu > +15 ms/s and outside the band, or B-A Ri < -0.3 ms and "
        "outside the band, or both B runs' gfps median at least 1 below both A runs'. "
        "CLEARED (pass): none of those. A pass bounds the cost under the floor; it is not zero. "
        "VOID: a run with no mark gameplay, fewer than 60 [rdc] lines in the window ([rdc] is "
        "one line per ~2 s, so a full window has ~80), or a B "
        "run with a '[perflog] runtime tier ON' or '[tcg787]' line (B must be OFF). "
        "ON leg (not in this pair; needs the profile.c + renderer.c lend): with perflog.on "
        "dropped, one 'hakuX-perf: [perflog] runtime tier ON (frame N, by marker)' within ~1 s, "
        "then hakuX-phase lines with Sfp/Mfp/FTx/TxH every 60 frames and [tcg787] lines; "
        "a marker with no runtime tier line is a failed switch."),
    "expect": {
        "M0/b_runtime_tier_on_lines": 0,
        "M0/b_tcg787_lines": 0,
        "M1/rdc_lines_min": 60,
        "P1/tcpu_b_minus_a_max_ms_per_s": 15.0,
        "P1/ri_b_minus_a_min_ms": -0.3,
        "P1/gfps_both_b_below_both_a_by": 1,
        "P1/prior_band_tcpu_ms_per_s": 14.0,
        "P1/prior_band_ri_ms": 0.2,
        "P1/window_from_mark_s": [20, 180],
    },
    "expect_counts": {},
    "expect_note": ("Named rules read by docs/lanes/perflog1016/abread.py --judge, "
                    "not golden keys."),
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
