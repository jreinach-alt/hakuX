#!/usr/bin/env python3
"""Writes lane.idlehalt's spin-variant predictions (hand-read, run through
request.sh; a_ref == b_ref, so the arms job skips them). Kept as the
provenance of their text."""
import datetime
import json

now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
Z = '40fabbaacc7f0fb06e5a003f1a38631fae6d8194'
SPIN = 100
ENV = {'A': [], 'B': ['HAKUX_IDLE_HALT=1'],
       'C': ['HAKUX_IDLE_HALT=1', 'HAKUX_IDLE_HALT_SPIN_US=%d' % SPIN]}

V = ("Per run: >= 20 [idlehalt] windows inside the window and ihread.py's checks ok; "
     "every line on=0 in A, on=1 in B and C, spin_us=0 in A and B and spin_us=%d in C; the "
     "route's play shots show level play. A run whose thermal record shows cpu3-7 paused "
     "inside the window is VOID for fps, on-CPU share and J/frame (#507), not a zero." % SPIN)
L = ("The point. C's pg raise-to-run share at >= 50 us is at most half of B's (same "
     "binary, same device, same session). Reported, not judged: C against the first "
     "prediction's <= 1%% bound; and the consistency check that C's reduction is about B's "
     "kpg share under %d us (halt entry to pg kick), since the spin can only catch a kick "
     "that lands inside it." % SPIN)
H = ("C's vCPU run%% is at most B's + 12 points (the spin's cost: ~1000 halts/s x up to "
     "%d us is <= 10 points), and at least 25 points under A's." % SPIN)
C = ("B and C: tp = 0 and xpc = 0 over the window. C: sh > 0 (kicks landed inside the "
     "spin). A: halts = 0.")
F = ("gfps in the window: B and C each >= 0.95 x A. The first batch measured B at 0.987 "
     "and 0.990 x A on these titles.")
J = ("title_verdict.py (master) on a copy of each result dir, power.measured true with >= "
     "4 samples in each: C's j_per_frame <= 0.85 x A's. The first batch measured B at 0.68 "
     "(AUF) and 0.73 (Blinx) x A. B's is reported beside it.")
FALS = ("The spin variant is refuted in any of these worlds: C's pg >= 50 us share above "
        "half of B's (the callback lands later in the halt than %d us, so the spin misses "
        "it: B's kpg shows it); C's run%% more than 12 points over B's, or less than 25 "
        "under A's (the spin eats the saving); C's gfps under 0.95 x A; C's J/frame over "
        "0.85 x A; tp > 0 in B or C; a C run that wedges. Any of these keeps the default "
        "off." % SPIN)

PREDS = {
    'idlehalt-spin-auf.json': dict(
        title="4541000D-007_Agent_Under_Fire.xiso.iso",
        window="299-420 s since the logcat's first line (as the first AUF prediction)",
        judge="python3 docs/lanes/idlehalt/ihread.py --from 299 --to 420 <C1> <B1> <A1>",
        extra="AUF is Nova-only; every run on the Nova."),
    'idlehalt-spin-blinx.json': dict(
        title="4D530013-Blinx_The_Time_Sweeper.xiso.iso",
        window="`mark play` + 10 s to 10 s before the log ends (ihread.py --play)",
        judge="python3 docs/lanes/idlehalt/ihread.py --play <C1> <B1> <A1>",
        extra=("Blinx takes ~15 callbacks a frame against AUF's ~2, so L is loaded hardest "
               "here. Every run on the Nova, the device of the first batch.")),
}

for fn, p in PREDS.items():
    d = {
        "registered_utc": now, "who": "lane.idlehalt", "issue": "525",
        "title": p['title'], "device": "nova", "seconds": 420, "route": "survey",
        "perflog": True, "frames_every": 0, "runs_per_arm": 1,
        "a_ref": Z, "b_ref": Z, "c_ref": Z,
        "a_env": ENV['A'], "b_env": ENV['B'], "c_env": ENV['C'],
        "queue_order": ("C1, B1, A1, each request.sh --title <title> --route survey "
                        "--seconds 420 --perflog --device nova --ref %s with the arm's "
                        "env. One binary." % Z[:10]),
        "window": p['window'],
        "judge": p['judge'] + "; J/frame: title_verdict.py on a copy of each dir",
        "prediction": (
            "#525 idle halt, latency variant, on %s. The first batch showed the halt frees "
            "the core (J/frame -32%% AUF, -27%% Blinx) but the push-buffer callback's "
            "raise-to-run tail failed its bound (14.2%% and 3.7%% of pg wakes >= 50 us): a "
            "futex wake of a sleeping thread. With HAKUX_IDLE_HALT_SPIN_US=%d each idiom "
            "halt first spins up to %d us without the BQL, polling for its kick, so a "
            "callback raised inside the spin runs without that wake; the spin costs a "
            "bounded share of the saving. A = off, B = halt, C = halt + spin, all at %s. %s"
            % (p['title'], SPIN, SPIN, Z[:10], p['extra'])),
        "legs": {
            "V (validity)": V,
            "L (callback latency)": L,
            "H (host)": H,
            "C (counters)": C,
            "F (fps)": F,
            "J (energy per frame)": J,
            "Falsifier": FALS,
        },
        "expect": {}, "expect_counts": {},
        "expect_note": ("EMPTY ON PURPOSE: a soak writes no captures. The legs are read off "
                        "[idlehalt], [rr425w] and hakuX-perf lines by ihread.py, and power "
                        "by title_verdict.py."),
    }
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    with open('docs/testing/predictions/' + fn, 'w') as f:
        f.write(s)
    print(fn, len(s))
