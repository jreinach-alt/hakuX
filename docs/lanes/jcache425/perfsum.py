import re, sys, statistics as st
# Per soak: hakuX-perf gfps and G (game ms) medians/p90 over 90-240 s from the
# first hakuX-perf line; [tlb68] cpu and jcus over the same span.
# Also the [jc425] line (this lane's counters) when present.


def ts(l):
    m = re.match(r'\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d+)', l)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))] if v else float('nan')


def kv(lines, k):
    out = []
    for l in lines:
        m = re.search(r'\b%s=(\d+)' % k, l)
        if m:
            out.append(int(m.group(1)))
    return out


for p in sys.argv[1:]:
    L = open(p, errors='replace').read().splitlines()
    perf = [l for l in L if 'hakuX-perf' in l and 'gfps=' in l]
    if not perf:
        print(p, 'NO hakuX-perf')
        continue
    t0 = ts(perf[0])
    lo, hi = t0 + 90, t0 + 240

    def win(l):
        t = ts(l)
        return t is not None and lo <= t <= hi
    g = [int(re.search(r'gfps=(\d+)', l).group(1)) for l in perf if win(l)]
    G = [float(re.search(r' G:([\d.]+)', l).group(1)) for l in perf if win(l) and re.search(r' G:([\d.]+)', l)]
    t = [l for l in L if '[tlb68]' in l and win(l)]
    cpu, dt, jcus, jci, jcx = (kv(t, k) for k in ('cpu', 'dt', 'jcus', 'jci', 'jcx'))
    tl = [ts(l) for l in L if ts(l) is not None]
    fx = re.search(r'fx=(\S+)', t[-1]).group(1) if t else '-'
    name = p.split('/')[-2][-40:]
    print('%-40s fx=%s n=%d gfps med %s p10 %s | G med %.1f p90 %.1f | cpu/dt %.3f | jcus/cpu %.2f%% | jci/s %.0f jcx/s %.0f | span %.0fs' % (
        name, fx, len(g), st.median(g) if g else '-', q(g, .1),
        st.median(G) if G else -1, q(G, .9),
        sum(cpu) / max(1, sum(dt)), 100 * sum(jcus) / 1000 / max(1, sum(cpu)),
        1000 * sum(jci) / max(1, sum(dt)), 1000 * sum(jcx) / max(1, sum(dt)),
        (tl[-1] - t0) if tl else -1))
    j = [l for l in L if '[jc425]' in l and win(l)]
    if j:
        keys = re.findall(r'\b([a-z]+)=\d+', j[0])
        tot = {k: sum(kv(j, k)) for k in keys}
        print('    [jc425] n=%d ' % len(j) + ' '.join('%s=%d' % (k, v) for k, v in tot.items()))
