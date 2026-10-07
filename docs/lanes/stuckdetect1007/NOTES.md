# lane.stuckdetect1007 -- a stuck/menu detector for the pathfind hold (#433)

Owner order 10-07 14:10 PDT: "make these improvements so we're not burning runs stuck in a menu
or a corner." Three Nova runs on 2026-10-07 each burned 30-40 min of the Nova stuck where the
existing hold-play checks (`docs/testing/titles/pathfind.py`, `hold_play`) did not catch it:
Arx Fatalis (view pressed to a wall), Cel Damage (car against a canyon wall), Gui Yi (the genre
loop walked back into a merchant NPC and reopened its shop for ~1700 s).

Territory for this lane: `docs/lanes/stuckdetect1007/**` only. No edits to `pathfind.py`
(lane.pathfind's file) or `drive.py` (lane.local's file); the integration points this module is
built for are named exactly in `OUTBOX.md`, for lane.local to grant. No device time was used or
needed: everything below is read-only replay of stored frames already on disk.

## What was built

`stuckdetect.py` (standalone module, no pathfind/classify import):

- `frame_signature(path)`: a coarse grey-level grid (16x12, the FPS-overlay corner masked) plus
  an 8-bucket grey histogram. Needs PIL/numpy.
- `sig_distance`/`near_identical`: two zero-model distances between signatures (grid: mean abs
  grey diff; histogram: half the L1 distance), both plain-tuple operations -- no image decode.
- `is_stuck(history)`: **near-identical for >= 4 consecutive kept samples = stuck.** This is the
  headline fix: every consecutive pair in the trailing window must be near-identical, not just
  the window's first and last sample.
- `menu_stuck(history, states, shed_states)`: the same trailing-run test, further gated on every
  look-state in that window being `menu`/`pause`/`other` (pathfind's `HOLD_SHED_STATES`).
- `distinct_views(history)`: a whole-hold greedy clustering count. Implemented and reported, but
  **not used as a gate** -- see "What this module cannot see" below for why.
- `stuck_step(history, genre, rung, states, shed_states, unstick_ladder, fallback_ladder,
  max_rungs)`: the hook. Returns `{"stuck": False}` or a dict with the next unstick rung's tokens
  (or `abort: True` once every rung has been tried). It takes the genre's own unstick ladder as a
  parameter rather than hardcoding a second copy of `pathfind.HOLD_UNSTICK`, so the two cannot
  drift apart (see OUTBOX.md).
- `StuckWatch`: an optional thin stateful wrapper (history/rung bookkeeping) around `stuck_step`,
  for a caller that would rather feed samples in than manage the ladder itself.
- `validate`: replays the stored hold runs below and reports pass/fail; skips (never fails) when
  PIL/numpy or the run dirs are absent, since both are host-local, not CI-portable.

## Why "all consecutive pairs", not "first vs last"

The existing offline check (`hitch_report.position_change`/`position_fail`, run after the hold by
`title_verdict.py`) already does two things: first-vs-last, AND a share of consecutive sample
pairs that changed (`POSITION_STILL_BAR=0.5`: fails if over half the pairs show no change). Arx
Fatalis still got through it. Its route-frames drift slowly -- the camera jitters against the
wall, so no single step looks dramatic and not even half the pairs read "unchanged" by
`classify.motion`'s pixel-count bar -- but not one of those steps is real progress. A rule that
requires **every** pair in a trailing window to be near-identical (not a share, not the
endpoints) is strictly harder to satisfy by jitter, and `stuckdetect.py`'s own selftest encodes
this exact shape as its mutant-driven regression test (see below).

## Validation: must-flag vs must-not-flag, on stored frames

`stuckdetect.py validate` replays `route-frames/*.png` (pathfind's `route_frame()` hardlink, the
same post-mark window `hitch_report.position_change` scores) for the hold's kept-frame cadence.
Run dirs: `/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/<id>`. Table (GRID_BAR
7.0, HIST_BAR 0.05, STUCK_MIN_SAMPLES 4):

| run | want | frames | flagged at sample # | distinct views | longest stuck run |
|---|---|---|---|---|---|
| Arx Fatalis (n-44430002-1007) | FLAG | 25 | 9 | 8 | 7 |
| Cel Damage (n-45410011-1007) | FLAG | 33 | 10 | 28 | 5 |
| Gui Yi (n-58500001-1007) | FLAG | 65 | 21 | 12 | 16 |
| Indigo Prophecy (n-4947007B-1007) | clear | 39 | -- | 31 | 2 |
| Blade II (n-41560005-1007) | clear | 40 | -- | 31 | 3 |
| Capcom vs SNK 2 EO (n-43430008-1007) | clear | 47 | -- | 47 | 1 |
| Future Tactics (n-43560007-1007) | clear | 18 | -- | 18 | 1 |
| Mortal Kombat: Armageddon (armageddon1006d) | clear | 19 | -- | 19 | 1 |
| Fight Club (fightclub-1006) | clear | 24 | -- | 24 | 1 |
| Blowout (blowout-val2) | clear | 18 | -- | 5 | 2 |
| NBA Live 2004 (nbalive04-1006) | clear | 16 | -- | 16 | 1 |
| Call of Duty 3 (cod3-1006b) | clear | 17 | -- | 17 | 1 |
| Rogue Trooper (sweep-5343000E) | clear | 17 | -- | 12 | 2 |
| Ratatouille (sweep-54510109) | clear | 17 | -- | 17 | 1 |
| World Soccer Winning Eleven 9 (sweep-4B4E002F) | clear | 17 | -- | 13 | 2 |

Every must-flag run flags; every must-not-flag run stays clear. The 3 explicitly-named runs
(Indigo Prophecy, Blade II, Capcom vs SNK 2) plus every other `n-<tid>-1007` run and every
non-`1007` banked Playable with a `route-frames` window I found on disk from `pm/playable-
accepted.tsv` (read-only) are included -- 11 clear runs beyond the 3 the brief named. Two banked
Playables from `pm/playable-accepted.tsv` (`spikeout-hold`, `panzer-dragoon-hold3`) predate
`route_frame()` (added 10-03) and have no `route-frames/` window on disk; `validate` reports them
`unmeasured` rather than guessing from `frames/`, the same way `hitch_report.static_window_
unmeasured` treats a window it cannot read.

### Threshold search and the margin

Swept `GRID_BAR` in [5, 9] x `HIST_BAR` in [0.03, 0.08] x `STUCK_MIN_SAMPLES` in [3, 6] against
the table above. `GRID_BAR` in [6, 8] (any `HIST_BAR` in that range) cleanly separates every
run at `STUCK_MIN_SAMPLES=4`: shortest true stuck run measured 5 (Cel Damage), longest incidental
run on a must-not-flag run measured 3 (Blowout, a dark hangar patrol -- see below), a 2-sample
margin. `GRID_BAR=9.0` (pathfind's own `SIG_MATCH`, "the same menu screen" for its replay
matcher) is too loose here: Blowout's frame-to-frame grid distance sits at 8.7-9.3 for several
steps in a row (slow movement, low contrast), enough to false-trigger a 4-sample run at that
bar. **`GRID_BAR=7.0`** (middle of the clean range) is what ships. `HIST_BAR` did not matter
anywhere in [0.03, 0.08] on this data; kept at 0.05 as a second, independent signal in case a
future title's grid distance alone is ambiguous (e.g. a palette swap with near-identical
luminance).

