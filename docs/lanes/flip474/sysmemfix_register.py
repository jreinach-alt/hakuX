#!/usr/bin/env python3
"""Write the predictions for the sysmem default (instance.c).

    python3 docs/lanes/flip474/sysmemfix_register.py <a_ref> <b_ref>

- flip474-sysmemfix-pgraph.json: A = master, B = the default, the same 27
  suites as flip474-sysmem-pgraph.json. The arms job queues it.
- flip474-sysmemfix-doa.json: DOA on the Nova, B only, no env: the default
  reaches the driver without the env_vars pref.
"""
import json
import subprocess
import sys

A = subprocess.check_output(['git', 'rev-parse', sys.argv[1]]).decode().strip()
B = subprocess.check_output(['git', 'rev-parse', sys.argv[2]]).decode().strip()
NOW = subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ']).decode().strip()
P = 'docs/testing/predictions/'

env = json.load(open(P + 'flip474-sysmem-pgraph.json'))
cmd = ['python3', 'docs/testing/ab_compare.py', '--register',
       P + 'flip474-sysmemfix-pgraph.json', '--who', 'lane.flip474',
       '--issue', '474', '--a-ref', A, '--b-ref', B,
       '--disc-suites', ','.join(env['disc']['suites']),
       '--disc-skip-tests', 'Texture_render_target::RenderTextureLoop',
       '--prediction',
       '#474: b_ref sets TU_DEBUG=sysmem before the first vkCreateInstance '
       'on Android when TU_DEBUG is unset (instance.c '
       'default_turnip_render_mode). On the bundled Turnip that renders '
       'every pass in system memory; the flag is read only by the render-'
       'mode choice. This pair is the shipped form of '
       'flip474-sysmem-pgraph.json (the same flag through the env_vars '
       'pref). Every capture is byte-identical in A and B, if and only if '
       'that pair is.']
for g in env['must_not_move']:
    cmd += ['--must-not-move', g]
subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

d = {
    "registered_utc": NOW, "who": "lane.flip474", "issue": "474",
    "title": "54430006-Dead_or_Alive_1_Ultimate.xiso.iso", "device": "nova",
    "seconds": 300, "route": "survey", "perflog": True, "frames_every": 0,
    "runs_per_arm": 1, "a_ref": A, "b_ref": B,
    "arms": "B only, no env. Compared with NOTES.md section 16's arms on "
            "795ea6b3af: sysmem by env (X/R 0.02) and gmem (X/R 1.02).",
    "judge": "grep 'init: TU_DEBUG' and 'env: TU_DEBUG' in the logcat; "
             "python3 docs/lanes/flip474/phaseread.py --from 151 --to 288 "
             "<B>; lockread.py and gfpsseries.py on the same window; "
             "crashcheck.py, tailcheck.py; the shots, by eye",
    "must_not_move": ["pgraph: " + P + "flip474-sysmemfix-pgraph.json"],
    "prediction": "#474: the default reaches the driver with no env_vars "
                  "pref. DOA's heavy pass then runs its draw stream once.",
    "legs": {
        "M0 (instrument)": ">= 15 hakuX-phase lines with GPU > 0 in "
        "151-288 s, and the shots show the fight. Otherwise VOID, rerun once.",
        "D0 (the line)": "exactly one 'init: TU_DEBUG=sysmem (default' line, "
        "and no 'env: TU_DEBUG' line. KILL: none, or a line saying the "
        "value came from the environment.",
        "D1 (the mode)": "X/R median <= 0.25 (GMEM reads 0.98 to 1.02 on "
        "DOA). Confidence 90%. KILL of 'the default reaches the driver': "
        "X/R >= 0.8.",
        "F1 (the frame)": "gfps median >= 18 in the fight (sysmem by env "
        "read 21, the GMEM arms 14 to 16). Confidence 70%; the opponent is "
        "drawn per run.",
        "H0 (no hang)": "longest gap between hakuX-perf lines <= 3 s, lines "
        "to the end, no crash marker.",
    },
    "expect": {}, "expect_counts": {},
    "expect_note": "EMPTY ON PURPOSE: a soak writes no captures.",
}
s = json.dumps(d, indent=2) + "\n"
json.loads(s)
with open(P + 'flip474-sysmemfix-doa.json', 'w') as f:
    f.write(s)
print('flip474-sysmemfix-*.json', A[:10], B[:10])
