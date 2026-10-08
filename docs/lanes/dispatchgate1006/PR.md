# dispatchgate1006: a generated title registry and one admit() gate between "decide to run it" and a handheld (shadow mode); a fix counts only when recorded against the gate it answers
State: ready

Lane: dispatchgate1006            Issue: none (harness defect, dispatched directly)
Base: master @ 6cef37f426
Files: docs/lanes/dispatchgate1006/NOTES.md, docs/lanes/dispatchgate1006/OUTBOX.md, docs/lanes/dispatchgate1006/PR.md, docs/lanes/dispatchgate1006/owner-holds.seed.tsv, docs/lanes/dispatchgate1006/patches/hold.sh.patch, docs/lanes/dispatchgate1006/patches/hourly_report.sh.patch, docs/lanes/dispatchgate1006/patches/pathfind.py.patch, docs/lanes/dispatchgate1006/patches/pathfind_selftest.py.patch, docs/lanes/dispatchgate1006/patches/request.sh.patch, docs/lanes/dispatchgate1006/patches/title_verdict.py.patch, docs/lanes/dispatchgate1006/title-fixes.template.tsv, docs/lanes/dispatchgate1006/tools/live_incidents.py, docs/lanes/dispatchgate1006/tools/make_patches.py, docs/lanes/dispatchgate1006/tools/verify_patches.py, docs/testing/dispatch_audit.py, docs/testing/dispatch_gate.py, docs/testing/dispatch_gate_selftest.py, docs/testing/jobs/selftest.d/99-dispatch-gate.sh, docs/testing/title_registry.py
Prediction: none: no arm (harness tooling; no emulator change, no device run)
Needs device: no    Needs NDK: no

Release note: none. This PR changes no emulator code.

The owner's order of 10-06 ~16:50, after four wrong dispatches in one day: nothing reaches a
device unless a gate has checked the title and the run against the project's own records.

**What it adds.**
- `title_registry.py` builds `pm/title-registry.tsv`: one generated row per canonical title id
  (951 rows).
  - It **recomputes every gate from the verdict's values**, never from `failing`. DOA3's `failing`
    reads "menu time"; its fps miss (0.4394) is in `failing_all`.
  - Identity is the title id. A name-only record resolves only by exact normalised name against the
    device listings, owner library, inventory and xemu's canonical ids. All 32 ledger rows resolve;
    AMF Xtreme (42530014) is not the ledger's AMF Bowling 2004 (42530009).
- `dispatch_gate.py admit()` denies by default. Five classes x eight statuses decide.
  - A fix answers a failed gate only through a row of `pm/title-fixes.tsv` (lane.local's) or a
    change to the title's own path file. A commit that is merely newer than the verdict is not a fix:
    `fix:6cef37f426`, an unrelated fold, is a regression fixture that denies DOA3. A below-bar title
    never gets a Playable attempt. Its fix allows TELEMETRY or VALIDATION, and a verdict after it
    that clears the bar comes first.
  - Owner holds come from `pm/owner-holds.tsv` (seeded from the memory notes and briefs) and
    `host-tools/blocked-titles.txt`; an owner-order id there is the only override, and the process
    environment is never read.
  - Issue states come from the local forge over HTTP, never `gh`. If the forge is unreadable, the
    issue holds stay active.
  - Run-level checks: APK read back against `dispatch/builds/<sha>.apk`, the libfolders and #583
    build floors, the Thor's 480 s cap, the 21:15 window, a recorded input sequence, a valid end,
    declared env, staging, plan order, and a request `title_id` that disagrees with its ISO.
  - Every decision is a row of `pm/dispatch-log.tsv` with an HMAC token.
  - `plan_check` rejects plan rows that do not resolve, are not eligible, or say "folded" with no
    commit and no verdict after it.
- `dispatch_audit.py` is the 24-hour review: ungated runs, refusals, and Nova minutes on flagged
  titles.

**Call sites** are patches in `docs/lanes/dispatchgate1006/patches/` (request.sh, hold.sh take,
pathfind intake + selftest leg, title_verdict.py `failing_all`, the hourly report). All are
verified by `tools/verify_patches.py`. The gate is in **shadow mode** until lane.local writes
`pm/dispatch-gate.mode`.

| check | result |
|---|---|
| `dispatch_gate_selftest.py` (incident fixtures, each with a mutant that must flip it) | 59 legs, 59 green |
| CI harness fragment `99-dispatch-gate.sh` | 4 passed, 0 failed |
| today's incidents against the real records (`tools/live_incidents.py`, scratch registry) | DOA3, Dino Crisis 3, RalliSport, Strike Force, Tron/NGB/Amped 2/Spider-Man 2, NFL Blitz Pro, NBA 2K3, AMF Xtreme, Marvel: DENY; DOA3/Hulk UD/LOTR ROTK citing `fix:6cef37f426`: DENY; Blowout VALIDATION: ALLOW |
| `plan-check` on the 10-06 evening and replan plans | rc 2; 7 of 7 and 14 of 14 rows rejected, each with a reason |
| host registry, rebuilt | 951 rows; Fight Club PLAYABLE (flicker UNCHECKED); RalliSport EXCLUDED |
| `verify_patches.py` | all six patches apply; hold.sh shadow takes and logs, enforce refuses (exit 3) |
| `preflight.sh --allow-tracker` | passed |

Findings, not-machine-checkable rules and the enforcement order are in NOTES.md and OUTBOX.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
