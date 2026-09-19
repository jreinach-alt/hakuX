"""Close out the four lanes that reported with nothing to fold, and give the
running fold lane the issue it is actually folding.

`reported` means "has commits waiting on the fold job". None of these four
produced any: two found their work already an ancestor of origin/master, two
were analysis-only. Left as `reported` they would FAIL every future tick as
"reported and left unfolded -- their claim still reads as coverage".
"""
import json, os, sys

D = "/home/justin/hakux-work/dispatch/fleet"
CLOSED = {
    "toolsmith": "#94 and #95 CLOSED 2026-09-19 by the board: already in master as 99800a64d0 "
                 "and baa5b32698. Nothing to fold -- the branch is an ancestor of origin/master.",
    "tier81fix": "#81 and #90 CLOSED 2026-09-19 by the board: folded as 7dfa94c403 via 4d3edc563d. "
                 "Nothing to fold -- rev-list --left-right prints 109 0.",
    "stencil99": "#99 CLOSED 2026-09-19 as a duplicate of #75 (itself a duplicate of #39). "
                 "Analysis only, no commits, nothing to fold.",
    "blit83":    "#83 LEFT OPEN with its premise corrected on the board branch: the '1 px' is the "
                 "max_rgb column, the control leg is tautological, and #38's PASS stands. "
                 "Analysis only, no commits, nothing to fold. The board applied the lane's "
                 "board-request to [issue.83] blocker_falsifier, blocker_tested, status_note and "
                 "blocked_on.",
}

staged = {}
for name, note in CLOSED.items():
    p = os.path.join(D, name + ".json")
    row = json.load(open(p))
    assert row["state"] == "reported", (name, row["state"])
    row["state"] = "retired"
    row["folded_utc"] = ""
    row["board_outcome"] = note
    staged[p] = json.dumps(row, indent=2) + "\n"

# lane.fold is running and its own `asked` names #84; fleet.py had no way to
# see that, so #84 read as dispatchable while the fold job held it.
p = os.path.join(D, "fold.json")
row = json.load(open(p))
assert row["state"] == "running", row["state"]
row["issues"] = sorted(set(row.get("issues", []) + ["84"]), key=int)
row["board_note"] = ("board tick 2026-09-19T00:16Z: #84 added to this row. The lane's own `asked` "
                     "names it, but issues[] was empty, so fleet.py counted #84 as dispatchable "
                     "while the fold job was holding it.")
staged[p] = json.dumps(row, indent=2) + "\n"

for p, t in staged.items():
    json.loads(t)
if "--write" not in sys.argv:
    for p in sorted(staged):
        print("WOULD WRITE", p)
    sys.exit(0)
for p, t in sorted(staged.items()):
    open(p, "w").write(t)
    print("wrote", p)
