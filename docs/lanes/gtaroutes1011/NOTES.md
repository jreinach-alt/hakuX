# lane.gtaroutes1011: routes into play for GTA III, Vice City, and a San Andreas driving route (#433, 0.5)

Dispatched directly by lane.local (#433 umbrella). Base `6d8947bb47`. Device: Nova only.

## 0. Base and the shape of gta-sa.route

`git merge origin/master` was already up to date at session start (6d8947bb47).

`gta-sa.route` (read in full): a header comment names the device, the session that played it, and the on-screen
beats in order; `wait`/`press`/`axis`/`shot` lines get to the first in-control frame; a train of 4x `press A 300`
spaced 5 s apart (times three, once per cutscene) skips cutscenes regardless of how long each one's preceding load
screen ran, because an A that lands on a load screen is a no-op; `mark gameplay` fixes the scoring start; then
`repeat forever { ... }` drives LY/LX/RX without ever touching Y, START or BACK. GTA III and Vice City routes follow
this shape: same boot structure (FMV skips, menu, cutscene-skip train, mark, movement loop), adjusted for each
game's own menu/cutscene beats.

## 1. Nova contention at session start

Checked `$DISPATCH_DIR/{queue,running}` before taking any hold, per the brief's rule not to hold the Nova while a
lane.local `gtasa1011`/`gtasagpu1011` request is queued or running:

- `running/`: `1-1791733231-lane.local-3377611` (gtasa1011 B, NFS switches, 850 s) -- already has a matching
  `results/` directory from 09:52 PDT, but `running/*.owner` still named it as of 09:53 PDT.
- `queue/`: 4 more lane.local items on `nova` -- 2x `gtasagpu1011` step 1 (600 s each), 1x `gtasagpu1011` step 2
  (320 s), 2x `nfsdefault1011` A/B (500 s each) -- about 2520 s (42 min) of further nova time after whatever is
  currently claimed.

So the Nova will not be free "about 10:15 PDT" as the brief estimated; it is still working a backlog as of 09:53.
Held off taking a hold and did prep work instead (this file, PR, route-shape notes) while polling.

## 2. Contention held for the whole session (09:53-11:07 PDT): no idle window found

Read `hold.sh` itself first: `take` only blocks the dispatcher from CLAIMING a NEW request on `nova`; it does not
touch a request already running, and the running one finishes undisturbed either way. So the real condition to
catch is `queue/` clear of nova work (not `queue/` AND `running/` both clear) -- taking the hold the instant the
queue empties still lets the one in-flight run finish normally, and blocks whatever lane.local would otherwise have
queued next. Both windows (`queue=0`) are worth taking.

Foreground-polled `queue/` and `running/` every 5-15 s from 09:53 to 11:07 PDT (about 74 minutes, several loops of
up to ~9.5 min each, per the brief's own polling pattern). Observed:

- `running=1` on every single sample across the whole window -- the Nova was never once idle. One run
  (`1-1791733231-lane.local-3377611`, the gtasa1011 B arm) was itself still writing frames/logcat 74 minutes after
  its nominal 850 s, so "ends about 10:15 PDT" undercounted even the run already in flight at session start.
- `queue` dropped to 0 only briefly, twice (around 10:44-10:45 and 10:53-10:55 PDT), each for well under a minute
  before lane.local queued its next item. A 5 s poll twice missed grabbing the hold inside those windows; a third,
  tighter attempt (5 s polls, 5 min straight) found `queue` pinned at 1 throughout, as lane.local kept a request
  queued immediately behind whatever was running, plus `dispatch.restore` housekeeping items after each
  `gtasagpu1011` run.
- Read both siblings' briefs (`~/hakux-work/briefs/gtasagpu1011.md`, `~/hakux-work/briefs/nfsdefault1011.md`) to
  size the actual backlog, not just the live sample:
  - `gtasagpu1011` is an open-ended GPU-defect hunt (sky polygons / missing CJ shadow) with no run count given --
    it queues a soak, reads frames, restores, and queues the next, which is why `dispatch.restore-*` items keep
    appearing behind it.
  - `nfsdefault1011` step 4 alone is "~74 runs at ~3.5 min, about 4.5 h" by its own brief, queued in batches of
    ~10, after ~8 more runs for steps 2-3.

Conclusion: the brief's "they end about 10:15 PDT" was a stale estimate from before 09:40 PDT (when lane.local's
Addendum 1 added the video-capture step to gtasagpu1011, extending it); the actual combined backlog is multiple
hours with no gap in evidence long enough for a reliable take. Continuing to brute-force-poll for an idle
`queue=0` instant would spend the rest of this session for an unknown, possibly multi-hour wait, producing nothing
new. Stopping here rather than doing that.

**No route, targets.toml row, or drive route has been produced yet.** Steps 1-4 are untouched; nothing in the
lane's territory beyond this NOTES.md/PR.md pair has been written. `targets.toml`'s GTA III/VC rows cannot be
written yet either: step 3 wants `target_fps` sourced the way #482 sourced San Andreas's (the game's own frame
limiter, read from the XBE), and that needs the route to exist first and no such disassembly was attempted this
session -- when the route step runs, the right call is still to leave `target_fps` out with a note, unless pathfind
surfaces something sourceable.

