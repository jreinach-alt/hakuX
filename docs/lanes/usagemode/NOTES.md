# lane.usagemode -- a meter and a mode switch for the account's weekly window

Issue #433 (0.5: 50 Playable). Branch `lane/usagemode`, base `origin/master`
(66bce0c222). OFFLINE PROTOCOL in force (GitHub suspended 2026-09-29): no PR,
no CI, no device. PR.md and OUTBOX.md carry what would have been posted.

## What was built

1. `docs/testing/jobs/usage/meter.py` -- the meter. Model-free, incremental
   (remembers a byte offset per transcript file), run by a 30-min systemd
   timer. Writes `$WORK/usage/state.json` and a one-line
   `$WORK/usage/summary.txt`.
2. `docs/testing/jobs/usage/mode.sh normal|low|auto|status` -- the switch.
   `tick` is a fifth, private entrypoint the timer calls; it is not part of
   the four the brief named.
3. `docs/testing/jobs/usage/units/hakux-usage-meter.{service,timer}` -- text
   only. lane.local installs these in `~/.config/systemd/user`; this lane
   does not touch host units.
4. `docs/testing/jobs/window.sh` -- the anchor, changed from Monday 00:00 UTC
   to **Thursday 21:00 America/Los_Angeles** (owner, 2026-10-02 10:10 PDT),
   computed with `zoneinfo` rather than a fixed UTC hour so it does not drift
   by an hour across the DST boundary. Nothing else in the file moved.
