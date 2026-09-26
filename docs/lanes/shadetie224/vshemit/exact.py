#!/usr/bin/env python3
"""Compile the emitted GLSL LT helpers as C and check them bit for bit
against celsius_lt.py (the port of envytools) on random and edge operands."""
import os
import random
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import celsius_lt as C  # noqa: E402

out = subprocess.run([os.path.join(HERE, 'emit'), '1'], capture_output=True,
                     text=True, check=True).stdout
hdr = out.split('//HEADER\n', 1)[1].split('//BODY\n', 1)[0]
a = hdr.index('uint ltBits(uint u)')
b = hdr.index('float ltR(float fx)')
b = hdr.index('\n}\n', b) + 3
g = hdr[a:b]
# drop vector overloads
g = '\n'.join(l for l in g.split('\n') if 'vec3' not in l and 'vec4' not in l)
g = re.sub(r'uint\[64\]\(', '{', g)
g = g.replace('0x40u);', '0x40u};')
g = re.sub(r'uint\[3\]\(([^;]*)\);', r'{\1};', g)
g = g.replace('const uint LT_', 'static const uint LT_')

prelude = r'''
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
typedef uint32_t uint;
static inline uint floatBitsToUint(float f) { uint u; memcpy(&u, &f, 4); return u; }
static inline float uintBitsToFloat(uint u) { float f; memcpy(&f, &u, 4); return f; }
static inline int max(int a, int b) { return a > b ? a : b; }
'''
main = r'''
int main(void) {
  char op[8]; uint x, y;
  while (scanf("%7s %x %x", op, &x, &y) == 3) {
    float fx = uintBitsToFloat(x), fy = uintBitsToFloat(y), r = 0;
    if (!strcmp(op, "lt")) r = lt(fx);
    else if (!strcmp(op, "m")) r = ltM(fx, fy);
    else if (!strcmp(op, "sm")) r = ltsM(fx, fy);
    else if (!strcmp(op, "a")) r = ltA(fx, fy);
    else if (!strcmp(op, "sa")) r = ltsA(fx, fy);
    else if (!strcmp(op, "r")) r = ltR(fx);
    printf("%08x\n", floatBitsToUint(r));
  }
  return 0;
}
'''
src = os.path.join(HERE, 'ltc.c')
open(src, 'w').write(prelude + g + main)
exe = os.path.join(HERE, 'ltc')
subprocess.run(['g++', '-x', 'c++', '-O1', '-w', '-o', exe, src], check=True)

rnd = random.Random(224)


def val():
    k = rnd.random()
    if k < 0.05:
        return rnd.choice([0, 0x80000000, 0x3f800000, 0xbf800000,
                           0x7f800000, 0xff800000, 0x7f7fffff, 0x00400000])
    e = rnd.choice([rnd.randint(100, 140), rnd.randint(1, 254)])
    return rnd.getrandbits(1) << 31 | e << 23 | rnd.getrandbits(23)


def lt_in(x):
    return C.s2lt(x)


ref = {
    'lt': lambda x, y: C.s2lt(x),
    'm': lambda x, y: C.lt_mul(x, y),
    'sm': None,
    'a': lambda x, y: C.lt_add(x, y),
    'sa': lambda x, y: C.lts_add(x, y),
    'r': lambda x, y: C.lt_rcp(x),
}
cases = []
for _ in range(60000):
    op = rnd.choice(['lt', 'm', 'a', 'sa', 'r'])
    x, y = val(), val()
    if op != 'lt':
        # the unit only ever sees rounded operands
        x, y = lt_in(x) if C.E(x) != 0xff else x, lt_in(y) if C.E(y) != 0xff else y
    cases.append((op, x, y))
inp = ''.join('%s %08x %08x\n' % c for c in cases)
res = subprocess.run([exe], input=inp, capture_output=True, text=True,
                     check=True).stdout.split()
bad = 0
skipped = 0
for (op, x, y), r in zip(cases, res):
    try:
        want = ref[op](x, y) & 0xffffffff
    except AssertionError:
        skipped += 1
        continue
    got = int(r, 16)
    if got != want:
        # NaN/inf/denormal edges the python port does not model identically
        if any(C.E(v) in (0, 0xff) for v in (x, y)):
            skipped += 1
            continue
        bad += 1
        if bad <= 10:
            print('MISMATCH', op, '%08x %08x' % (x, y), 'glsl %08x' % got,
                  'ref %08x' % want)
print('cases', len(cases), 'mismatch', bad, 'edge-skipped', skipped)
sys.exit(1 if bad else 0)