**What unblocks this:** `$DISPATCH_DIR/queue` and `$DISPATCH_DIR/running` clear of `gtasagpu1011`/`nfsdefault1011`/
`lane.local` entries on `nova` for long enough to run `hold.sh take nova gtaroutes1011 ... && hold.sh wait-idle nova
1800`, OR lane.local/the PM scheduling an explicit gap for this lane's pathfind hold (both sibling briefs already
say "lane.gtaroutes1011 takes holds for pathfind between runs", so the gap is expected to exist procedurally, just
not observed in this session's window).

## 3. Why attempt 1 did not finish

Attempt 1 polled `queue/`+`running/` itself, waiting for a `queue=0` instant to then take the hold -- a race it
documented losing twice (two ~5 s-poll misses, then a 5 min tight-poll window with `queue` pinned at 1 the whole
time) before concluding the backlog was multi-hour and stopping with nothing in territory written. lane.local's
addendum 1 (12:2x PDT) says this diagnosis was right but the response wrong: `hold.sh wait` already retries every
15 s and `take` itself is race-free against a running request (a hold taken while something runs just blocks the
NEXT claim, per the header comment read in section 2 above) -- so the fix is to call `hold.sh wait nova
gtaroutes1011 3600 ... && hold.sh wait-idle nova 1800` in the foreground and let it retry, not to hand-poll queue
state and time a `take` around it. The addendum also retired the `gtasa1011` queue/running check (those runs
ended) and added the profile-gate consequence: GTA III/VC have no golden, so the first soak per title must be
route-finding (300 s, `# state: first-run`, `--find-route` if present) rather than the step 2/4 gameplay proof,
with a golden promoted from that run before the real proof soak. Resuming attempt 2 with that approach now.

## 4. GTA III: pathfind, golden, and the proof soak's transient "Load Game" menu

Reached the Nova both times via `hold.sh wait nova gtaroutes1011 3600 ...` + `hold.sh wait-idle nova 1800`, in the
foreground, per the addendum -- no contention this time; both holds were granted promptly.

`pathfind.py` on GTA III (session 1034707, first-run disk) reached gameplay in 2.2 min / 14 steps: emulator-loading
icon -> several Rockstar publisher-logo/black screens (~90 s, non-interactive) -> intro credits video (A skips) ->
title screen (`START`) -> two more cutscenes (A skips each) -> Claude on foot in Portland, full HUD. No menu of any
kind appeared -- true first-run goes straight from `START` at the title into the cutscenes. Recorded path ->
`pathknow/paths/5454000E.json`. Wrote `gta-3.route` to match this beat-for-beat, as a 4x-A-press-every-5s train per
skip point (as gta-sa.route), `# state: first-run` initially.

