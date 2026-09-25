#!/usr/bin/env python3
"""Resolve every NV2A MMIO offset a guest source tree accesses (#189).

Usage: mmio_offsets.py <root> [<root> ...]

Each root is a checkout of code that runs on the guest -- for #189,
nxdk_pgraph_tests @ 6743b6ab (the nv2a index's provenance.tests_commit), its
nxdk submodule @ 73c95900, and pbkitplusplus @ f1491d1a and @ e91d509e. See
NOTES.md for the fetch commands.

Two access paths are enumerated:
  - direct: VIDEOREG/VIDEOREG8/VIDEOREG16(x) and VIDEO_BASE + x
  - indirect: pbkit's PB_SETOUTER interrupt routine does VIDEOREG(paramA) =
    paramB, with paramA pushed as NV20_TCL_PRIMITIVE_3D_PARAMETER_A, so every
    PARAMETER_A push is resolved too.

Offsets are resolved by substituting #defines found anywhere under the roots
and evaluating the result. An expression with a runtime term (index*16, Inst<<4)
is reported by its constant base. Exits 1 if any access resolves to TARGET, or
has a base at or below it (which could reach it through the runtime term).
"""
import collections
import pathlib
import re
import sys

TARGET = 0x004  # NV_PMC_BOOT_1

ACCESS = re.compile(r'VIDEOREG(?:8|16)?\(([^()]*(?:\([^()]*\)[^()]*)*)\)'
                    r'|VIDEO_BASE\s*\+\s*([\w() +*<>]+)')
PARAM_A = re.compile(r'PARAMETER_A\s*,\s*([^,;]+),')


def sources(roots):
    for root in roots:
        for p in pathlib.Path(root).rglob('*'):
            if p.suffix in ('.c', '.cpp', '.h', '.hpp') and p.is_file():
                yield p


def collect_defines(files):
    defs = {}
    for p in files:
        text = p.read_text(errors='replace')
        for m in re.finditer(r'^\s*#define\s+(\w+)\s+([^\n/]+)', text, re.M):
            defs.setdefault(m.group(1), m.group(2).strip())
    return defs


def evaluate(expr, defs, depth=0):
    if depth > 8:
        return None

    def sub(m):
        name = m.group(1)
        if name in defs:
            return '(' + str(evaluate(defs[name], defs, depth + 1)) + ')'
        return name
    e = re.sub(r'\b([A-Za-z_]\w*)\b', sub, expr)
    e = re.sub(r'(0x[0-9a-fA-F]+|\d+)[uUlL]+', r'\1', e)
    try:
        v = eval(e, {'__builtins__': {}})
    except Exception:
        return None
    return v if isinstance(v, int) else None


def main(roots):
    files = list(sources(roots))
    defs = collect_defines(files)
    resolved = collections.Counter()
    by_base = collections.Counter()
    opaque = collections.Counter()
    hits = []
    for p in files:
        for n, line in enumerate(p.read_text(errors='replace').splitlines(), 1):
            if line.lstrip().startswith('#define'):
                continue
            args = [(m.group(1) or m.group(2)).strip().rstrip(')')
                    for m in ACCESS.finditer(line)]
            args += [m.group(1).strip() for m in PARAM_A.finditer(line)
                     if 'FIRE_INTERRUPT' not in line]
            for arg in args:
                v = evaluate(arg, defs)
                if v is not None:
                    resolved[v] += 1
                    if v == TARGET:
                        hits.append('%s:%d exact: %s' % (p, n, line.strip()))
                    continue
                base = evaluate(re.split(r'\s*\+\s*', arg)[0], defs)
                if base is None:
                    opaque[arg] += 1
                    continue
                by_base[base] += 1
                if base <= TARGET:
                    hits.append('%s:%d base %#x: %s' % (p, n, base, line.strip()))
    print('files scanned:', len(files))
    print('accesses with a constant offset: %d (%d distinct)'
          % (sum(resolved.values()), len(resolved)))
    print('  PMC-range (< 0x1000):',
          ', '.join('%#05x x%d' % (k, resolved[k]) for k in sorted(resolved) if k < 0x1000))
    print('accesses with a runtime term, by constant base: %d' % sum(by_base.values()))
    print('  lowest bases:', ', '.join('%#x' % b for b in sorted(by_base)[:6]))
    print('accesses with no constant term (check by hand): %d' % sum(opaque.values()))
    for arg, k in sorted(opaque.items()):
        print('   %3d  %s' % (k, arg))
    print('accesses that are or could be %#05x: %d' % (TARGET, len(hits)))
    for h in hits:
        print('  ', h)
    return 1 if hits else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
