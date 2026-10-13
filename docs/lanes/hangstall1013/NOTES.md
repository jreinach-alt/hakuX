# lane.hangstall1013: notes

## The change

`docs/testing/hangwatch.py` now judges a HANG on either of two arms:

- `pinned` (unchanged): still + quiet + pinned, for `HANG_S` (90 s).
- `stalled` (new): still, and together `kicks0` ([hakuX-perf] fifoskew `kicks=0`: the GPU got no new push-buffer
  work), `idle0` ([rr425w] `idle_us` <= `IDLE_US`: the vCPU never idled -- the same idle half `pinned` already
  checked, without the pc-share test), and `discsilent` ([pic14] `raise=0`: no disc interrupt), all for `HANG_S`.

`Telemetry.feed` already parsed `idle_us` out of every `[rr425w]` line; `idle0` is derived from that, not a new
regex. `kicks0` and `discsilent` are two new regexes (`KICKS`, `RAISE`) fed per line in `scan_events`/`Watch.poll`,
joined to the other signals the same way `quiet` already was: each signal holds its last-seen value in a `state`
dict until its own next line updates it, so the three lines (`fifoskew`, `[pic14]`, `[rr425w]`) do not need a
shared window id. I checked this against the real logs (next section) before relying on it: `fifoskew`, `[pic14]`
and `[rr425w]` lines land every ~2 s, close enough in practice, and the state-holds-until-updated model is what
`quiet` already used for a line on its own independent cadence.

`Watch` now tracks `arm_start` (one start time per arm) instead of a single `start`; `_judge` checks both arms on
every relevant signal update and returns the first that has held `HANG_S`. `look()` reads which arm tripped from
the trip dict and re-checks that same arm after the one A-press probe, exactly as before. `start()`/`look()`/
`close()` keep their signatures; `pathfind.py` needs no change (confirmed by reading its three call sites,
`docs/testing/titles/pathfind.py:1705,1732,2121,2530`; not read on the live device since this lane has no device
and no grant for that file).

`scan()` keeps its `pinned`/`quiet`/`pinned+quiet` keys for `calibrate.py` (`docs/lanes/hangwatch/calibrate.py`,
outside this lane's territory; it only indexes those three keys and filters `events` on `s == "pinned"`, both
still exactly as before) and adds a fourth, `stalled`: the offline upper bound of `kicks0`+`idle0`+`discsilent`
together (no `still` check offline, same caveat as `pinned+quiet`). `scan`'s CLI output reports it alongside the
other three, per the brief.

Docstrings: the module and `Audio` docstrings now say "non-flat" instead of "non-silent" (matching the APU's own
`counted ... flat` terms) and spell out that a frozen title can keep driving the APU with a steady hum or looping
ambience forever -- non-flat, so its window count keeps climbing, so `quiet` never fires -- which is why `stalled`
exists. `quiet`'s own measurement is unchanged.

## Why fifoskew/[pic14]/[rr425w] join safely without a shared window id

Checked directly against Voodoo Vince's log (`$R/n-4D53005F-1013r/screen-logcat.txt`, lines 4042-4138, 10-13
14:22:53-14:23:05): `fifoskew` (tag hakuX-perf, I), `[pic14]` (tag hakuX, W) and `[rr425w]` (tag hakuX, W) each
appear once every ~2 s but at their own offsets (`:53.239`, `:54.186`/`:56.186`/..., `:54.713`/`:56.713`/...) --
three independent per-line cadences, not one shared window. `streaks()` only needs each signal's last reported
value to persist until replaced, which is exactly how `quiet` already worked against the audio line's own 5 s
cadence. No window-id join was needed or added.

## Measurement

`hangwatch.py scan` over the brief's three cases, after the change:

| run | pinned | quiet | pinned+quiet | stalled | HANG_S |
|---|---:|---:|---:|---:|---:|
| Voodoo Vince `n-4D53005F-1013r` | 2036 | 60 | 0 | **2035** | 90 |
| Die Hard `n-56560029-1011` | 0 | 0 | 0 | **261** | 90 |
| KOTOR II `n-4C410014-1011` | 0 | 5 | 0 | **2** | 90 |

Matches the brief's own figures for Voodoo Vince and Die Hard almost exactly (their table measured kicks0+idle0
only, a 2-signal subset; `stalled` adds the disc test on top and the numbers hold). KOTOR II's 106 s two-signal
stretch collapses to 2 s once `discsilent` is required, confirming the disc test is what tells its load apart from
the two freezes, as the brief's PC/disc breakdown already showed.

### Full scan: every file in scope

