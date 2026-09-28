#!/usr/bin/env python3
"""Coverage of a title's pixel-shader keys by the #569 P6 ubershader.

    keys_coverage.py shader_module_keys.bin [--layout keylayout.json]
    keys_coverage.py --selftest

The key file is vk/shaders.c's shader_module_key_persist(): whole
ShaderModuleCacheKey records appended in compile order. keylayout.json is
keyinfo.c's print of this tree's layout; a file whose size is not a whole
number of records was written by a build whose structs differ, and is
refused rather than misread.

For the fragment keys it reports, at two family widths:

  L1  the combiner registers are uniforms (what psh-uber.c implements):
      combiner_control, rgb/alpha inputs and outputs, final_inputs_0/1.
  L2  L1 plus alpha_test/alpha_func and fog_enable/fog_mode (hypothetical:
      cheap to make uniforms, not implemented in this spike).

  * modules    distinct PshStates, i.e. specialised fragment compiles;
  * families   distinct family keys;
  * uncovered  states with the final combiner off (psh-uber refuses them);
  * served     modules whose family had been compiled at an EARLIER key in
               the file, in file order: the first sights a hybrid could have
               drawn with an already-built ubershader instead of waiting.

And which fields still split the L1 families: for each field, how many
families would merge if that field were a uniform too.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
L1 = ("combiner_control", "rgb_inputs", "rgb_outputs", "alpha_inputs",
      "alpha_outputs", "final_inputs_0", "final_inputs_1")
L2 = L1 + ("alpha_test", "alpha_func", "fog_enable", "fog_mode")


def load_layout(path):
    d = json.load(open(path))
    fields = {k: tuple(v) for k, v in d.items() if isinstance(v, list) and k != "kind"}
    return d, fields


def psh_states(data, lay):
    rec = lay["record"]
    if len(data) % rec:
        raise SystemExit("keys_coverage: %d bytes is not a whole number of %d-byte "
                         "records; the file comes from a build whose "
                         "ShaderModuleCacheKey differs from this tree's" % (len(data), rec))
    ko, ks = lay["kind"]
    ps, pn = lay["psh_state"], lay["psh_state_size"]
    kinds = {}
    out = []
    for i in range(0, len(data), rec):
        k = int.from_bytes(data[i + ko:i + ko + ks], "little")
        kinds[k] = kinds.get(k, 0) + 1
        if k == lay["fragment_kind"]:
            out.append(data[i + ps:i + ps + pn])
    return out, kinds


def blank(state, fields, names):
    b = bytearray(state)
    for n in names:
        off, size = fields[n]
        b[off:off + size] = bytes(size)
    return bytes(b)


def covered(state, fields):
    o0, s0 = fields["final_inputs_0"]
    o1, s1 = fields["final_inputs_1"]
    return any(state[o0:o0 + s0]) or any(state[o1:o1 + s1])


def analyse(states, fields, names):
    seen_mod, seen_fam = set(), set()
    served = unc = 0
    for s in states:
        if s in seen_mod:
            continue
        seen_mod.add(s)
        if not covered(s, fields):
            unc += 1
            continue
        f = blank(s, fields, names)
        if f in seen_fam:
            served += 1
        seen_fam.add(f)
    return len(seen_mod), len(seen_fam), unc, served


def report(path, lay, fields, out=sys.stdout):
    data = open(path, "rb").read()
    states, kinds = psh_states(data, lay)
    print("%s: %d records (%s)" % (path, len(data) // lay["record"],
          ", ".join("kind %d: %d" % kv for kv in sorted(kinds.items()))), file=out)
    rows = {}
    for label, names in (("L1 combiners", L1), ("L2 +alpha test, fog", L2)):
        mods, fams, unc, served = analyse(states, fields, names)
        rows[label] = (mods, fams, unc, served)
        print("  %-22s modules %d, families %d, uncovered %d, served %d of %d "
              "(%.1f%%)" % (label, mods, fams, unc, served, mods,
                            100.0 * served / mods if mods else 0.0), file=out)
    # Which fields still split the L1 families.
    fam = {blank(s, fields, L1) for s in set(states) if covered(s, fields)}
    base = len(fam)
    splits = []
    for n in fields:
        if n in L1:
            continue
        merged = len({blank(f, fields, (n,)) for f in fam})
        if merged < base:
            splits.append((base - merged, n))
    splits.sort(reverse=True)
    print("  fields splitting the %d L1 families (families merged if the field "
          "were a uniform too):" % base, file=out)
    for d, n in splits[:15]:
        print("    %-24s %d" % (n, d), file=out)
    return rows


def selftest(lay, fields):
    """Twelve fragment keys with a known answer, plus vertex keys between
    them: 3 texture configurations x 3 combiner programs, one repeat, one
    final-combiner-off state, one alpha-test variant of a seen family."""
    import io
    import tempfile
    rec, ps = lay["record"], lay["psh_state"]

    def key(kind, **vals):
        b = bytearray(rec)
        b[0:4] = kind.to_bytes(4, "little")
        for n, v in vals.items():
            off, size = fields[n]
            b[ps + off:ps + off + size] = v.to_bytes(size, "little")
        return bytes(b)

    frag = lay["fragment_kind"]
    keys = []
    for tex in (0x1, 0x2, 0x3):
        for prog in (0x11, 0x22, 0x33):
            keys.append(key(1, combiner_control=prog))
            keys.append(key(frag, shader_stage_program=tex, combiner_control=1,
                            rgb_inputs=prog, final_inputs_1=0x1c00))
    keys.append(keys[1])                                   # a repeat
    keys.append(key(frag, shader_stage_program=0x1))       # final combiner off
    keys.append(key(frag, shader_stage_program=0x1, combiner_control=1,
                    rgb_inputs=0x11, final_inputs_1=0x1c00, alpha_test=1))
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(b"".join(keys))
    buf = io.StringIO()
    rows = report(f.name, lay, fields, buf)
    os.unlink(f.name)
    want = {"L1 combiners": (11, 4, 1, 6), "L2 +alpha test, fog": (11, 3, 1, 7)}
    ok = rows == want
    print(buf.getvalue())
    print("selftest: %s (got %s, want %s)" % ("PASS" if ok else "FAIL", rows, want))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="?")
    ap.add_argument("--layout", default=os.path.join(HERE, "keylayout.json"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    lay, fields = load_layout(a.layout)
    if a.selftest:
        return selftest(lay, fields)
    if not a.keys:
        ap.error("a key file, or --selftest")
    report(a.keys, lay, fields)
    return 0


if __name__ == "__main__":
    sys.exit(main())
