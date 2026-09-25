#!/usr/bin/env python3
"""Static coverage of nv2a_regs.h's PGRAPH field masks by pgraph.c's writers.

Issue #200 asks whether every bit nv2a_regs.h does not name is unreachable,
because method handlers rebuild registers with PG_SET_MASK against named
fields.  This reads the source instead of a device: for every PGRAPH register
it collects

  declared  -- the OR of the field masks nv2a_regs.h lists under it
  covered   -- the OR of every mask any writer in pgraph.c can put a guest
               value into (PG_SET_MASK, the method_fast[] table, and whole
               pgraph_reg_w() stores, which cover all 32 bits)

and reports declared-but-unwritten fields and undeclared-and-unwritten bits,
split by who writes: a method handler (the path every test and title drives)
versus the MMIO path pgraph_write(), which stores a guest CPU's word whole.

Instanced registers (TEXFMT0..3, TEXPALETTE0..3, CSV1_A/B, ...) are folded
onto the instance the header declares fields for, because the handlers write
`NV_PGRAPH_X0 + slot * 4` with X0's masks.

Usage:  python3 docs/testing/pgraph_set_mask_coverage.py [--root DIR] [--md]
"""
import argparse
import os
import re
import sys

FULL = 0xFFFFFFFF


def parse_header(path):
    """Return (addr_of, fields_of, order): PGRAPH register -> address,
    register -> [(field, mask)], and registers in header order."""
    addr_of, fields_of, order = {}, {}, []
    cur = None
    in_pgraph = False
    num = r'(0x[0-9A-Fa-f]+|\(\s*1\s*<<\s*\d+\s*\)|\d+)'
    for line in open(path):
        m = re.match(r'#define\s+(NV_PGRAPH_\w+)\s+' + num + r'\s*(/\*.*)?$',
                     line.rstrip())
        if m:
            in_pgraph = True
            cur = m.group(1)
            addr_of[cur] = int(m.group(2), 0)
            fields_of.setdefault(cur, [])
            order.append(cur)
            continue
        if re.match(r'#define\s+NV_(?!PGRAPH)\w+\s', line):
            cur = None
            in_pgraph = False
            continue
        m = re.match(r'#   define\s+(NV_PGRAPH_\w+)\s+(.*?)\s*(/[/*].*)?$',
                     line.rstrip())
        if m and in_pgraph and cur:
            expr = m.group(2)
            if not re.fullmatch(r'[0-9A-Fa-fx()<|\s]+', expr) or \
                    not m.group(1).startswith(cur + '_'):
                print('header: field not parsed: %s' % line.strip(),
                      file=sys.stderr)
                continue
            fields_of[cur].append((m.group(1), eval(expr) & FULL))
    return addr_of, fields_of, order


def call_args(src, start):
    """Split the argument list of the call whose '(' ends at src[start-1]."""
    depth, j, cur, parts = 1, start, '', []
    while depth:
        c = src[j]
        j += 1
        if c in '([':
            depth += 1
        elif c in ')]':
            depth -= 1
            if not depth:
                break
        if c == ',' and depth == 1:
            parts.append(' '.join(cur.split()))
            cur = ''
            continue
        cur += c
    parts.append(' '.join(cur.split()))
    return parts


FUNC_RE = re.compile(
    r'^(?:DEF_METHOD\w*\((\w+),\s*(\w+)\)|(?:static\s+)?(?:inline\s+)?'
    r'[a-zA-Z_][\w\s\*]*?\b(\w+)\s*\([^;]*$)', re.M)


def enclosing(src, pos):
    best = None
    for m in FUNC_RE.finditer(src, 0, pos):
        best = m
    if not best:
        return '?'
    if best.group(1):
        return 'DEF_METHOD(%s, %s)' % (best.group(1), best.group(2))
    return best.group(3)


