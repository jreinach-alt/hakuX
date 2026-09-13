#!/usr/bin/env python3
"""
Check the parse of `hakuX-phase` against the emitter's own identities, before
any number derived from it is believed.

  I1  Pipe == Tx + Sh + Lu                       (create_pipeline sub-phases)
  I2  Tot  == Surf + Tex + Shd + Draw + Fin
              + Flip + Idle                      (profile.c total_ms)
  I3  Draw >= Vtx+Syn+Prw+Pipe+Desc+Setup+Cmd    (sub-phases do not cover all
                                                  of draw_dispatch)
  I4  Fin  == Sub + Fen

Every field is printed to one decimal, so an identity can only be expected to
hold to the rounding of its terms. I1/I2/I4 are exact identities in the source;
a residual larger than the rounding bound is a PARSE fault, not noise.
"""
import re, sys

FIELDS = ["Surf", "Tex", "Shd", "Draw", "Vtx", "Syn", "Prw", "Pipe", "Tx", "Sh",
          "Lu", "Desc", "Setup", "Cmd", "Fin", "Sub", "Fen", "Flip", "Idle",
          "Fr", "St", "Tot"]


def parse(path):
    rows = []
    for line in open(path, errors="replace"):
        if "hakuX-phase" not in line:
            continue
        d = {}
        for f in FIELDS:
            m = re.search(r"(?<![A-Za-z])" + re.escape(f) + r":(-?[\d.]+)", line)
            if m:
                d[f] = float(m.group(1))
        d["_raw"] = line.strip()
        rows.append(d)
    return rows


def g(d, k):
    return d.get(k, 0.0)


fails = 0
n = 0
worst = {}
for p in sys.argv[1:]:
    for d in parse(p):
        n += 1
        checks = {
            # terms, rounding bound = 0.05 * number of terms summed
            "I1 Pipe=Tx+Sh+Lu":
                (g(d, "Pipe"), g(d, "Tx") + g(d, "Sh") + g(d, "Lu"), 4),
            "I2 Tot=Surf+Tex+Shd+Draw+Fin+Flip+Idle":
                (g(d, "Tot"),
                 g(d, "Surf") + g(d, "Tex") + g(d, "Shd") + g(d, "Draw")
                 + g(d, "Fin") + g(d, "Flip") + g(d, "Idle"), 8),
            "I4 Fin=Sub+Fen":
                (g(d, "Fin"), g(d, "Sub") + g(d, "Fen"), 3),
        }
        for name, (lhs, rhs, nterms) in checks.items():
            resid = abs(lhs - rhs)
            bound = 0.05 * nterms
            worst[name] = max(worst.get(name, 0.0), resid)
            if resid > bound:
                fails += 1
                print("FAIL %-40s lhs=%.2f rhs=%.2f resid=%.2f > %.2f"
                      % (name, lhs, rhs, resid, bound))
                print("   ", d["_raw"][:150])
        # I3 is an inequality: sub-phases must not EXCEED draw_dispatch
        sub = sum(g(d, k) for k in
                  ["Vtx", "Syn", "Prw", "Pipe", "Desc", "Setup", "Cmd"])
        if sub > g(d, "Draw") + 0.35:
            fails += 1
            print("FAIL I3 draw sub-phases exceed Draw: %.2f > %.2f"
                  % (sub, g(d, "Draw")))
        worst["I3 Draw-sub (unattributed)"] = max(
            worst.get("I3 Draw-sub (unattributed)", 0.0), g(d, "Draw") - sub)

print("\n%d phase lines checked, %d identity violations" % (n, fails))
for k, v in sorted(worst.items()):
    print("  worst residual %-42s %.2f ms" % (k, v))
