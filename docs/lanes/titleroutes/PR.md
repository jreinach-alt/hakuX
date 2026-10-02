# titleroutes: session 62 -- Castlevania withdrawn/handed to lane.routedriver; Sonic Heroes and Super Monkey Ball findings stand; no device work available tonight (#397)

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 8e3b1f2ad2 (merge of origin/master into this branch, carrying session 61's own fold plus localjobs/litcompile569/forzadecay414)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: notes/status update only, no route or targets.toml edit this session
Needs device: no -- the Nova is currently running another lane's request and the Thor stays closed to title gameplay (dead fan); nothing of this lane's own is queued

## What changed (session 62)

Resolved session 61's `waiting:`: `1790918365-titleroutes-76920` (the
Castlevania `waitfor` verification queued at the end of session 61) came
back `WITHDRAWN`. The owner read it directly and cancelled the whole
Castlevania line of work ("ADDENDUM 13 (owner, 10-01 ~22:45 PDT)" in the
brief): the route died at `route.txt:73` because the dispatched run's
`refs/` directory had no copy of the `name-entry-header` reference crop,
so the app looped the intro video for the rest of the window (confirmed
directly from `WITHDRAWN.txt`, `run.log`, and `result.json`'s
`frames.count=0` -- not re-derived from the addendum's prose alone).
Castlevania's input-sequencing now belongs to `lane/routedriver`; this
session did not touch `castlevania-cod.first-run.route` or queue any
further Castlevania run, per the owner's explicit instruction.

Flagged a harness-side gap in OUTBOX rather than fixing it here (out of
`routes/**`/`targets.toml`, so out of this lane's files): a `waitfor`
step's reference crop is committed next to its route, but nothing stages
a copy of it into the per-run `refs/` directory the dispatcher's `route.sh`
snapshot reads, so `route.sh --check` can prove a route parses without
proving its crops resolve once dispatched -- which is how this run got
661s into a 900s hard-pinned Nova slot before failing.

Re-checked Sonic Heroes and Super Monkey Ball Deluxe (the other two items
the owner's addendum named as this lane's "remaining work, in order");
both were already finished in session 61 before that addendum was
written, with terminal findings (Sonic Heroes: loop fix committed, not
confirmed to advance past an in-level geometry obstacle; Super Monkey
Ball: Stage Select reads no stage-selection input at all, an input-layer
finding flagged for a tracked-issue decision, not a route bug). Nothing to
add on either this session.

**No device work this session.** `dispatch/running/*.owner` shows the Nova
running another lane's request (`lane.collapse433`) right now, so it is
not free; the Thor stays closed to all title-gameplay work (dead fan,
unchanged). Even once the Nova frees up, tonight's owner-granted allowance
for it was scoped to Sonic Heroes/Monkey Ball re-checks (done) plus
`lane/routedriver`'s own Castlevania need, not a blanket grant for the
13-title Nova-only backlog from session 51's "State for a successor",
which stays blocked on the same device-role-split/queue-depth question.

Ending this session on `blocked:`, not `waiting:`: nothing of this lane's
own is queued or running, and the two things that would unblock the next
batch (a general-Nova-session decision, or the Thor's replacement fan) are
external and already named in OUTBOX.

## Why session 61 didn't pick up where session 60 left off

Session 60 queued a Castlevania `waitfor` verification and ended cleanly
(committed, PR ready, pushed). That verification came back `WITHDRAWN`
(ADDENDUM 12): the dispatcher's own `route.sh` snapshot still predated the
`waitfor` grammar session 60 built, so the run parsed-failed and sat idle
for 904s. ADDENDUM 13 confirmed the branch had folded (`0f07dbfede`) but
the checkout (`/home/justin/hakuX`) had not yet been fast-forwarded, and
told this lane to re-check both preconditions itself before re-queueing,
and to spend this session on two OTHER open items that don't depend on it
(ADDENDUM 9, ADDENDUM 10) while waiting.

Re-checked at the start of this session: checkout was 11 commits behind
`origin/master` and the dispatcher's `route.sh` snapshot had 0 `waitfor`
occurrences -- still unmet. So this session did ADDENDUM 9 and ADDENDUM 10
first, as directed.

## What changed (session 61)

**Sonic Heroes (ADDENDUM 10, owner's fix).** Rewrote
`routes/sonic-heroes.route`'s post-mark loop to hold `axis LY min`
continuously -- no LX swings, `A` only occasionally for a jump -- exactly
per the owner's instruction. `route.sh --check`: ok.

Replayed it on the Nova (`scratch/replay.sh`, foregrounded via the Bash
tool's own backgrounding + a Monitor watch on the output file, not a
session-ending wait). It reaches `mark gameplay` and the first ~10s
genuinely advance (score 60->80, rings 006->008), confirming the loop
fix removes the old route's aimless wandering. **But it does not confirm
advance through the whole window**: from clock ~01:02 onward, Team Sonic
is pressed against a stone riser in the level geometry and stays there
(score/rings frozen) for the rest of the ~2 minutes I observed. I drove
the still-live app by hand afterward (it was still running after the
scripted replay ended) and tried 5 more input combinations -- an attack
press, a held jump, a running jump with a backed-off start, and a
backoff-and-turn -- none reliably cleared the obstacle; one combination
freed the team into an open junction but a different approach just led
back to the same obstacle from another angle.

**Not nominating this route.** It's committed because it's strictly
better than the old wandering version and matches the owner's explicit
instruction, but `targets.toml`'s note says plainly that whole-window
advance is unconfirmed, with the exact clock offset and a description of
what a stuck frame looks like, so a successor doesn't have to rediscover
it. Checked whether lane.hitchwatch's new `static_window` check (now
folded, see below) would quietly let a stuck confirmation through: no --
this particular stuck state has a genuinely frozen camera (unlike the
Monkey Ball case below), so `static_window` would likely catch it if a
confirmation were run against it, which lowers the risk of an accidental
false PASS somewhat, but doesn't make the route fix unnecessary.

**Super Monkey Ball Deluxe (ADDENDUM 9) -- turned out not to be a route
bug.** Before writing a new post-mark loop, drove a fresh game live on
the Nova to understand why the existing loop's `press A` + `axis LX`
swings never got the game back into a stage after a death. Found: a
fresh game reaches stage 1-1 directly (no Stage Select before the first
stage), and a plain held-forward input cleared it in ~15s (`GOAL!!`,
confirming "hold forward" genuinely works when the track allows it). The
stage-clear screen then lands on Stage Select with the cursor ALREADY
correctly on the next unlocked stage -- the same screen the original
rejected confirmation sat frozen on for 10 minutes.

From there, 9 separate live input attempts against that screen -- `A`
(tap, held+released, repeated), `B`, the D-pad, the analog stick held
hard in one direction for 2+ seconds, and explicitly zeroed axis values
-- produced **no change at all**: the cursor never moved and the screen
never advanced. `START` was the only input that did anything (opened the
in-game pause popup), which rules out a focus-loss explanation (also
confirmed directly via `dumpsys input`: focus and the focused window both
correct) and proves input generally reaches the app. `logcat` around this
period shows no ANR, no save-in-progress, normal frame rendering at
44-59fps -- just a game that isn't reading stage-selection input on this
screen. This also re-explains the original rejected confirmation's
frames: the same stage stayed highlighted the whole 10 minutes with only
the idle camera rotating, which I'd misread (before this session) as "the
LX swings moved the cursor to a locked stage" -- the swings never moved
the cursor at all, on either run.

**No route redesign can fix a screen that isn't reading stage-selection
input**, so I have not changed `super-monkey-ball-deluxe.route`.
`targets.toml`'s note records the finding precisely. Flagged in OUTBOX
for a decision on whether this is worth a tracked issue -- it's outside
this lane's remit (adjacent to/inside the input-handling stack, not
`routes/**`/`targets.toml`). Super Monkey Ball Deluxe stays nominated at
stage-1-1-only (unaffected, since stage 1-1 never needs Stage Select);
going further is blocked on this finding, not on the route.

**Checked lane.hitchwatch's fold** (merged in via the fast-forward from
`origin/master`, `56c2a7b4a9`): `title_verdict.py` now computes
`hitch_report.find_hitches`/`report` over the scored window and fails a
run on hitches past the owner's bar (per-title override via
`hitch_allowance`), plus a whole-window `static_window` check. Read
`static_window()`'s logic against the Monkey Ball Stage Select frames
already on disk: it compares every post-mark frame to the window's FIRST
frame, and the Stage Select screen's idle camera rotation means most
pixels DO move some over 10 minutes, so `frozen_frac` likely lands under
the fail bar even with zero actual progress -- `static_window` would
likely NOT have caught this case by itself, confirming a route/input fix
(not a verdict-side check) is the right place for it.

