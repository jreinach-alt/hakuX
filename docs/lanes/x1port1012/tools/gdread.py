#!/usr/bin/env python3
"""Reader for a schema-9 frame dump taken with the `gd` token (#939).

Replays each draw's "gd" deltas so every draw has its full guest state
(registers, vertex constants, lighting context, transform program,
fixed-function values, inline attributes), then:

  gdread.py DUMP frames              per frame: draws, skips, image, host mix
  gdread.py DUMP draws F [MIN]       F's draws with >= MIN indices: kind,
                                     count, prim, target, stages, blend, depth
  gdread.py DUMP draw F N            one draw in full: decoded combiners,
                                     texgen, texture matrix, lighting, stages
  gdread.py DUMP odd F               F against F-1 and F+1, draw by draw:
                                     guest words where F differs from both
                                     neighbours while they agree (a toggle),
                                     and host fields that differ with the
                                     guest's input the same
  gdread.py DUMP diff F G            F against G, draw by draw, every field

DUMP is the framedump_<session>.jsonl. Register offsets are named from
hw/xbox/nv2a/nv2a_regs.h. Draws are aligned by a signature (kind, count,
prim, shader, stage offsets) so an inserted or dropped draw shows as one.
"""
import difflib, json, os, re, struct, sys
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
REGS_H = os.path.join(ROOT, "hw", "xbox", "nv2a", "nv2a_regs.h")

GROUPS = {"r": 0x2000, "c": 192 * 4, "la": 26 * 4, "lb": 52 * 4, "l1": 20 * 4,
          "p": 136 * 4, "ff": 3 + 8 * 3 * 4 + 6 + 6 + 8, "va": 16 * 4}
FLOAT_GROUPS = {"c", "la", "lb", "l1", "ff", "va"}


def reg_names():
    names = {}
    pat = re.compile(r"^#define (NV_PGRAPH_[A-Z0-9_]+)\s+0x([0-9A-Fa-f]{8})\s*$")
    with open(REGS_H) as fh:
        for line in fh:
            m = pat.match(line)
            if m:
                names.setdefault(int(m.group(2), 16), m.group(1)[10:])
    # arrays the header names by their first element only
    for base, name, n, step in ((0x1880, "COMBINEFACTOR0_", 8, 4),
                                (0x18A0, "COMBINEFACTOR1_", 8, 4),
                                (0x18C0, "COMBINEALPHAI", 8, 4),
                                (0x18E0, "COMBINEALPHAO", 8, 4),
                                (0x1900, "COMBINECOLORI", 8, 4),
                                (0x1920, "COMBINECOLORO", 8, 4)):
        for i in range(n):
            names[base + i * step] = f"{name}{i}"
    return names


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def load(path):
    """Draws (with their deltas), frames, skips and shaders, in file order."""
    draws, frames, skips, shaders, session = [], {}, [], {}, None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            t = rec.get("t")
            if t == "draw":
                draws.append(rec)
            elif t == "frame":
                frames[rec["f"]] = rec
            elif t == "skip":
                skips.append(rec)
            elif t == "shader":
                shaders[rec["shader"]] = rec
            elif t == "session":
                session = rec
    return session, draws, frames, skips, shaders


def replay(draws, want):
    """Full guest state for the draws whose frame is in `want`, as
    {(f, n): {group: array}}."""
    cur = {g: array("I", [0]) * n for g, n in GROUPS.items()}
    out = {}
    for d in draws:
        gd = d.get("gd")
        if gd is None:
            continue
        for g in GROUPS:
            lst = gd.get(g)
            if lst:
                a = cur[g]
                for i in range(0, len(lst), 2):
                    a[lst[i]] = lst[i + 1]
        if d["f"] in want:
            out[(d["f"], d["n"])] = {g: array("I", a) for g, a in cur.items()}
    return out


