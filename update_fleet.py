"""Reconcile dispatch/fleet rows with what the lane units and logs actually did.

Six lanes were started by lane.sh at 2026-09-19T00:00Z. No fleet row was
written or updated, so fleet.py -- which reads state only from these rows --
still saw six retired lanes and counted their eleven issues as dispatchable.
Two of the six are still running; four exited ok and reported.

Written in memory and validated before anything is written to disk.
"""
import json, os, sys

D = "/home/justin/hakux-work/dispatch/fleet"

RUNNING = {
    "blitsafe": {
        "agent": "hakux-lane-blitsafe",
        "issues": ["88", "89", "91", "92"],
        "dispatched_utc": "2026-09-19T00:00:14Z",
        "worktree": "/home/justin/hakux-work/wt/blitsafe",
        "asked": "Restarted by lane.sh 2026-09-19T00:00Z on lane/blitsafe. #88/#91 the "
                 "Color_zeta_overlap Swap regression, #89 the desktop/device split, #92 "
                 "SurfaceShape carrying no address. Unit active at the 00:16Z board tick.",
    },
    "swizzle87": {
        "agent": "hakux-lane-swizzle87",
        "issues": ["85", "87"],
        "dispatched_utc": "2026-09-19T00:00:20Z",
        "worktree": "/home/justin/hakux-work/wt/swizzle87",
        "asked": "Restarted by lane.sh 2026-09-19T00:00Z on lane/swizzle87. #87's swizzled "
                 "render-target layout and #85's never-exercised mem_dirty half of the "
                 "surface-upload gate. Unit active at the 00:16Z board tick.",
    },
}