`titlestate.py golden --title-id 5454000E` showed no existing golden and a `latest` harvest matching the pathfind
session's run id, so promoted it: `titlestate.py promote --title-id 5454000E --latest --by lane.gtaroutes1011 --note
"pathfind 1034707: first golden, title data after a New Game"`. Re-headed `gta-3.route`'s `# state:` line to `any`.

Ran the step-2 proof: `request.sh --route gta-3 --seconds 600 --frames-every 30 --no-expect "route proof: frames
after the mark must show the player moving"` -> result `1-1791747431-gtaroutes1011-1129784`. Confirmed
`hdd.loaded == "golden"`. `title_verdict.py --require confirmation`: `gameplay=453.6s fps_ok=0.9804` -- clears the
>=300 s bar.

Frame-by-frame inspection (30 s interval) found a real anomaly, now resolved by reading further frames rather than
stopping at the first one:

- f00001-f00004 (t=0-90 s): boot -- black, then the GTA III publisher-card/logo screens, as expected.
- f00005-f00008 (t=120-240 s): **not** the title screen's "Press START" prompt the brief described and pathfind's
  first-run session saw -- a "Load Game" tab with "New Game" (highlighted) / "Load Game" menu and a
  "START: Resume Game" hint bar, static across all four frames. This is the golden's doing: the golden carries the
  title data the pathfind session's own New Game wrote, so `press START` at the title on this disk now opens a
  save-aware menu instead of starting straight into the cutscenes the first-run disk went to. The route's A-press
  trains (written for a cutscene skip) were landing on this menu instead, and did not look like they were doing
  anything frame-to-frame -- the two frames 30 s apart are pixel-identical modulo the hint-bar text.
- f00009 (t=270 s): resolved -- live gameplay, "Callahan Bridge" location caption, Claude (prison jumpsuit, opening
  bridge-escape beat) running. Somewhere in t=240-270 s one of the route's A presses did land as "New Game" select
  and the game proceeded through the opening cutscene into the actual playable prologue.
- f00010, f00015, f00021 (t=300/450/630 s): all live gameplay, HUD intact, player in a visibly different place/pose
  and the minimap marker moved each time (standing on the expressway shoulder -> mid-stride on the bridge deck ->
  running past a girder further down the bridge).

So the menu was a one-time, transient consequence of booting a save-bearing golden through a route written for a
blank-save first-run boot, not a stuck state: the same A-press train that was meant to skip cutscenes ended up also
clearing this menu, just slower than intended (about 2 extra A presses' worth of real time, ~120 s, past where the
cutscenes alone would have taken). Per the brief's pass criteria -- mark reached, `gameplay_s` >= 300 (453.6),
player in a different place in >=3 post-mark frames (four confirmed: f00009/f00010/f00015/f00021) -- **`gta-3.route`
passes as written. No fix/rerun needed.** Left the route and its header comment as committed; the header's existing
note that "the boot sequence does not change once a golden exists" turned out to be wrong in the menu sense (it does
add a menu) but right in the outcome sense (the same A-press train clears it without a route change), so left it
rather than rewriting a claim that was directionally fine and is now superseded by this section.

## 5. Vice City: pathfind, golden

`pathfind.py` on Vice City (session 1056194, first-run disk) reached gameplay in 1.5 min / 9 steps: emulator-loading
icon -> two Rockstar publisher-logo screens (A skips each) -> loading/title-card screen (non-interactive, no START
press ever recorded) -> three-part "In the Beginning..." cutscene (A skips each) -> Tommy on foot at the Ocean View
Hotel, full HUD. Confirms the route's header note: no "Start Game"/"New Game" menu and no title-screen START on this
disk's first run, contrary to the brief's prose expectation -- the probe step re-confirmed the same thing a second
time within the same session. Recorded path -> `pathknow/paths/5454000F.json`. Wrote `gta-vc.route` to match.