def sig(d):
    st = tuple((s.get("off"), s.get("fmt")) for s in d.get("tex", []) if s.get("en"))
    return (d["kind"], d["count"], d["prim"], d["shader"], st)


def frame_draws(draws, f):
    return [d for d in draws if d["f"] == f]


def align(a, b):
    sm = difflib.SequenceMatcher(None, [sig(d) for d in a], [sig(d) for d in b],
                                 autojunk=False)
    pairs = []
    for tag, i0, i1, j0, j1 in sm.get_opcodes():
        if tag == "equal":
            pairs += [(a[i0 + k], b[j0 + k]) for k in range(i1 - i0)]
        else:
            # same-length replace: pair them (a changed draw); else unpaired
            if tag == "replace" and i1 - i0 == j1 - j0:
                pairs += [(a[i0 + k], b[j0 + k]) for k in range(i1 - i0)]
            else:
                pairs += [(a[i], None) for i in range(i0, i1)]
                pairs += [(None, b[j]) for j in range(j0, j1)]
    return pairs


def word_name(g, i, names):
    if g == "r":
        return names.get(i, f"r{i:#06x}")
    if g == "c":
        return f"c[{i // 4}].{'xyzw'[i % 4]}"
    if g == "va":
        return f"va[{i // 4}].{'xyzw'[i % 4]}"
    if g == "p":
        return f"p[{i // 4}].{i % 4}"
    return f"{g}[{i}]"


def fmt_word(g, v):
    if g in FLOAT_GROUPS:
        return f"{f32(v):.6g}"
    return f"{v:#010x}"


def host(d):
    gd = d.get("gd") or {}
    return {k: gd.get(k) for k in ("path", "cp", "ready", "uv", "up", "vkp",
                                    "gu", "lto", "vu", "pu")}


def stage_ids(d):
    return [(s["s"], s.get("off"), s.get("fmt"), s.get("gh"), s.get("th"),
             s.get("img"), s.get("s2t")) for s in d.get("tex", []) if s.get("en")]


def short(d):
    st = ",".join(f"s{s['s']}:{s.get('fmt', '')[-4:]}@{s.get('off', '')}"
                  f"{'*' if s.get('s2t') else ''}"
                  for s in d.get("tex", []) if s.get("en"))
    col = d.get("color") or {}
    rs = d.get("rs", {})
    return (f"n{d['n']:4d} {d['kind'][:6]:6s} cnt {d['count']:5d} prim {d['prim']:2d} "
            f"col {col.get('addr', '-')} sh {d['shader'][:8]} "
            f"bl {rs.get('blend', '')} c0 {rs.get('c0', '')} c1 {rs.get('c1', '')} "
            f"[{st}]")


def cmd_frames(draws, frames, skips):
    nd, ns, paths, ubers = {}, {}, {}, {}
    for d in draws:
        nd[d["f"]] = nd.get(d["f"], 0) + 1
        h = host(d)
        paths.setdefault(d["f"], [0, 0, 0])
        if h["path"] in (0, 1, 2):
            paths[d["f"]][h["path"]] += 1
        if h["gu"] == 1:
            ubers[d["f"]] = ubers.get(d["f"], 0) + 1
    for s in skips:
        ns[s["f"]] = ns.get(s["f"], 0) + 1
    for f in sorted(set(nd) | set(frames)):
        fr = frames.get(f, {})
        p = paths.get(f, [0, 0, 0])
        print(f"f{f:03d} draws {nd.get(f, 0):5d} skips {ns.get(f, 0):3d} "
              f"sfp/mfp/full {p[0]}/{p[1]}/{p[2]} uberpipe {ubers.get(f, 0):4d} "
              f"nv2a {fr.get('nv2a_frame', '-')} img {fr.get('image')}")


def cmd_draws(draws, f, mincount):
    for d in frame_draws(draws, f):
        if d["count"] >= mincount:
            print(short(d))


COMB_IN = ["zero", "c0", "c1", "fog", "v0", "v1", "?6", "?7", "t0", "t1", "t2",
           "t3", "r0", "r1", "spec+r0", "ef_prod"]