REPORTED = {
    "toolsmith": {
        "agent": "lane-toolsmith/9fa9a07b",
        "issues": ["94", "95"],
        "dispatched_utc": "2026-09-19T00:00:51Z",
        "reported_utc": "2026-09-19T00:04:56Z",
        "worktree": "/home/justin/hakux-work/wt/toolsmith",
        "asked": "#94 request.sh dropping all but the last list flag, #95 the prediction "
                 "schema's missing composition field.",
        "resolved": "BOTH ALREADY IN MASTER, and the lane supplied the verification that was "
                    "missing. #94 landed as 99800a64d0 (the four list flags append, duplicates "
                    "refused, queued record re-read); #95 as baa5b32698 (--disc-from writes a "
                    "disc block, composition_notes() refuses an absolute and downgrades a delta "
                    "on mismatch). lane/toolsmith @ baa5b32698 is an ANCESTOR of origin/master. "
                    "Falsifier run against a scratch DISPATCH_DIR: 8 --only-tests flags survive "
                    "as 8. Log blit/toolsmith.20260919T000051Z.json, 43 turns.",
    },
    "tier81fix": {
        "agent": "lane-tier81fix/f9306ce7",
        "issues": ["81", "90"],
        "dispatched_utc": "2026-09-19T00:00:45Z",
        "reported_utc": "2026-09-19T00:05:53Z",
        "worktree": "/home/justin/hakux-work/wt/tier81fix",
        "asked": "#81's tier-1 promotion fix and #90's dead anti-churn preprocessor, as two "
                 "changes measured separately.",
        "resolved": "ALREADY FOLDED, and the lane refused to re-implement. rev-list "
                    "--left-right origin/master...HEAD prints 109 0 -- zero commits of the "
                    "branch outside master. Landed as 7dfa94c403 (#81 dedup on (pc, cs_base, "
                    "flags) plus exec_count reset) via fold 4d3edc563d. Two deviations from the "
                    "audit wording are documented in the commit: the budget charge moved to "
                    "tier1_maybe_promote() so a dedup hit is not charged, and the tb->tier latch "
                    "declined. Log tier81fix.20260919T000045Z.json, 34 turns.",
    },
    "stencil99": {
        "agent": "lane-stencil99/33f5cdba",
        "issues": ["99"],
        "dispatched_utc": "2026-09-19T00:01:02Z",
        "reported_utc": "2026-09-19T00:09:11Z",
        "worktree": "/home/justin/hakux-work/wt/stencil99",
        "asked": "#99: three ZERO captures regressed 0 -> 100,000 px between two shas.",
        "resolved": "#99 IS A DUPLICATE OF #75, which is itself a duplicate of #39. Not a "
                    "regression -- nondeterminism. Title byte-identical to #75, body empty, "
                    "opened 39 minutes after #39 was closed. Two of the three captures are in "
                    "#79's nine outright; the third (ZERO_DT) is in #79's own mechanism table, "
                    "and #79's nine is a lower bound on the unstable set, not a partition. "
                    "stencil_observable_79.py fires at BOTH shas the issue names, so the "
                    "sha-to-sha attribution does not hold. Verdict posted as "
                    "issuecomment-5737683005. No commits, no device, no build. Log "
                    "stencil99.20260919T000102Z.json, 66 turns.",
    },
    "blit83": {
        "agent": "lane-blit83/dcc482b0",
        "issues": ["83"],
        "dispatched_utc": "2026-09-19T00:00:56Z",
        "reported_utc": "2026-09-19T00:12:47Z",
        "worktree": "/home/justin/hakux-work/wt/blit83",
        "asked": "#83: eight Overlap_* captures each 1 px low on the SRCCOPY path, and the "
                 "control question for the BLEND_AND arm.",
        "resolved": "CONTROL SOUND BUT INERT, and #83's premise is a column misread. The folded "
                    "BLEND_AND work cannot reach SRCCOPY: the SRCCOPY branch (blit.c:60-65) last "
                    "changed in 24087af22a, 2026-01-15, an ancestor of every ref in play, while "
                    "#38's whole diff and #84's guards sit inside the BLEND_AND arm. So #38's "
                    "PASS of 2026-09-18 stands. But the eight captures' differing pixels are not "
                    "written by the blit at all, so the must_not_move leg reads unmoved whatever "
                    "the divide does: #83's blocker_falsifier is TAUTOLOGICAL. The lane also "
                    "corrected its own brief -- there is no #84 arm; the arm carrying the eight "
                    "is #38's blit38-blend-and-divide.json. Verdict posted as "
                    "issuecomment-5737707468. Log blit83.20260919T000056Z.json, 62 turns.",
    },
}

NOTE = ("board tick 2026-09-19T00:16Z: row reconciled against the live systemd unit and "
        "$HAKUX_WORK/logs/lane. lane.sh does not write a fleet row; the board job does, and "
        "the 00:00Z restart of six lanes left every row saying retired. fleet.py reads state "
        "only from here, so all eleven issues read as dispatchable.")

staged = {}
for name, meta in list(RUNNING.items()) + list(REPORTED.items()):
    path = os.path.join(D, name + ".json")
    row = {}
    if os.path.exists(path):
        row = json.load(open(path))
        prior = dict((k, row[k]) for k in ("asked", "state", "resolved", "dispatched_utc",
                                           "agent", "worktree") if k in row)
        row.setdefault("prior_attempts", []).append(prior)
    row["lane"] = name
    row.update(meta)
    row["state"] = "running" if name in RUNNING else "reported"
    row.setdefault("waiting_on", "")
    row["board_note"] = NOTE
    # A row the board writes is only useful if fleet.py can read it.
    assert row["lane"] and isinstance(row["issues"], list), name
    assert row["state"] in ("running", "reported", "folded", "retired"), name
    staged[path] = json.dumps(row, indent=2) + "\n"

# Validate every staged document parses back before touching disk.
for path, text in staged.items():
    json.loads(text)

if "--write" not in sys.argv:
    for path in sorted(staged):
        print("WOULD WRITE", path, len(staged[path]), "bytes")
    sys.exit(0)

for path, text in sorted(staged.items()):
    open(path, "w").write(text)
    print("wrote", path)
