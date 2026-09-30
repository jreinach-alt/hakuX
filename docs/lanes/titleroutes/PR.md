# titleroutes: sessions 39-41, three titles routed once both handhelds turned out to be free

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 2ba1a6e9a2
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/PR.md, docs/lanes/titleroutes/OUTBOX.md,
       docs/testing/titles/routes/galleon.route, docs/testing/titles/routes/burnout-revenge.returning.route,
       docs/testing/titles/routes/doa3.route, docs/testing/titles/targets.toml,
       docs/lanes/titleroutes/frames/burnout-revenge-replay-gameplay.jpg
Prediction: none: no arm (route validation + same-pass fps benchmark soaks, not A/B arms)
Needs device: yes -- three requests queued this session, results pending (see below)

## What this session found

Session 38's own work had already folded cleanly into `origin/master` as
`2c59b7bbba` before session 39 started -- not a failure recovery, a
routine continuation. Merged `origin/master` (fast-forward,
`39d518f9b6..2ba1a6e9a2`, no conflicts): brings in `lane.defecttriage433`'s
classification of the six titles blocking 0.5 Playable (analysis only, no
files of mine).

Sessions 39 and 40 found neither handheld had device work available (Nova
busy with a `lane.verdict433` confirmation soak / earmarked for Playable
confirmations; Thor's `lanelocal-fanwait` hold text reading "no queued
runs"). Both sessions ended correctly on a `waiting:` rather than guessing.
Cross-referenced `lane.routeprep`'s 24 offline route drafts against this
lane's adopted routes (9 still pending device validation, ranked by
evidence quality) while waiting -- detail in NOTES.md sessions 39-40.

## Session 41 update (resumed 13:34 PDT): both signals had resolved

Checked fresh rather than assumed: `dispatch/hold/thor.why` now explicitly
allows queued Thor requests <=480s (the owner's 12:30 PDT "Thor screening
program"), and the Nova has no hold, is idle, battery 38%. Worked
routeprep's ranked backlog in order:

1. **Galleon** (Thor+Nova): an earlier session had already driven a full
   interactive nav.py session on the Thor and left the emitted route
   unformalized in scratch/. Assembled it into `routes/galleon.route`,
   checked clean with `route.sh --check`, wired `targets.toml`. No
   interactive Thor session is available (fan still dead), so queued as
   the Thor screening program's combined validate+benchmark soak:
   `1790800614-titleroutes-1024666` (480s).
2. **Burnout Revenge** (Nova): `titlestate.py show` reported a profile
   "found" on the Nova disk, but Load Profile answered "There are no
   profiles to load" in-game -- the exact trap routeprep's pass-1 evidence
   predicted. Drove the rest interactively in a HELD Nova session
   (13:37-13:53 PDT, battery 38% -> 34%, released clean): Create Profile,
   an Autosave prompt, name entry, an empty profile slot, World Tour,
   Sunshine Keys, a Traffic Attack event, car select, a loading montage, an
   event brief, then live gameplay starting immediately at 70 mph. Several
   of routeprep's Burnout-3-derived guesses were wrong (corrected in the
   route's header). Player control confirmed two ways (a steer input
   changed the road section; the play pattern scored live Traffic-Check/
   Near-Miss events, $0 -> $14,550). **Replayed once unattended and it
   reached the same gameplay frame, then ran the event through to its own
   RESULTS screen within the extra window** -- this route is solid.
   Queued its same-pass benchmark: `1790801593-titleroutes-1202186` (480s).
3. **DOA3** (Thor): adopted routeprep's draft as-is -- the warning-wait and
   title-screen START are from real pass-1 frames, but the menu path past
   the title is recalled/guessed, not played. Queued as a Thor screening
   soak anyway, per that program's own design (a soak that fails to reach
   `mark gameplay` is itself the validation result):
   `1790801641-titleroutes-1213635` (480s).

Did not take a second interactive Nova hold this session (34% battery, 4
points of margin over the floor, and the queued benchmark will draw it
down further).

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks pass.
- `targets.toml`: parses with `tomllib` (Galleon, Burnout Revenge, DOA3 now
  carry a `route` key).
- `bash docs/testing/titles/route.sh --check` on all three new route files:
  clean.

## Device proof

- Burnout Revenge: interactive nav frames in
  `/home/justin/hakux-work/nav/burnout-revenge.returning-20260930T133805/`
  and unattended replay frames in
  `scratch/replay/burnout-revenge.returning-134524/` (not committed, local
  to the worktree); 640x480 copy of the replay's gameplay frame committed
  at `docs/lanes/titleroutes/frames/burnout-revenge-replay-gameplay.jpg`.
- Galleon: Thor screening soak `0-0-s-1790800614-titleroutes-1024666`
  landed during this session -- DONE, 265.6s gameplay, fps share at target
  9.88%, no crash/hang, not thermal-limited. Route validated:
  `route-frames/134228-gameplay.png` in the result dir shows the exact
  tutorial scene the route's header describes.
- DOA3: screening soak `1790801641-titleroutes-1213635` still running as
  of this push; its result dir (once landed) is the proof.

Release note (performance|stability|rendering|other|none): none -- this PR
touches only route data and lane bookkeeping, no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
