# titleroutes: session 59 -- fixed castlevania-cod.first-run's name-entry timing race, flagged a stale-ref confirmation

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 4f37bdfbc7 (session 57's fold; merged clean before this session's work)
Files: docs/testing/titles/routes/castlevania-cod.first-run.route, docs/testing/titles/routes/sonic-heroes.route, docs/testing/titles/targets.toml, docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: analysis/route-authoring only, no pixel-affecting arm
Needs device: yes -- a verification already queued (`1790903439-titleroutes-1317193`, Nova, route check), not a background task of this session's

## What changed (session 59)

Read the Castlevania first-run route-check from ADDENDUM 8/9
(`1790902028-titleroutes-1005086`, Nova) and found it FAILED differently
than the addendum expected: `castlevania-cod.first-run.route`'s
letter-typing step (`press A` on the highlighted "A" tile, right after
the Name Entry screen opens) raced the screen's own load. The frame taken
right after that press (`174838-name-a.png`) shows the name field still
EMPTY, unlike the identical step in the original interactive nav.py
session that authored this route (`003-name-a.png`, field shows "A"
typed). Every frame after that in the dispatch run is the same Name Entry
screen with an unacceptable empty name -- the save creation, cutscene and
`mark gameplay` the rest of the route assumes never happened, and the
registry's stored save for 4B4E002D (`53f0a40fe626`) is unchanged by the
run, confirming no save was created.

Fixed (`castlevania-cod.first-run.route`): made the letter-type step
self-healing -- press A on the "A" tile twice, a few seconds apart (the
cursor stays on "A" after a successful type, so a redundant second press
just yields "AA" instead of breaking anything), plus a larger initial
margin before the first attempt.

**Verification queued, not yet landed**: `1790903439-titleroutes-1317193`
(`request.sh --device nova --hard-pin --route castlevania-cod.first-run
--seconds 900`, ref `e7eee5688d`, tagged as a route check per ADDENDUM 8).
It queued behind the already-running Sonic Heroes confirmation and had not
started by the time this session ended. Next session reads its result
before anything else (see NOTES.md).

**Also flagged** (not touched, no fix needed from this lane): the Sonic
Heroes Playable confirmation (`1790902215-autoverdict-1078702`, still
running at session end) is building from `ref=575c480d27`, which predates
session 57/58's fold of the route rewrite -- it's running the OLD 9-cycle
route. Its mid-run frames already show the known frozen-PAUSE failure
(`180609-gameplay.png` / `181308-play.png`, 7 minutes apart, byte-identical
pause screen). This is a fold-timing gap (nominate-before-fold queues
against stale master), not a route defect -- it needs re-nomination after
sessions 57-59 fold, not a third route rewrite. Recorded in OUTBOX for
whoever reviews it.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py` -- all checks passed.
- `targets.toml` parses via `tomllib` (80 titles).
- `bash docs/testing/titles/route.sh --check docs/testing/titles/routes/castlevania-cod.first-run.route` -- route ok.

Release note (none): lane/testing-infrastructure data (routes, notes), not
emulator code.

No specific next title named by a new addendum; absent one, the next
session reads the two open request results (see NOTES.md "State for a
successor"), finishes the Castlevania first-run/base-name/nomination work
per ADDENDUM 8, then Super Monkey Ball Deluxe's post-mark stage-select-menu
fix (ADDENDUM 9 item 2), then the still-open backlog (13 Nova-only
no-route titles; the Thor's untouched titles remain blocked on the
fan/CPU-stop decision).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