def path_of(func):
    if func.startswith('DEF_METHOD') or func in (
            'pgraph_method', 'fast_entry_apply', 'fast_entry_apply_atomic'):
        return 'method'
    if func == 'pgraph_write':
        return 'mmio'
    return 'other:' + func


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--md', action='store_true', help='markdown table')
    ap.add_argument('--sites', action='store_true',
                    help='list the write sites under each register')
    a = ap.parse_args()
    hdr = os.path.join(a.root, 'hw/xbox/nv2a/nv2a_regs.h')
    csrc = os.path.join(a.root, 'hw/xbox/nv2a/pgraph/pgraph.c')
    addr_of, fields_of, order = parse_header(hdr)
    mask_owner = {f: (r, mk) for r, fl in fields_of.items() for f, mk in fl}
    src = open(csrc).read()

    def family(expr):
        """Register a write expression lands in, folded onto its base."""
        toks = re.findall(r'NV_PGRAPH_\w+', expr)
        return toks[0] if toks else None

    def local_assign(func_pos, name):
        """`unsigned int <name> = <expr>;` in the function around func_pos."""
        start = src.rfind('\nDEF_METHOD', 0, func_pos)
        body = src[start:func_pos]
        ms = list(re.finditer(r'\b%s\s*=\s*([^;]+);' % name, body))
        return ms[-1].group(1) if ms else ''

    # (register, path) -> [(mask, site)]
    writes = {}

    def add(reg, path, mask, site):
        writes.setdefault((reg, path), []).append((mask, site))

    for m in re.finditer(r'\bPG_SET_MASK\(', src):
        ln = src.count('\n', 0, m.start()) + 1
        if ln < 60:
            continue                                  # the macro itself
        reg_e, mask_e = call_args(src, m.end())[:2]
        func = enclosing(src, m.start())
        path = path_of(func)
        site = 'pgraph.c:%d %s' % (ln, func)
        if mask_e == 'mask':
            # SET_TEXGEN_{S,T,R,Q}: reg is CSV1_A or CSV1_B by slot, the
            # mask is T0_x or T1_x of CSV1_A's layout by slot parity.
            masks = re.findall(r'NV_PGRAPH_\w+',
                               local_assign(m.start(), 'mask'))
            regs = re.findall(r'NV_PGRAPH_\w+', local_assign(m.start(), 'reg'))
            for r in regs:
                for mk in masks:
                    add(r, path, mask_owner[mk][1], site)
            continue
        if mask_e in mask_owner:
            r, mk = mask_owner[mask_e]
        else:
            mk = int(mask_e, 0)
            r = family(reg_e) or family(local_assign(m.start(), reg_e))
        add(r, path, mk, site)

    for m in re.finditer(r'\bpgraph_reg_w(?:_atomic)?\(', src):
        ln = src.count('\n', 0, m.start()) + 1
        if ln < 60:
            continue                                  # PG_SET_MASK's body
        args = call_args(src, m.end())
        if len(args) != 3 or args[0] != 'pg':
            continue
        reg_e, val_e = args[1], args[2]
        func = enclosing(src, m.start())
        if func in ('fast_entry_apply', 'fast_entry_apply_atomic'):
            continue                   # method_fast[] is expanded below
        path = path_of(func)
        site = 'pgraph.c:%d %s' % (ln, func)
        if reg_e in ('reg', 'rv'):
            reg_e = local_assign(m.start(), 'reg')
        if reg_e == 'addr':
            add('*', path, FULL, site)                # any register
            continue
        if reg_e.startswith('swizzle'):
            for r in ('NV_PGRAPH_BUMPMAT00', 'NV_PGRAPH_BUMPMAT01',
                      'NV_PGRAPH_BUMPMAT10', 'NV_PGRAPH_BUMPMAT11'):
                add(r, path, FULL, site)
            continue
        r = family(reg_e)
        if r is None:
            print('unresolved write %s: %s' % (site, reg_e), file=sys.stderr)
            continue
        const = re.fullmatch(r'NV_PGRAPH_\w+', val_e)
        if const and val_e in mask_owner:
            add(r, path, mask_owner[val_e][1], site + ' (constant)')
        else:
            add(r, path, FULL, site)

    # method_fast[]: the lockless fast path, method-driven like DEF_METHOD.
    lut_m = re.search(r'mask_lut\[\]\s*=\s*\{(.*?)\};', src, re.S)
    lut = {}
    for idx, val in re.findall(r'/\*\s*(\d+)\s*\*/\s*([\w]+)', lut_m.group(1)):
        lut[int(idx)] = mask_owner[val][1] if val in mask_owner else int(val, 0)
    tab = re.search(r'method_fast\[0x800\]\s*=\s*\{(.*?)\n\};', src, re.S)
    tab_line = src.count('\n', 0, tab.start()) + 1
    for m in re.finditer(r'MF_(DIRECT|MASKED|XLAT|TEX)\(([^)]*)\)', tab.group(1)):
        kind, args = m.group(1), [x.strip() for x in m.group(2).split(',')]
        ln = tab_line + tab.group(1).count('\n', 0, m.start())
        site = 'pgraph.c:%d method_fast[]' % ln
        r = family(args[0])
        if kind in ('DIRECT', 'TEX'):
            add(r, 'method', FULL, site)
        else:
            add(r, 'method', lut[int(args[1])], site)

    # Fold instances with no declared fields onto the declared base, and
    # the texgen CSV1_B writes onto CSV1_A's layout for reporting.
    # Only a register the source indexes as `X0 + slot * 4` has instances;
    # CONTROL_1 sits at CONTROL_0 + 4 and is a different register.
    instanced = set(re.findall(r'(NV_PGRAPH_\w+0)\s*\+\s*slot\s*\*\s*4', src))

    def base(r):
        # X1..X3 at X0 + 4*n is an instance of X0 (TEXFMT1 is TEXFMT0's
        # slot 1); BUMPMAT01 and COMBINEFACTOR1 are distinct registers.
        m = re.fullmatch(r'(.*\D)(\d)', r)
        if m and int(m.group(2)):
            cand = m.group(1) + '0'
            n = int(m.group(2))
            if cand in instanced and addr_of.get(cand) is not None and \
                    addr_of.get(r) == addr_of[cand] + 4 * n:
                return cand
        return r

    rows = []
    regs = set(r for r, _ in writes if r != '*') | set(
        r for r in order if fields_of[r])
    regs |= set(base(r) for r in regs)
    mmio_all = ('*', 'mmio') in writes
    for r in sorted(regs, key=lambda x: addr_of.get(x, 1 << 20)):
        b = base(r)
        if b != r:
            continue                   # reported on its base row
        declared = 0
        for _, mk in fields_of.get(r, []):
            declared |= mk
        members = [x for x in regs | set(order) if base(x) == r]
        meth = 0
        sites = []
        for x in members:
            for mk, s in writes.get((x, 'method'), []):
                meth |= mk
                sites.append(s)
        other = 0
        for (x, p), lst in writes.items():
            if x in members and p.startswith('other'):
                for mk, s in lst:
                    other |= mk
                    sites.append(s)
        unwritten_fields = [f for f, mk in fields_of.get(r, [])
                            if mk & ~meth & FULL]
        rows.append(dict(
            reg=r, addr=addr_of.get(r), members=sorted(members),
            declared=declared, method=meth, other=other,
            undecl_holes=(~declared & ~meth) & FULL,
            decl_holes=declared & ~meth & FULL,
            unwritten_fields=unwritten_fields, sites=sites))

    written = [x for x in rows if x['method']]
    with_decl_hole = [x for x in written if x['decl_holes']]
    with_any_hole = [x for x in written
                     if (x['decl_holes'] | x['undecl_holes'])]
    full = [x for x in written if x['method'] == FULL]

    if a.md:
        print('| register | addr | declared mask | method-written | '
              'declared, never written | undeclared, never written |')
        print('|---|---|---|---|---|---|')
        for x in rows:
            name = x['reg'].replace('NV_PGRAPH_', '')
            if len(x['members']) > 1:
                name += ' (x%d)' % len(x['members'])
            print('| `%s` | %s | `%08X` | `%08X` | %s | %s |' % (
                name, '0x%04X' % x['addr'] if x['addr'] is not None else '?',
                x['declared'], x['method'],
                ', '.join('`%s`' % f.replace(x['reg'] + '_', '')
                          for f in x['unwritten_fields']) or '--',
                '`%08X`' % x['undecl_holes'] if x['method'] and
                x['undecl_holes'] else ('--' if x['method'] else
                                        'not written')))
    else:
        for x in rows:
            print('%-28s %-6s decl=%08X meth=%08X other=%08X '
                  'decl_holes=%08X undecl_holes=%08X %s' % (
                      x['reg'], hex(x['addr'] or 0), x['declared'],
                      x['method'], x['other'], x['decl_holes'],
                      x['undecl_holes'] if x['method'] else 0,
                      ','.join(x['unwritten_fields'])))
            if a.sites:
                for s_ in x['sites']:
                    print('    ' + s_)
    print()
    print('registers (families) with a declared field or any writer: %d'
          % len(rows))
    print('written by a method handler: %d' % len(written))
    print('  whole-word written (no holes possible): %d' % len(full))
    print('  masked only, with >=1 declared field never written: %d / %d'
          % (len(with_decl_hole), len(written)))
    print('  with >=1 bit (declared or not) never written: %d / %d'
          % (len(with_any_hole), len(written)))
    print('  bits never written in those, summed per family: %d declared, '
          '%d undeclared' % (
              sum(bin(x['decl_holes']).count('1') for x in written),
              sum(bin(x['undecl_holes']).count('1') for x in written)))
    print('declared-field registers no method handler writes: %d'
          % len([x for x in rows if x['declared'] and not x['method']]))
    print('header registers with no field and no method writer: %d'
          % len([r for r in order if not fields_of[r] and base(r) == r
                 and r not in regs]))
    print('MMIO pgraph_write default stores the whole word: %s' % mmio_all)


if __name__ == '__main__':
    main()
