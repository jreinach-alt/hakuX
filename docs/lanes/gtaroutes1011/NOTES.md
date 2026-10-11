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
