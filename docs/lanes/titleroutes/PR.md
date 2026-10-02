# titleroutes: session 60 -- build the real waitfor/press-until fix (ADDENDUM 11) for castlevania-cod.first-run

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 4f37bdfbc7 (session 57's fold; merged clean before this session's work)
Files: docs/testing/titles/route.sh, docs/testing/titles/waitfor_match.py, docs/testing/titles/waitfor_selftest.py, docs/testing/titles/routes/castlevania-cod.first-run.route, docs/testing/titles/routes/sonic-heroes.route, docs/testing/titles/routes/refs/castlevania-cod.first-run/name-entry-header.png, docs/testing/titles/routes/refs/castlevania-cod.first-run/name-field-empty.png, docs/testing/titles/routes/refs/castlevania-cod.first-run/selftest/field-black.png, docs/testing/titles/routes/refs/castlevania-cod.first-run/selftest/field-empty.png, docs/testing/titles/routes/refs/castlevania-cod.first-run/selftest/field-typed.png, docs/testing/titles/routes/refs/castlevania-cod.first-run/selftest/header-black.png, docs/testing/titles/routes/refs/castlevania-cod.first-run/selftest/header-empty.png, docs/testing/titles/routes/refs/castlevania-cod.first-run/selftest/header-typed.png, docs/testing/titles/targets.toml, docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: analysis/route-authoring only, no pixel-affecting arm
Needs device: yes -- a verification already queued (`1790905334-titleroutes-1780552`, Nova, route check), not a background task of this session's

## What changed (session 60)

Session 59's fix (below) was wrong: the owner's own verification run
(`1790903439-titleroutes-1317193`) showed both presses of the "self-heal"
landing on a still-black, not-yet-loaded screen (`181831-name-a.png` and
`181838-name-a2.png`, both black), not a single dropped press. The owner
stopped that run (ADDENDUM 11, 2026-10-01 ~18:30 PDT) and asked for a route
that looks at the screen before pressing into it, for every title, not
another guess at this one.

Built it: `route.sh` gained `waitfor <name> <timeout_s> <x,y,w,h>
<threshold>` and `press-until <BTN> <name> <max_n> <gap_s> <x,y,w,h>
<threshold>` steps that poll a screencap region against a committed
reference crop (`docs/testing/titles/waitfor_match.py`, PIL+numpy mean abs
diff over a grayscale downscale) instead of a fixed `wait`, and ABORT the
route (`ROUTE FAIL ...`, a frame kept) rather than typing blind. The
existing grammar is unchanged -- all 58 pre-existing `.route` files still
pass `route.sh --check` byte-for-byte, and a `ROUTE_DRY=1` run of the
rewritten route shows the new steps falling through cleanly.

Proved the comparator against the exact failure before spending any device
time: `docs/testing/titles/waitfor_selftest.py`, 5/5 cases, using committed
fixture crops under `routes/refs/castlevania-cod.first-run/selftest/`
(including the real still-black frame from the withdrawn run). Also ran
`waitfor_match.py` directly against the real failed-run frames: the black
`name-a2.png` scores 102.9 NOMATCH, the loaded `name-start.png` scores 2.9
MATCH against a threshold of 15 -- the fix would have caught exactly what
session 59 missed.

Re-authored `castlevania-cod.first-run.route`'s newgame -> Name-Entry
section (the only section with diagnosed evidence of a race; the rest of
the route is unchanged) to `waitfor` the Name Entry screen before pressing,
then `press-until` the letter and check the field itself (up to 5 presses,
1.5s apart) instead of a fixed wait and a guessed press count.

**Verification queued, not replayed live** (ADDENDUM 11's own sequencing,
ADDENDUM 8's disk-state reasoning still holds -- only a dispatch rebuild
reproduces the no-save disk state this route targets): `request.sh --who
titleroutes --title 4B4E002D-Castlevania_Curse_of_Darkness.xiso.iso
--device nova --hard-pin --route castlevania-cod.first-run --seconds 900
--ref 1f23c068f0 --no-expect "route authoring check, no Playable verdict
expected"` -> `1790905334-titleroutes-1780552`. Next session reads its
result before anything else (route-frames, frame by frame, not the exit
code or mark alone).

## What changed (session 59, carried forward)

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
- `python3 docs/testing/titles/waitfor_selftest.py` -- 5/5 cases passed.
- `targets.toml` parses via `tomllib` (80 titles).
- `bash docs/testing/titles/route.sh --check <f>` over all 58 `docs/testing/titles/routes/*.route` files -- all ok, no regression from the new grammar.
- `ROUTE_DRY=1 bash docs/testing/titles/route.sh docs/testing/titles/routes/castlevania-cod.first-run.route` -- runs cleanly through both new steps and the rest of the route (killed by the dry run's own short timeout, as expected; not a route failure).

Release note (none): lane/testing-infrastructure data and route-player
tooling (route.sh, routes, refs, notes), not emulator code.

Next session reads `1790905334-titleroutes-1780552`'s result first
(route-frames, frame by frame). If it reaches real play and creates a
save: the base-name run (ADDENDUM 8 step b), then nominate `castlevania-cod`
(not the variant name). Then: Super Monkey Ball Deluxe's post-mark
stage-select-menu fix (ADDENDUM 9 item 2), Sonic Heroes' play-loop fix
(ADDENDUM 10), then the still-open backlog (13 Nova-only no-route titles;
the Thor's untouched titles remain blocked on the fan/CPU-stop decision).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
