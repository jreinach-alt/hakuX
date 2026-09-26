#!/usr/bin/env python3
"""Score the nv2a_vsh_cpu evaluator, pristine and patched, on the host.

    cpu_rows.py ORIG_SRC_DIR NEW_SRC_DIR SILICON_SPECIAL_raw.txt [--sweep N]

Builds cpu_rows.c once against each library's src/ and reports:

  1. rows: each build's result on the 44 console rows of CPU Shader
     Tests::SPECIAL_RAW (PR #344), and how many agree with silicon;
  2. sweep: every finite input in a fixed pseudo-random sweep whose result
     differs between the two builds, grouped by op and by kind of change.

The host is x86-64 without flush-to-zero; the device is aarch64. A row whose
input is subnormal can differ between the two for that reason alone.
"""
import argparse
import collections
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def build(src, out):
    subprocess.run(["cc", "-O2", "-std=c11", "-I", src, "-o", out,
                    os.path.join(HERE, "cpu_rows.c"), "-lm"], check=True)


def f(h):
    return struct.unpack("<f", struct.pack("<I", int(h, 16)))[0]


TWO64, TWOM64 = 2.0 ** 64, 2.0 ** -64
# The pristine library's decimal bounds, as the float literals it compares with.
OLD_HI, OLD_LO = (struct.unpack("<f", struct.pack("<f", x))[0] for x in (1.884467e19, 5.42101e-20))


def classify(op, a, b):
    """Name the kind of change between result words a and b (4 components)."""
    kinds = set()
    for wa, wb in zip(a, b):
        if wa == wb:
            continue
        fa, fb = f(wa), f(wb)
        if fa == 0.0 and fb == 0.0:
            kinds.add("zero sign %s -> %s" % (wa, wb))
        elif (op == "RCC" and abs(fb) == TWOM64 and OLD_LO <= abs(fa) < TWOM64
              and (fa < 0) == (fb < 0)):
            kinds.add("RCC low clamp: [5.42101e-20, 2^-64) -> 2^-64")
        elif (op == "RCC" and abs(fb) == TWO64 and TWO64 < abs(fa) <= OLD_HI
              and (fa < 0) == (fb < 0)):
            kinds.add("RCC high clamp: (2^64, 1.884467e19] -> 2^64")
        else:
            kinds.add("OTHER")
    return "; ".join(sorted(kinds))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("orig")
    ap.add_argument("new")
    ap.add_argument("silicon")
    ap.add_argument("--sweep", type=int, default=200000)
    args = ap.parse_args()
    silicon = [l.rstrip("\n") for l in open(args.silicon) if l.strip()]
    with tempfile.TemporaryDirectory() as tmp:
        exes = {}
        for name, src in (("orig", args.orig), ("new", args.new)):
            exes[name] = os.path.join(tmp, name)
            build(os.path.join(src, "src"), exes[name])
        rows = {}
        for name, exe in exes.items():
            out = subprocess.run([exe, "rows"], input="\n".join(silicon) + "\n",
                                 capture_output=True, text=True, check=True).stdout
            rows[name] = out.splitlines()
        print("== rows: CPU Shader Tests::SPECIAL_RAW, first component vs silicon")
        agree = collections.Counter()
        for i, s in enumerate(silicon):
            hw = s.split(" hw=")[1].split(",")[0]
            got = {n: rows[n][i].split(" hw=")[1].split(",")[0] for n in rows}
            full = {n: rows[n][i] == s for n in rows}
            for n in rows:
                agree[n] += full[n]
            mark = "".join("%s=%s%s " % (n, got[n], "" if full[n] else "(*)") for n in rows)
            print("%-3s %-60s silicon=%s %s" % (s[:3], s.split(" hw=")[0][4:60], hw, mark))
        for n in rows:
            print("%s: %d / %d rows byte-identical to silicon (all four components)"
                  % (n, agree[n], len(silicon)))

        print("\n== sweep: finite inputs, orig vs new (%d per op)" % args.sweep)
        outs = {}
        for name, exe in exes.items():
            outs[name] = subprocess.run([exe, "sweep", str(args.sweep)], capture_output=True,
                                        text=True, check=True).stdout.splitlines()
        assert len(outs["orig"]) == len(outs["new"])
        per_op = collections.Counter()
        kinds = collections.Counter()
        examples = {}
        for lo, ln in zip(outs["orig"], outs["new"]):
            op = lo.split()[0]
            per_op[op] += 1
            if lo == ln:
                continue
            ins, a = lo.split(" -> ")
            _, b = ln.split(" -> ")
            k = (op, classify(op, a.split(), b.split()))
            kinds[k] += 1
            examples.setdefault(k, (ins, a, b))
        for op in per_op:
            changed = sum(v for (o, _), v in kinds.items() if o == op)
            print("%s: %d of %d finite inputs changed" % (op, changed, per_op[op]))
        for (op, kind), v in sorted(kinds.items()):
            ins, a, b = examples[(op, kind)]
            print("  %s %-28s %6d  e.g. %s : %s -> %s" % (op, kind, v, ins, a, b))
        if any("OTHER" in kind for _, kind in kinds):
            print("OTHER changes present: a finite result moved by more than a zero's "
                  "sign or the RCC clamp")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
