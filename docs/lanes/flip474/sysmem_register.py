#!/usr/bin/env python3
"""Write the predictions for Turnip's sysmem render mode (sysmem.md).

    python3 docs/lanes/flip474/sysmem_register.py <ref>

One binary; the env TU_DEBUG=sysmem is the variable, so a_ref and b_ref
are the same sha and every arm is queued by hand (the arms job skips a pair
with a_ref == b_ref). Five files:

- flip474-sysmem-pgraph.json: the pgraph suites, default against sysmem,
  on the Nova. Written by ab_compare.py --register.
- flip474-sysmem-{auf,blinx,forza}.json: soaks on the Nova.
- flip474-sysmem-crimson.json: the capped control, on the Thor.

The soak files are serialised and parsed back before they are written.
"""
import json
import subprocess
import sys

REF = subprocess.check_output(['git', 'rev-parse', sys.argv[1]]).decode().strip()
NOW = subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ']).decode().strip()
P = 'docs/testing/predictions/'

# The twelve suites every flip474 inertness arm has used, and fifteen more
# whose output a render-mode change could reach: clears, MSAA resolves,
# surface formats and pitches, render-to-texture, blits, stencil, window
# clipping and occlusion counts (GMEM and sysmem count samples in different
# passes).
SUITES = [
    '3D_primitive', 'Attrib_float', 'Blend_tests', 'Depth_buffer', 'Fog_gen',
    'Lighting_spotlight', 'Specular', 'Surface_clip', 'Texture_CPU_Update',
    'Texture_DXT', 'Texture_format', 'Vertex_shader_rounding_tests',
    'Antialiasing_tests', 'Blend_surface', 'Clear', 'Color_mask_blend',
    'Color_zeta_overlap', 'Image_blit', 'Stencil', 'Stencil_func',
    'Surface_format', 'Surface_pitch', 'Texture_Framebuffer_Blit',
    'Texture_render_target', 'Texture_render_update_in_place', 'Window_clip',
    'ZPass_pixel_count',
]
# It leaves the texture stage disabled and blanks the tests after it.
SKIP = 'Texture render target::RenderTextureLoop'

cmd = ['python3', 'docs/testing/ab_compare.py', '--register',
       P + 'flip474-sysmem-pgraph.json', '--who', 'lane.flip474',
       '--issue', '474', '--a-ref', REF, '--b-ref', REF,
       '--disc-suites', ','.join(SUITES), '--disc-skip-tests', SKIP,
       '--prediction',
       '#474, Addendum 7 step 1: Turnip renders every pass in system memory '
       'under TU_DEBUG=sysmem instead of choosing GMEM tiling per pass. A = '
       'no env, B = TU_DEBUG=sysmem, one binary, both on the Nova. The flag '
       'is read in one place, use_sysmem_rendering() (tu_cmd_buffer.cc), '
       'and only picks the render mode. The guess: every capture is '
       'byte-identical, because both modes run the same shaders with the '
       'same fixed-function state into attachments of the same format. '
       'Where it could fail: MSAA resolves (a GMEM resolve and a sysmem '
       'resolve are different paths), loadOp/storeOp DONT_CARE contents, '
       'and occlusion counts. Confidence 75% that all are identical; a '
       'capture that moves is named and read before any change ships.']
for s in SUITES:
    cmd += ['--must-not-move', s + '/*']
subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

NOTE = ("EMPTY ON PURPOSE: a soak writes no captures. The legs are read off "
        "hakuX-phase, hakuX-perf and the app's 'env:' lines.")
COMMON = {
    "M0 (instrument)": ">= 15 hakuX-phase lines with GPU > 0 in the window "
    "in each arm, and the shots show play. Otherwise VOID for that arm, "
    "rerun once.",
    "E0 (the env reached the app)": "the sysmem arm's logcat has 'env: "
    "TU_DEBUG=sysmem' and the base has no TU_DEBUG line. Otherwise VOID.",
    "T0 (steady)": "the smallest gfps line in the window is >= 0.6 x the "
    "median, unless the shots show a scene change there. Otherwise VOID for "
    "that arm (thermal pause, section 15 of NOTES.md).",
    "H0 (no hang)": "each arm: longest gap between hakuX-perf lines in the "
    "window <= 3 s, lines to the end, no crash marker.",
}
JUDGE = ("python3 docs/lanes/flip474/phaseread.py --from F --to T <base> "
         "<sysmem>; lockread.py and gfpsseries.py on each over the same "
         "window; grep 'env: TU_DEBUG' in each logcat; crashcheck.py and "
         "tailcheck.py on each; the shots in the window, by eye")


