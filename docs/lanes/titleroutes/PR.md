# titleroutes: session 58 -- Sonic Heroes' route rewritten and CONFIRMED on the Nova

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 575c480d27 (session 56's fold; merged clean before this session's work)
Files: docs/testing/titles/routes/sonic-heroes.route, docs/testing/titles/routes/super-monkey-ball-deluxe.route, docs/testing/titles/targets.toml, docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: analysis/route-authoring only, no pixel-affecting arm
Needs device: no (device time for this title already spent this session; see below)

## What changed (session 58)

Per session 57's hand-off ("the next session does Sonic Heroes"): Sonic
Heroes (5345002B) had a known-flaky route (session 47 Thor screen: live
play; session 48 Thor re-screen, same route: a frozen PAUSE menu) from a
fixed 9-cycle START/A guess that raced the title's own variable boot
timing -- a START press during already-live play pauses it, and the old
route's single post-pause `A` never resumed it.

Rewrote `routes/sonic-heroes.route` from two nav.py observation sessions
instead of a cycle-count guess: one on a fresh Nova copy (no Game Data) and
one on the same disk after that session wrote game data to slot 01 (the
disk state the actual confirmation will find, per session 56's Castlevania
lesson that dispatch runs start from disk state, not nav state). Both
disk states need exactly one START and three A presses to reach Main Menu
(different intermediate screens -- Create-Game-Data vs. slot-select -- but
the same count and the same default-highlighted option each time), so one
route covers both. The fix for the pause trap: the route never presses
START again after the title screen, and waits out the ~85-90s post-team-
select cutscene with no input at all before `mark gameplay`.

**Replayed unattended, succeeded cleanly on the first attempt.**
`scratch/judge/sonic-heroes-171639/`: all 17 scripted frames captured in
order, `mark gameplay` at 17:21:33 (Seaside Hill, HUD live), then three
`play` shots over the next 28s with the score (60->80), ring count
(006->008) and timer all advancing and Sonic's pose/position visibly
different frame to frame -- live, evolving play.

`sonic-heroes.route`'s header updated from the prior coin-flip account to
CONFIRMED, with this session's evidence (old Thor history kept, not
deleted, so the trap stays documented). `targets.toml`'s note rewritten to
lead with the fix and confirmation. Added a line to
`host-tools/nova-nominations.tsv` (a host file outside this repo, not part
of this PR) for `autoverdict.sh`'s own 600s Nova fps confirmation -- not
queued by this lane, per the brief.

Released the Nova hold (`titleroutes:1790900058`), restored rest state
(performance_mode=0, fan_mode=4, screen asleep, verified
`mWakefulness=Dozing`).

Also carried forward from session 57 (same PR, never folded while GitHub
was suspended): `super-monkey-ball-deluxe.route`'s CONFIRMED rewrite and
the `premark.py` repeat-depth fix -- see NOTES.md session 57 for that
detail; nothing in this session touched Super Monkey Ball Deluxe further.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py` -- all checks passed.
- `targets.toml` parses via `tomllib` (80 titles).
- `bash docs/testing/titles/route.sh --check routes/sonic-heroes.route` -- route ok.

Release note (none): lane/testing-infrastructure data (routes, targets),
not emulator code.

No further device time taken this session beyond the one replay. No
specific next title was named by an addendum; absent one, the next session
should check for a new addendum first and otherwise continue down the
still-open backlog from sessions 56/57 (13 Nova-only no-route titles; the
Thor's untouched titles are all blocked on the fan/CPU-stop decision).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
