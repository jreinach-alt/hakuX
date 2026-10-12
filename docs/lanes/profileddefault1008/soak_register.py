#!/usr/bin/env python3
"""Write the per-title bandwidth-vs-profiled soak predictions (lane.profileddefault1008).

    python3 docs/lanes/profileddefault1008/soak_register.py <ref>

Same binary both arms; the only difference is --env TU_AUTOTUNE_ALGO=bandwidth
vs. TU_AUTOTUNE_ALGO=profiled (ApplyRenderMode's setenv is overwrite=0, so the
request's env always wins). The win/hold/lose rule is NOTES.md's, written
before any run; these files restate it as predictions so each result can be
checked without re-deriving it.
"""
import datetime
import json
import subprocess
import sys

REF = subprocess.check_output(['git', 'rev-parse', sys.argv[1]]).decode().strip()
NOW = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
P = 'docs/testing/predictions/'

RULE = (
    "WINS: gfps >= bandwidth+2 and >= 1.08x, J/frame <= 1.05x. "
    "HOLDS: gfps within +/-1, J/frame <= 1.05x. "
    "LOSES: gfps < bandwidth-1, or J/frame > 1.05x at equal gfps, or a "
    "perf-line gap >= 2s bandwidth's arm lacks. A thermal pause voids the "
    "arm (rerun once, only after the cause is read)."
)

TITLES = [
    dict(
        key="topspin", title="4D530035-Top_Spin.xiso.iso", route="fps786-topspin",
        role="candidate",
        prediction="#474: profiled may pick sysmem-like binning on Top Spin's "
        "tennis court scenes the way it did on DOA3 and NG Black's attract/intro "
        "(gpunonrender attempts 13-14). No prior perf read exists for this "
        "title (FAILED_HARNESS: ran, no scored window) -- this pair is also "
        "its first clean fps/J-per-frame reading.",
    ),
    dict(
        key="fuzion", title="Fuzion Frenzy (USA).xiso.iso", route="fuzion-frenzy",
        role="candidate",
        prediction="#474: same axis as Top Spin. Fuzion Frenzy's last run "
        "(09-27) hung; the pilot's bandwidth arm must complete clean before "
        "this profiled arm is queued, or this file stays unqueued.",
    ),
    dict(
        key="crimson", title="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso",
        route="crimson-skies", role="guard",
        prediction="#474 energy guard, not a win-counting candidate: Crimson "
        "is already Playable. flip474-crimson-ab.json read Crimson's Thor "
        "lock-wait share under a different flag; this just confirms profiled "
        "does not regress the title that is already on the wall.",
    ),
    dict(
        key="kabuki", title="43560001-Kabuki_Warriors.xiso.iso", route="kabuki-warriors",
        role="stall-guard",
        prediction="#474 stall guard: Kabuki is in ApplyRenderMode's guard "
        "list, so its SHIPPED default never reaches profiled -- but this A/B "
        "forces profiled through --env on purpose, to confirm the gmem474 "
        "stall this guard exists for actually reproduces under profiled too, "
        "not just under a hand-set TU_DEBUG=sysmem. If profiled does NOT "
        "stall here, that is new information for the guard list, not a "
        "reason to remove it unreviewed.",
    ),
    dict(
        key="forza", title="4D53006E-Forza_Motorsport.xiso.iso", route="forza.drive",
        role="control",
        prediction="#474 control: Forza's Xfr/T is 0.13 (gpunonrender's "
        "survey), so profiled should pick the same mode bandwidth already "
        "gets and gfps/J should not move. The forza-583-floor hold's "
        "invalid-surfaces defect (#517) is fixed on this branch (10fe2f59a7 "
        "is an ancestor) -- watch [watch311] invalid= anyway; a climbing "
        "count is a void, not a profiled loss.",
    ),
]

for t in TITLES:
    d = {
        "registered_utc": NOW, "who": "lane.profileddefault1008", "issue": "433,474",
        "title": t["title"], "device": "nova", "seconds": 600, "route": t["route"],
        "perflog": True, "frames_every": 30, "runs_per_arm": 1,
        "a_ref": REF, "b_ref": REF,
        "role": t["role"],
        "queue_order": "A (bandwidth) then B (profiled), each request.sh --title --route "
                       + t["route"] + " --device nova --seconds 600 --perflog --frames-every 30 "
                       "--env TU_AUTOTUNE_ALGO=<bandwidth|profiled>",
        "rule": RULE,
        "judge": "grep 'render_mode:' in each logcat for 'autotune=' and "
                 "'TU_AUTOTUNE_ALGO=' to confirm the arm actually set what it "
                 "asked for; gfps and J/frame over the gameplay window from "
                 "perflog; eyeball the two shots for the same scene (region "
                 "check); longest gap between hakuX-perf lines for a stall.",
        "prediction": t["prediction"],
        "legs": {
            "M0 (instrument)": "both arms reach 'mark gameplay' (or the "
            "route's equivalent) and perflog lines run to the end. Otherwise "
            "VOID, rerun once.",
            "D0 (the env took)": "B's logcat 'render_mode:' line shows "
            "TU_AUTOTUNE_ALGO=profiled; A's shows bandwidth or unset. KILL: "
            "either arm's line does not match what --env asked for.",
            "F1 (the rule)": RULE,
        },
        "expect": {}, "expect_counts": {},
        "expect_note": "EMPTY ON PURPOSE: a soak writes no captures.",
    }
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    path = P + "profileddefault1008-" + t["key"] + "-ab.json"
    with open(path, "w") as f:
        f.write(s)
    print(path, REF[:10])
