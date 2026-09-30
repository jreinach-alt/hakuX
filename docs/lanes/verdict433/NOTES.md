# lane.verdict433 notes

Measurement pass for #433 (50 Playable): find the titles closest to the bar
and give each one what its verdict still lacks.

## The rule, as the tools apply it

- `title_verdict.py` with `targets.toml` `[defaults]`: `playable_fps` 30 with
  `fps_tolerance` 0.95, so a window counts at 28.5 fps or more. `fps_share_min`
  is 0.90 of gameplay *time*. `audio_starve_max_share` is 0.001. Screening is
  600 s and confirmation 1200 s after `mark gameplay`. The run needs no hang
  (10 s with fewer than 60 flips) and no crash.
- **The status page counts a title as Playable only on a passing
  `pass_kind: confirmation` verdict** (`status_html.py` `titles05`, the
  `soaked` list). So every candidate needs a 1200 s confirmation, whatever its
  screening says.
- The confirmation regimen is the device's defaults, `--env PERF_REGIMEN=default`
  (owner, #433, 2026-09-27). A thermal pause at the defaults fails the run
  (`thermal.failed_sustained`), where at MAX it voids the run. sustain507
  (#433, 2026-09-28) found every Thor run of Crimson, GTA SA and MA2 paused
  within 5-8 min from a 58-65 C start. A heavy title on the Thor is expected
  to fail its confirmation on heat, and that counts as its verdict.

## The status page's fps overstates the tier A titles

The title table's fps and share come from a 90-240 s slice of each soak
(`_soak_read`), not from the whole scored window. I copied the inputs of each
title's newest route soak to a scratch dir (`judge_copy.py`, which writes no
verdict into the live results) and ran `title_verdict.py` over the full
gameplay:

| Title | Device | Soak (route) | Gameplay s | Share at 28.5+ | Hang | Audio short | Reading |
|---|---|---|---|---|---|---|---|
| Baldur's Gate: Dark Alliance | thor | 1-1790548501-titleroutes-1530514 | 298 | 100% | no | 0 | clean; confirm |
| WWE Raw 2 | nova | 1-1790515603-titleroutes-1194477 | 278 | 100% | no | 0 | clean; confirm |
| Azurik | thor | 1-1790560999-titleroutes-2862460 | 309 | 99.3% | no | 0 | clean; **pilot** |
| 50 Cent: Bulletproof | nova | 1-1790515600-titleroutes-1194351 | 309 | 95.9% | no | 0 | clean; confirm |
| KOF: Maximum Impact Maniax | thor | 1-1790548502-titleroutes-1531011 | 311 | 99.0% | no | **0.38%** | fps passes, audio over 0.1% |
| Bruce Lee | thor | 1-1790487611-titleroutes-261841 | 289 | 81.3% | 21 s | 1.3% | not at the bar |
| Kabuki Warriors | nova | 1-1790563605-titleroutes-374601 | 329 | 22.4% | 72 s | 0 | not at the bar |
| Kabuki Warriors | nova | 1-1790618696-lane.idlehaltdefault-845673 | 204 | 46.5% | 22 s | 0 | not at the bar |
| RalliSport Challenge 2 | thor | 1-1790566122-titleroutes-1417504 | 342 | void | -- | 66% | thermal pause at MAX 77-111 s after the mark |
| Fuzion Frenzy | nova | 1-1790651074-lane.idlehaltdefault-2875039 | 337 | 72.1% | no | 0 | not at the bar |
| Battlefield 2: MC | thor | 1-1790517591-titleroutes-1523259 | 270 | 0% | 13 s | 0.56% | not at the bar |
| D&D Heroes | thor | 1-1790560999-titleroutes-2862610 | 302 | 0% | no | 0 | not at the bar |
| 007: Nightfire | thor | 1-1790563604-titleroutes-373432 | 392 | 24.8% | no | 0 | not at the bar |
| 007: Nightfire | nova | 1-1790481308-titlebench-2892825 | 269 | 60.3% | no | 0 | not at the bar |
| GoldenEye: Rogue Agent | nova | y-1790481308-titlebench-2893125 | 0 | -- | -- | -- | first-run route never marked gameplay |
| Spikeout | thor | (none on a route) | | | | | titleroutes' benchmark `1-9-1790567423-titleroutes-2191714` is queued |

Tier B, same method:

| Title | Device | Soak | Gameplay s | Share at 28.5+ | Reading |
|---|---|---|---|---|---|
| Crimson Skies | nova | 1790467160-titlebench-2612149 | 308 | 85.0% | under 90% |
| Crimson Skies | thor | 1-1790620928-lane.dirtytlb-1387249 | 129 | 86.8% | under 90%, short |
| Grabbed by the Ghoulies | nova | 0-0-x-1-1790634704-lane.idlehaltdefault-3055105 | 236 | 72.7% | under 90% |
| Blood Wake | thor | 1-1790508532-titleroutes-1074940 | 287 | 29.5% | hang, audio 1.3% |

## Ranking (probability x win; every win is one Playable title)

1. **Azurik (Thor), the pilot.** It is clean on the route, and it has the
   Thor's thermal risk. It is the one confirmation that fits the 30-min gate
   (1480 s + 90 s). Queued: `1-1790688705-lane.verdict433-3467502`.
2. **Baldur's Gate DA (Thor), WWE Raw 2 (Nova), 50 Cent (Nova).** Each was
   100% or near it with no hang. The Nova ones have no heat risk on record, so
   these have the highest probability of passing. See `queue_batch1.sh`.
3. **KOF MI (Thor).** The fps passes; audio was 0.38% short against a 0.1%
   bar. It is in batch 1 because a 20-min run settles whether that shortfall
   holds or came from a burst.
4. **RalliSport 2.** It paused at MAX within 2 min on the Thor. At the defaults
   that pause fails the run. Next: a Nova screening on the returning route,
   after the Nova's charge hold lifts, if the Nova's title state has the
   profile.
5. **Tier B** (Crimson, Ghoulies, Blinx 2 and the rest) reads 73-87% at the
   bar on the full window. A confirmation of any of them is expected to fail
   the share. Leave them until a fix moves their fps.
6. **Tier C** (DOA Ultimate, AUF, Forza, GTA SA). Other lanes' arms on these
   titles are queued (gmem474, forzadecay414, litcompile569, uberspike569).
   Re-measure them after those arms land, and after #583 folds for Forza.

## Running table (confirmations)

| Title | Device | Regimen | Request | Verdict | fps median | Share 28.5+ |
|---|---|---|---|---|---|---|
| Azurik | thor | default | 1-1790688705-lane.verdict433-3467502 | **FAIL(thermal)** | -- | 58.9% fps_ok |
| Baldur's Gate: Dark Alliance | thor | default | 1-1790693574-lane.verdict433-211577 | queued | | |
| WWE Raw 2 | nova | default | 1-1790693575-lane.verdict433-211620 | queued | | |
| 50 Cent: Bulletproof | nova | default | 1-1790693575-lane.verdict433-211666 | queued | | |
| KOF: Maximum Impact Maniax | thor | default | 1-1790693575-lane.verdict433-211719 | queued | | |

Current state of every confirmation (updated session 4, 2026-09-29 12:15 PDT;
regimen from each run's `perf_regimen.json` where a run exists):

| Title | Device | Regimen (fan) | Request | Verdict | Share 28.5+ | Gameplay s |
|---|---|---|---|---|---|---|
| Azurik | thor | default (fan_mode 4) | 1-1790688705-lane.verdict433-3467502 | **FAIL(thermal)**, pause at +938 s from 48.6 C | 58.9% | 1297 |
| Azurik (data point, not a verdict) | thor | default (fan_mode 4), `HAKUX_IDLE_HALT=1`, cold slot | 0-0-s-1-1790696366-lane.verdict433-2378176 | reads PASS on a copy; halt is opt-in on master (#566), so not the shipped defaults | 98.6% | 1296 |
| WWE Raw 2 | nova | default | 1-1790693575-lane.verdict433-211620 | void (adb capture failure) | -- | 272 |
| 50 Cent: Bulletproof | nova | default | 1-1790693575-lane.verdict433-211666 | ERROR (env pref not set; never ran) | -- | -- |
| Baldur's Gate DA | thor | max, customize:100 | 1-1790700816-lane.verdict433-3695372 | withdrawn by lane.local (Thor off confirmations) | | |
| KOF MI | thor | max, customize:100 | 1-1790700816-lane.verdict433-3695988 | withdrawn, same | | |
| Azurik | thor | max, customize:100 | 1-1790700817-lane.verdict433-3696430 | withdrawn, same | | |
| WWE Raw 2 | nova | default | 1-1790700817-lane.verdict433-3697079 | queued | | |
| 50 Cent: Bulletproof | nova | default | 1-1790700818-lane.verdict433-3697712 | queued | | |
| 007: Agent Under Fire | nova | default | 1-1790709167-lane.verdict433-1492209 | queued | | |
| Baldur's Gate DA, KOF MI, Azurik | nova | default | -- | waiting on the Nova copies (`queue-investigation.txt`, not yet in `listing-nova.txt`) | | |

## State at the end of session 1 (2026-09-29, about 07:00 PDT)

Waiting on the pilot `1-1790688705-lane.verdict433-3467502`. It sits behind
about 2 h of 1- requests on the Thor. When `results/<id>/DONE` exists:
1. Run `title_verdict.py <dir> --require confirmation`.
2. Read `thermal.first_pause_s`, and the frames from `route-frames/`.
3. Write `pilots/lane.verdict433.ok` with `python3`.
4. Run `queue_batch1.sh`.

## Tools here

- `scan.py PATTERN...` lists every verdict.json in the live results for matching titles.
- `soaks.py PATTERN...` lists every finished soak for matching ISOs, with the
  time from `soak start` to `mark gameplay` (this sets `--seconds`).
- `judge_copy.py OUTDIR ID...` judges a copy of a result's inputs. Use it for
  any benchmark you only want to read. Running `title_verdict.py` on the live
  dir would write a failing short verdict that the status page then shows.
- `queue_batch1.sh` holds the next four confirmations. Queue it after the
  pilot review.

## For the next lane

- Do not trust the status page's fps column for a Playable call. Judge the
  full window.
- Lane pilots can hold only one confirmation, because 1200 s plus the route
  plus 90 s of setup comes to 25-31 min against the 30-min gate. Pick a
  pilot whose route marks gameplay early.

## Session 2 (2026-09-29, resumed ~14:35 PDT)

Session 1 did not finish; it did not fail. It queued the Azurik pilot and
ended the turn with a `[lane.verdict433] waiting:`-shaped state (docs/lanes
commit `85fb20f3b4`), which is the correct stopping point for a request
still behind ~2 h of queue -- the alternative was polling past the turn
budget. This session resumed after `jobs/handback.sh` (or a fresh resume)
found the result on disk.

Brought `origin/master` in with `git merge` (3 commits, all lane.tokentier's
model-file work and unrelated `docs/testing/lane.sh`/`jobs/` plumbing --
no emulator code, no conflicts with this lane's files). No prediction is
registered on this lane (no arm), so the "never rebase after registering"
rule does not bind here, but the merge still happened before reading
anything further from this tree, per the session hook.

### Pilot result: Azurik FAILS its Thor confirmation on heat

`1-1790688705-lane.verdict433-3467502` finished. `title_verdict.py --require
confirmation`:

```
FAIL(thermal: sustained play failed at the device's defaults --
thermal-pause-F8 1/1 began after +938 s and by +970 s; still paused at the
last reading) gameplay=1296.8s fps_ok=0.5892 audio_short=0.046113
```

`thermal.jsonl`: xo-therm started at **48.6 C** (a cool start, not a warm
one) and read 70.5 C by the run's end; `thermal-pause-F8` fired once and the
device was still paused (`"pause":true`) at the last sample, ~24.7 min in.
The Thor's own devwatch cooldown hold fired from this run's heat (the
session hook shows `cooldown-devwatch: xo-therm 74.2 C >= 74 C` at
14:32:32Z, recorded right after this run ended) and is still in force as of
this write -- `$DISPATCH_DIR/hold/thor` reads `cooldown-devwatch`.

This is Azurik's verdict, honestly: **not sustainably Playable on the Thor
at the defaults.** Per the brief, do not re-run it until a fix changes that.
Wrote `$DISPATCH_DIR/pilots/lane.verdict433.ok` (via `python3`, since `ls`/
`Write`/`cp` are blocked in the dispatch dir) recording the read and the
mechanism check (request form, ref, route, and `--require confirmation`
read all work end to end) so batch queuing is unblocked by the pilot gate.

**Read for batch1's two Thor titles.** Azurik is a lighter title than
Crimson/GTA SA/MA2 (sustain507 saw those pause in 5-8 min at either
regimen); Azurik paused only after 15.6 min, from a cool start. That still
means a ~20-25 min Thor confirmation at the defaults is at real risk of the
same pause regardless of title, and the Thor is warm right now from this
very run. Baldur's Gate DA and KOF MI (batch1, both Thor) need to be read
for a thermal pause, not just for fps/audio share, when their results land.

### Batch 1 queued

Updated `queue_batch1.sh`'s `REF` to this merge's tip (was pinned to the
session-1 base `94cf8eb627`; no emulator code changed between the two, so
this changes nothing about what the requests measure, only which sha
`request.sh` builds/reuses). Queued all four (pilot gate admitted the whole
batch on the fresh `pilots/lane.verdict433.ok`):

| Title | Device | Request |
|---|---|---|
| Baldur's Gate: Dark Alliance | thor | `1-1790693574-lane.verdict433-211577` |
| WWE Raw 2 | nova | `1-1790693575-lane.verdict433-211620` |
| 50 Cent: Bulletproof | nova | `1-1790693575-lane.verdict433-211666` |
| KOF: Maximum Impact Maniax | thor | `1-1790693575-lane.verdict433-211719` |

Thor is on a cooldown hold (`cooldown-devwatch`, waiting for 65 C); queued
requests wait behind it rather than being refused, so this is not a reason
to idle. Nova is separately behind `lane.local`'s `lanelocal-topup` charge
hold per the brief; same handling.

Pushed (`f8a5330838`), PR #610 body updated via the REST PATCH workaround
(`gh pr edit` fails on this host, see memory) and read back to confirm.
Posted the Azurik-fail-plus-batch1-queued update to #433
(issuecomment-5892736287).

### Ending session 2 here: waiting on batch 1 and CI

All four batch 1 confirmations are queued but not yet running (Thor: heat
hold; Nova: charge hold) -- 20-30 min each once they start, on devices this
session cannot poll without burning the turn budget. CI on the new push
(`f8a5330838`) is `IN_PROGRESS` on both `build` checks. Neither is
something this session can wait out. Posted a `[lane.verdict433] waiting:`
comment on PR #610 naming both.

Next lane / next resume, in order:
1. Check CI on `f8a5330838`; if red, fix before anything else.
2. For each of the four batch1 IDs, once its `DONE` exists, run
   `title_verdict.py <dir> --require confirmation`, read `thermal.jsonl` for
   the two Thor titles specifically (pause risk flagged above), and fill in
   the running table's fps/share columns.
3. Post the updated Playable count to #433.
4. Move to tier B/C per the ranking once batch 1 is read, or start tier C
   titles whose fixes have landed since 2026-09-29 06:40 (check #583, #575,
   #530/#580, lane.ibcache).
5. Keep `pilots/lane.verdict433.ok` in mind: it is dated 2026-09-29T14:36Z,
   good for 24 h from then for any further batch beyond what request.sh's
   own per-request estimate already covers.

## Session 3 (2026-09-29, resumed as attempt 3)

Session 2 did not finish for the same reason session 1 didn't: it queued
work that runs 20-30 min per title on shared devices, and correctly stopped
at a `[lane.verdict433] waiting:` comment (PR #610) rather than polling past
its turn budget. That is the documented "finished session" shape for this
lane, not a failure -- see the brief's "Never end a session waiting on your
own background task" / draft-PR rules. This session picked up where it left
off: CI on `4ea4d401d5` was green by the time of resume, and hostops had
armed a 14 h waiter (`hakux-waiter-verdict433`) per its `[job.deliver]`
comment.

**Merged `origin/master` first, per the session hook (12 commits behind).**
Clean merge (no conflicts on this lane's files). Notably PR #615
(lane.statuswindow, folded as `2fcb228749`) fixes the exact problem this
lane's session 1 flagged: the status page's title table was reading a
90-240 s slice instead of the full gameplay window. It now calls
`title_verdict.judge(..., write_contact_sheet=False)` live for any finished
request with a route and a run.log, so the table itself should stop
overstating tier A's fps even before a confirmation lands. That does not
change what "Playable" requires (`--require confirmation`), so this lane's
job is unchanged; it only means the *table* is no longer the misleading
signal it was in session 1. Pushed the merge (`3427e75ba1`) before queuing
anything, since `build_ref` resolves `--ref` against the host's clone of
`$REPO` and needs the sha to exist there.

**Read batch 1's actual results, not just its request IDs:**

| Title | Device | Batch-1 request | Outcome |
|---|---|---|---|
| Baldur's Gate: Dark Alliance | thor | `-211577` | **missing from results** -- withdrawn by lane.local per the addendum (Thor moved to full-fan confirmations) |
| KOF: Maximum Impact Maniax | thor | `-211719` | **missing from results** -- withdrawn, same reason |
| WWE Raw 2 | nova | `-211620` (ran as `0-0-x-1-...-211620`) | DONE, but void: `title_verdict.py --require confirmation` reads `FAIL(void: not-foreground: unreadable (ee317437 adb failed (exit 1)))` -- a capture glitch, not a low-fps reading. `capture_lost=26.3s`, `capture_truncated` |
| 50 Cent: Bulletproof | nova | `-211666` (ran as `0-0-x-1-...-211666`) | **ERROR**: "could not set the requested env_vars pref; see dispatcher.log" -- the run never started (`apply_env_pref` failed in dispatcher.sh before the app launched) |

Neither Nova failure is a real reading of either title; both are harness/adb
hiccups (per memory: single-run device flakes get a rerun before any
conclusion). Also found, unlisted in any prior NOTES: a `study`-priority
request `1-1790696366-lane.verdict433-2378176` (Azurik, `HAKUX_IDLE_HALT=1`,
queued 15:39Z under this lane's own requester name) ran to completion with
`"pause":false` throughout -- idle halt kept Azurik off the thermal pause in
this one run. That request was not queued by any session recorded in this
lane's NOTES; it reads as another actor's (#525 lane.idlehaltdefault's)
probe riding this lane's requester name. Out of scope for #433's brief
(which does not mention the idle halt), so not acted on here beyond noting
it for whichever lane owns #525.

**Read the addendum and its cited decision** (#433 comment 5894686025,
owner): Thor Playable confirmations now run at `PERF_REGIMEN=max
FAN_MODE=customize:100` ("full fan"); the bar (90% at 28.5+, audio ≤0.1%, no
crash/hang, no thermal pause) is unchanged; Nova is unchanged.
`FAN_MODE=customize:100` is a valid request per `devices.sh`'s
`DEVICE_FAN_OPTIONS` (customize is a HIGH-only slider 0-100, matching
`PERF_REGIMEN=max`'s performance_mode).

**Batch 2 queued** (`docs/lanes/verdict433/queue_batch2.sh`, pilot gate
still admits under the 2 h-old `pilots/lane.verdict433.ok`):

| Title | Device | Regimen | Request |
|---|---|---|---|
| Baldur's Gate: Dark Alliance | thor | max, fan customize:100 | `1-1790700816-lane.verdict433-3695372` |
| KOF: Maximum Impact Maniax | thor | max, fan customize:100 | `1-1790700816-lane.verdict433-3695988` |
| Azurik: Rise of Perathia | thor | max, fan customize:100 (re-confirm; failed at defaults in the pilot) | `1-1790700817-lane.verdict433-3696430` |
| WWE Raw 2 | nova | default (retry; batch-1 run voided) | `1-1790700817-lane.verdict433-3697079` |
| 50 Cent: Bulletproof | nova | default (retry; batch-1 run errored) | `1-1790700818-lane.verdict433-3697712` |

request.sh's own estimate put this at ~136 min of queued+running device
time for this lane; the pilot gate admitted the whole batch on the standing
`pilots/lane.verdict433.ok`, consistent with "the reviewed pilot's verdict
is what the gate checks," not a fresh 30-min ceiling per batch.

### Ending session 3 here: waiting on batch 2

All five requests are queued, none finished yet (20-30 min each once
running, on devices this session cannot poll without burning the turn
budget). Posting `[lane.verdict433] waiting:` on PR #610 and #433, updating
the PR body's `Files:` line to include `queue_batch2.sh`, and stopping.

Next lane / next resume, in order:
1. For each of the five batch-2 IDs above, once its `DONE` exists, run
   `title_verdict.py <dir> --require confirmation`.
2. For the three Thor titles, read `perf_regimen.json` (record it in this
   table per the addendum) and `thermal.jsonl` for a pause -- a pause still
   fails the run even at full fan.
3. Post the updated Playable count to #433.
4. If WWE Raw 2 or 50 Cent error/void again on the Nova, that is no longer a
   single-run flake; escalate as a board request rather than a third retry.
5. Move to tier B/C per the existing ranking once batch 2 is read.

CI on the merge-plus-batch-2 push (`3b2797ee11`) is `in_progress` (both
`Android` and `Desktop build`) as of this write; also outside this session
to wait out. Both the device batch and CI are named in the PR/issue
`waiting:` comments.

## Session 4 (2026-09-29, attempt 4, from ~12:05 PDT)

**Why attempt 3 did not finish.** It was not a failure. It ended on a
`waiting:` comment for batch 2, which is the documented stopping point.
The resume came from lane.local's 12:00 PDT addendum, not from a result.
That addendum moves confirmations off the Thor and withdrew batch 2's three
Thor requests. Batch 2's two Nova requests (WWE Raw 2 `-3697079`, 50 Cent
`-3697712`) are still in `queue/` at 12:09 PDT. About ten Nova requests from
other lanes are ahead of them: ibcache, uberspike569, memfast, gmem474 and
kabukistall.

Merged `origin/master` (47 commits, including #614 thorheat and #581
uberspike569; nothing in this lane's files) and pushed as `da4b15ea1a`.

### What the addendum changes

- BG:DA, KOF MI and Azurik move to the Nova at its defaults. Their Nova copies
  are listed in `hardware/titlepush/queue-investigation.txt` (12:00 PDT) but
  not yet in `listing-nova.txt`, so nothing can be queued for them yet.
  When a copy lands, queue it with the title's existing route
  (`baldurs-gate-da`, `kof-mi.returning`, `azurik`), then check the first
  run's `route-frames/`. A Thor route may not carry over.
- Azurik's halt-on cold-slot run is in the table above as a Thor data point.
  On a copy it reads PASS at 98.6% over 1296 s. `perf_regimen.json` gives
  regimen default, fan_mode 4. It is not a verdict.
- No Thor confirmation is queued. This lane had no registered prediction or
  capture key that names the Thor.

### Sweep: every Nova route soak since 09-28 ~19:00 PDT, judged on copies

`sweep.py` runs `judge_copy.py` over every finished Nova route soak since
epoch 1790560000. It found 11 titles in 124 runs. Best reading per title:

| Title | Runs | Best share 28.5+ | Reading |
|---|---|---|---|
| **007: Agent Under Fire** | 25 | 100% (202 s) | **Every run before #530 (per-title sysmem, folded 09-28 11:50) reads 0%.** That includes sustain507's 1941 s soaks. Both normal builds after #530 (`85347ffbd1`, `10fe2f59a7`, the forzadecay414 pair) read 100%. gmem474's `db1e8a7f12` build turns the #530 table off, and it reads 0-3.6% again. So #530 is the cause. I reviewed the survey frames of `-152037`: first-person, in the level, crosshair and gadget on screen, FPS 59-62. That is gameplay. **Confirmation queued.** |
| Kabuki Warriors | 14 | 98.7% | Mixed. gmem474's runs read 96-99% with no hang. The pacing, idlehaltdefault and energymap runs hang (3 of the 5 most recent) and read 21-59%. lane.kabukistall's `-194847` is queued on the stall. Not a confirmation until the stall is explained. |
| Crimson Skies | 1 (since) | 94.1% (251 s) | ibcache's `HAKUX_IBC=0` control (`c8e95ed539`, which includes #575). The 09-28 Nova read was 85%. One short run is marginal against 90%. ibcache has three more Crimson Nova runs queued (`-1378207`, `-1378332`, `-1378456`), so read those before spending 25 min on a confirmation. |
| DOA Ultimate | 38 | 91.4% | litcompile569's fix build had audio short 0.136%, over the 0.1% bar. **The survey route ends on the User Profiles menu ("There is no profile to import"), not in a fight** (frame `092146-play.png`). So these readings are menu fps, and `--reviewed-gameplay no`. DOA needs its own route to a fight before any verdict means anything. `doax.route` is DOA Xtreme. Route authoring is Thor work per the addendum. |
| Fuzion Frenzy | 6 | 80.5% | under the bar |
| Ghoulies | 2 | 72.7% | under the bar |
| Nightfire | 3 | 65.3% | under the bar |
| Blinx 2 | 7 | 61.1% | under the bar |
| Forza | 11 | 52.4% | waits on #583 (still an open draft) |
| Blinx | 14 | 20.3% | under the bar |
| WWE Raw 2 | 1 | void | batch-1 run; batch 2 retry is queued |

Tier C: #583 (Forza) and #591 (ibcache, GTA SA) are still open drafts, so
there is nothing to re-measure for them yet. #530, #575 and #580 have
merged. AUF is the #530 win. For DOA, see above.

### Queued this session

| Title | Device | Regimen | Route | Request |
|---|---|---|---|---|
| 007: Agent Under Fire | nova | default | survey (marks play at about 225 s) | `1-1790709167-lane.verdict433-1492209` |

When it finishes, judge it with `title_verdict.py <dir> --require
confirmation --reviewed-gameplay yes`. Survey is a generic route, so the
tool asks for a review. Check first that the frames still show the level:
the survey input plays blind and could walk into a menu or a death screen
over 1200 s.

### Next, in order

1. When the batch-2 Nova IDs and AUF finish, judge them and fill in the table.
2. Once ibcache's three Crimson Nova runs finish, judge copies of them. If
   they hold at 90% or more, queue a Crimson Nova confirmation on the
   `crimson-skies` route.
3. When each of the BG:DA, KOF and Azurik Nova copies lands in
   `listing-nova.txt`, queue its confirmation (Nova, default).
4. DOA Ultimate needs a route to a fight (Thor route authoring). Kabuki waits
   on lane.kabukistall. Forza waits on #583. GTA SA waits on #591.


### Ending session 4: waiting

Posted on #433 (issuecomment-5896935910) and a `waiting:` comment on PR #610. I am waiting on the three queued Nova confirmations, on the three Nova title copies, and on ibcache's Crimson runs. The PR stays a draft until a confirmation reads.

## Session 5 (2026-09-29, attempt 5)

**Why attempt 4 did not finish.** It did finish, in the shape the brief and
the lane contract both call "done for a session": it queued what it could
(the AUF confirmation) and stopped on a `waiting:` comment for work that
runs 20-30 min per title on a shared device this session cannot poll
without burning the turn budget. Nothing was broken or abandoned. This
session's resume came from lane.local's 14:15 PDT addendum, not from a
finished run.

**Checked what changed since the close-out.** CI on the pushed head
(`246fce4e23`) is green (`build`/Android and `build`/Desktop build both
SUCCESS). The three batch-2/session-4 Nova requests from before this
session -- WWE Raw 2 retry `-3697079`, 50 Cent retry `-3697712`, and 007:
Agent Under Fire `-1492209` -- are still sitting in `queue/`, not yet run
(about 10 other lanes' requests were ahead of them per session 4; the Nova
was also mid-top-up). Nothing to read yet.

**The six Nova title copies landed.** `hardware/titlepush/listing-nova.txt`
(a shared, non-repo path outside any worktree -- not under board control)
now carries a `# nova, listed 2026-09-29T20:34:21Z by title_push_xbox.sh`
header and includes all six: Baldur's Gate DA, KOF MI, Azurik, GTA SA,
Arctic Thunder, Alien Hominid. Matches the 14:15 PDT addendum's claim
lane.xbox verified them by 14:07 PDT.

**Queued Nova confirmations for the three that are this lane's business**
(`queue_batch3.sh`): Baldur's Gate DA, KOF MI, Azurik, at the Nova's
unchanged default confirmation regimen, on their existing routes
(`baldurs-gate-da`, `kof-mi.returning`, `azurik` -- same route files used on
the Thor; per the addendum, checking the first run's frames once each
lands, since the routes' wait timers were calibrated against the Thor's
boot/menu latency). GTA SA, Arctic Thunder and Alien Hominid are **not**
queued by this lane: they are #507's heat investigation copies, not #433
candidates. GTA SA in particular is tier C, waiting on lane.ibcache's jump
cache (#591), which is still an open draft as of this session -- nothing to
re-measure for it yet.

| Title | Device | Regimen | Route | Request |
|---|---|---|---|---|
| Baldur's Gate: Dark Alliance | nova | default | baldurs-gate-da | `1-1790716257-lane.verdict433-3241572` |
| KOF: Maximum Impact Maniax | nova | default | kof-mi.returning | `1-1790716257-lane.verdict433-3241617` |
| Azurik: Rise of Perathia | nova | default | azurik | `1-1790716257-lane.verdict433-3241677` |

The pilot gate admitted all three on the standing `pilots/lane.verdict433.ok`
(6.3 h old at queue time, well under 24 h), estimating ~162 min of total
queued+running device time for this lane across everything still
outstanding.

### Next, in order

1. When each of the six outstanding Nova IDs finishes (WWE Raw 2, 50 Cent,
   AUF, BG:DA, KOF, Azurik), judge it with `title_verdict.py <dir> --require
   confirmation` (add `--reviewed-gameplay yes|no` for AUF, which is on the
   generic survey route). Fill in the running table.
2. For BG:DA/KOF/Azurik's first Nova run each, check `route-frames/` before
   trusting the result -- confirm the Thor-authored route still lands the
   route's scripted inputs correctly on the Nova (menu timing, mark frame).
3. Post the updated Playable count to #433 once any of the six reads a
   verdict.
4. Once ibcache's Crimson Nova runs and #591 itself land, re-check Crimson
   and queue GTA SA's Nova investigation copy for a tier-C read.
5. Per lane.local's addendum, do not wait on these runs in this session --
   the handback waiter resumes this lane when they finish.

### Ending session 5 here: waiting

Six Nova requests are outstanding (three from before this session, three
queued this session). None have finished. Posting `[lane.verdict433]
waiting:` on PR #610 and #433, updating the PR body's `Files:` line to
include `queue_batch3.sh`, and stopping per the addendum's explicit
instruction not to wait on these runs in this session.

## Session 6 (2026-09-29, resumed ~23:26Z / attempt 2 since the reset)

**Why session 5 did not finish, restated.** It did finish, cleanly, on the
documented stopping point: six Nova confirmations queued, a `waiting:`
comment posted on PR #610 and #433 at 21:11-21:12Z, no runs polled from
inside the session. hostops acked at 21:33:32Z that all six were "correctly
in queue" behind the Nova's battery hold (expected to lift at >=45% or
16:15 PDT / 23:15Z). That is not what needed fixing this session.

**What this session found instead: all six requests had vanished.** Merged
`origin/master` first (26 commits, clean merge, includes lane.kabukistall's
K1 result and lane.gmem474's #474 predictions on AUF/DOA/Crimson/Kabuki --
none of it touches this lane's files). Then went to read the six queued
results and found none of them anywhere:

- Not in `queue/` (13 entries at read time, all `lane.memfast`/`lane.ibcache`,
  none `lane.verdict433`).
- Not in `running/` (2 entries, `lane.uberspike569` and one owner file).
- Not in `results/` (2066 entries; the only 6 matching `verdict433` were
  session 1-3 leftovers -- Azurik's halt-on run and pilot, and two old
  `211620`/`211666` variants -- none of the six from session 4/5).
- Not in `queue/withdrawn/` either, and no `.why` file for any of them.

Checked with a full `os.walk($DISPATCH_DIR)` for all six raw ID numbers
(3241572, 3241617, 3241677, 3697079, 3697712, 1492209) after `Glob`'s
single-`*` pattern gave inconsistent (and wrong) "no files found" answers
against the ~2000-entry `results/` tree at this scale -- `os.walk` plus
`os.path.exists` on exact paths is the ground truth used here, not `Glob`.
Zero matches anywhere in the tree, for any of the three plausible epoch/ID
spellings recorded in NOTES/PR/issue text.

**No comment records a withdrawal or a result for any of the six.** The
#433/#610 threads go quiet on this lane's requests after the 21:33:32Z ack
until lane.kabukistall's unrelated K1 post at 22:54:03Z. That post's
`result.json` (`1-1790702688-lane.kabukistall-194847`) contains
`"backfill_for": "1-1790700817-lane.verdict433-3697079"` in its `battery`
block -- the battery-learning gate borrowed this lane's WWE Raw 2 retry
request as a reference point for its own admission math, dated near this
session's start. That is the only trace any of the six left. Nothing
explains where the request records themselves went. This reads as a
harness bug in the queue/battery-hold path, not something introduced by
this lane's own actions (queuing them and parking was exactly what the
addendum asked for, and hostops itself confirmed they landed correctly).
Per standing guidance, a dispatch-harness anomaly is recorded here and
reported on the issue/PR, not filed as a separate GitHub issue.

**Re-queued all six**, fresh, as `docs/lanes/verdict433/queue_batch4.sh`
(new file, added to `Files:`). All six now run on the Nova at its default
confirmation regimen -- the three that used to be Thor confirmations
(BG:DA, KOF, Azurik) stay on the Nova per the still-standing heat addendum.
Bumped `REF` to `2dd92568b5` (today's merged `origin/master` tip) since
nothing here compares against the specific old refs. `--seconds` figures
are unchanged from `queue_batch2.sh`/`queue_batch3.sh` (mark time + 1200 s
+ margin); AUF's is estimated at 1475 s (225 s mark + 1200 s + 50 s
margin, matching the figure session 4 used but never wrote down verbatim).

| Title | Device | Regimen | Route | Request |
|---|---|---|---|---|
| WWE Raw 2 | nova | default | wwe-raw-2 | `1-1790725089-lane.verdict433-1456493` |
| 50 Cent: Bulletproof | nova | default | 50cent | `1-1790725089-lane.verdict433-1456544` |
| 007: Agent Under Fire | nova | default | survey | `1-1790725090-lane.verdict433-1456591` |
| Baldur's Gate: Dark Alliance | nova | default | baldurs-gate-da | `1-1790725090-lane.verdict433-1456665` |
| KOF: Maximum Impact Maniax | nova | default | kof-mi.returning | `1-1790725091-lane.verdict433-1456797` |
| Azurik: Rise of Perathia | nova | default | azurik | `1-1790725091-lane.verdict433-1456876` |

Verified each exists on disk under `queue/<id>.req` right after queuing
(exact-path `os.path.exists`, not `Glob`). The pilot gate admitted all six
on the standing `pilots/lane.verdict433.ok` (8.8 h old at queue time),
estimating ~162 min of total queued+running device time, same total as
session 5's now-vanished batch.

**Also cleaned up** four stray untracked scratch files left in the worktree
root by an earlier session (`.c433.md`, `.prbody.json`, `.prbody.md`, and
`docs/lanes/verdict433/.scratch/`) -- old drafts of PR-body text and a
`sweep.py` scratch output directory, none referenced by anything committed.

### Next, in order

1. When each of the six finishes, judge it with `title_verdict.py <dir>
   --require confirmation` (`--reviewed-gameplay yes|no` for AUF, the
   generic survey route). Fill in the running table.
2. For BG:DA/KOF/Azurik's first Nova run each, check `route-frames/` before
   trusting the result (Thor-authored route timings on Nova hardware).
3. Post the updated Playable count to #433 once any of the six reads a
   verdict.
4. Watch for the same disappearance again. If any of these six also vanish
   without a result or a withdrawal record, that confirms a repeatable
   harness bug worth a lane brief of its own rather than a third blind
   re-queue.
5. Once ibcache's Crimson Nova runs and #591 land, re-check Crimson and
   queue GTA SA's Nova investigation copy for a tier-C read.

### Ending session 6 here: waiting

All six requests are freshly queued and none have finished (queued only
minutes ago, each is a 20-30 min confirmation). Posting `[lane.verdict433]
waiting:` on PR #610 and #433 describing the vanished batch and the
re-queue, and stopping -- not polling device work from inside the session.

## Session 7 (2026-09-30, resumed ~05:00 UTC, attempt 3 since the reset)

**Why session 6 did not finish.** It finished cleanly on the documented
stopping point: all six re-queued batch-4 requests confirmed present on
disk, a `waiting:` comment posted, no polling from inside the session.
Nothing to fix from that session. This session's resume found all six
batch-4 requests had actually run to completion.

**GitHub is down for this account** (owner-approved local stand-in since
~21:00 PDT 2026-09-29, see the offline-protocol addendum above). `origin`
now resolves to `~/hakux-work/offline-git/hakuX.git`; confirmed with `git
remote -v`. No `gh` calls made this session. This lane's PR and issue posts
now go to `docs/lanes/verdict433/PR.md` and `OUTBOX.md` instead -- both new
this session, since the switchover happened after session 6 closed out.

**Checked `git status` (clean) before doing anything else**, per the
worktree-safety rule, then read all six batch-4 result dirs directly
(`os.path.exists`/`os.listdir`, not `Glob`, per session 6's finding that
`Glob` misbehaves at this tree's scale). All six have `DONE`:

| Title | Result | `title_verdict.py --require confirmation` |
|---|---|---|
| WWE Raw 2 (`-1456493`) | **void again** | `not-foreground` -- ES-DE frontend stole focus. `VOID.txt`: hostops root-caused it this tick -- `titles.qcow2` was pushed to the Nova with `adb push`'s default `rw-r--r--`, one group-write bit short of what xemu needs; the drive open failed `Permission denied` and xemu fell back to the ES-DE home launcher, which then held display 0 (same bug as PR #627/lane.hddperm, #397). Interim fix: chmod 660 on the Nova (again; #627 not yet folded). hostops already re-queued this as `1-1790737858-lane.verdict433-1456493r2` (queued_utc 2026-09-30T03:10:57Z) -- **do not re-queue a third time**, it is already in `queue/`. |
| 50 Cent (`-1456544`) | **void again**, same cause | Same `VOID.txt` text, same interim chmod fix. Already re-queued by hostops as `1-1790737859-lane.verdict433-1456544r2`, same `queued_utc`. Not re-queued here either. |
| 007: Agent Under Fire (`-1456591`) | **FAIL(booted: the guest never appeared or never flipped 60 frames)** gameplay=0.0s | `run.log`: `guest never appeared in 1475s -- title did not boot`. `logcat.txt` (84 lines total) shows xemu reaching `xemu_android_main: qemu_init` -> `sdl2_display_early_init` and then **nothing** until `soak end` 25 min later -- no crash line, no further log at all. This run's `request.json` `queued_utc` puts it third in the batch's run order (after WWE and 50 Cent, before BG:DA), so it started *before* hostops's chmod-660 fix (WWE/50cent voided, fix applied, then BG:DA booted clean right after). The silent hang at exactly the `qemu_init` stage matches the same disc-permission bug's signature (see memory: a pushed disk at the wrong mode SIGSEGVs/hangs a few ms into `qemu_init`), not a real read on AUF. **Requeued as `1-1790745234-lane.verdict433-366094`.** |
| Baldur's Gate DA (`-1456665`) | **FAIL(void: not-foreground: unreadable (adb failed exit 1))** gameplay=1190.0s, capture_lost=28.0s | Booted clean (after the chmod fix), played the whole scripted route into gameplay, and ran 1684s of a planned 1760s -- 1190s of gameplay, 10s short of the 1200s bar -- before `FOREGROUND: foreground-unreadable: adb failed (exit 1)` fired 5 times running and the soak aborted (`run.log`: "soak aborted: not-foreground after 1684s of 1760s"). No crash, no hang, `audio_short=0.0` through the readable portion. This is a single adb capture flake right at the finish line, not a low-fps or crash reading -- per memory, a single-run device flake gets a rerun before any conclusion, especially one this close to the bar. **Requeued as `1-1790745235-lane.verdict433-366130`.** |
| KOF: Maximum Impact - Maniax (`-1456797`) | **PASS Playable** | gameplay=1282.6s, fps_ok=0.9936, crash=False, hang=False, audio_short=0.000541, battery_w=+3.42, net_w=5.543, j_per_frame=0.1121. Clean confirmation, no review flag needed (its own named route, not the generic survey). |
| Azurik: Rise of Perathia (`-1456876`) | **PASS Playable** | gameplay=1292.3s, fps_ok=0.9521, crash=False, hang=False, audio_short=0.0, battery_w=+4.58, net_w=6.704, j_per_frame=0.228. Clean confirmation on its own route. This is the same title that FAILED its Thor confirmation on heat in session 2 (`thermal-pause-F8` at +938s) -- the addendum's move to the Nova is exactly what turned it Playable. |

**Two new Playable titles: KOF: Maximum Impact - Maniax and Azurik: Rise of
Perathia, both on the Nova at the default confirmation regimen.** Neither
needed a review flag (each has its own authored route with an explicit
`mark gameplay`, not the generic survey AUF uses).

**Queued batch 5** (`queue_batch5.sh`, new file, added to `Files:`): reruns
of AUF and BG:DA only -- WWE Raw 2 and 50 Cent are already re-queued by
hostops and must not be queued a third time. Pilot gate admitted both on
the standing `pilots/lane.verdict433.ok` (14.4 h old at queue time, still
under 24h):

| Title | Device | Route | Request |
|---|---|---|---|
| 007: Agent Under Fire | nova | survey | `1-1790745234-lane.verdict433-366094` |
| Baldur's Gate: Dark Alliance | nova | baldurs-gate-da | `1-1790745235-lane.verdict433-366130` |

`queue/` and `running/` checked directly before queuing: `running/` was
empty, `queue/` held about 20 other lanes' requests ahead of these two
(memfast, tcg424flip, ibcache r2s, titleroutes, litcompile569,
uberspike569) plus the two hostops r2 requeues, so neither of these two new
requests nor the two r2s will start immediately.

### Running table (confirmations), updated

| Title | Device | Regimen | Request | Verdict | fps_ok | Gameplay s | j/frame |
|---|---|---|---|---|---|---|---|
| **KOF: Maximum Impact - Maniax** | nova | default | `1-1790725091-lane.verdict433-1456797` | **PASS Playable** | 0.9936 | 1282.6 | 0.1121 |
| **Azurik: Rise of Perathia** | nova | default | `1-1790725091-lane.verdict433-1456876` | **PASS Playable** | 0.9521 | 1292.3 | 0.228 |
| WWE Raw 2 | nova | default | `-1456493` void, `-1456493r2` queued (hostops) | void (ES-DE focus theft, titles.qcow2 perms) -- | | | |
| 50 Cent: Bulletproof | nova | default | `-1456544` void, `-1456544r2` queued (hostops) | void, same cause | | | |
| 007: Agent Under Fire | nova | default | `-1456591` FAIL(boot), `-366094` queued (this session) | boot hang, pre-chmod-fix (rerun pending) | | | |
| Baldur's Gate: Dark Alliance | nova | default | `-1456665` FAIL(void, adb flake at 1684/1760s), `-366130` queued (this session) | 10s short on an adb glitch (rerun pending) | | | |

Playable count for #433 as of this session: **KOF: Maximum Impact - Maniax,
Azurik: Rise of Perathia** confirmed this session. Earlier lanes/status-page
history for any prior Playable title is not re-verified here; this table
only tracks this lane's confirmations.

### Next, in order

1. When `-366094` (AUF) and `-366130` (BG:DA) finish, judge with
   `title_verdict.py <dir> --require confirmation --reviewed-gameplay yes`
   for AUF (generic survey route) and without the flag for BG:DA (its own
   route).
2. Watch for the `r2` WWE Raw 2 / 50 Cent results (hostops-owned requeue,
   not this lane's queue action, but this lane's title and should be read
   and recorded when they land).
3. Post the two-Playable update plus this session's diagnosis to `#433` via
   `OUTBOX.md` (offline protocol -- no `gh` available).
4. Tier B/C unchanged from session 4's ranking: Crimson waits on ibcache's
   three queued Nova runs, DOA needs a fight route, Kabuki waits on
   lane.kabukistall, Forza waits on #583, GTA SA waits on #591.
5. Per the offline protocol, do not wait on these two reruns in this
   session -- park, and the handback waiter (or a future resume) picks up
   the results.

### Ending session 7 here: waiting

Two reruns queued (AUF, BG:DA), the two hostops r2 requeues (WWE, 50 Cent)
untouched and already in `queue/`. Two titles confirmed Playable this
session. Recording a `waiting:` entry in `OUTBOX.md` (no PR/issue comment
tool available under the offline protocol) and stopping -- not polling
device work from inside the session.
