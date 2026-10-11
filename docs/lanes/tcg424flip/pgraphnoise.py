"""For each capture that differs byte-for-byte between the tcg424flip pgraph
arms, look for the fix arm's exact bytes in a pgraph run built from a ref that
does not contain the flip (62ef8bf0fe). A match means the fix's image is a
state a no-flip build also produces: device nondeterminism, not the flip."""
import os, json, hashlib, subprocess, collections
R = '/home/justin/hakux-work/dispatch/results/'
BASE = R + '1-1790726318-arms-tcg424flip-base-1704391/captures1/'
FIX = R + '1-1790726318-arms-tcg424flip-fix-1704464/captures1/'
FLIP = '62ef8bf0fe'


def h(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


diff = []
for n in sorted(os.listdir(FIX)):
    if not n.endswith('.png') or not os.path.isfile(BASE + n):
        continue
    if h(BASE + n) != h(FIX + n):
        diff.append(n)
print('differing captures:', len(diff))

anc = {}


def noflip(ref):
    if ref not in anc:
        rc = subprocess.run(['git', 'merge-base', '--is-ancestor', FLIP, ref],
                            capture_output=True).returncode
        anc[ref] = (rc == 1)
    return anc[ref]


seen = collections.defaultdict(list)  # (name, hash) -> [(run, ref, dev)]
for r in sorted(os.listdir(R)):
    if 'tcg424flip' in r:
        continue
    cd = R + r + '/captures1/'
    if not os.path.isdir(cd):
        continue
    try:
        j = json.load(open(R + r + '/result.json'))
    except Exception:
        continue
    ref = j.get('ref') or ''
    if not ref or not noflip(ref):
        continue
    for n in diff:
        if os.path.isfile(cd + n):
            seen[(n, h(cd + n))].append((r, ref, j.get('device_label')))

nomatch = 0
for n in diff:
    fh, bh = h(FIX + n), h(BASE + n)
    fm, bm = seen.get((n, fh), []), seen.get((n, bh), [])
    if not fm:
        nomatch += 1
    ex = fm[0] if fm else None
    print('%-60s fix-bytes in %2d no-flip runs, base-bytes in %2d  e.g. %s'
          % (n[:60], len(fm), len(bm), ex))
print('fix captures with no byte-identical no-flip match:', nomatch)
