#!/usr/bin/env python3
"""Write lane.gmem474's three predictions (#474: Turnip render mode by J/frame).

    python3 docs/lanes/gmem474/gmem474_register.py <measurement ref>

One binary per device, the measurement build (#530's table rows read "auto",
so the request env alone picks the mode). a_ref == b_ref, so the arms job
skips these; this lane queues every run with request.sh (queue.sh here).
Each file is serialised and parsed back before it is written.
"""
import json
import subprocess
import sys

REF = subprocess.check_output(['git', 'rev-parse', sys.argv[1]]).decode().strip()
# Optional keys after the ref write only those files, so a title added later
# (kabuki, 2026-09-28) leaves the already-registered files byte-identical.
ONLY = set(sys.argv[2:])
NOW = subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ']).decode().strip()
P = 'docs/testing/predictions/'
FILES = '/sdcard/Android/data/com.jreinach.hakux.debug/files/'

ARMS = {
    "A": ("autotune (the driver's default algorithm, bandwidth)", ["TU_DEBUG=startup"]),
    "B": ("sysmem (what #530 ships for DOA and AUF)", ["TU_DEBUG=startup,sysmem"]),
    "C": ("gmem + forcebin", ["TU_DEBUG=startup,gmem,forcebin"]),
    "D": ("autotune, profiled algorithm", ["TU_DEBUG=startup", "TU_AUTOTUNE_ALGO=profiled"]),
}
MESA_WORD = {"A": "0x1", "B": "0x9", "C": "0x1011", "D": "0x1"}


def env_of(key, run):
    arm = run[0]
    return (["PERF_REGIMEN=default"] + ARMS[arm][1]
            + ["MESA_LOG_FILE=%sgmem474-%s-%s.log" % (FILES, key, run.lower())])


PROOF = (
    "Fleet driver T30 (vulkan.purple.so sha256 1d80dfa01965..., 'PurpleVK "
    "26.3.0-devel (git-62ac221a33)'), read before registering: its "
    "tu_debug_options table holds startup=0x1, nobin=0x4, sysmem=0x8, "
    "forcebin=0x10, gmem=0x1000; the TU_AUTOTUNE_ALGO parser (call_once "
    "lambda of tu_autotune::get_env_config at 0x9e3ca4) compares an 8-byte "
    "immediate 0x64656c69666f7270 ('profiled') and sets algorithm 1, and "
    "holds 'Unknown TU_AUTOTUNE_ALGO' for anything else. Each run proves "
    "its own mode at run time: TU_DEBUG=startup makes the driver log the "
    "parsed flag word ('TU_DEBUG=0x..') and, when the variable is set, "
    "'TU_AUTOTUNE_ALGO=N (name)', into MESA_LOG_FILE, which --pull brings "
    "back (the TU log tag is not in the dispatcher's LOGCAT_SPEC).")

COMMON = {
    "V0 (instrument; a run failing it is VOID and re-queued once)":
        "result.json device and apk as queued; perf_regimen.json regimen "
        "'default', perf_mode 0; >= 15 hakuX-phase lines with GPU > 0 in the "
        "window; >= 3 power samples in the window with sign_suspect 0; gfps "
        "lines to the end of the run and no crash marker; the route's shots "
        "in the window show play.",
    "E0 (the mode that ran)":
        "the app's line reads 'render_mode: auto (table|default) title=<TID> "
        "TU_DEBUG=<the arm's TU_DEBUG>' and the pulled Mesa log reads "
        "TU_DEBUG=0x1 (A, D), 0x9 (B), 0x1011 (C); D's log reads "
        "'TU_AUTOTUNE_ALGO=1 (profiled)' with no 'Unknown TU_AUTOTUNE_ALGO', "
        "and A, B, C have no TU_AUTOTUNE_ALGO line. If no log was pulled, B "
        "is shown by X/R <= 0.25 and the other arms are 'mode not shown', "
        "not measurements.",
    "T0 (heat)":
        "no thermal-pause episode overlaps the window (thermal_state."
        "in_window). A paused run is VOID for gfps and J/frame (#507), is "
        "reported with its pause, and is re-queued once.",
    "N0 (noise floor, not a guess)":
        "n = |J/frame(A1) - J/frame(A2)| / their mean, and the same for gfps. "
        "A difference between two arms smaller than max(n, 5 %) in J/frame, "
        "or max(|A1 - A2|, 1) in gfps, is 'not separated'.",
}