40 Nova `screen-logcat.txt` files (`find $R -maxdepth 2 -name screen-logcat.txt -newermt '2026-10-11 00:00' -size
+200k`) plus every run `pm/playable-accepted.tsv` names with a kept logcat (33 more `pathfind held run runs/...`
entries under `$R`, resolved by name; 18 dispatch-id entries with `dispatch/results/<id>/logcat.txt`) -- 81 unique
files after dedup (several Nova logs and banked-Playable evidence point at the same run). 19 of the 81 predate the
`[pic14]` telemetry (older dispatch/pathfind runs, `pic=0` greps) and so can never trip `stalled`, by the "unknown
never confirms" rule; none of those 19 are the freeze class this lane is for.

Only two files reach 30 s or more on the `stalled` arm, both already in the table above and neither a banked
Playable (`grep` of `pm/playable-accepted.tsv` for both title ids and names: no match):

- Voodoo Vince, 2035 s -- the freeze this lane started from.
- Die Hard: Vendetta, 261 s -- the other freeze the brief named.

Every other file -- all 40 Nova logs from 10-11 to 10-13, all 33 banked `pathfind`-held runs, all 18 banked
dispatch runs -- stays at 18 s or under on `stalled`. The single largest non-freeze value is 18 s
(`n-53430006-1013`, Conflict Desert Storm II; `result.json` calls it `"result": "gameplay"`, not a hang or a
timeout, so an 18 s stretch there is an ordinary loading or cutscene pause, not a near-miss). The next largest is
10 s.

**Margin:** 90 s (`HANG_S`) against the largest non-freeze stretch of 18 s is a 72 s margin, about 5x. `HANG_S`
stays 90; nothing in this scan asks for a change.

No banked Playable reaches `HANG_S` (or even 30 s) on the stalled arm. Nothing to put under `WAITING`.

## Selftest

`python3 docs/testing/hangwatch.py selftest`: 27 checks, all ok (14 pre-existing cases unchanged in substance, two
of them now phrased with `arm_start` instead of the old single `start`; 13 new cases for the stalled arm, using the
real line shapes from Voodoo Vince, Die Hard and KOTOR II, not synthetic numbers). Also green as the harness runs
it: `SELFTEST_ONLY=59-hangwatch docs/testing/jobs/selftest.sh` -> `1 passed, 0 failed`.

New cases: Voodoo Vince's shape trips `stalled` (and confirms `quiet` never holds, so only `stalled` catches it);
Die Hard's shape trips `stalled` despite a pin share far under `PIN_SHARE` (confirms `pinned` still misses this
class, same as the brief's PC breakdown); KOTOR II's load shape (kicks0, idle0, but the disc keeps raising) is not
a HANG on either arm; a log with no `fifoskew` lines never fires `stalled` even with idle0+discsilent both true; a
log with no `[pic14]` lines never fires `stalled` even with kicks0+idle0 both true. The pre-existing Whiteout case
still trips the `pinned` arm exactly as before (checked explicitly: `hang.get("arm") == "pinned"`).

## Mutants (run and reverted; not left in the tree)

1. Drop `discsilent` from `STALL_NEED` (the disc test): KOTOR II's selftest case fails (`not a HANG (the disc is
   not silent)` -> FAIL, since idle0+kicks0 alone are enough under the mutant), plus the no-pic14 case fails the
   same way. 2 of 27 checks fail; the real selftest harness would catch this.
2. Drop the `stalled` arm entirely (`ARMS = (("pinned", PIN_NEED),)`, today's code before this lane): both freeze
   cases fail (`Voodoo Vince shape, screen still: HANG on the stalled arm` and the matching Die Hard check), 2 of
   27 checks fail. (A naive version of this mutant crashed on an unrelated check with `KeyError: 'stalled'` because
   the selftest itself hard-indexed `arm_start["stalled"]`; fixed those four checks to `arm_start.get("stalled")`
   so the mutant fails on the cases the brief names, not on an incidental KeyError elsewhere.)

Both mutants ran against a temp copy of the module (`python3 /tmp/hangwatch_mutant_*.py selftest`), not the
committed file; the committed `hangwatch.py` has both the disc test and the stalled arm.

## Territory

Only `docs/testing/hangwatch.py`, `docs/testing/jobs/selftest.d/59-hangwatch.sh` (unchanged -- it already just runs
`hangwatch.py selftest`), and `docs/lanes/hangstall1013/**` were touched. `pathfind.py` was read, not edited, per
the brief; its three `hangwatch.look`/`start`/`close` call sites still match the unchanged signatures.

## Waiting

Nothing. The merge-and-rerun step (base: origin/master) is still to do before `State: ready`.
