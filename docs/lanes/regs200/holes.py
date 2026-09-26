#!/usr/bin/env python3
"""Per-register hole table for #200, computed from source alone.

For every NV_PGRAPH_* register that some PGRAPH method path writes, list:
  - whether any method path stores a whole word into it (then no bit is
    unreachable through methods), or
  - the union of the masks the masked writers cover, and the bits outside
    that union ("holes": no method can ever set them; they keep their init
    value of zero unless the guest pokes the register over MMIO).
Also list every PG_SET_MASK whose value comes from GET_MASK(parameter, NV097_*)
with a method field wider or narrower than the register field.

Reads hw/xbox/nv2a/nv2a_regs.h and hw/xbox/nv2a/pgraph/pgraph.c; writes
nothing. Usage: python3 docs/lanes/regs200/holes.py [--json] [--measured]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HDR = ROOT / "hw/xbox/nv2a/nv2a_regs.h"
SRC = ROOT / "hw/xbox/nv2a/pgraph/pgraph.c"
FULL = 0xFFFFFFFF


def parse_header():
    """Return (consts, regs, fields_of, owner).

    consts: name -> int for every #define that evaluates.
    regs:   NV_PGRAPH_* register name -> address (top-level defines).
    fields_of: register name -> [(field name, mask)] (one-indent defines).
    owner:  field name -> register name.
    """
    raw = {}
    order = []
    for line in HDR.read_text().splitlines():
        m = re.match(r"#(\s*)define\s+(\w+)\s+(.+?)\s*(//.*|/\*.*)?$", line)
        if not m:
            continue
        indent, name, expr = len(m.group(1)), m.group(2), m.group(3)
        raw[name] = expr
        order.append((indent, name))
    consts = {}

    def ev(name, depth=0):
        if name in consts:
            return consts[name]
        if depth > 20 or name not in raw:
            return None
        expr = raw[name]
        toks = set(re.findall(r"(?<![\w.])[A-Za-z_]\w*", expr))
        env = {}
        for t in toks:
            v = ev(t, depth + 1)
            if v is None:
                return None
            env[t] = v
        try:
            v = eval(re.sub(r"(?<=[0-9A-Fa-f])[uUlL]+\b", "", expr),
                     {"__builtins__": {}}, env)
        except Exception:
            return None
        if not isinstance(v, int):
            return None
        consts[name] = v & FULL
        return consts[name]

    for _, n in order:
        ev(n)
    regs, fields_of, owner = {}, {}, {}
    cur = None
    for indent, name in order:
        if indent == 0 and name.startswith("NV_PGRAPH_") and name in consts:
            cur = name
            regs[name] = consts[name]
            fields_of.setdefault(name, [])
        elif indent == 0:
            cur = None
        elif cur and indent <= 3 and name.startswith(cur + "_") \
                and name in consts:
            fields_of[cur].append((name, consts[name]))
            owner[name] = cur
    return consts, regs, fields_of, owner


def split_args(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


def calls(text, fname):
    """Yield (offset, [args]) for each fname( ... ) call, parens balanced."""
    for m in re.finditer(r"\b%s\s*\(" % re.escape(fname), text):
        i, depth = m.end(), 1
        while depth and i < len(text):
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        yield m.start(), split_args(text[m.end():i - 1])


def functions(text):
    """Return [(start, end, header)] for each top-level brace block."""
    out, depth, start = [], 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                hdr = text[text.rfind("\n", 0, text.rfind("\n", 0, start)) + 1:
                           start].strip()
                out.append((start, i, hdr))
    return out


def line_of(text, off):
    return text.count("\n", 0, off) + 1


def resolve_var(body, var, before):
    """Last `var = expr;` assignment in body before offset `before`."""
    last = None
    for m in re.finditer(r"\b%s\s*=\s*([^;]+);" % re.escape(var), body):
        if m.start() < before:
            last = m.group(1)
    return last


def resolve_reg(expr, body, before, regs):
    """Map a register expression to (base register name, arrayed?)."""
    for _ in range(4):
        names = re.findall(r"\bNV_PGRAPH_\w+", expr)
        if names:
            base = names[0]
            arrayed = bool(re.search(r"\+\s*\(?\s*\w*\s*\*|\+\s*\w+\s*$",
                                     expr)) and not re.search(
                                         r"\+\s*(0x)?\d+\s*$", expr)
            off = re.search(r"\+\s*((?:0x)?[0-9A-Fa-f]+)\s*$", expr)
            if off and base in regs:
                addr = regs[base] + int(off.group(1), 0)
                for n, a in regs.items():
                    if a == addr:
                        return n, False
            return base, arrayed
        if re.fullmatch(r"[A-Za-z_]\w*", expr.strip()):
            nxt = resolve_var(body, expr.strip(), before)
            if nxt is None:
                return None, False
            expr = nxt
        else:
            return None, False
    return None, False


def array_members(base, regs, fields_of):
    """Registers an arrayed write `base + slot*4` reaches.

    The slot count is not in the header, so take every register at
    base + 4k whose name is the base's stem plus a digit, stopping at the
    first address that is not one."""
    stem = re.sub(r"_?\d+$", "", base)
    out, k = [base], 1
    by_addr = {a: n for n, a in regs.items()}
    while True:
        n = by_addr.get(regs[base] + 4 * k)
        if not n or not re.fullmatch(re.escape(stem) + r"_?\d+", n):
            break
        out.append(n)
        k += 1
    return out


def width(m):
    return bin(m).count("1")


def bits(m):
    return [b for b in range(32) if m >> b & 1]


def fmt_bits(m):
    bs = bits(m)
    if not bs:
        return "-"
    runs, s = [], bs[0]
    for a, b in zip(bs, bs[1:] + [None]):
        if b != a + 1:
            runs.append(str(s) if s == a else "%d-%d" % (s, a))
            s = b
    return ",".join(runs)


def scan():
    consts, regs, fields_of, owner = parse_header()
    text = SRC.read_text()
    funcs = functions(text)

    def func_at(off):
        for s, e, h in funcs:
            if s <= off <= e:
                return s, e, h
        return None, None, ""

    masked = {}      # reg -> {mask: [sites]}
    whole = {}       # reg -> [sites]
    mismatches = []
    unresolved = []

    def add_masked(reg, mask, site):
        masked.setdefault(reg, {}).setdefault(mask, []).append(site)

    # PG_SET_MASK(reg, mask, value)
    for off, args in calls(text, "PG_SET_MASK"):
        if len(args) != 3 or args[0] == "reg" and args[1] == "mask":
            continue  # the macro's own definition
        s, e, hdr = func_at(off)
        body = text[s:e] if s is not None else ""
        rel = off - (s or 0)
        reg, arrayed = resolve_reg(args[0], body, rel, regs)
        mexpr = args[1]
        mask = 0
        for t in re.findall(r"[A-Za-z_]\w*", mexpr):
            if t in consts:
                mask |= consts[t]
        if not mask:
            try:
                mask = eval(mexpr, {"__builtins__": {}}) & FULL
            except Exception:
                pass
        ln = line_of(text, off)
        site = "pgraph.c:%d" % ln
        if reg is None or not mask:
            unresolved.append((site, args[0], mexpr))
            continue
        targets = array_members(reg, regs, fields_of) if arrayed else [reg]
        for r in targets:
            add_masked(r, mask, site)
        # width check: value traced to GET_MASK(parameter, NV097_*)
        vexpr = args[2]
        src = re.search(r"GET_MASK\(\s*parameter\s*,\s*(NV097_\w+)\s*\)",
                        vexpr)
        transformed = False
        a = None
        if not src and re.fullmatch(r"[A-Za-z_]\w*", vexpr.strip()):
            a = resolve_var(body, vexpr.strip(), rel)
            if a:
                src = re.search(
                    r"GET_MASK\(\s*parameter\s*,\s*(NV097_\w+)\s*\)", a)
                transformed = bool(src) and a.strip() != src.group(0)
        if vexpr.strip() == "parameter":
            mismatches.append(dict(
                site=site, handler=hdr, reg=reg, reg_field=mexpr,
                reg_mask=mask, method_field="parameter (whole word)",
                method_mask=FULL, transformed=False, value_expr=vexpr))
        if src and src.group(1) in consts:
            smask = consts[src.group(1)]
            if width(smask) != width(mask):
                mismatches.append(dict(
                    site=site, handler=hdr, reg=reg, reg_field=mexpr,
                    reg_mask=mask, method_field=src.group(1),
                    method_mask=smask, transformed=transformed,
                    value_expr=a or vexpr))

    # pgraph_reg_w(pg, reg, value) with a whole word
    for fn in ("pgraph_reg_w", "pgraph_reg_w_atomic"):
        for off, args in calls(text, fn):
            if len(args) != 3 or args[1] in ("r", "f->reg", "reg") and \
                    args[2] in ("v", "rv"):
                continue
            s, e, hdr = func_at(off)
            if hdr.startswith("#define") or "static inline" in hdr:
                continue
            body = text[s:e] if s is not None else ""
            rel = off - (s or 0)
            if args[1] == "f->reg":
                continue  # fast table: handled below
            ln = line_of(text, off)
            site = "pgraph.c:%d" % ln
            if args[1] == "addr":
                continue  # MMIO pgraph_write: every register, see notes
            reg, arrayed = resolve_reg(args[1], body, rel, regs)
            if reg is None:
                unresolved.append((site, args[1], args[2]))
                continue
            targets = array_members(reg, regs, fields_of) if arrayed \
                else [reg]
            for r in targets:
                whole.setdefault(r, []).append(site)

    # method_fast[] table
    lut = []
    m = re.search(r"static const uint32_t mask_lut\[\]\s*=\s*\{(.*?)\};",
                  text, re.S)
    for item in split_args(re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)):
        if not item:
            continue
        v = consts.get(item)
        if v is None:
            try:
                v = int(item, 0)
            except ValueError:
                v = None
        lut.append(v)
    for mm in re.finditer(
            r"\[MI\(([^)]*)\)\]\s*=\s*MF_(DIRECT|MASKED|XLAT|TEX)\(([^;]*)\),",
            text):
        kind, args = mm.group(2), split_args(mm.group(3))
        ln = line_of(text, mm.start())
        site = "pgraph.c:%d" % ln
        reg, _ = resolve_reg(args[0], "", 0, regs)
        if reg is None:
            unresolved.append((site, args[0], kind))
            continue
        if kind in ("DIRECT", "TEX"):
            whole.setdefault(reg, []).append(site)
        else:
            mask = lut[int(args[1])]
            add_masked(reg, mask, site)

    table = []
    for reg in sorted(set(masked) | set(whole), key=lambda r: regs[r]):
        named = 0
        for _, fm in fields_of.get(reg, []):
            named |= fm
        cover = 0
        for mk in masked.get(reg, {}):
            cover |= mk
        row = dict(reg=reg, addr=regs[reg], named=named, covered=cover,
                   whole_writers=whole.get(reg, []),
                   masked_writers=sorted({s for ss in masked.get(reg, {})
                                          .values() for s in ss},
                                         key=lambda s: int(s.split(":")[1])))
        row["holes"] = 0 if reg in whole else (~cover) & FULL
        table.append(row)
    return dict(table=table, mismatches=mismatches, unresolved=unresolved,
                fields_of=fields_of, regs=regs)


# The Blend spot_0_ADD hardware-vs-emulator rows
# (docs/testing/emulator-vs-hardware-registers.md): (before, after) each side.
MEASURED = {
    "NV_PGRAPH_SURFACE": ((0x30100001, 0x30200001), (0x30100000, 0x30200000)),
    "NV_PGRAPH_TEXFMT0": ((0x089104B8, 0x08813AB8), (0x0AA1068A, 0x08813A88)),
    "NV_PGRAPH_TEXFMT1": ((0x000105B8, 0x09913AB8), (0x0881198A, 0x09913A88)),
}


def measured(res):
    """Reproduce the three rows: every differing bit must be a hole with
    hardware 1 and emulator 0; any other differing bit is unexplained."""
    rows = {r["reg"]: r for r in res["table"]}
    out = []
    for reg, (hw, em) in MEASURED.items():
        row = rows[reg]
        for snap, h, e in (("before", hw[0], em[0]), ("after", hw[1], em[1])):
            diff = h ^ e
            expl = diff & row["holes"]
            # a hole explains a bit only in the direction the mechanism
            # allows: hardware set, emulator clear
            wrong_dir = expl & e
            out.append(dict(reg=reg, snap=snap, hw=h, em=e, diff=diff,
                            explained=expl & ~wrong_dir,
                            unexplained=diff & ~(expl & ~wrong_dir),
                            em_sets_a_hole=e & row["holes"]))
    return out


NV2A = ROOT / "hw/xbox/nv2a"
READ_RE = r"(?:pgraph_reg_r|pgraph_vk_reg_r|PG_GET_MASK)\s*\(\s*(?:pg\s*,\s*)?"


def readers(res):
    """For each register with holes: which hole bits a consumer can read.

    named, never written: a header field that overlaps a hole; its uses are
        listed (a consumer reading it always sees the init value).
    raw word read: the whole word is read on a line with no GET_MASK, so
        the hole bits travel into whatever the value feeds (a key, a hash,
        a copy); classify each by hand.
    """
    consts, regs, fields_of, owner = parse_header()
    files = [p for p in NV2A.rglob("*") if p.suffix in (".c", ".h", ".inc")
             and p.name != "nv2a_regs.h"]
    texts = {p: p.read_text(errors="replace") for p in files}
    out = {}
    for row in res["table"]:
        reg, holes = row["reg"], row["holes"]
        if not holes:
            continue
        stem = re.sub(r"_?\d+$", "", reg)
        famfields = (fields_of.get(reg) or fields_of.get(stem + "0")
                     or fields_of.get(stem + "_0") or [])
        hole_fields = [(n, m) for n, m in famfields if m & holes]
        names = {reg, stem + "0", stem + "_0"}
        field_uses, raw_uses = {}, set()
        for p, t in texts.items():
            rel = str(p.relative_to(ROOT))
            for i, line in enumerate(t.splitlines(), 1):
                for n, m in hole_fields:
                    if re.search(r"\b%s\b" % n, line) and \
                            "PG_SET_MASK" not in line:
                        field_uses.setdefault(n, []).append(
                            "%s:%d" % (rel, i))
                for r in names:
                    if re.search(READ_RE + r"%s\b" % r, line) and \
                            "GET_MASK" not in line:
                        raw_uses.add("%s:%d" % (rel, i))
        whole_uses = []
        for site in sorted(raw_uses):
            whole_uses += trace_raw(site, texts, owner, consts)
        out[reg] = dict(holes=holes, named_unwritten=hole_fields,
                        field_uses=field_uses, raw_uses=sorted(raw_uses),
                        whole_uses=whole_uses)
    return out


def statement_at(t, off):
    s = max(t.rfind(";", 0, off), t.rfind("{", 0, off),
            t.rfind("}", 0, off)) + 1
    e = t.find(";", off)
    return s, e


def named_only(expr, var):
    """True if every use of var in expr is GET_MASK(var, NAMED) or
    var & NAMED (a header field or an OR of header fields)."""
    uses = list(re.finditer(r"\b%s\b" % re.escape(var), expr))
    ok = 0
    for m in uses:
        before = expr[:m.start()]
        after = expr[m.end():]
        if re.search(r"GET_MASK\s*\(\s*$", before) and \
                re.match(r"\s*,\s*\(?\s*NV_PGRAPH_\w+", after):
            ok += 1
        elif re.match(r"\s*&\s*\(?\s*~?\s*NV_PGRAPH_\w+", after) or \
                re.search(r"NV_PGRAPH_\w+\s*\)?\s*&\s*$", before):
            ok += 1
    return ok == len(uses)


def trace_raw(site, texts, owner, consts):
    """Follow one whole-word read; return the uses that are not a named
    field mask (each is a place a hole bit could reach)."""
    rel, ln = site.rsplit(":", 1)
    p = ROOT / rel
    t = texts[p]
    lines = t.splitlines(True)
    off = sum(len(x) for x in lines[:int(ln) - 1])
    s, e = statement_at(t, off + len(lines[int(ln) - 1]) // 2)
    stmt = t[s:e]
    call = re.search(READ_RE + r"[^;]*?\)", stmt)
    if not call:
        return ["%s: %s" % (site, " ".join(stmt.split()))]
    rest = stmt[call.end():]
    before = stmt[:call.start()]
    # masked in the same expression: `reg_r(...) & NAMED`
    if re.match(r"\s*\)?\s*&\s*\(?\s*~?\s*NV_PGRAPH_\w+", rest):
        return []
    if re.search(r"GET_MASK\s*\(\s*$", before) and \
            re.match(r"\s*,\s*NV_PGRAPH_\w+", rest):
        return []
    m = re.match(r"\s*(?:const\s+)?(?:uint32_t|unsigned(?:\s+int)?|int)?\s*"
                 r"([A-Za-z_][\w.\->\[\]]*)\s*=\s*$", before)
    if not m or rest.strip() not in ("", ")"):
        return ["%s: %s" % (site, " ".join(stmt.split()))]
    var = m.group(1)
    if not re.fullmatch(r"[A-Za-z_]\w*", var):
        # stored whole into a field or array: the word travels on
        return ["%s: %s" % (site, " ".join(stmt.split()))]
    # uses of the local until the end of its enclosing block
    depth, i, end = 0, e, len(t)
    while i < len(t):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            if depth == 0:
                end = i
                break
            depth -= 1
        i += 1
    bad = []
    j = e + 1
    while j < end:
        ss, ee = j, t.find(";", j)
        if ee < 0 or ee > end:
            ee = end
        st = t[ss:ee]
        if re.search(r"\b%s\b" % var, st):
            if re.search(r"\b%s\s*=[^=]" % var, st):
                break  # reassigned
            if not named_only(st, var):
                bad.append("%s:%d: %s" % (rel, t.count("\n", 0, ss) + 1 +
                                           (len(st) - len(st.lstrip("\n"))),
                                           " ".join(st.split())[:140]))
        j = ee + 1
    return bad


def main():
    res = scan()
    if "--readers" in sys.argv:
        for reg, r in readers(res).items():
            print("\n%s holes %s" % (reg, fmt_bits(r["holes"])))
            for n, m in r["named_unwritten"]:
                print("   named, never written: %s bits %s -> used at %s" % (
                    n, fmt_bits(m), ", ".join(r["field_uses"].get(n, []))
                    or "NOWHERE"))
            print("   whole-word reads: %d sites, %d uses not a named mask" %
                  (len(r["raw_uses"]), len(r["whole_uses"])))
            for s in r["whole_uses"]:
                print("     %s" % s)
        return
    if "--json" in sys.argv:
        print(json.dumps(res["table"] + [dict(mismatches=res["mismatches"])],
                         indent=1, default=str))
        return
    print("| register | addr | named bits | masked-writer cover | "
          "whole-word writer | holes (never set by a method) |")
    print("|---|---|---|---|---|---|")
    for r in res["table"]:
        print("| `%s` | `%04X` | %s | %s | %s | **%s** |" % (
            r["reg"][len("NV_PGRAPH_"):], r["addr"], fmt_bits(r["named"]),
            fmt_bits(r["covered"]),
            ", ".join(r["whole_writers"][:2]) or "none",
            fmt_bits(r["holes"]) if not r["whole_writers"] else "-"))
    print()
    print("mismatches (method field width != register field width):")
    for m in res["mismatches"]:
        print("  %s %s: %s 0x%08X (%d bits) -> %s 0x%08X (%d bits)%s" % (
            m["site"], m["reg"], m["method_field"], m["method_mask"],
            width(m["method_mask"]), m["reg_field"], m["reg_mask"],
            width(m["reg_mask"]),
            " [value transformed first]" if m["transformed"] else ""))
    if res["unresolved"]:
        print("\nunresolved write sites:")
        for u in res["unresolved"]:
            print("  ", u)
    if "--measured" in sys.argv:
        print("\nmeasured rows (Blend spot_0_ADD):")
        for r in measured(res):
            print("  %-18s %-6s hw %08X em %08X diff bits %-8s "
                  "explained %-8s unexplained %-12s em-sets-a-hole %s" % (
                      r["reg"], r["snap"], r["hw"], r["em"],
                      fmt_bits(r["diff"]), fmt_bits(r["explained"]),
                      fmt_bits(r["unexplained"]),
                      fmt_bits(r["em_sets_a_hole"])))


if __name__ == "__main__":
    main()
