# titleroutes: session 57 -- Super Monkey Ball Deluxe confirmed on the Nova, a premark.py timing bug fixed

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 575c480d27 (session 56's fold; merged clean before this session's work)
Files: docs/testing/titles/routes/super-monkey-ball-deluxe.route, docs/testing/titles/targets.toml, docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md
Prediction: none: analysis/route-authoring only, no pixel-affecting arm
Needs device: no (device time for this title already spent this session; see below)

## What changed (session 57)

Per ADDENDUM 6 (lane.local, 16:50 PDT), the owner copied Super Monkey Ball
Deluxe (53450038) and Sonic Heroes (5345002B) to the Nova. Both already had
Thor-confirmed routes (sessions 46-48) but neither had ever been replayed
on the Nova. This session did Super Monkey Ball Deluxe only, as instructed;
Sonic Heroes is explicitly the next session's title.

Added `iso.nova` to both titles' `targets.toml` entries (factual: both
ISOs verified present on the Nova via `adb ls`).

**First replay attempt failed on a tooling bug, not the route.**
`scratch/premark.py` (my own scratch tool) sums every route `wait` line
once, in source order, with no account for an enclosing `repeat N { }` --
so a route whose pre-mark waits sit inside a 10x repeat loop (this one)
got a pre-mark estimate of 73s instead of the real 163s. The first replay's
own `timeout $((PRE+EXTRA))` killed it 5 of 10 START/A cycles short of
`mark gameplay`. Fixed `premark.py` to track a repeat-depth multiplier;
routes with no repeat before their mark (both Castlevania variants) are
unaffected (unchanged at 268s/213s), which is why the bug went unnoticed
through two prior sessions.

**Second replay, with the corrected timing, succeeded cleanly.**
`scratch/judge/super-monkey-ball-deluxe-165430/`: all 26 scripted frames
captured through all 10 START/A cycles, `mark gameplay` at 191.5s
(route.sh start) / 198.4s (launch intent) -- stage "1-1 SIMPLE", timer
counting down, 46 mph, score 0 -- then a `play` shot 11s later with a
different score (6286), a different timer reading, and a goal-clear
celebration pose: live, evolving play, not a frozen menu. This is the
first confirmation of this route with no thermal limit; both Thor runs
(sessions 47/48) heat-stopped at 48-51s of scored play.

`super-monkey-ball-deluxe.route`'s header updated from "DRAFT until a soak
replays it" to CONFIRMED (both devices, with paths/timestamps).
`targets.toml`'s note appended (not rewritten) with this session's finding
so the Thor history stays legible. Added a line to
`host-tools/nova-nominations.tsv` (a host file outside this repo, not part
of this PR) for `autoverdict.sh`'s own 600s Nova fps confirmation -- not
queued by this lane, per the brief.

Released the Nova hold (`titleroutes:1790898676`), restored rest state
(performance_mode=0, fan_mode=4, screen asleep, verified
`mWakefulness=Dozing`).

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py` -- all checks passed.
- `targets.toml` parses via `tomllib` (80 titles: the two new `iso.nova`
  keys don't change the title count).
- `bash docs/testing/titles/route.sh --check routes/super-monkey-ball-deluxe.route`
  -- route ok.

Release note (none): lane/testing-infrastructure data (routes, targets),
not emulator code.

No further device time taken this session beyond the one replay. Next
session's title is Sonic Heroes (ADDENDUM 6); its `iso.nova` key is already
added, but its own prior Thor run (session 48) landed on a frozen PAUSE
menu as its mark frame, so it needs a careful frame check, not a blind
replay -- see NOTES.md session 57 "State for a successor".

🤖 Generated with [Claude Code](https://claude.com/claude-code)
