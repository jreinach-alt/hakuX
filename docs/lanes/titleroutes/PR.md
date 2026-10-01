# titleroutes: session 53 -- Castlevania: Curse of Darkness reaches gameplay on both variants (owner-approved one-time Nova session)

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ ec244430e3 (unchanged this session; no master movement to merge)
Files: docs/testing/titles/routes/castlevania-cod.first-run.route, docs/testing/titles/routes/castlevania-cod.returning.route, docs/testing/titles/targets.toml, docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: analysis/route-authoring only, no pixel-affecting arm
Needs device: no (device time for this title already spent this session; see below)

## What changed

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

No further device time taken or requested this session: the usage-budget
hold (reset 21:00 PDT) and the Thor CPU-stop decision are both still
standing for everything outside this one approved title. The next step for
Castlevania is an unattended `route.sh` replay of each variant (either
handheld; the ISO is on both) to move both routes out of DRAFT, then the
same-pass benchmark once confirmed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