`STUCK_MIN_SAMPLES=4` matches the brief's own number and needed no change once `GRID_BAR` was
tightened off pathfind's looser bar.

### Blowout: the closest false-positive risk, and why it's safe

Blowout patrols a dark hangar (`pm/playable-accepted.tsv`, 2026-10-06: "FAIL on the static-window
check only... a dark hangar... patrolling in place accepted as gameplay by the owner"). At
`GRID_BAR=9.0` it produced a 4-sample stuck run (a false `stuck_abort` on an owner-accepted
Playable); at `GRID_BAR=7.0` its longest run is 2. This is the real-world case the brief's rule
("bias thresholds toward not flagging... a false stuck_abort costs a Playable") is about, and
it is the reason the threshold search above is reported with its margin rather than a single
number asserted by feel.

## Distinct views: implemented, not a gate

Item 4 of the brief asks for a distinct-view-count minimum "so a wall-pressed run no longer
passes position on a lucky first/last pair." Measured over the whole scored window, the count
does **not** separate must-flag from must-not-flag on this data: Cel Damage (a must-flag run)
measured 28 distinct views, overlapping Indigo Prophecy (31), Blade II (31) and Capcom vs SNK 2
(47) -- all must-NOT-flag. The reason is that a hold is not just "stuck or playing": menu visits,
results screens and cutscenes elsewhere in the SAME hold (Cel Damage's checks include `menu`,
`results` and `cutscene` states, not only `gameplay`) add distinct-looking frames with no
relation to whether the player ever got anywhere, so a whole-hold diversity count answers a
different question than "is the trailing window stuck."

Per the brief's own instruction ("if no thresholds separate them, say so plainly and report the
overlap rather than fitting"): no `distinct_views` minimum is used as a gate. The count is still
computed and returned (and shown in `validate`'s table above) as a diagnostic -- useful context
for a human reading `result.json` -- but the gate that actually gets a wall-pressed run out of
"passed because of a lucky first/last pair" is the trailing-run `is_stuck`/`menu_stuck` test
described above, run continuously through the hold rather than once at the end.

## Why HOLD_SHED did not fire again for Gui Yi

`hold.jsonl` for `n-58500001-1007` (65 kept-frame rows, 279 total rows) shows exactly one `shed`
event: `n=67, hold_s=565.2, shed="B"`. From there, 229 more `check` rows read `menu` (vs. 5
`gameplay`), spanning roughly hold_s 565 to 2261 (~1700 s, matching the brief's figure) -- A
tried 124 times, START 67 times, B 39 times, none of them escaping. Reading `hold_play`'s shed
condition (`if off and was_play and st in HOLD_SHED_STATES`): `was_play` is computed from the
PREVIOUS cycle's `off` flag, so the condition is only true on the single frame play flips to
off. Once off-play persists across checks (as it did here, continuously, for the rest of the
hold), `was_play` is false on every later check and a second shed can never fire, no matter how
many more menu checks happen. One shed per excursion into off-play is the most this mechanism can
ever contribute.

That would still be enough if the ONE shed picked the right button -- but the row data suggests
the shop was not opened by a fixed loop button in the first place: the genre loop's own `STICK:
up` walk (visible in the pre-shed rows) put the player back at the merchant's position, and `A`
(the model's chosen escape input in 124 of 235 checks) is also the shop's own "select/confirm"
button, which inside an open shop buys or selects rather than closing it. Shedding `B` (the first
`HOLD_SHED` token present in the loop) removed one candidate but not the one actually responsible
for re-entering the shop's trigger zone. A button-shed cannot fix a menu that reopens from
movement, not a press; this module's `menu_stuck`+ladder (`stuck_step` with `menu=True` prefixes
`B` to whatever positional rung the caller supplies, which for a "team"/"other" genre with no
`HOLD_UNSTICK` entry falls back to a few single buttons) does not solve that either on its own --
it only guarantees the hold does not spend another 1700 s finding out. The real fix for Gui Yi's
specific shop-proximity trigger is outside this module's scope (it would need a "walk away N
steps" positional retreat before resuming the loop, which `OUTBOX.md` names as a candidate follow-
up, not something this module invents unasked).

## What this module cannot see (do not claim it)

- **The Puyo Pop case** (lost a match, then story dialogue played): a scene-not-changing check
  cannot catch it, by construction -- each dialogue line draws a new text box/portrait, so
  consecutive frames are NOT near-identical even though none of them is play. No stored run for
  this title exists on disk to replay (checked: no `*uyo*` run dir under lane.pathfind's runs),
  so this is a structural limit stated from the mechanism, not a measurement. Catching it needs
  a content-aware state signal (what `hold_look`'s state answer already is), not a frame
  signature; this module does not attempt it.
- **A menu that reopens from movement, not a button** (Gui Yi, see above): `menu_stuck` detects
  that the player is stuck in a menu; it does not diagnose why the loop keeps re-entering it, and
  shedding a button is the only reaction this module (or pathfind's existing `HOLD_SHED`) has.
- **Distinct-view count as an independent signal**: see above -- implemented, reported, not
  gated, because it does not separate on this data.

## Selftest

`docs/lanes/stuckdetect1007/stuckdetect.py selftest`: 20 synthetic-signature checks (no image
decode, no PIL/numpy import required to pass -- `frame_signature` is never called), covering
`near_identical`, `is_stuck`, `menu_stuck`, `distinct_views`, `stuck_step` (ladder rungs, the
fallback ladder, the menu `B`-prefix, abort past the ladder) and the "drifting wall" fixture a
first-vs-last-only rule would clear but this module's trailing-run test does not.

`docs/lanes/stuckdetect1007/95-stuckdetect.sh` (the selftest.d-shaped leg, staged here per
territory until lane.local grants the move): runs `selftest`, runs `validate` (shown, not gated,
except on an actual separation failure), and two source mutants (python3 `str.replace`, the
`84-perf-regimen.sh` technique) that must each turn `selftest` red:
1. the fix removed outright (`stuck_run` always returns 1): caught (several checks fail/error).
2. the weaker rule reinstated (first-vs-last only, `hitch_report.position_fail`'s own shape):
   caught specifically by the drifting-wall check.

Verified locally against a harness shim reproducing `selftest.sh`'s `ok`/`bad`/`check` contract
(the real `docs/testing/jobs/selftest.sh` run itself needs an approval this session could not
grant itself; the shim exercises the exact same sourced leg file with the same function
contracts). `python3 docs/lanes/stuckdetect1007/stuckdetect.py selftest` and `... validate` were
also run directly and pasted above.

## Not done in this lane (by brief, and by territory)

- `pathfind.py`/`drive.py` are not edited. `OUTBOX.md` names the exact integration points for
  lane.local to grant.
- No Nova smoke test queued: the Nova is Playable-only until 7 are banked today and holds lane.
  pathfind's own queued hold; nothing here needed device time to validate (it is pure offline
  frame replay), so none was requested.
- No board files touched.
