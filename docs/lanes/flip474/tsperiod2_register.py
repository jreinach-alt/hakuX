#!/usr/bin/env python3
"""Write the predictions for the second cut of the timestamp-period change.

    python3 docs/lanes/flip474/tsperiod2_register.py <a_ref> <b_ref>

The first cut's predictions (flip474-tsperiod-*.json) name 902cf1ab53 and
stay on file with their verdicts in tsperiod.md. These name the second cut.
The pgraph file is written by ab_compare.py --register, with the first
file's suites and must-not-move list; the two device files are serialised
and parsed back before they are written.
"""
import json
import subprocess
import sys

A = subprocess.check_output(['git', 'rev-parse', sys.argv[1]]).decode().strip()
B = subprocess.check_output(['git', 'rev-parse', sys.argv[2]]).decode().strip()
NOW = subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ']).decode().strip()
P = 'docs/testing/predictions/'

old = json.load(open(P + 'flip474-tsperiod-pgraph-inert.json'))
cmd = ['python3', 'docs/testing/ab_compare.py', '--register',
       P + 'flip474-tsperiod2-pgraph-inert.json', '--who', 'lane.flip474',
       '--issue', '474', '--a-ref', A, '--b-ref', B,
       '--disc-suites', ','.join(old['disc']['suites']),
       '--prediction',
       '#474: the GPU timestamp period measured at start-up, second cut '
       '(renderer.c gpu_ts_calibrate). b_ref adds only the calibration, and '
       'only in perflog builds: one-timestamp command buffers on the aux '
       'command buffer for ~120 ms at init, before any guest work, on a '
       'one-query pool created and destroyed there. The period feeds only '
       'the GPU phase stats. Every capture is identical in A and B.']
for g in old['must_not_move']:
    cmd += ['--must-not-move', g]
subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

NOTE = ("EMPTY ON PURPOSE: a soak writes no captures. The legs are read off "
        "the start-up 'GPU timestamp period' line, hakuX-phase and [surf413] "
        "lines.")
LINE = ("'init: GPU timestamp period reported= measured= (+-%, span, samples "
        "k of n, halves differ %) using= (measured|reported[; not measured: "
        "why])'")


def base(title, device, seconds, route):
    return {
        "registered_utc": NOW, "who": "lane.flip474", "issue": "474",
        "title": title, "device": device, "seconds": seconds, "route": route,
        "perflog": True, "frames_every": 0, "runs_per_arm": 1,
        "a_ref": A, "b_ref": B,
        "arms": "B only. No leg compares against an A run: each is read off "
                "B's own start-up line or compares two clocks inside B.",
        "must_not_move": [
            "pgraph: " + P + "flip474-tsperiod2-pgraph-inert.json (12 "
            "suites, identical captures, same refs)"],
        "expect": {}, "expect_counts": {}, "expect_note": NOTE,
    }


doa = base("54430006-Dead_or_Alive_1_Ultimate.xiso.iso", "nova", 300, "survey")
doa["judge"] = ("grep 'GPU timestamp' logcat.txt; python3 docs/lanes/flip474/"
                "phaseread.py --from 151 --to 288 <B>; lockread.py on the "
                "same window for cdef and gfps; gfpsseries.py for the cut at "
                "a scene change; crashcheck.py, tailcheck.py")
doa["prediction"] = (
    "#474: the second cut measures the period with the GPU kept busy. The "
    "first cut slept 100 ms between its samples and read 4636 ns on the "
    "Thor. On the Nova the counter ticks every 52.083 ns (o4clock.py's fit "
    "under load, and upstream Turnip's constant) and the driver reports "
    "33.11. DOA's fight is GPU-bound, so its GPU span and the PFIFO "
    "thread's wait for the same command buffer (cdef, CPU clock) are the "
    "same interval read on two clocks.")
doa["legs"] = {
    "M0 (instrument)": ">= 15 hakuX-phase lines with GPU > 0 in 151-288 s, "
    "and the shots show the fight. Otherwise VOID, rerun once.",
    "K0 (the line)": "exactly one " + LINE + " in the logcat. KILL: none.",
    "K1 (the value)": "measured= is 52.08 ns +-1% (51.56 to 52.60) and "
    "using= is the measured value. KILL: using= is a measured value "
    "outside 49.5 to 54.7 ns.",
    "K3 (the self-check, a guess)": "halves differ < 2% and the scatter "
    "(+-) < 2%, so the line says (measured). Confidence 70%: nothing on "
    "disk says how this counter behaves across a 300 us idle gap. If it "
    "says '(reported; not measured: ...)', the change is safe and useless "
    "on this device: K1 is then not met, the reason is the finding, and "
    "G1 must show GPU at 0.64 of cdef.",
    "G1 (two clocks, one interval)": "B's phase GPU median over the fight "
    "is within 8% of B's cdef median. With the reported period it reads "
    "0.64 of cdef (today's three runs on 795ea6b3af: 0.65, 0.65, 0.66). "
    "KILL: using= is a measured value and GPU is outside 0.85 to 1.15 of "
    "cdef.",
    "P1 (no regression)": "B's gfps median in the fight >= 12. Today's "
    "master runs read 13 to 16. The change is ~120 ms at start-up.",
    "H0 (no hang)": "longest gap between hakuX-perf lines in the window "
    "<= 3 s, lines to the end, no crash marker.",
}

th = base("Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)"
          ".xiso.iso", "thor", 120, "crimson-skies")
th["judge"] = ("grep 'GPU timestamp' logcat.txt; python3 docs/lanes/flip474/"
               "gfpsseries.py --from 0 --to 120 <B>; crashcheck.py")
th["prediction"] = (
    "#474, the Thor check. The first cut read 4636.591 ns here "
    "(1-1790540677-flip474-2313275): its counter advanced 1.2 ms over a "
    "110 ms span with a 100 ms sleep in it. The Thor's SoC and driver are "
    "the Nova's, so the guess is the same 52.083 ns counter. The route need "
    "not play: both Thor runs of the first cut were refused input focus, "
    "and every leg here is read off the start-up line or off whatever the "
    "title draws unattended.")
th["legs"] = {
    "K0 (the line)": "exactly one " + LINE + " in the logcat. KILL: none.",
    "K1 (the value, a guess)": "measured= is 52.08 ns +-1% and using= is "
    "the measured value. KILL: using= is a measured value outside 49.5 to "
    "54.7 ns; the first cut's 4636 would be that.",
    "K3 (the self-check, a guess)": "as on the Nova, confidence 70%. If the "
    "line says '(reported; not measured: ...)', the Thor's counter depends "
    "on idle gaps of 300 us; that is the finding and using= is 33.11.",
    "G2 (physically possible)": "every hakuX-phase line has GPU <= 1.05 x "
    "Tot. The first cut read GPU 28 to 30 ms of a 32.5 ms frame on a "
    "two-pass screen that reads 0.2 ms with the reported period.",
    "G3 (the screen the first cut got wrong)": "on the unattended screen "
    "(RP:2), GPU is under 1 ms. KILL: over 5 ms.",
    "H0": "no crash marker.",
}

for name, d in (("flip474-tsperiod2-doa-nova.json", doa),
                ("flip474-tsperiod2-thor.json", th)):
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    with open(P + name, "w") as f:
        f.write(s)
    print(name, A[:10], B[:10])
print("flip474-tsperiod2-pgraph-inert.json", A[:10], B[:10])
