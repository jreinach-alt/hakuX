"""Inferred J/frame split for one representative run per title.

MODEL (inferred, every coefficient labelled):
  idle      P_idle / fps. P_idle = median `cool` thermal.jsonl sample (screen on,
            before launch): Thor 1.97 W (92 samples), Nova 3.40 W (76).
  vCPU      share x k_v / fps. k_v = dW / d(vCPU on-CPU share) from same-build
            idle-halt pairs: Nova MAX 3.5-5.3 (4 pairs), Nova defaults 3.7
            (1 pair), Thor defaults 0.8 (1 pair, inside run noise).
            Thor MAX has no same-build pair; the Thor range used is 0.8-3.5.
  otherCPU  (process CPU - vCPU) per frame x k_o, k_o = 1.0-1.5 W per busy
            core (mid cores near max clock; public SoC figures, not measured
            here). Where process CPU is not logged, PFIFO busy wall time is used
            and the term is a LOWER bound (render/audio/compile unseen).
  GPU       GPU span per frame x k_g, k_g = 3-5 W while busy (public Adreno 740
            figures, not measured here). The span counts gaps inside command
            buffers, so this over-reads.
"""
import os
# Run from the worktree root. RUNS holds COPIES of dispatch/results/<id>
# (title_verdict.py writes verdict.json into the dir it judges).
RUNS = os.environ.get('ENERGYMAP_RUNS', 'scratch/runs')
OUT = os.environ.get('ENERGYMAP_OUT', 'scratch')
import json
S = {r['run']: r for r in json.load(open(OUT + '/summary.json'))}
EX = json.load(open(OUT + '/extract.json'))
REP = [
    ('AUF', '1-1790582079-idlehalt-2124199', 'nova', 'max'),
    ('AUF (defaults)', '1-1790593206-lane.sustain507-3238659', 'nova', 'def'),
    ('Blinx', '1-1790582080-idlehalt-2124441', 'nova', 'max'),
    ('Blinx (Thor defaults)', '1-1790593205-lane.sustain507-3238578', 'thor', 'def'),
    ('Crimson', '1-1790620928-lane.dirtytlb-1387249', 'thor', 'max'),
    ('DOA1U (sysmem)', '1-1790575472-rendermode474-966037', 'nova', 'max'),
    ('Kabuki', '1-1790618696-lane.idlehaltdefault-845673', 'nova', 'max'),
    ('Otogi', '1-1790609660-lane.slowtier2-otogi762702', 'thor', 'max'),
    ('Forza (pre-leak)', '1-1790561602-forza414-3260817', 'thor', 'max'),
    ('Forza (leak)', '1-1790619761-forza414-1092523', 'thor', 'max'),
    ('GTA SA (defaults)', '0-0-x-1790565677-lane.sustain507-1257857', 'thor', 'def'),
    ('Nightfire', '1-1790563604-titleroutes-373432', 'thor', 'max'),
    ('Azurik', '1-1790560999-titleroutes-2862460', 'thor', 'max'),
    ('D&D Heroes', '1-1790560999-titleroutes-2862610', 'thor', 'max'),
    ('Alien Hominid', '1-1790572033-lane.pacing-1078761', 'thor', 'max'),
    ('MA2 (defaults, paused)', '1-1790572031-lane.sustain507-4131051', 'thor', 'def'),
]
PIDLE = {'thor': 1.97, 'nova': 3.40}
KV = {('nova', 'max'): (3.5, 5.3), ('nova', 'def'): (3.5, 3.9), ('thor', 'max'): (0.8, 3.5), ('thor', 'def'): (0.8, 3.5)}
out = []
for name, run, dev, reg in REP:
    r = S[run]; m = EX[run]
    fps = r['fps']; fms = 1000 / fps; j = r['jpf']
    gi = None
    if 'rrw_idle_us' in m:
        gi = m['rrw_idle_us'][2] / (m['rrw_idle_us'][2] + m['rrw_busy_us'][2])
    idle = PIDLE[dev] / fps
    kv = KV[(dev, reg)]
    v = [r['vcpu_share'] * k / fps for k in kv]
    if r.get('proc'):
        oth_ms = r['proc'] - r['vcpu']; oth_kind = 'proc'
    elif r.get('pf_busy') is not None:
        oth_ms = r['pf_busy']; oth_kind = 'pfifo>='
    else:
        oth_ms = None; oth_kind = '-'
    o = [oth_ms / fms * k / fps for k in (1.0, 1.5)] if oth_ms is not None else None
    g = [r['gpu'] / 1000 * k for k in (3, 5)] if r.get('gpu') is not None else None
    lo = idle + v[0] + (o[0] if o else 0) + (g[0] if g else 0)
    hi = idle + v[1] + (o[1] if o else 0) + (g[1] if g else 0)
    row = dict(name=name, run=run, dev=dev, reg=reg, ref=r['ref'], fps=fps, net=r['net'], jpf=j,
               vcpu_ms=r['vcpu'], vcpu_share=r['vcpu_share'], guest_idle=gi, render_ms=r.get('render'),
               disp_ms=r.get('disp'), proc_ms=r.get('proc'), pf_busy=r.get('pf_busy'), pf_draw=r.get('pf_draw'),
               pf_surf=r.get('pf_surf'), pf_fin=r.get('pf_fin'), gpu=r.get('gpu'), gpu_r=r.get('gpu_r'),
               j_idle=idle, j_vcpu=v, j_oth=o, oth_kind=oth_kind, j_gpu=g, model=(lo, hi))
    out.append(row)
    f = lambda x: '-' if x is None else ('%.3f' % x)
    fr = lambda p: '-' if not p else '%.3f-%.3f' % (p[0], p[1])
    print('%-24s %s %s fps %.1f J/f %s | idle %s vCPU %s oth(%s) %s GPU %s | model %.3f-%.3f gi=%s' % (
        name, dev, reg, fps, f(j), f(idle), fr(v), oth_kind, fr(o), fr(g), lo, hi, f(gi)))
json.dump(out, open(OUT + '/split.json', 'w'), indent=0)
