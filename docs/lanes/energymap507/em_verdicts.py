import os
# Run from the worktree root. RUNS holds COPIES of dispatch/results/<id>
# (title_verdict.py writes verdict.json into the dir it judges).
RUNS = os.environ.get('ENERGYMAP_RUNS', 'scratch/runs')
OUT = os.environ.get('ENERGYMAP_OUT', 'scratch')
import os, subprocess, json
D = RUNS
out = open(OUT + '/verdicts.log', 'w')
for d in sorted(os.listdir(D)):
    r = subprocess.run(['python3', 'docs/testing/title_verdict.py', os.path.join(D, d)],
                       capture_output=True, text=True)
    last = (r.stdout + r.stderr).strip().splitlines()[-1:]
    out.write('== %s %s\n' % (d, last[0] if last else ''))
out.close()