DECISION = (
    "Registered before any run. Per title, the shipped mode is B (sysmem) "
    "for DOA and AUF (#530) and A (autotune) for Crimson (not tabled). "
    "Another arm Y replaces it only if (1) neither run is VOID, (2) Y's "
    "gfps_med >= shipped's - 1, and (3) Y's J/frame <= shipped's x (1 - "
    "max(n, 0.05)). Only 'sysmem', 'gmem' and 'auto' are expressible in "
    "#530's table: a win by C (forcebin) or D (profiled) is reported with "
    "its number and not shipped by this lane. No sysmem default for a "
    "title whose sysmem run has qry_lines > 0 in its window (#527's "
    "ZPASS caveat); it is reported. Otherwise keep what ships.")

JUDGE = ("python3 docs/lanes/gmem474/gmemread.py --from F --to T <A1> <B> "
         "<C> <D> <A2>; the route's shots in the window, by eye")


def write(key, title, device, seconds, route, window, basis, legs, order,
          extra=None):
    if ONLY and key not in ONLY:
        return
    runs = {r: dict(arm=ARMS[r[0]][0], env=env_of(key, r),
                    pull="gmem474-%s-%s.log" % (key, r.lower()))
            for r in ("A1", "B", "C", "D", "A2")}
    d = {
        "registered_utc": NOW, "who": "lane.gmem474", "issue": "474",
        "title": title, "device": device, "seconds": seconds, "route": route,
        "perflog": True, "frames_every": 0, "runs_per_arm": "1 (A twice: A1, A2)",
        "a_ref": REF, "b_ref": REF, "window_s": window,
        "runs": runs,
        "queue_order": order + ". Each: request.sh --who lane.gmem474 --title "
                       "<title> --device %s --route %s --seconds %d --perflog "
                       "--ref %s --pull <pull> --env <each env> --expect this "
                       "file, HAKUX_RELEASE_PRIO=1." % (device, route, seconds, REF[:10]),
        "judge": JUDGE.replace('F', str(window[0]), 1).replace('T', str(window[1]), 1),
        "driver_options_proof": PROOF,
        "units": "gfps_med: time-weighted median of 60-flip windows in the window. "
                 "J/frame: net_w (battery + usb) x the windows' seconds / their "
                 "flips. GPU, R, X as printed by hakuX-phase; only ratios inside "
                 "one device are read.",
        "decision_rule": DECISION,
        "must_not_move": [],
        "prediction": basis,
        "legs": dict(COMMON, **legs),
        "expect": {}, "expect_counts": {},
        "expect_note": "EMPTY ON PURPOSE: a soak writes no captures. The legs are "
                       "read by gmemread.py off logcat.txt, thermal.jsonl, "
                       "perf_regimen.json and pulled/, and the shots by eye.",
    }
    d.update(extra or {})
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    with open(P + 'gmem474-%s.json' % key, 'w') as f:
        f.write(s)


BASIS = ("flip474 (sysmem.md), MAX regimen, Nova, older code: AUF 16 -> 24 gfps "
         "and DOA 13 -> 21 under sysmem, X/R 1.0 -> 0.02: in GMEM the heavy "
         "pass has 1-2 tiles and no binning, so its draw stream runs once per "
         "tile. J/frame was never measured. The review (thermal-review.md 3.4) "
         "leaves the sign open: sysmem adds DRAM traffic, GMEM replays the "
         "draws. forcebin (tu_util.cc) splits a 1-tile direction into 2 and "
         "forces a hardware binning pass, so C is a binning pass plus up to 4 "
         "tiles that each run only the draws binned to them. profiled (D) "
         "times both modes per render pass and picks by measured time. ")

