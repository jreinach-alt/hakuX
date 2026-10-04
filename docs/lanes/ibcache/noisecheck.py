#!/usr/bin/env python3
"""Is a moved capture an image that builds WITHOUT the change also draw?

For each capture that differs byte for byte between the two arms, hash the
A and the B image and look for the same bytes in every other pgraph result
dir. A B image that an unrelated build drew is not the change's drawing.

A result dir holds captures<N>/<Suite>::<Test>.png, one flat dir per run.

usage: noisecheck.py RESULTS_DIR A_ID B_ID [--exclude-ref REF ...]
"""
import sys, os, json, hashlib, collections


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def runs(d):
    return [r for r in sorted(os.listdir(d))
            if r.startswith('captures') and os.path.isdir(os.path.join(d, r))]


def captures(d):
    """(run, file name) -> path, for one result dir."""
    out = {}
    for run in runs(d):
        rp = os.path.join(d, run)
        for f in os.listdir(rp):
            if f.endswith('.png'):
                out[(run, f)] = os.path.join(rp, f)
    return out


def meta(d):
    try:
        return json.load(open(os.path.join(d, 'result.json')))
    except Exception:
        return None


def main():
    res, a_id, b_id = sys.argv[1:4]
    exclude = set()
    args = sys.argv[4:]
    while args:
        if args[0] == '--exclude-ref':
            exclude.add(args[1])
            args = args[2:]
        else:
            sys.exit('unknown arg ' + args[0])
    A = captures(os.path.join(res, a_id))
    B = captures(os.path.join(res, b_id))
    moved = [k for k in sorted(A) if k in B and sha(A[k]) != sha(B[k])]
    print('A %s  B %s' % (a_id, b_id))
    print('shared captures %d, differing byte for byte %d'
          % (len(set(A) & set(B)), len(moved)))
    # file name -> hash -> 'A' or 'B'
    want = collections.defaultdict(dict)
    for k in moved:
        want[k[1]][sha(A[k])] = 'A'
        want[k[1]][sha(B[k])] = 'B'
    seen = collections.defaultdict(lambda: collections.defaultdict(list))
    other = collections.defaultdict(collections.Counter)
    # file name -> apk -> the hashes its runs drew
    byapk = collections.defaultdict(lambda: collections.defaultdict(list))
    own =set([os.path.realpath(os.path.join(res, a_id)),
               os.path.realpath(os.path.join(res, b_id))])
    ndirs = nruns = 0
    for d in sorted(os.listdir(res)):
        p = os.path.join(res, d)
        if os.path.islink(p) or not os.path.isdir(p):
            continue
        if os.path.realpath(p) in own:
            continue
        m = meta(p)
        if not m or m.get('program') != 'pgraph':
            continue
        if m.get('ref') in exclude:
            continue
        hit = False
        for run in runs(p):
            rhit = False
            for name, hs in want.items():
                fp = os.path.join(p, run, name)
                if not os.path.exists(fp):
                    continue
                rhit = True
                h = sha(fp)
                tag = '%s ref=%s apk=%s dev=%s env=%s %s' % (
                    d, m.get('ref'), m.get('apk_sha'),
                    m.get('device_label'),
                    ','.join(m.get('env') or []) or '-', run)
                byapk[name][m.get('apk_sha')].append(h)
                if h in hs:
                    seen[name][h].append(tag)
                else:
                    other[name][h] += 1
            nruns += rhit
            hit = hit or rhit
        ndirs += hit
    print('other pgraph result dirs holding one of these captures: %d '
          '(%d runs)' % (ndirs, nruns))
    print('excluded refs: %s' % (sorted(exclude) or 'none'))
    for name in sorted(want):
        print()
        print(name)
        for h, arm in sorted(want[name].items(), key=lambda x: x[1]):
            tags = seen[name][h]
            refs = sorted(set(t.split(' ref=')[1].split()[0] for t in tags))
            devs = collections.Counter(
                t.split(' dev=')[1].split()[0] for t in tags)
            print('  %s image %s: drawn by %d other run(s), %d ref(s), %s'
                  % (arm, h, len(tags), len(refs), dict(devs)))
            for t in tags[-3:]:
                print('      ' + t)
        print('  other images of this capture elsewhere: %d distinct, %d runs'
              % (len(other[name]), sum(other[name].values())))
        # One apk drawing two images is the flip with nothing changed.
        multi = [(a, hs) for a, hs in byapk[name].items() if len(hs) > 1]
        flips = [(a, hs) for a, hs in multi if len(set(hs)) > 1]
        both = [a for a, hs in flips
                if set(want[name]) <= set(hs)]
        print('  apks run more than once: %d; drew more than one image: %d; '
              'drew both the A and the B image: %d'
              % (len(multi), len(flips), len(both)))
        for a, hs in flips[:4]:
            c = collections.Counter(hs)
            print('      apk %s: %s' % (a, ', '.join(
                '%s x%d%s' % (h, n, ' (%s)' % want[name][h]
                              if h in want[name] else '')
                for h, n in c.most_common())))


if __name__ == '__main__':
    main()