def soak(key, title, device, seconds, route, window, prediction, legs):
    d = {
        "registered_utc": NOW, "who": "lane.flip474", "issue": "474",
        "title": title, "device": device, "seconds": seconds, "route": route,
        "perflog": True, "frames_every": 0, "runs_per_arm": 1,
        "a_ref": REF, "b_ref": REF, "window_s": window,
        "arms": {"base": "no env", "sysmem": "--env TU_DEBUG=sysmem"},
        "queue_order": "base, then sysmem; each request.sh --title, "
                       "--device %s, --route %s, --seconds %d, --perflog, "
                       "--expect this file" % (device, route, seconds),
        "judge": JUDGE.replace('F', str(window[0]), 1)
                      .replace('T', str(window[1]), 1),
        "units": "GPU, R and X as printed use limits.timestampPeriod; every "
                 "leg is a ratio of two arms of one binary, or a CPU-clock "
                 "time, so the period cancels.",
        "must_not_move": ["pgraph: " + P + "flip474-sysmem-pgraph.json"],
        "prediction": prediction,
        "legs": dict(COMMON, **legs),
        "expect": {}, "expect_counts": {}, "expect_note": NOTE,
    }
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    with open(P + 'flip474-sysmem-%s.json' % key, 'w') as f:
        f.write(s)


BASIS = ("DOA's fight on the Nova (NOTES.md section 16): GMEM executes the "
         "draw stream of its one heavy pass twice (X/R 0.99) and sysmem once "
         "(X/R 0.02); GPU 34.4 -> 19.6 printed, Tot 64 -> 41 ms, gfps 14 -> "
         "21. X/R from runs on disk: AUF 1.01, Blinx 0.13, Forza 0.25. ")

soak('auf', '4541000D-007_Agent_Under_Fire.xiso.iso', 'nova', 420, 'survey',
     [299, 420],
     BASIS + "AUF reads like DOA, so the guess is the same: its GPU time "
     "falls by about the replay, and the frame follows if it is GPU-bound.",
     {"S1 (replays go)": "sysmem's X/R median <= 0.25. Confidence 85%.",
      "S2 (GPU falls)": "sysmem's phase GPU median <= 0.75 x the base's. "
      "Confidence 70%. KILL of 'AUF is rendered twice': >= 0.95 x.",
      "F1 (frame)": "sysmem's gfps median >= the base's + 2. Confidence 55%; "
      "if S2 holds and F1 fails, AUF's frame is not GPU-bound.",
      "L1 (no loss)": "sysmem's gfps median >= the base's - 1. Confidence "
      "90%."})

soak('blinx', '4D530013-Blinx_The_Time_Sweeper.xiso.iso', 'nova', 420,
     'survey', [255, 411],
     BASIS + "Blinx's X is small (X/R 0.13), so a replay is not most of its "
     "GPU time: its passes have many tiles and binning, or its X is loads "
     "and stores. Sysmem saves at most X and may cost fill bandwidth. The "
     "guess: GPU and gfps about equal. This is the title that can show "
     "sysmem losing.",
     {"S2 (GPU about equal)": "sysmem's phase GPU median is 0.80 to 1.15 x "
      "the base's. Confidence 65%.",
      "L1 (no loss)": "sysmem's gfps median >= the base's - 1. Confidence "
      "75%. KILL of a global sysmem policy: gfps median falls by 2 or more "
      "in a like scene, or GPU >= 1.25 x the base's."})

soak('forza', '4D53006E-Forza_Motorsport.xiso.iso', 'nova', 420, 'survey',
     [125, 240],
     BASIS + "Forza's X/R is 0.25: a quarter of a replay, so a small gain "
     "at most from the render mode, and its frame is set by the deferred "
     "surface downloads (#414). The guess: GPU falls a little, gfps about "
     "equal.",
     {"S2 (GPU)": "sysmem's phase GPU median is 0.70 to 1.10 x the base's. "
      "Confidence 65%.",
      "L1 (no loss)": "sysmem's gfps median >= the base's - 1. Confidence "
      "80%. KILL of a global sysmem policy: gfps median falls by 2 or more "
      "in a like scene, or GPU >= 1.25 x the base's."})

soak('crimson', 'Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)'
     '.xiso.iso', 'thor', 240, 'crimson-skies', [120, 240],
     BASIS + "Crimson paces itself to 30 and reads X/R 0.09 on the Thor "
     "(tsperiod.md). lane.turnipfork found the three modes flat at 29 gfps. "
     "The capped control: it cannot show a gain, only a cost, and it is the "
     "Thor leg (same bundled Turnip).",
     {"C1 (capped, no loss)": "sysmem's gfps median is within 1 of the "
      "base's. Confidence 85%.",
      "C2 (GPU not dearer)": "sysmem's phase GPU median <= 1.25 x the "
      "base's. Confidence 75%. KILL of a global sysmem policy: C1 fails "
      "downward with the shots in like scenes."})

print('flip474-sysmem-*.json', REF[:10])