5. `docs/testing/jobs/selftest.d/88-window-budget.sh` -- its `SUN`/`WED`
   fixtures and the three `hits` blocks were tied to the OLD Monday anchor
   (comments said so explicitly: "95% through a Mon-anchored week", "opens
   at Sat 14:24Z under a Monday anchor"). Changing window.sh's default
   anchor silently changed what those fixed timestamps mean, so this file
   had to move with it or the suite's own gate on jobs/ would go red for a
   reason that has nothing to do with this lane's work. Recomputed against
   the new anchor (window opens 2026-09-23T18:24Z, Wed 11:24 PDT, 5.6 days
   into the week starting 2026-09-18T04:00Z) and verified against the real
   `window_check` output, not by hand -- see "the anchor change" below.
6. `docs/testing/jobs/selftest.d/89-usage-mode.sh` -- new, 47 checks, no live
   transcripts: every `~/.claude/projects` file it reads is one it wrote
   itself under its own `HAKUX_CLAUDE_PROJECTS`.

## Territory note (offline, no board row yet)

`origin/board:territory.toml` has no `[lane.usagemode]` row at all (checked
directly; this is a fresh dispatch). The brief's own "Territory requested"
line names `docs/testing/jobs/window.sh` and the new `89-usage-mode.sh`, but
not `88-window-budget.sh` -- touching it anyway is a direct, provable
consequence of the one file the brief DID name (its fixtures encode the old
anchor by date; there is no way to change the anchor without them going red
or being updated), so it is included in `Files:` rather than left broken.
No other open lane claims either file (checked `origin/board:territory.toml`
for `window.sh` and `88-window-budget` before touching them: both hits are
in a `[retired.*]` block, nothing live). lane.local reconciles the row when
folding.

## The meter: actors, the week window, and what cannot be seen from here

Actor rules (`classify_dir` in meter.py), derived from the real directory
names under `~/.claude/projects` on this host (not guessed):

    *-board-wt              -> board
    *-wt-cloud-<anything>   -> cloud          (cloud.sh's audit/remediate worktrees)
    *-wt-<name>             -> lane:<name>
    the bare orchestrator checkout (...-hakuX) -> hostops, if the first user
        message starts "FOCUS --" or "OVERRIDE (" (hostops.sh's own brief
        markers); interactive otherwise
    anything else                              -> not scanned at all

That last row is deliberate, not an oversight: this only scans transcripts
that look like hakuX work. Everything else this host's Claude Code use
touches (other projects, and the owner's own claude.ai web use, which never
appears in `~/.claude/projects` at all) is invisible to this file BY
CONSTRUCTION. That is exactly why the calibration exists, and why it is
framed the way it is below.

### The calibration gap the brief asked to be stated plainly

The two seeded readings (owner, 2026-10-02 10:10 PDT) imply very different
weekly dollar capacities when run through this file's own spend-at-reading
numbers:

| reading | instant (PDT) | this fleet's spend from that week's start to the reading | implied capacity |
|---|---|---|---|
| 92% | 2026-09-30 22:40 | $7,581 | **$8,241/week** |
| 16% | 2026-10-02 10:10 | $612 | **$3,823/week** |

**2.2x apart.** Both numbers are real (computed by running meter.py against
this host's actual transcripts once, to seed the two points -- see "numbers
measured on the host" below), and the gap is not a bug in either reading:
it is the owner's own non-harness claude.ai use being a different share of
the account's week each time, which this file has no way to measure
directly. The estimate therefore uses **the most recent calibration point's
capacity, not an average** -- recency is the only information available
about which share is current, and averaging two readings that already
disagree by more than 2x would blend two different unknown ratios into a
number with no claim to being either. `calibrate PCT` appends a new point
computed the same way (this fleet's own spend since the current week's
start, divided by PCT/100) and does not touch the two seeds; each new
reading the owner takes narrows the estimate without needing a restart.

### Numbers measured on the host, 2026-10-02 (real transcripts, one real run)

Spend since the live reset (2026-10-01 21:00 PDT), `~/.claude/projects`
scanned for real, aggregated by actor (dollar figures and model names only,
per the brief's "never print or copy anything from transcripts" instruction):

    $656 total; top actors: lane:routedriver2 $122, hostops $69,
    lane:titleroutes2 $61, lane:routerca433 $53, lane:pathknow $38
    83,679 priced assistant messages matched a hakuX-relevant directory
    rate over the trailing 6h: ~$67/h
    estimated_percent (16% seed's capacity): ~17%
    projected_percent_at_reset at that rate: ~290%

**That projection is the signal the brief's auto-mode rule exists to catch.**
At the measured 6h rate, this fleet is on pace to spend about 2.9x the
16%-seed's implied weekly capacity before the Thursday reset. Whether that
rate is a sustained pattern or a catch-up burst (several offline-protocol
lanes landing at once) is exactly the kind of thing `mode.sh auto`'s
threshold (`projected >= 100% -> Low`) is supposed to react to without a
person watching a dashboard -- it is not a test artifact, it is what the
tool found. The one-time run that produced these numbers, and the one
`calibrate` call made while developing the selftest fixtures, were cleaned
up afterward (`~/hakux-work/usage/` removed) so no test-generated state
ships ahead of the real timer.

### The week anchor: duplicated, not shared, and cross-checked

meter.py's `week_bounds()` computes the same Thursday-21:00-Pacific anchor
as `window.sh`'s `window_check`, independently -- there is no runtime
dependency between a Python module under `docs/testing/jobs/usage/` and a
bash function in `docs/testing/jobs/window.sh`, and importing one from the
other would create a cross-directory dependency neither lane owns outright.
`selftest.d/89-usage-mode.sh` sources `window.sh` and calls `meter.week_bounds`
directly, and asserts they agree on the week start for four instants,
including one on each side of the 2026-11-01 DST fall-back -- the same
cross-check `jobs/localtime.sh`/`localtime.py` already use for the display
zone, for the same reason: two independent implementations of one rule are
only safe if something keeps asserting they still agree.

### Incremental reads

`state["offsets"][path] = {size, mtime, actor}`. A file whose size and mtime
match the stored record is never opened. A file that only grew is
`seek()`ed to the stored byte and only the new tail is read and parsed. The
one unavoidable full read is the first time a file is seen at all -- on a
brand-new host, that is every relevant transcript, once; every tick after
that reads only what changed since the last one. Measured on this host: the
very first run (above) took under 10s against ~84k matching messages;
repeat ticks with nothing new were well under 1s. The two seeded calibration
points are read from that same first full pass (`ensure_calibration` runs
AFTER the scan and BEFORE the 8-day event trim), not from a second pass over
the same files -- an earlier version of this file did a dedicated backfill
scan per seed point and read the same transcripts three times over on the
very first tick; reusing the already-scanned events removed two of those.

### rate_1h vs rate_6h are both $/hour

`spend in the last 1h` is already a $/h figure by construction; `spend in
the last 6h` is NOT, and summary_line's first draft printed the raw 6h
total labelled "/h" -- a burn rate six times too high, caught only by
inspecting the real numbers (see "numbers measured" above, where the
printed total and a *recomputed* $67/h did not match before the fix). Fixed
by dividing the 6h total by 6 before it is stored anywhere; both figures in
`state.json["last_report"]` and in `summary.txt` are now the same unit.

## The mode switch

`mode.sh low|normal|auto|status`, one dial each (brief, Build item 2):

| dial | low | normal | mechanism |
|---|---|---|---|
| `LANE_MAX` | 3 | the value saved on the way into Low | `$WORK/limits.env`, `sed` in place |
| `MODEL_LANE_ESCALATED` | claude-sonnet-5 | saved value | same |
| `PATHFIND_MODEL_CALLS_MAX` | 20 (new dial) | removed if absent before, else saved value | same |
| every existing `$WORK/briefs/*.model` | overwritten to claude-sonnet-5 | restored byte-for-byte, or deleted if it did not exist before Low | files copied to `$WORK/usage/saved/models/` once, on the way in |
| hostops heartbeat | 2h -> 4h | restored | a systemd drop-in, same technique as `host-tools/overnight_mode.sh`'s own schedule change |

The snapshot (`$WORK/usage/saved/`) is taken **once per Low episode** --
re-entering Low while already low (a stray `mode.sh low`, or `tick` running
again before the next `normal`) does not re-snapshot over the real original
values with whatever Low itself set. Verified in the selftest by drifting
`LANE_MAX` to a third value *while* low and confirming `normal` restores the
value from *before* low, not the drifted one.

A lane with no `.model` override is not given one by Low (it keeps running
on `MODEL_LANE`, i.e. Opus, through `lane.sh`'s own default -- consistent
with the brief not listing `MODEL_LANE` as a Low dial: no lane but
lane.local's own starts new work in Low at all, so `MODEL_LANE` is never
read for a fresh start during that window).

### auto vs tick, and why there are two

The brief's CLI is four commands. The 30-min timer needs a fifth, private
one (`tick`): `auto` (typed by a person) means "I am explicitly putting this
back under automatic control, right now" and clears any manual lock before
evaluating; a timer that called `auto` every 30 minutes would silently clear
an owner's `mode.sh low`/`mode.sh normal` the very next tick, which is the
opposite of "never flaps ... until the reset or a manual mode.sh normal."
`tick` is a no-op whenever `source=manual`, and is what the shipped
`hakux-usage-meter.service` actually runs.

### What is NOT wired, named explicitly rather than claimed done

**"No new lanes started by anything but lane.local" is not enforced.**
`mode.sh low` writes `$WORK/usage/low-active` (one line, the reason) as the
signal, but the file that would have to read it -- `board.sh`'s capacity
gate -- is outside this lane's granted territory
(`docs/testing/jobs/usage/**`, `window.sh`, `88-window-budget.sh`,
`89-usage-mode.sh` only). The integration point is small and is spelled out
in OUTBOX.md for lane.local: three lines in `board.sh`'s gate, parallel to
how `window.sh`'s own `WINDOW_DEFER` is already read there.

**Device work, the dispatcher, autoverdict, the check-in report,
foldqueue** -- untouched, because nothing written here calls into any of
them. Confirmed by reading, not merely by omission: `grep -rl 'usage/mode\|usage/state' docs/testing/jobs/*.sh` outside this lane's own files returns nothing.

## What the next lane should not repeat

- **Export `HAKUX_NOW`, don't just set a shell variable.** The first draft
  of `89-usage-mode.sh` built all its fixture timestamps as offsets from a
  fixed instant (`UM_NOW`) but never `export`ed it, so `meter.py`'s own
  `os.environ.get("HAKUX_NOW", ...)` fell through to the real wall clock.
  Every check still happened to pass or nearly pass, because this sandbox's
  simulated "now" is itself 2026-10-02 -- which made the bug look like
  rounding noise (a ~7-point mismatch in one derived check) rather than the
  wrong clock entirely. Fixed by `export HAKUX_NOW="$UM_NOW"` once, and
  `unset HAKUX_NOW` at the fragment's end so later fragments keep the real
  clock they expect.
- **A per-hour rate check against a formula that multiplies it by ~1000x
  needs a loose tolerance, not a tight one.** `rate_6h` is stored rounded to
  2dp; `hours_left/capacity*100` in this fixture's numbers is a ~960x
  multiplier on it, so 2dp rounding alone produces single-digit-percent
  disagreement against a recompute from the rounded fields. The check
  recomputes from the SAME rounded fields the report exposes (not from
  private unrounded internals) and widens its tolerance accordingly, with
  the amplification factor stated in a comment -- a tight tolerance there
  would be testing float formatting, not the formula.
- **window.sh's anchor defaults are read by other fragments' fixtures, not
  just by window.sh's own logic.** `88-window-budget.sh` hardcoded instants
  and called them "95% through a Mon-anchored week" in a comment; the
  comment was the only thing that made the coupling visible. Re-derive
  fixture instants from the real `window_check` output (`HAKUX_NOW=... ;
  window_check; echo "$WINDOW_FACTS"`) rather than by hand arithmetic --
  this lane did both and they agreed, which is the only reason the 50
  checks in that file are trusted here rather than merely hoped to be
  right.

## Local verification (no CI, no device: offline protocol)

- `docs/testing/jobs/selftest.d/89-usage-mode.sh` in isolation
  (`SELFTEST_ONLY=89-usage-mode`): **47 passed, 0 failed**, twice in a row
  (determinism check after the HAKUX_NOW fix).
- `docs/testing/jobs/selftest.d/88-window-budget.sh` in isolation, after the
  anchor-change fixture update: **50 passed, 0 failed** (unchanged count
  from before this lane -- the fixtures moved, the coverage did not shrink).
- Full `docs/testing/jobs/selftest.sh` (no shard, no `SELFTEST_ONLY`): see
  the run logged alongside this file / PR.md for the final pass/fail count
  against the whole suite, including the fragments this lane did not touch.
- No device: this brief has no arm (`Prediction: none` in PR.md).

## Dials (all in `$WORK/limits.env` or `$WORK/usage/`, none in a commit)

    WEEK_ANCHOR=Thu              (was Mon)
    WEEK_ANCHOR_HOUR=21          in WEEK_ANCHOR_TZ, NOT UTC any more (was 0, UTC)
    WEEK_ANCHOR_TZ=America/Los_Angeles   new
    PATHFIND_MODEL_CALLS_MAX=    new; set to 20 by Low, otherwise lane.pathfind's own default applies
