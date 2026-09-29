import os
# Run from the worktree root. RUNS holds COPIES of dispatch/results/<id>
# (title_verdict.py writes verdict.json into the dir it judges).
RUNS = os.environ.get('ENERGYMAP_RUNS', 'scratch/runs')
OUT = os.environ.get('ENERGYMAP_OUT', 'scratch')
import json, os, re, sys
ex = json.load(open(OUT + '/extract.json'))
D = RUNS

def key(run):  # strip the dispatcher's copy prefixes
    return re.sub(r'^(0-0-[sx]-|1-9-|1-)', '', run)

seen = {}
rows = []
for run in sorted(ex):
    k = key(run)
    if k in seen: continue
    seen[k] = run
    p = os.path.join(D, run)
    try:
        v = json.load(open(os.path.join(p, 'verdict.json')))
        rq = json.load(open(os.path.join(p, 'request.json')))
    except Exception:
        continue
    m = ex[run]
    pw = v.get('power') or {}
    th = v.get('thermal') or {}
    g = lambda f: m[f][0] if f in m else None
    s = lambda f: m[f][2] if f in m else None
    fl, sc = pw.get('flips'), pw.get('scored_s')
    fps = fl / sc if fl and sc else None
    if not fps and m.get('pace_ms60'):
        fps = 60000.0 / m['pace_ms60'][0]
    fms = 1000.0 / fps if fps else None
    r = dict(run=run, name=(v.get('name') or '')[:22], dev=v.get('device'), reg=th.get('regimen'),
             ref=rq.get('ref'), env=' '.join(e.replace('HAKUX_', '') for e in (rq.get('env') or [])),
             fps=fps, net=pw.get('net_w'), jpf=pw.get('j_per_frame'), pause=bool(th.get('pauses')),
             void=(v.get('void') or '')[:12])
    if fms:
        if s('tlb_cpu') and s('tlb_dt'):
            r['vcpu'] = s('tlb_cpu') / s('tlb_dt') * fms
            r['vcpu_share'] = s('tlb_cpu') / s('tlb_dt')
        if s('ih_run_us') and s('ih_span_us'):
            r['vcpu_rq'] = s('ih_run_us') / s('ih_span_us') * fms
        if s('rdc_tcpu') and s('rdc_f'):
            r['render'] = s('rdc_tcpu') / s('rdc_f')
        if s('p526_proc_cpu_ms') and s('p526_flips'):
            r['proc'] = s('p526_proc_cpu_ms') / s('p526_flips')
            r['disp'] = s('p526_thr_cpu_ms') / s('p526_flips')
        if g('ph_Tot') is not None:
            r['pf_tot'] = g('ph_Tot'); r['pf_idle'] = g('ph_Idle')
            r['pf_busy'] = g('ph_Tot') - g('ph_Idle')
            r['pf_fin'] = g('ph_Fin'); r['pf_tex'] = (g('ph_Tex') or 0); r['pf_txh'] = g('ph_TxH')
            r['pf_surf'] = g('ph_Surf'); r['pf_draw'] = g('ph_Draw'); r['pf_shd'] = g('ph_Shd')
            r['pf_sub'] = g('ph_Sub'); r['pf_fen'] = g('ph_Fen')
            r['gpu'] = g('ph_GPU'); r['gpu_r'] = g('ph_GPU_R'); r['rp'] = g('ph_RP')
        if g('cpu_push') is not None:
            r['push'] = g('cpu_push'); r['pull'] = g('cpu_pull')
    rows.append(r)
json.dump(rows, open(OUT + '/summary.json', 'w'), indent=0)
F = lambda x, n=1: ('%.*f' % (n, x)) if isinstance(x, (int, float)) else '-'
rows.sort(key=lambda r: (r['name'], r['dev'] or '', r['run']))
print('name dev reg fps net jpf | vcpu vcpu% vcpu_rq render disp proc | pfbusy fin(sub/fen) tex txh surf draw shd push pull | gpu gpuR rp | run env')
for r in rows:
    if len(sys.argv) > 1 and not r.get('jpf'): continue
    print('%-22s %-4s %-3s %5s %5s %6s | %5s %4s %5s %5s %4s %5s | %5s %4s(%s/%s) %4s %4s %4s %4s %4s %4s %4s | %5s %5s %3s | %s %s %s' % (
        r['name'], r['dev'], (r['reg'] or '')[:3], F(r['fps']), F(r['net'], 2), F(r['jpf'], 3),
        F(r.get('vcpu')), F(r.get('vcpu_share'), 2), F(r.get('vcpu_rq')), F(r.get('render')), F(r.get('disp')), F(r.get('proc')),
        F(r.get('pf_busy')), F(r.get('pf_fin')), F(r.get('pf_sub')), F(r.get('pf_fen')), F(r.get('pf_tex')), F(r.get('pf_txh')),
        F(r.get('pf_surf')), F(r.get('pf_draw')), F(r.get('pf_shd')), F(r.get('push')), F(r.get('pull')),
        F(r.get('gpu')), F(r.get('gpu_r')), F(r.get('rp'), 0), r['run'], r['env'][:40], 'PAUSE' if r['pause'] else ''))
