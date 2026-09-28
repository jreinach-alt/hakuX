import os
# Run from the worktree root. RUNS holds COPIES of dispatch/results/<id>
# (title_verdict.py writes verdict.json into the dir it judges).
RUNS = os.environ.get('ENERGYMAP_RUNS', 'scratch/runs')
OUT = os.environ.get('ENERGYMAP_OUT', 'scratch')
import json
ex = json.load(open(OUT + '/extract.json'))
runs = {'AUF 40fab': '1-1790582078-idlehalt-2124125', 'AUF sysmem': '1-1790575472-rendermode474-965811',
        'Blinx N': '1-1790582080-idlehalt-2124441', 'Blinx T': '1-1790569182-idlehalt-3065294',
        'Crimson': '1-1790620928-lane.dirtytlb-1386630', 'DOA sysmem': '1-1790575472-rendermode474-966037',
        'Forza preleak': '1-1790561602-forza414-3260817', 'Forza leak': '1-1790619761-forza414-1092523',
        'Kabuki': '1-1790618696-lane.idlehaltdefault-845673', 'Otogi': '1-1790609660-lane.slowtier2-otogi762702'}
keys = ['ph_Surf', 'ph_Tex', 'ph_TxH', 'ph_Shd', 'ph_Draw', 'ph_Vtx', 'ph_Syn', 'ph_Prw', 'ph_Pipe', 'ph_Tx', 'ph_Sh',
        'ph_Lu', 'ph_Desc', 'ph_Setup', 'ph_Cmd', 'ph_Sfp', 'ph_Mfp', 'ph_FTx', 'ph_Fin', 'ph_Sub', 'ph_Fen', 'ph_Flip',
        'ph_Idle', 'ph_Fr', 'ph_St', 'ph_Tot', 's413_part', 's413_upl', 's413_fin', 'txw_bt', 'txw_scan', 'txw_up',
        'txw_faf', 'cpu_push']
print('%-14s' % '' + ' '.join('%6s' % k.split('_', 1)[1][:6] for k in keys))
for n, r in runs.items():
    m = ex[r]
    print('%-14s' % n + ' '.join('%6s' % (m[k][0] if k in m else '-') for k in keys))