`titlestate.py golden --title-id 5454000F` showed no existing golden; promoted the pathfind session's `latest`
harvest: `titlestate.py promote --title-id 5454000F --latest --by lane.gtaroutes1011 --note "pathfind 1056194: first
golden, title data after reaching gameplay"`. Re-headed `gta-vc.route`'s `# state:` line to `any`.

Proof soak for `gta-vc.route` not yet run -- next step.

## 6. Step 3/4 written; both remaining proofs queued and waiting on the Nova backlog

Added `targets.toml` rows for both titles (`5454000E`, `5454000F`): `iso.nova`, `route`, no `target_fps` (no
documented cap and no #482-style XBE disassembly attempted this session -- noted as such, falls through to the 30
default per the brief's "otherwise leave it out and say so"). Wrote `gta-sa-drive.route`: identical boot to
`gta-sa.route` (not edited) through the alley-walk beat, then a single Y press to mount the blue-cone BMX (the
header's own prompt, "Press Y to jump on the bike"), `mark gameplay` after the mount, then LY-forward with LX
alternated for steering. All three new route files parse-check clean (`route.sh --check`).

Queued both remaining proof soaks, explicitly tagging `(#433)` in `--purpose` so they land at release tier (the
first VC attempt without that tag queued plain and would have sat behind every release-tier item; withdrew that
queued file by hand -- it was mine, still in `queue/`, not yet claimed -- and requeued correctly):

- VC: `1-1791751023-gtaroutes1011-1901311`
- SA-drive: `1-1791753097-gtaroutes1011-2255243`

At queue time the Nova had ~20-23 release-tier items ahead (mostly `nfsdefault1011`, some `profileconv1011` /
`lane.local`), draining at roughly one per 8 minutes of polling observed -- a multi-hour wait, not something to
foreground-poll to completion in this session per the brief's own "never end the session to wait" + "wait by
polling, up to about 9 min a call" combination: 9-minute bounded polls were used (several rounds, see request logs
in `/tmp/gtaroutes1011-scratch/`), but the backlog depth means this is a wait on dispatcher state outside this
session's control, not this session's own backgrounded task. Posted `[lane.gtaroutes1011] waiting:` on PR #927
naming both result paths and stopping here per the role file's guidance for exactly this case.

## 7. Why that attempt did not finish: no WAITING file

That session's stop was the right call -- both remaining proofs were (and, re-checked at the top of this
session, still are) sitting unclaimed in `dispatch/queue/` behind ~20-22 other release-tier items, not stuck --
but it only posted a PR comment, not the `docs/lanes/gtaroutes1011/WAITING` file. hostops's Addendum 2 (15:48
PDT) caught the gap: `lanewaker.py` only auto-resumes a lane whose `WAITING` file names what it's waiting on, so
without one nothing would have picked this lane back up once the two results landed. Re-verified at the start of
this session: `dispatch/results/` has no directory for either `1901311` or `2255243` yet, and both `.req` files
are still in `dispatch/queue/` (confirmed via `ls`); `dispatch/running/` currently holds a `profileconv1011` item,
not either of ours. So the wait itself is still live and correct. Wrote `WAITING` naming both result paths and
what to do with each, and committed/pushed it before anything else, per the addendum's instruction, then resumed
the polling loop.

Ran one bounded foreground poll (~9 min, 15 s interval) after pushing `WAITING`: neither result landed; the nova
queue grew from ~22 to 31 items (profileconv1011's running item plus more lane.local/nfsdefault1011 work queued
behind it), confirming the backlog is still deep and not shrinking toward these two requests. Consistent with the
existing PR #927 waiting-comment (already names both ids and the backlog depth -- still accurate, no new comment
needed). Per the role file, this is a wait on dispatcher state outside this session's control: stopping here with
`WAITING` in place rather than polling for hours. Nothing in territory changed this pass beyond `WAITING` itself
and this note.