COMB_MAP = ["unsigned_identity", "unsigned_invert", "expand_normal",
            "expand_negate", "half_bias_normal", "half_bias_negate",
            "signed_identity", "signed_negate"]


def comb_input(b, alpha_stage):
    reg = b & 0xF
    alpha = (b >> 4) & 1
    mp = (b >> 5) & 7
    return f"{COMB_MAP[mp]}({COMB_IN[reg]}.{'a' if alpha else ('rgb' if not alpha_stage else 'b')})"


def decode_comb(inp, outp, alpha):
    a, b, c, d = (inp >> 24) & 0xFF, (inp >> 16) & 0xFF, (inp >> 8) & 0xFF, inp & 0xFF
    cd = outp & 0xF
    ab = (outp >> 4) & 0xF
    sm = (outp >> 8) & 0xF
    flags = outp >> 12
    return (f"A={comb_input(a, alpha)} B={comb_input(b, alpha)} "
            f"C={comb_input(c, alpha)} D={comb_input(d, alpha)} -> "
            f"ab:{COMB_IN[ab]} cd:{COMB_IN[cd]} sum:{COMB_IN[sm]} flags:{flags:#x}")


def cmd_draw(draws, shaders, f, n, names):
    d = next((x for x in draws if x["f"] == f and x["n"] == n), None)
    if d is None:
        sys.exit(f"no draw f{f} n{n}")
    st = replay(draws, {f})[(f, n)]
    r = st["r"]
    R = lambda name: r[next(k for k, v in names.items() if v == name)]
    print(short(d))
    print("host", host(d))
    print("rs", d.get("rs"), "zeta", d.get("zeta"))
    cc = R("COMBINECTL")
    nst = cc & 0xFF
    print(f"COMBINECTL {cc:#010x}: {nst} stages; SHADERPROG {R('SHADERPROG'):#010x} "
          f"SHADERCTL {R('SHADERCTL'):#010x}")
    for i in range(max(1, nst)):
        ci, co = r[0x1900 + 4 * i], r[0x1920 + 4 * i]
        ai, ao = r[0x18C0 + 4 * i], r[0x18E0 + 4 * i]
        print(f" st{i} rgb  {decode_comb(ci, co, False)}")
        print(f" st{i} a    {decode_comb(ai, ao, True)}")
        print(f" st{i} c0 {r[0x1880 + 4 * i]:#010x} c1 {r[0x18A0 + 4 * i]:#010x}")
    sf0, sf1 = R("COMBINESPECFOG0"), R("COMBINESPECFOG1")
    print(f" final  SPECFOG0 {sf0:#010x} SPECFOG1 {sf1:#010x} "
          f"SPECFOGFACTOR {R('SPECFOGFACTOR0'):#010x} {R('SPECFOGFACTOR1'):#010x}")
    print(f"CSV0_D {R('CSV0_D'):#010x} CSV0_C {R('CSV0_C'):#010x} "
          f"CSV1_A {R('CSV1_A'):#010x} CSV1_B {R('CSV1_B'):#010x}")
    for s in d.get("tex", []):
        if s.get("en"):
            print(" tex", s)
    sh = shaders.get(d["shader"])
    if sh:
        print("shader uber_vs", sh.get("uber_vs"), "psh glsl", len(sh.get("psh", "")),
              "bytes")


def diff_words(sa, sb, names, limit=40):
    out = []
    for g in GROUPS:
        a, b = sa[g], sb[g]
        for i in range(len(a)):
            if a[i] != b[i]:
                out.append(f"{word_name(g, i, names)} {fmt_word(g, a[i])}->{fmt_word(g, b[i])}")
    return out