SAT = {
    "S1 (sysmem is faster where GMEM replays)":
        "B's gfps_med >= A's (mean of A1, A2) + 4. Confidence 80%. Fails in "
        "the world where #517/#543 already removed what sysmem saved.",
    "P1 (THE POINT: sysmem is cheaper per frame)":
        "B's J/frame <= 0.85 x A's. Confidence 70%. Fails in the world where "
        "sysmem's DRAM traffic costs more energy than the replay it saves: "
        "then #530's default is fast but not efficient, and the decision "
        "rule decides.",
    "P2 (power about equal, the frame rate carries it)":
        "B's net_w within +-15% of A's. Confidence 55%. Fails high in the "
        "world where the frame rate rise brings the CPU up with it; fails "
        "low where the GPU idles more in sysmem.",
    "C1 (forcebin does not remove the replay cost)":
        "C's gpu_ms >= 0.9 x A's. Confidence 55%. Fails in the world where "
        "the heavy pass's cost is per pixel and binning culls it, so the "
        "brief's 'one binning pass' reading was right.",
    "C2 (sysmem beats forcebin on energy)":
        "C's J/frame >= B's. Confidence 70%.",
    "D1 (profiled finds sysmem by itself)":
        "D's x_over_r <= 0.25 and D's gfps_med within 2 of B's. Confidence "
        "45%. Fails in the world where the profiled algorithm keeps GMEM or "
        "alternates for the whole window (its X/R between 0.25 and 0.9).",
}

write('doa', '54430006-Dead_or_Alive_1_Ultimate.xiso.iso', 'nova', 300, 'survey',
      [151, 288],
      BASIS + "DOA's fight (151-288 s from soak start, as flip474 and "
      "rendermode474 read it) is GPU-bound in GMEM, so the guess is that sysmem "
      "is cheaper per frame mostly by making more frames for about the same "
      "watts: J/frame ~ W/fps.", SAT,
      "Nova, interleaved with gmem474-auf.json: DOA A1, AUF A1, DOA B, AUF B, "
      "DOA C, AUF C, DOA D, AUF D, DOA A2, AUF A2 (DOA A1 is the apk's first "
      "run on the Nova, so its shader cache is cleared; the rest keep it)")

write('auf', '4541000D-007_Agent_Under_Fire.xiso.iso', 'nova', 600, 'survey',
      [299, 590],
      BASIS + "AUF's mission play (from 299 s; 600 s so the window holds about "
      "10 power samples) reads like DOA (X/R 1.01), so the guess is the "
      "same.", SAT,
      "Nova, interleaved with gmem474-doa.json (see there)")

write('crimson', 'Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)'
      '.xiso.iso', 'thor', 360, 'crimson-skies', [120, 350],
      BASIS + "Crimson is the title that is NOT GPU-saturated: it paces "
      "itself to 30 (29-30 gfps) with GPU ~5-7 ms of a 33 ms frame, X/R ~0.1 "
      "(flip474 on the Thor; lane.turnipfork found autotune, sysmem and gmem "
      "flat at 29). Forza, the brief's other candidate, decays from the "
      "invalid-surface list since #517 (#579), so its fps is not a steady "
      "state. At equal fps J/frame is W/fps, so every leg here is watts. "
      "The guess: the render mode moves less than 5% of the frame's energy, "
      "and sysmem is, if anything, the dearer.",
      {"K1 (capped: fps does not move)":
       "every arm's gfps_med within 1 of A's. Confidence 80%. Fails in the "
       "world flip474 half-saw (sysmem 2 lower where not capped).",
       "K2 (sysmem about the same energy)":
       "B's J/frame within +-5% of A's; direction guess B >= A. Confidence "
       "55%. Fails high in the world where sysmem's DRAM traffic is a real "
       "energy cost on an unsaturated title: then the table must not grow "
       "to titles that are not replay-bound.",
       "K3 (forcebin costs a binning pass)":
       "C's J/frame >= A's. Confidence 55%.",
       "K4 (profiled is autotune here)":
       "D's J/frame within +-5% of A's. Confidence 60%."},
      "Thor. PILOT first: C then D (the two options whose run-time proof is "
      "unshown; C is the apk's first run on the Thor, so its shader cache is "
      "cleared). After the pilot is read: A1, B, A2")

