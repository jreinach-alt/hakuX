#!/usr/bin/env python3
"""Which VshState fields vary across a title's vertex-shader keys.

    vsh_fields.py shader_module_keys.bin

Reads the key file with keylayout.json and vshlayout.json (this tree's
layouts), and prints, for the distinct vertex states: every top-level field
that takes more than one value, with its values and counts; the fixed-function
sub-state (texture-matrix enables, texgen, skinning); and the program lengths.
It scopes the uber vertex stage (BUILD.md): a field that never varies within a
title need not be a uniform for that title.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    lay = json.load(open(os.path.join(HERE, "keylayout.json")))
    v = json.load(open(os.path.join(HERE, "vshlayout.json")))
    data = open(sys.argv[1], "rb").read()
    rec = lay["record"]
    ko, ks = lay["kind"]
    vo, vn = lay["vsh_state"], lay["vsh_state_size"]
    if len(data) % rec:
        raise SystemExit("not a whole number of %d-byte records" % rec)
    mods = []
    for i in range(0, len(data), rec):
        if int.from_bytes(data[i + ko:i + ko + ks], "little") != lay["vertex_kind"]:
            continue
        s = data[i + vo:i + vo + vn]
        if s not in mods:
            mods.append(s)
    fields = {k: x for k, x in v.items() if isinstance(x, list)}
    ff = [s for s in mods if s[fields["is_fixed_function"][0]]]
    pr = [s for s in mods if not s[fields["is_fixed_function"][0]]]
    print("vertex modules %d: fixed-function %d, programs %d" % (len(mods), len(ff), len(pr)))
    for k, (o, n) in fields.items():
        if k == "program":
            continue
        for label, group in (("ff", ff), ("prog", pr)):
            vals = collections.Counter(s[o:o + n].hex() for s in group)
            if len(vals) > 1:
                print("  %-5s %-22s %s" % (label, k, dict(vals)))
    po = fields["program"][0]
    sub = {"texmat_en": (po, 4), "texgen": (po + 4, 64), "skinning": (po + 68, 4)}
    for name, (o, n) in sub.items():
        vals = collections.Counter(s[o:o + n].hex() for s in ff)
        print("  ff    %-22s %d values %s" % (name, len(vals), dict(vals) if len(vals) < 8 else ""))
    plo = po + fields["program"][1] - 4
    print("  prog  lengths %s" % sorted(int.from_bytes(s[plo:plo + 4], "little") for s in pr))


if __name__ == "__main__":
    main()