def cmd_diff(draws, f, g, names):
    st = replay(draws, {f, g})
    pairs = align(frame_draws(draws, f), frame_draws(draws, g))
    same = 0
    for a, b in pairs:
        if a is None or b is None:
            print("UNPAIRED", "F" if a else "G", short(a or b))
            continue
        w = diff_words(st[(f, a["n"])], st[(g, b["n"])], names)
        hd = {k: (host(a)[k], host(b)[k]) for k in host(a) if host(a)[k] != host(b)[k]}
        td = stage_ids(a) != stage_ids(b)
        if not w and not hd and not td:
            same += 1
            continue
        print(short(a))
        if b["n"] != a["n"]:
            print(f"   (pairs with G n{b['n']})")
        if hd:
            print("   host", hd)
        if td:
            print("   stages F", stage_ids(a))
            print("   stages G", stage_ids(b))
        if w:
            print(f"   guest {len(w)}: " + "; ".join(w[:40]) + (" ..." if len(w) > 40 else ""))
    print(f"{same} draws identical in guest, host and stages")


def cmd_odd(draws, f, names):
    st = replay(draws, {f - 1, f, f + 1})
    A, B, C = (frame_draws(draws, x) for x in (f - 1, f, f + 1))
    ab = {id(b): a for a, b in align(A, B) if a and b}
    cb = {id(b): c for c, b in align(C, B) if c and b}
    toggles, hostonly, unp = {}, 0, 0
    for b in B:
        a, c = ab.get(id(b)), cb.get(id(b))
        if a is None or c is None:
            unp += 1
            print("UNPAIRED in F", short(b))
            continue
        sa, sb, sc = st[(f - 1, a["n"])], st[(f, b["n"])], st[(f + 1, c["n"])]
        tog = []
        for g in GROUPS:
            xa, xb, xc = sa[g], sb[g], sc[g]
            for i in range(len(xa)):
                if xb[i] != xa[i] and xa[i] == xc[i]:
                    tog.append(f"{word_name(g, i, names)} {fmt_word(g, xa[i])}/{fmt_word(g, xb[i])}")
                elif g in FLOAT_GROUPS and xb[i] != xa[i] and xb[i] != xc[i]:
                    va, vb, vc = f32(xa[i]), f32(xb[i]), f32(xc[i])
                    if not (min(va, vc) <= vb <= max(va, vc)):
                        tog.append(f"~{word_name(g, i, names)} {va:.6g}/{vb:.6g}/{vc:.6g}")
        ha, hb, hc = host(a), host(b), host(c)
        hd = {k: (ha[k], hb[k], hc[k]) for k in ha if hb[k] != ha[k] or hb[k] != hc[k]}
        sd = not (stage_ids(a) == stage_ids(b) == stage_ids(c))
        if tog or hd or sd:
            print(short(b))
            if tog:
                print("   toggle " + "; ".join(tog[:30]) + (" ..." if len(tog) > 30 else ""))
                for t in tog:
                    toggles[t.split(" ")[0]] = toggles.get(t.split(" ")[0], 0) + 1
            if hd:
                print("   host", hd)
                if not tog:
                    hostonly += 1
            if sd:
                print("   stages", [stage_ids(x) for x in (a, b, c)])
    print(f"toggled words (draws): {sorted(toggles.items(), key=lambda kv: -kv[1])[:30]}")
    print(f"host-only differences: {hostonly} draws; unpaired: {unp}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    path, cmd, rest = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3:]]
    session, draws, frames, skips, shaders = load(path)
    names = reg_names()
    if cmd == "frames":
        if session:
            print("session", {k: session.get(k) for k in ("schema", "spec", "gd")})
        cmd_frames(draws, frames, skips)
    elif cmd == "draws":
        cmd_draws(draws, rest[0], rest[1] if len(rest) > 1 else 0)
    elif cmd == "draw":
        cmd_draw(draws, shaders, rest[0], rest[1], names)
    elif cmd == "diff":
        cmd_diff(draws, rest[0], rest[1], names)
    elif cmd == "odd":
        cmd_odd(draws, rest[0], names)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
