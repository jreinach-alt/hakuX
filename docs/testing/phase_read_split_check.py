#!/usr/bin/env python3
"""
Check the parse of `hakuX-phase` against the emitter's own identities, before
any number derived from it is believed.

  I1  Pipe >= Tx + Sh + Lu + Shd                 (create_pipeline sub-phases;
                                                  shader_compile is timed only
                                                  inside it. Not an identity:
                                                  create_clear_pipeline() and
                                                  the pipeline-cache save sit
                                                  in Pipe with no child span)
  I2  Tot  == Surf + Tex + Shd + Draw + Fin
              + Flip + Idle                      (profile.c total_ms)
  I3  Draw >= Vtx+Syn+Prw+Pipe+Desc+Setup+Cmd    (sub-phases do not cover all
              + Sfp+Mfp+FTx                       of draw_dispatch)
  I4  Fin  >= Sub + Fen                          (finish also ends the render
                                                  pass, the queries and the
                                                  command buffer before Sub, and
                                                  processes pending reports
                                                  after Fen)
  I5  TxH + Tex <= Tx + FTx                      (the content hash and the
                                                  upload are reached only from
                                                  the texture binds; lines that
                                                  carry Sfp/Mfp/FTx/TxH only)

Every field is printed to one decimal, so an identity can only be expected to
hold to the rounding of its terms. I2 is an exact identity in the source; a
residual larger than the rounding bound is a PARSE fault, not noise. I1, I3,
I4 and I5 are inequalities: a child may not exceed its parent beyond rounding.

Since #426's instrument fix every child of Draw and of Pipe is exclusive of
finish, as Draw is, and the fall-through clear is timed as Draw, whose
children it adds to. On an older line a finish nested in a child is counted
there and again in Fin, and a clear's children fall outside Draw, so I1 and
I3 can fail on an older line by design.
"""
import re, sys

FIELDS = ["Surf", "Tex", "Shd", "Draw", "Vtx", "Syn", "Prw", "Pipe", "Tx", "Sh",
          "Lu", "Desc", "Setup", "Cmd", "Fin", "Sub", "Fen", "Flip", "Idle",
          "Fr", "St", "Tot", "Sfp", "Mfp", "FTx", "TxH"]


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
            "I2 Tot=Surf+Tex+Shd+Draw+Fin+Flip+Idle":
                (g(d, "Tot"),
                 g(d, "Surf") + g(d, "Tex") + g(d, "Shd") + g(d, "Draw")
                 + g(d, "Fin") + g(d, "Flip") + g(d, "Idle"), 8),
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
        # I4 is an inequality: Sub and Fen must not EXCEED finish
        if g(d, "Sub") + g(d, "Fen") > g(d, "Fin") + 0.15:
            fails += 1
            print("FAIL I4 Sub+Fen exceed Fin: %.2f > %.2f"
                  % (g(d, "Sub") + g(d, "Fen"), g(d, "Fin")))
        worst["I4 Fin-Sub-Fen (rest of finish)"] = max(
            worst.get("I4 Fin-Sub-Fen (rest of finish)", 0.0),
            g(d, "Fin") - g(d, "Sub") - g(d, "Fen"))
        # I1 is an inequality: create_pipeline's sub-phases must not EXCEED
        # draw_pipeline, which also holds work that has no child span
        kids = g(d, "Tx") + g(d, "Sh") + g(d, "Lu") + g(d, "Shd")
        if kids > g(d, "Pipe") + 0.25:
            fails += 1
            print("FAIL I1 Pipe sub-phases exceed Pipe: %.2f > %.2f"
                  % (kids, g(d, "Pipe")))
        worst["I1 Pipe-kids (unattributed in Pipe)"] = max(
            worst.get("I1 Pipe-kids (unattributed in Pipe)", 0.0),
            g(d, "Pipe") - kids)
        # I3 is an inequality: sub-phases must not EXCEED draw_dispatch
        sub = sum(g(d, k) for k in
                  ["Vtx", "Syn", "Prw", "Pipe", "Desc", "Setup", "Cmd",
                   "Sfp", "Mfp", "FTx"])
        if sub > g(d, "Draw") + 0.35:
            fails += 1
            print("FAIL I3 draw sub-phases exceed Draw: %.2f > %.2f"
                  % (sub, g(d, "Draw")))
        worst["I3 Draw-sub (unattributed)"] = max(
            worst.get("I3 Draw-sub (unattributed)", 0.0), g(d, "Draw") - sub)
        # I5 is an inequality too, and an older line has no FTx to hold the
        # fast paths' uploads, so it applies only where the new fields are
        if "Sfp" in d:
            nested = g(d, "TxH") + g(d, "Tex")
            binds = g(d, "Tx") + g(d, "FTx")
            if nested > binds + 0.2:
                fails += 1
                print("FAIL I5 TxH+Tex exceed Tx+FTx: %.2f > %.2f"
                      % (nested, binds))

print("\n%d phase lines checked, %d identity violations" % (n, fails))
for k, v in sorted(worst.items()):
    print("  worst residual %-42s %.2f ms" % (k, v))