**Checkout caught up mid-session.** By the time the above was done,
`/home/justin/hakuX` had been fast-forwarded (the dispatcher's `route.sh`
snapshot now has `waitfor`) and the fold was confirmed live on
`origin/master`. Committed and pushed this session's work (`c7aae3bf5c`),
then queued session 60's still-pending Castlevania verification:
`request.sh --who titleroutes --title
4B4E002D-Castlevania_Curse_of_Darkness.xiso.iso --device nova --hard-pin
--route castlevania-cod.first-run --seconds 900 --ref c7aae3bf5c
--no-expect "route authoring check, no Playable verdict expected"` ->
`1790918365-titleroutes-76920`.

## Local checks (session 61, still valid -- no route/targets.toml edit this session)

- `python3 docs/testing/titles/titlestate_selftest.py` -- all checks passed.
- `targets.toml` parses via `tomllib` (80 titles).
- `bash docs/testing/titles/route.sh --check docs/testing/titles/routes/sonic-heroes.route` -- ok.

Release note (none): lane/testing-infrastructure data and notes, not emulator code.

Next session: re-check `dispatch/running/*.owner` for the Nova and the
Thor-fan decision before taking any hold. Do not queue or drive
Castlevania (now `lane/routedriver`'s). Sonic Heroes' in-level obstacle and
the Super Monkey Ball Stage Select input finding are both terminal for
this lane unless a new idea or a decision arrives from outside it. The
13 Nova-only no-route titles and the Thor's 300+ fan-blocked titles are
unchanged and listed in NOTES.md "State for a successor".

🤖 Generated with [Claude Code](https://claude.com/claude-code)
