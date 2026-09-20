#!/usr/bin/env python3
"""Compare measured writable masks against what this tree assumes.

Two different questions, and conflating them hides the interesting one:

  DECLARED  -- nv2a_regs.h gives each register a set of named bitfields. Their
               union is the bits this tree has a name for.
  IMPLEMENTED -- the block's .c file switches on the register. A register with
               no `case` in the write handler has its writes DROPPED, however
               thoroughly nv2a_regs.h documents its fields.

A register can be fully declared and entirely unimplemented. That combination
is invisible to a header-only comparison and is exactly the defect worth
finding, so it is reported as its own class.

What this cannot see is stated rather than glossed: it reads C by regex, so a
register handled through a range check, a helper, or a computed case will look
unimplemented here. Every finding is therefore a claim to confirm by reading
the handler, not a verdict. The register list and offsets are exact; the
"implemented" column is a strong hint.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

REG_RE   = re.compile(r"^#define\s+(NV_\w+)\s+(0x[0-9A-Fa-f]+)\s*$")
FIELD_RE = re.compile(r"^#\s+define\s+(NV_\w+)\s+(.+?)\s*$")
CASE_RE  = re.compile(r"case\s+(NV_\w+)\s*:")


def eval_mask(expr: str) -> int | None:
    expr = expr.split("/*")[0].strip()
    if not re.fullmatch(r"[0-9A-Fa-fxX()\s<>|+*-]+", expr or ""):
        return None
    try:
        v = eval(expr, {"__builtins__": {}}, {})      # noqa: S307 - constrained above
        return v & 0xFFFFFFFF if isinstance(v, int) else None
    except Exception:
        return None


def parse_regs(path: str, prefix: str):
    """-> {offset: {'name':.., 'fields':{name:mask}}} for registers under prefix."""
    regs, by_name, current = {}, {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = REG_RE.match(line)
        if m:
            name, off = m.group(1), int(m.group(2), 16)
            current = name
            if name.startswith(prefix):
                entry = {"name": name, "offset": off, "fields": {}}
                regs.setdefault(off, entry)
                by_name[name] = regs[off]
            continue
        m = FIELD_RE.match(line)
        if m and current and current.startswith(prefix):
            fname, expr = m.group(1), m.group(2)
            if fname.startswith(current + "_"):
                v = eval_mask(expr)
                if v is not None and current in by_name:
                    by_name[current]["fields"][fname[len(current) + 1:]] = v
    return regs


W1C_RE = re.compile(r"case\s+(NV_\w+)\s*:[^;]*?&=\s*~", re.S)


def parse_w1c(path: str):
    """Registers the write handler treats as write-1-to-CLEAR.

    This matters because of what the sweep can and cannot see. It measures
    LATCHING -- write ones, write zeros, see which bits followed. For a W1C
    status register the correct hardware behaviour is that writing ones clears
    and writing zeros does nothing, so every declared bit reads back 0 and the
    measured writable mask is legitimately empty. Reporting that as "declared
    but not writable" turns correct silicon into a finding.
    """
    if not os.path.exists(path):
        return set()
    return set(W1C_RE.findall(open(path, encoding="utf-8").read()))


def parse_impl(path: str):
    """-> (read_cases, write_cases) register names each handler switches on."""
    src = open(path, encoding="utf-8").read()
    out = []
    for fn in ("_read", "_write"):
        i = src.find("uint64_t " + os.path.basename(path)[:-2] + fn) if fn == "_read" \
            else src.find("void " + os.path.basename(path)[:-2] + fn)
        if i < 0:
            out.append(set())
            continue
        j = src.find("\n}", i)
        out.append(set(CASE_RE.findall(src[i:j if j > 0 else len(src)])))
    return out[0], out[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True)
    ap.add_argument("--root", default=os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    ap.add_argument("--block", default="PMC")
    ap.add_argument("--block-base", default="0x000000",
                    help="the block's offset inside the BAR, subtracted before lookup")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    regs_h = os.path.join(root, "hw", "xbox", "nv2a", "nv2a_regs.h")
    impl_c = os.path.join(root, "hw", "xbox", "nv2a", args.block.lower() + ".c")
    base = int(args.block_base, 0)

    regs = parse_regs(regs_h, "NV_" + args.block.upper() + "_")
    reads, writes = (parse_impl(impl_c) if os.path.exists(impl_c) else (set(), set()))
    w1c = parse_w1c(impl_c)

    measured = {}
    for line in open(args.results, encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            measured[r["offset"]] = r

    print("block %s: %d registers declared in nv2a_regs.h, %d swept"
          % (args.block, len(regs), len(measured)))
    print("%s.c switches on %d registers for read, %d for write; %d write-1-to-clear\n"
          % (args.block.lower(), len(reads), len(writes), len(w1c)))

    findings = []
    hdr = ("%-28s %-8s %-10s %-10s %-10s %s"
           % ("register", "offset", "measured", "declared", "stuck1", "note"))
    print(hdr); print("-" * len(hdr))

    for off in sorted(measured):
        m = measured[off]
        reg = regs.get(off - base)
        name = reg["name"] if reg else "(undeclared)"
        declared = 0
        for v in (reg["fields"].values() if reg else []):
            declared |= v
        w = m["writable"]
        if not w and not m["orig"] and not m["stuck_ones"] and not reg:
            continue                      # silent, undeclared, uninteresting
        notes = []
        if reg and reg["name"] not in writes and w:
            notes.append("WRITES DROPPED by %s.c (no case) yet silicon accepts them"
                         % args.block.lower())
            findings.append(("unimplemented-write", name, off, w, declared))
        if reg and reg["name"] not in reads and (m["orig"] or m["stuck_ones"]):
            notes.append("READ not modelled (no case) yet silicon returns data")
            findings.append(("unimplemented-read", name, off, w, declared))
        if reg and declared and (w & ~declared):
            notes.append("writable bits outside declared fields: %08X" % (w & ~declared))
            findings.append(("undocumented-bits", name, off, w & ~declared, declared))
        if reg and declared and (declared & ~w) and reg["name"] in writes:
            if reg["name"] in w1c:
                # Expected, not a defect: see parse_w1c.
                notes.append("declared bits read back 0, but %s is write-1-to-clear "
                             "-- the sweep cannot measure W1C, so this is not a "
                             "disagreement" % reg["name"])
            else:
                notes.append("declared but not writable: %08X" % (declared & ~w))
                findings.append(("declared-not-writable", name, off,
                                 declared & ~w, declared))
        if not reg and w:
            notes.append("writable register absent from nv2a_regs.h")
            findings.append(("undeclared-writable", name, off, w, 0))
        print("%-28s %-8s %08X   %08X   %08X   %s"
              % (name, "%06X" % off, w, declared, m["stuck_ones"],
                 "; ".join(notes) if notes else ""))

    print("\n%d disagreement(s) between measured silicon and the tree" % len(findings))
    for kind, name, off, mask, _ in findings:
        print("  %-24s %-26s %06X  %08X" % (kind, name, off, mask))
    if args.json_out:
        json.dump([{"kind": k, "register": n, "offset": o, "mask": m}
                   for k, n, o, m, _ in findings],
                  open(args.json_out, "w", encoding="utf-8"), indent=2)
        print("\nwrote %s" % args.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
