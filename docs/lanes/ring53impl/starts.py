#!/usr/bin/env python3
"""Read every Ring_weights case's window starts from two capture roots with
lane.xbox's ringw_score.py reader, and compare them draw for draw.

    starts.py <silicon root> <ours root> [CASES]

CASES is comma-separated; default: every `<K>a_FF` found in the silicon root.
A row is `exact` only if all six draws read on both sides and agree; otherwise
it says which side was unreadable. Writes nothing.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "xbox"))
import ringw_score as rs  # noqa: E402


def read(root, k):
    pp, _ = rs.find(root, k + "a_FF")
    sp, sname = rs.find(root, k + "b_")
    if not pp or not sp:
        return None, "MISSING", None
    pa = rs.rgb(pp)
    prime = [v for quad in rs.PRIME_QUADS for v in rs.corners(pa, *quad)]
    sep = min(abs(x - y) for i, x in enumerate(prime) for y in prime[i + 1:])
    sa = rs.rgb(sp)
    starts = [rs.window_start(rs.corners(sa, *q), prime)[0] for q in rs.LIT_QUADS]
    return starts, sname, sep


def cases(root):
    base = os.path.join(root, rs.SUITE) if os.path.isdir(os.path.join(root, rs.SUITE)) else root
    out = []
    for f in sorted(os.listdir(base)):
        name = f[len(rs.SUITE) + 2:] if f.startswith(rs.SUITE + "::") else f
        if name.endswith("a_FF.png"):
            out.append(name[:-len("a_FF.png")])
    return out


def main():
    sil, ours = sys.argv[1], sys.argv[2]
    ks = sys.argv[3].split(",") if len(sys.argv) > 3 else cases(sil)
    exact = 0
    for k in ks:
        a, name, sa = read(sil, k)
        b, _, sb = read(ours, k)
        if a is None or b is None or None in a or None in b:
            verdict = "UNREADABLE (%s)" % ("silicon" if a is None or None in a else "ours")
        elif sa < rs.SEP or sb < rs.SEP:
            verdict = "UNREADABLE (priming separation %.1f / %.1f)" % (sa, sb)
        elif a == b:
            verdict = "exact"
            exact += 1
        else:
            verdict = "OFF by %s" % sorted({(y - x) % 6 for x, y in zip(a, b)})
        print("%-3s %-16s silicon %s  ours %s  %s" % (k, name, a, b, verdict))
    print("exact %d of %d" % (exact, len(ks)))
    return 0 if exact == len(ks) else 1


if __name__ == "__main__":
    sys.exit(main())
