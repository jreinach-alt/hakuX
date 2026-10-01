# titleroutes: session 51 -- still blocked on the Thor's CPU stop; fixed the stale rank_untouched exclusion list

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ c071ae6e60 (origin/master merged this session; session 50's PR folded there)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: no arm (lane notes only; no device run this session)
Needs device: no new device time requested this session (blocked; see below)

## What changed

Notes only. No routes and no targets.toml changes this session (`scratch/` is
not in this lane's `Files:` and is not committed).

**Confirmed the Thor-screening blocker from session 50 is still open.**
`escalations.md` (10-01 05:13 PDT) and `dispatch/hold/thor.why` (UPDATE
10-01 05:09 PDT) show the owner has not yet decided whether to raise
`thor_coldconfirm.sh`'s `CPU_STOP_C=90`, require consecutive reads, or grant
a one-time one-copy-per-title exception to screen the six pending titles
(Castlevania, Gauntlet, Capcom Classics Vol 2, Plus Plumb 2, Petit Copter,
Sonic Heroes) on the Nova. hostops tried to reach lane.local directly and
found no session; the decision sits in `hostops-inbox.md` as the durable
record. Queued nothing new on the Thor.

**Found and recorded a process loss: the six titles' survey/screen
evidence from sessions 47-50 is gone.** Neither `dispatch/results/` nor
`~/hakux-work/nav/` has anything for `castlevania-cod`'s survey, Gauntlet's
survey, or any of the six session-49/50 request ids -- `dispatch/results/`
is pruned sooner than assumed, and none of those results were copied into
`scratch/judge/` before they went. The offline cycle-by-cycle frame walk
session 50 asked a successor to do (the same method that found Gauntlet's
START-during-gameplay trap) can no longer happen; those titles will need a
fresh screen once device time is available. Recorded in NOTES as a lesson:
copy a dispatch result into `scratch/` the same session it's read, not a
session later.

**Fixed `scratch/targeted_ids.txt`**, the exclusion list session 49's own
notes flagged as stale (it was re-surfacing already-routed titles as
"untouched" to `scratch/rank_untouched.py`). Cross-checked all 50
`title_id`s with `route = "..."` in `targets.toml` against the file: 5 were
missing (THPS3, Gauntlet, Sonic Heroes, Super Monkey Ball Deluxe, Family
Guy). Added those plus 3 mid-investigation titles with a bare
`targets.toml` entry but no route yet (Plus Plumb 2, Petit Copter, Bistro
Cupid), so they don't get re-surfaced either. Verified
`python3 scratch/rank_untouched.py` now lists 319 genuinely untouched
titles headed by Doom 3, Bicycle Casino, Monster Garage, and others -- no
already-routed titles in the output anymore.

**No device work.** The Thor stays off-limits under the open decision. The
Nova has no hold file, but neither the 09-26 21:10 PDT device-role split
(Nova = #462 only) nor a one-copy-per-title exception has been lifted, and
its queue still carries 30+ pinned #462/#474/#414/#569/#507 requests
(escalations.md). Taking a Nova session for title-pipeline work without
that exception would be making the owner's open decision myself, so none
was taken. 13 Nova-only titles needing no copy and still unrouted are
listed in NOTES for whoever next gets Nova time cleared for this work.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed.
- `targets.toml` parses (tomllib, 80 titles; unchanged).
- No harness files changed, so `docs/testing/jobs/selftest.sh` does not apply.

Release note (none): lane notes only; no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
