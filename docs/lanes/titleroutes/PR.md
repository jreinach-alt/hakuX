# titleroutes: session 56 -- Castlevania: Curse of Darkness's returning route CONFIRMED by an unattended replay

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 6b9fbe4093 (unchanged this session; already the fold-head when this session started)
Files: docs/testing/titles/routes/castlevania-cod.first-run.route, docs/testing/titles/routes/castlevania-cod.returning.route, docs/testing/titles/routes/castlevania-cod.route (removed), docs/testing/titles/targets.toml, docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: analysis/route-authoring only, no pixel-affecting arm
Needs device: no (device time for this title already spent this session; see below)

## What changed (session 56)

`castlevania-cod.returning.route` is now CONFIRMED by a full unattended
`route.sh` replay on the Nova (`scratch/replay/castlevania-cod.returning-145541`,
copied to `scratch/judge/`): all 19 scripted frames captured in order,
`mark gameplay` reached at 15:00:34.692, then ~28s of the repeat-forever
play pattern (visible attack animations) before the run's own PRE+EXTRA
timeout ended it cleanly. `movetest2.png`/the mark frame both show the HUD
(`Player HP 100/100`) with the character's stance shifted between them --
live control, not a static cutscene. `targets.toml`'s note and the route
file's own header are updated from DRAFT to CONFIRMED, and a line was added
to `host-tools/nova-nominations.tsv` (a host file outside this repo, not
part of this PR) for `autoverdict.sh`'s own 600s Nova fps confirmation --
not queued by this lane, per the brief.

**Correcting an intervening addendum's claim:** a 14:55 PDT addendum read
the *previous* replay attempt (`castlevania-cod.returning-144635`, from the
session before this one) as already successful, citing its last frame
(`loading3.png`) as the `mark gameplay` evidence. It wasn't: that run's own
`route.log` stops 10 scripted steps short of the mark (no
`movetest`/`movetest2`/`check1`/`loading6`), with only 4 of the route's 19
frames captured, and `loading3` is a shot taken *before* the HUD appears per
the route's own header. This session re-ran the replay properly (with an
explicit long timeout, monitored to completion rather than left to a
background task) before acting on that claim, so no route was nominated or
promoted on the strength of a run that never reached the mark. Full
comparison with log excerpts in NOTES.md session 56.

`castlevania-cod.first-run.route` is unchanged, still DRAFT: no unattended
replay has ever been attempted for it, and the Nova's Castlevania disk no
longer has a clean (no-save) state to replay it from (session 53's run
wrote a save to slot 1). Left as explicit open work for the next session
with device time on this title.

## Prior session's "What changed" (session 53, still accurate for what it covered)

The owner countermanded the 2026-10-01 06:15 PDT usage-budget no-resume hold
for this lane, for exactly one session: route Castlevania: Curse of Darkness
(4B4E002D) on the Nova (`<=300s`/`<=6` runs, hard-pinned). That session drove
the title by hand with `nav.py` and authored both variants:

- `castlevania-cod.first-run.route`: New Game's Name Entry keyboard needs an
  explicit `press START` to jump the cursor to Accept (`A` alone just types
  the highlighted letter); the save-creation prompt right after defaults to
  **No** (`axis LX min` onto Yes before `A`, or it declines its own save).
  Reaches a confirmed `mark gameplay`
  (`scratch/nav/castlevania-cod.first-run-20261001T141851/015-mark-gameplay.png`):
  player HUD 100/100 HP, gothic courtyard, gargoyle fountain, with a visible
  attack animation the frame after.
- `castlevania-cod.returning.route`: on a disk with slot 1 already filled,
  one `A` on the highlighted Continue only replays the recap cutscene and
  returns to the title with Continue still highlighted; a **second** `A`
  reaches LOAD HARD DISK -> slot 1 -> confirm -> the cutscene plays a third
  time -> the same courtyard, same confirmed mark frame pattern.

Both routes are real, frame-confirmed (nav.py interactive play, not a
dispatch soak), but **neither is yet confirmed by an unattended end-to-end
`route.sh` replay**, and their own in-file headers say so. This session's
one device action against the returning route was a 150s foreground replay
peek, cut short by a tight `timeout` (confirmed from `route.sh`'s own
TERM/INT trap writing the `end` log line, not end-of-file) well under
`premark.py`'s 268s pre-mark estimate for the file -- its five frames match
the interactive observations exactly (including the recap cutscene playing
a third time), so the first ~115s of 268s are now confirmed unattended too,
but the run to `mark gameplay` is not. Both stay DRAFT until that full
replay exists.

This continuation (picking the session back up after it ended improperly
mid-replay, waiting on what would have been a dead background task) also:
found and released a stray `dispatch/hold/nova` the original session had
taken (14:18 PDT) and never released; restored the Nova to its documented
rest state (performance/fan mode 0/4, screen asleep) since it had been left
at MAX (2/5); and wrote this PR, `NOTES.md`, and `OUTBOX.md` (the original
session wrote none of the three).

`targets.toml`'s Castlevania notes are rewritten to describe both routes and
their traps, and `route = "castlevania-cod"` is unchanged (the two variant
files are what `route.sh`/the dispatcher resolve by name). The old
never-replayed `castlevania-cod.route` (session 48's generic survey draft)
is removed, superseded by the two variant files above.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py` -- all checks passed.
- `targets.toml` parses via `tomllib` (80 titles, Castlevania's entry reads
  back as expected).

Release note (none): lane/testing-infrastructure data (routes, targets),
not emulator code.

Local checks re-run for session 56: `titlestate_selftest.py` all checks
passed; `targets.toml` parses via `tomllib`.

No further device time taken this session beyond the one replay. The
usage-budget hold (reset 21:00 PDT) and the Thor CPU-stop decision are both
still standing for everything outside this one approved title. The next
step for Castlevania is `castlevania-cod.first-run.route`'s own unattended
replay, which needs a clean (no-save) disk state first.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
