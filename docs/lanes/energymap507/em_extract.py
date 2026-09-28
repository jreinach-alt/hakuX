"""Per-run medians of the periodic perflog lines, gameplay window only
(from `mark gameplay` to `soak end`; whole run if no mark)."""
import os
# Run from the worktree root. RUNS holds COPIES of dispatch/results/<id>
# (title_verdict.py writes verdict.json into the dir it judges).
RUNS = os.environ.get('ENERGYMAP_RUNS', 'scratch/runs')
OUT = os.environ.get('ENERGYMAP_OUT', 'scratch')
import os, re, sys, json, statistics as st

KV = re.compile(r'([A-Za-z_][\w]*)[=:]\s*(-?[\d.]+)')

def parse_phase(msg):
    # Surf:0.0 Tex:0.1 ... Idle:31.4(Fr:10.6 St:20.9) | Tot:32.5 GPU:0.3(R:0.2 X:0.2 RP:2 ...) ms
    out = {}
    left, _, right = msg.partition('|')
    for k, v in re.findall(r'(\w+):(-?[\d.]+)', left):
        out['ph_' + k] = float(v)
    m = re.search(r'Tot:([\d.]+)', right)
    if m: out['ph_Tot'] = float(m.group(1))
    m = re.search(r'GPU:([\d.]+)\(R:([\d.]+) X:([\d.]+)', right)
    if m:
        out['ph_GPU'] = float(m.group(1)); out['ph_GPU_R'] = float(m.group(2)); out['ph_GPU_X'] = float(m.group(3))
    return out

def run(d):
    lc = os.path.join(d, 'logcat.txt')
    series = {}
    ingame = False
    txt = open(lc, errors='replace').read()
    start_lab = ('mark gameplay' if re.search(r'mark gameplay\s*$', txt, re.M)
                 else 'mark play' if re.search(r'mark play\s*$', txt, re.M) else None)
    ingame = start_lab is None
    for l in open(lc, errors='replace'):
        m = re.match(r'(\S+ \S+) ([VDIWEF])/([^(]+)\(\s*\d+\): (.*)', l)
        if not m: continue
        tag, msg = m.group(3).strip(), m.group(4)
        if tag == 'hakuX-route':
            if start_lab and msg.strip() == start_lab: ingame = True
            if 'soak end' in msg: ingame = False
            continue
        if not ingame: continue
        rec = None; pre = None
        if tag == 'hakuX-phase' and msg.startswith('Surf:'):
            rec = parse_phase(msg); pre = ''
        elif tag == 'xemu-gpu' and msg.startswith('GPU:'):
            pre = 'gpu_'; rec = {pre + k: float(v) for k, v in re.findall(r'(\w+):([\d.]+)', msg)}
        elif tag == 'hakuX' and msg.startswith('[tlb68]'):
            pre = 'tlb_'; rec = {pre + k: float(v) for k, v in KV.findall(msg)}
        elif tag == 'hakuX' and msg.startswith('[idlehalt]'):
            pre = 'ih_'; rec = {pre + k: float(v) for k, v in KV.findall(msg)}
        elif tag == 'hakuX' and msg.startswith('[rr425w]'):
            pre = 'rrw_'; rec = {pre + k: float(v) for k, v in KV.findall(msg.split(' 3')[0])}
        elif tag == 'hakuX-perf' and msg.startswith('[rdc]'):
            pre = 'rdc_'; rec = {pre + k: float(v) for k, v in KV.findall(msg)}
        elif tag == 'hakuX-perf' and msg.startswith('gfps='):
            rec = {'gfps': float(msg.split()[0].split('=')[1])}
            m2 = re.search(r'G:([\d.]+)', msg)
            if m2: rec['G_ms'] = float(m2.group(1))
        elif tag == 'hakuX-cpu' and msg.startswith('CPU:'):
            m2 = re.search(r'Push:([\d.]+)ms \[Pull:([\d.]+)', msg)
            if m2: rec = {'cpu_push': float(m2.group(1)), 'cpu_pull': float(m2.group(2))}
        elif tag == 'hakuX-stall' and msg.startswith('txw['):
            rec = {}
            for k, v in re.findall(r' ([a-z]+)([\d.]+)/', msg):
                rec['txw_' + k] = float(v)
        elif tag == 'hakuX' and msg.startswith('[surf413]'):
            rec = {}
            for k, v in re.findall(r'(\w+)=([\d.]+)', msg.split('|')[1] if '|' in msg else ''):
                rec['s413_' + k] = float(v)
        elif tag == 'hakuX-perf' and msg.startswith('cblat'):
            m2 = re.search(r'split\(([^)]*)\)', msg)
            rec = {}
            if m2:
                for k, v in re.findall(r'(\w+)=([\d.]+)', m2.group(1)): rec['cb_' + k] = float(v)
            m3 = re.search(r'win=(\d+)ms flips=(\d+)', msg)
            if m3: rec['cb_win'] = float(m3.group(1)); rec['cb_flips'] = float(m3.group(2))
        elif tag == 'hakuX-lane' and msg.startswith('[pace526] mode='):
            rec = {'p526_' + k: float(v) for k, v in KV.findall(msg)}
        elif tag == 'hakuX-pace' and msg.startswith('f='):
            m2 = re.search(r' ms=([\d.]+)', msg)
            if m2: rec = {'pace_ms60': float(m2.group(1))}
        elif tag == 'hakuX-perf' and msg.startswith('[shd413]'):
            rec = {'shd_' + k: float(v) for k, v in KV.findall(msg)}
        if rec:
            for k, v in rec.items(): series.setdefault(k, []).append(v)
    return {k: (round(st.median(v), 3), len(v), round(sum(v), 1)) for k, v in series.items()}

if __name__ == '__main__':
    out = {}
    for d in sys.argv[1:]:
        out[os.path.basename(d.rstrip('/'))] = run(d)
    json.dump(out, open(OUT + '/extract.json', 'w'), indent=0)
    for r, m in out.items():
        print(r, len(m))