KABUKI_DECISION = (
    "Registered before any run. Kabuki is not in #530's table, so the "
    "shipped mode is A (autotune). The FIGHT window (W1) decides: B "
    "replaces A only if (1) no run is VOID, (2) B's W1 gfps_med >= A's - "
    "max(|A1 - A2|, 1), and (3) B's W1 J/frame <= A's x (1 - max(n, 0.05)), "
    "with n from A1/A2 in W1. The menu window (W2, capped 59) is reported "
    "beside it and never ships a default by itself: its render passes are "
    "not the fight's. A C or D win is reported, not shipped. No sysmem "
    "default if B's W1 has qry_lines > 0 (#527). Otherwise keep what ships.")

write('kabuki', '43560001-Kabuki_Warriors.xiso.iso', 'nova', 420,
      'kabuki-warriors', [230, 415],
      BASIS + "Added 2026-09-28 on lane.energymap507's finding (#507, PR "
      "#586): Kabuki is the one untabled title with the GMEM signature, "
      "X/R 0.77 over its whole soak (1-1790618696-lane.idlehaltdefault-"
      "845673, Nova MAX, 3a5d79e3ea), priced there at -5 to -8% J/frame for "
      "sysmem. Read with gmemread.py before registering, that soak is two "
      "different regimes. Menus (30-180 s) hold gfps=59 on every line. The "
      "fight (mark gameplay at 227 s; 230-415 s) is 1-s windows at 59 "
      "separated by stalls of 20-60 s with no perf line (lane.energymap507's "
      "#5 'stall burn', 1.8-2.25 cores busy, dpm=0): time-weighted gfps_med "
      "2.78, GPU 10.75 ms, X/R 0.93, J/frame 0.326 (5 samples). So the fight "
      "is NOT a 60-capped steady state; its J/frame is set by how long the "
      "stalls last, which the random CPU opponent varies run to run. The "
      "guess: the render mode moves the menu window's watts a little and "
      "cannot be separated from stall noise in the fight, unless the stall "
      "is itself GPU work that sysmem shortens.",
      {"KW1 (fight: the stall noise swamps the mode)":
       "every arm's W1 J/frame within max(n, 5%) of A's (mean of A1, A2), "
       "i.e. 'not separated'. Confidence 60%. Fails in the world where the "
       "stall is GPU-side work that a mode shortens or lengthens: then that "
       "arm's W1 gfps_med differs from A's by >= 1.5x.",
       "KW2 (menus are capped: fps does not move)":
       "in W2 = 30-180 s every arm's gfps_med is 58-60. Confidence 85%. "
       "Fails in the world where a mode makes the menus GPU-bound.",
       "KW3 (energymap507's price, at equal fps)":
       "B's W2 net_w <= 0.95 x A's. Confidence 45%. Fails in the world "
       "where sysmem's DRAM traffic costs what the replay saved.",
       "KW4 (B really removes the replay)":
       "B's x_over_r <= 0.25 in W1 and W2, A's >= 0.6. Confidence 85%.",
       "KW5 (forcebin costs a binning pass)":
       "C's W2 net_w >= A's. Confidence 55%.",
       "KW6 (profiled finds sysmem by itself)":
       "D's W2 x_over_r <= 0.25. Confidence 40%."},
      "Nova, after the DOA/AUF interleave (gmem474-doa.json): Kabuki A1, B, "
      "C, D, A2. Not the apk's first Nova run, so the shader cache is kept",
      extra={
          "window2_s": [30, 180],
          "judge": "python3 docs/lanes/gmem474/gmemread.py --from 230 --to 415 "
                   "<A1> <B> <C> <D> <A2> (W1, decides) and --from 30 --to "
                   "180 (W2, reported); the route's shots, by eye",
          "decision_rule": KABUKI_DECISION,
      })

print('gmem474 predictions written for', sorted(ONLY) or 'all', REF[:10])
