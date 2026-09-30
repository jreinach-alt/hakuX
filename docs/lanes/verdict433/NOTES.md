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

## Session 8 (2026-09-30, resumed ~13:40 UTC / 06:40 PDT, attempt 4 since the reset)

**Why attempt 3 (session 7) did not finish.** It did finish, on the
documented stopping point: two Playable confirmations read (KOF MI, Azurik),
two reruns queued, a `waiting:` entry in `OUTBOX.md`. The PR stays
`State: draft` because four confirmations are still outstanding. This resume
came from lane.local's 06:45 PDT addendum (queue up to 3 more), not from a
result.

Merged `origin/master` (34 commits; clean, nothing in this lane's files) and
pushed as `15f476e77b`.

**The four outstanding Nova confirmations are all still in `queue/`, none
run** (the Nova is on the `lanelocal-topup` hold from 13:41Z): WWE Raw 2
`-1456493r2`, 50 Cent `-1456544r2`, AUF `-366094`, BG:DA `-366130`.
`running/` is empty.

### Picking three more (evidence, not the example list)

Swept every finished Nova route soak since session 4 (epoch 1790709000, 31
runs) with `sweep.py`, and judged copies of the newest Nightfire, Fuzion and
Spikeout soaks. The addendum's examples do not hold the bar on the Nova:

| Title | Newest evidence | Reading |
|---|---|---|
| 007: Nightfire | memfast 09-29, 3 judgeable Nova runs | 52-65% at 28.5+ |
| Fuzion Frenzy | idlehaltdefault, 6 Nova runs (session 4 sweep) | best 80.5% |
| Spikeout | only a Thor route run (`0-0-x-1-1790567423-titleroutes-2191714`) | void, thermal pause at +207 s; no Nova route run |
| GoldenEye: Rogue Agent | `y-1790481308-titlebench-2893125` | route never marked gameplay |
| RalliSport 2 | Thor only, thermal void | no Nova route run |

The titles that do hold it on the Nova, all newly routed or newly copied
since the brief's 09-29 06:40 list (so tier A by its definition, "at the
bar with no confirming verdict"):

| Title | Runs (build) | Share 28.5+ | fps median / min | Gameplay s | Mark s |
|---|---|---|---|---|---|
| **Alien Hominid** | 4 (ibcache `c8e95ed539`, two with `HAKUX_IBC=0`) | 100% all 4 | 59.94 / 41.2-43.4 | 257-260 | 109-110 |
| **187: Ride or Die** | 1 (titleroutes `1c0c23fabb`, ancestor of master) | 100% | 59.94 / 59.88 | 302 | 77 |
| **Arctic Thunder** | 4 (tcg424flip `7bcd6e6e2b`, both arms) | 100% all 4 | 39.4-42.1 / 31.4-34.3 | 195-198 | 226-229 |
| Crash Bandicoot: WoC | 2 (`1c0c23fabb`, hddcrash) | 100% | 56-58 / 41.8 | 144-309 | -- |
| Crimson Skies | 3 (ibcache probe on, not master) | 96.6% | 30.0 / 26.4 | 250-254 | -- |
| Midnight Club 3 | 1 | 87.5% | 29.7 / 13.8 | 289 | -- |

**Chosen: Alien Hominid, 187: Ride or Die, Arctic Thunder.**
- Alien Hominid has the most runs at the widest margin: four at 60 fps
  whose worst window is 41 fps, on both ibcache arms (the `HAKUX_IBC=0` arm
  is master's code path). Probability of a pass about 0.9.
- 187: Ride or Die is one run, but locked at 59.9 with a worst window of
  59.88, in a race, on a master build. Risk: its route notes one boot in
  three hanging on a spinner, which would void rather than fail. About 0.8.
- Arctic Thunder's worst window across four runs is 31.4 fps, above 28.5,
  with no audio shortfall. Its builds are tcg424flip's (not folded), but
  both arms of the #424 range setting read 100%, so that setting does not
  move it. Risk: the race ends inside 1200 s and the loop's A presses must
  carry it through the results screen. About 0.75.
- Passed over: Crash (the scored window is the warp-room hub, which the
  route itself calls an upper bound, and titleroutes plus hddcrash already
  have Crash runs queued); Crimson (paced at 30.0, 96.6% only on unmerged
  ibcache builds; the `HAKUX_IBC=0` control read 94.1% in session 4, a thin
  margin over 20 min); Kabuki (skipped per the addendum).

Refreshed `pilots/lane.verdict433.ok` (it was 22.9 h old) with the review of
batch 4's two passing Nova confirmations: both mark frames show gameplay
(KOF mid-round at FPS 58; Azurik in the training arena). Queued
`queue_batch6.sh` at `15f476e77b`, `--seconds` = mark + 1200 + 80:

| Title | Device | Regimen | Route | Seconds | Request |
|---|---|---|---|---|---|
| Alien Hominid | nova | default | alien-hominid | 1390 | `1-1790775886-lane.verdict433-3086847` |
| 187: Ride or Die | nova | default | 187-ride-or-die.returning | 1360 | `1-1790775886-lane.verdict433-3086875` |
| Arctic Thunder | nova | default | arctic-thunder | 1510 | `1-1790775886-lane.verdict433-3086903` |

All three verified in `queue/` by exact path. Pilot gate: ~185 min of this
lane's device time admitted on the refreshed pilot.

### Running table (confirmations), session 8

| Title | Device | Regimen | Request | Verdict |
|---|---|---|---|---|
| **KOF: Maximum Impact - Maniax** | nova | default | `1-1790725091-lane.verdict433-1456797` | **PASS Playable** (99.4%, 1282.6 s) |
| **Azurik: Rise of Perathia** | nova | default | `1-1790725091-lane.verdict433-1456876` | **PASS Playable** (95.2%, 1292.3 s) |
| WWE Raw 2 | nova | default | `1-1790737858-lane.verdict433-1456493r2` | queued |
| 50 Cent: Bulletproof | nova | default | `1-1790737859-lane.verdict433-1456544r2` | queued |
| 007: Agent Under Fire | nova | default | `1-1790745234-lane.verdict433-366094` | queued (`--reviewed-gameplay` needed: survey route) |
| Baldur's Gate: Dark Alliance | nova | default | `1-1790745235-lane.verdict433-366130` | queued |
| Alien Hominid | nova | default | `1-1790775886-lane.verdict433-3086847` | queued |
| 187: Ride or Die | nova | default | `1-1790775886-lane.verdict433-3086875` | queued |
| Arctic Thunder | nova | default | `1-1790775886-lane.verdict433-3086903` | queued |

### Next, in order

1. Judge each of the seven as it finishes: `title_verdict.py <dir> --require
   confirmation` (AUF also `--reviewed-gameplay yes|no` after its frames).
   For Arctic Thunder and 187, look at the last route frame: a results or
   continue screen for most of the window would make the share a menu
   reading.
2. Post the Playable count to `OUTBOX.md` #433.
3. Set `State: ready` once the outstanding confirmations have verdicts.

### Ending session 8 here: waiting

Seven Nova confirmations are queued behind the Nova's top-up hold. I am
waiting on those dispatch results, which are outside this session, and
stopping here.

## Session 9 (2026-09-30, attempt 5 since the reset)

**Why session 8 did not finish.** It did finish, on the documented stopping
point: three more Nova confirmations queued (batch 6: Alien Hominid, 187,
Arctic Thunder), a `waiting:` entry posted, no polling from inside the
session. This resume found four of the seven outstanding requests DONE.

**Merged `origin/master` first** (19 commits behind; clean merge, only
`docs/lanes/titleroutes/*` files touched, nothing of this lane's). Pushed as
`07d2718e7c`.

**Checked all seven outstanding IDs by exact path** (`os.path.exists`, not
`Glob`, per session 6's finding). Four are DONE, three (batch 6: Alien
Hominid, 187, Arctic Thunder) are still in `queue/` -- the Nova's `queue/`
has 6 entries total (our 3 plus 3 from `forzadecay414`'s arm), `running/` is
empty, and the Nova's own hold is no longer present (only the Thor carries
`lanelocal-fanwait`), so these three simply haven't reached the front yet.

### Three more titles PASS Playable

`title_verdict.py --require confirmation` on each of the four DONE results:

| Title | Request | Verdict | fps_ok | Gameplay s | audio_short | net_w | J/frame |
|---|---|---|---|---|---|---|---|
| **WWE Raw 2** | `-1456493r2` | **PASS Playable** | 0.9982 | 1276.9 | 0.0 | 7.956 | 0.1357 |
| **50 Cent: Bulletproof** | `-1456544r2` | **PASS Playable** | 0.9906 | 1348.3 | 0.0 | 7.471 | 0.2498 |
| **Baldur's Gate: Dark Alliance** | `-366130` | **PASS Playable** | 1.0 | 1303.9 | 0.0 | 7.628 | 0.1273 |
| 007: Agent Under Fire | `-366094` | FAIL, see below | 0.9956 | 1251.1 | 0.0 | 7.899 | 0.1837 |

hostops's chmod-660 fix for `titles.qcow2` (the bug that voided both of
these in their first attempt, session 7-8) held for all three reruns: no
capture faults, no voids, clean confirmations.

### 007: Agent Under Fire's rerun is stuck at a vault door, not gameplay

The tool printed `reached_gameplay: unconfirmed (generic route)` (AUF uses
the generic `survey` route, which marks `play` not `gameplay`, so it needs
`--reviewed-gameplay yes|no` after a frame review). Reviewed
`route-frames/`: the route walks the character up to a vault-style door at
`092408-play.png` (mark `play` fires here) and the identical camera angle,
down to the same red crosshair position on the same door panel, recurs at
`093305-play.png`, `093936-play.png`, and the last frame `094452-play.png`
(the full ~20 min window). The FPS overlay changes (51/45/44/42/43) so the
renderer is live, but the character never moves past this door -- no
progress, no combat, nothing but the scripted walk-forward/look-around loop
bouncing off the same obstacle for the entire confirmation. That is a
softlock against scenery, not gameplay, so this reads `--reviewed-gameplay
no`.

Ran it: `python3 docs/testing/title_verdict.py <dir> --require confirmation
--reviewed-gameplay no` still prints the same "unconfirmed" message and
leaves `reached_gameplay: null` in `verdict.json`, not `false` -- tracing
the code, the `reviewed == "no"` case has no branch of its own in the
`gameplay_by` selection (`docs/testing/title_verdict.py`, the `gp`/`play`
block around line 15958): it falls through to the same `elif play:` arm as
an unreviewed run, so `gameplay_by` stays `None` and `reached_gameplay`
stays `None` (unconfirmed) rather than `False` (reviewed, not gameplay) --
even though a later branch (`elif reviewed == "no": why = "a reviewer
judged the contact sheet not gameplay"`) clearly expects to be reached.
**Either way the run reads FAIL under `--require confirmation`**, so this
does not change AUF's verdict, only the label. Noting it as a harness
anomaly per standing guidance (report, don't fix from a measurement lane;
`docs/testing/title_verdict.py` is also the Playable rule the brief says not
to touch).

**AUF is not Playable from this run.** The generic survey route cannot get
it past this door; it needs its own authored route (like KOF, Azurik, BG:DA,
WWE, 50 Cent all have) before another confirmation is worth queuing. Not
re-queuing AUF from this lane -- route authoring is out of this lane's scope
(per the brief and the addendum's split: route authoring is Thor work).

### Running table (confirmations), updated

| Title | Device | Regimen | Request | Verdict |
|---|---|---|---|---|
| **KOF: Maximum Impact - Maniax** | nova | default | `-1456797` | **PASS Playable** (99.4%, 1282.6 s) |
| **Azurik: Rise of Perathia** | nova | default | `-1456876` | **PASS Playable** (95.2%, 1292.3 s) |
| **WWE Raw 2** | nova | default | `-1456493r2` | **PASS Playable** (99.8%, 1276.9 s) |
| **50 Cent: Bulletproof** | nova | default | `-1456544r2` | **PASS Playable** (99.1%, 1348.3 s) |
| **Baldur's Gate: Dark Alliance** | nova | default | `-366130` | **PASS Playable** (100%, 1303.9 s) |
| 007: Agent Under Fire | nova | default | `-366094` | FAIL (stuck at a door, not gameplay; needs its own route) |
| Alien Hominid | nova | default | `1-1790775886-lane.verdict433-3086847` | queued, not yet run |
| 187: Ride or Die | nova | default | `1-1790775886-lane.verdict433-3086875` | queued, not yet run |
| Arctic Thunder | nova | default | `1-1790775886-lane.verdict433-3086903` | queued, not yet run |

**Five titles confirmed Playable by this lane so far: KOF: Maximum Impact -
Maniax, Azurik: Rise of Perathia, WWE Raw 2, 50 Cent: Bulletproof, Baldur's
Gate: Dark Alliance.** That is the owner's "3-5 more titles Playable today"
target (06:45 PDT addendum) met, before batch 6 even lands.

### Next, in order

1. When the three batch-6 IDs finish, judge each with `title_verdict.py
   <dir> --require confirmation`. For Arctic Thunder and 187, check the last
   route frame per session 8's caution (a results/continue screen would make
   the share a menu reading, same failure mode as AUF's door).
2. Post the five-Playable update to `OUTBOX.md` #433.
3. AUF needs a dedicated route before it can be re-measured; flag it for
   whichever lane does Thor-side route authoring (titleroutes).
4. Tier B/C unchanged: Crimson waits on ibcache's three queued Nova runs and
   #575/#591, DOA needs a fight route, Kabuki waits on lane.kabukistall,
   Forza waits on #583, GTA SA waits on #591.
5. Once all of batch 6 has a verdict and the OUTBOX post is made, this
   lane's PR can move toward `State: ready` -- check with the owner whether
   the day's measurement pass is considered done at five, or whether to keep
   going into tier B.

### Ending session 9 here: waiting

Three Nova confirmations (batch 6) are still queued, behind three
`forzadecay414` arm/base requests, with the Nova otherwise idle
(`running/` empty). Recording this progress in `OUTBOX.md` and stopping --
not polling device work from inside the session.

## Session 10 (2026-09-30, resumed as attempt 1 after a reset)

**Why session 9 did not finish.** It did finish, on the documented stopping
point: three more titles confirmed Playable this session (WWE Raw 2, 50
Cent, Baldur's Gate DA), batch 6 (Alien Hominid, 187, Arctic Thunder) queued
and none of its three yet run, a `waiting:` entry posted to `OUTBOX.md`, no
polling from inside the session. Nothing to fix from session 9 itself.

**`git status` clean; `HEAD` (`b536bac125`) already carries everything on
`origin/master`** (`git rev-list --left-right --count HEAD...origin/master`
reads `21 0` -- 21 commits ahead, 0 behind), so no merge was needed this
session before reading anything further, per the session hook.

**Checked batch 6 by exact path** (`os.walk`/`os.path.exists`, not `Glob`,
per session 6's finding): all three requests are still present (no repeat of
session 6's vanishing-batch bug). Alien Hominid (`-3086847`) is now
`running/` (has a `results/` dir with `thermal.jsonl`/`battery.json`/etc but
no `DONE` yet); 187 (`-3086875`) and Arctic Thunder (`-3086903`) are still in
`queue/`. Nothing new to judge this session.

### Addendum (09:55 PDT): re-ranked by margin, checked the 30-capped examples -- none add

Re-swept every judgeable Nova route soak since the session-8 sweep's cutoff
(`sweep.py .scratch10 1790709000 nova`, 31 new runs) plus the full
default-cutoff sweep from session 4/8, specifically for the addendum's named
examples (Nightfire, Crimson Skies, Blinx 2, Grabbed by the Ghoulies):

| Title | Newest/best Nova evidence since the addendum | Reading |
|---|---|---|
| 007: Nightfire | one new run, `void` (frontend focus theft) | no new full-window read; last real one still 52-65% (session 8) |
| Crimson Skies | 3 new ibcache short runs (250-254s window), 96.6-96.6% | still on ibcache's unmerged `HAKUX_IBC` branch (#591 not folded into `origin/master` -- checked `git merge-base --is-ancestor`, answer no); the one master-build control read 85-94% (sessions 4/8), under 90% on a clean build |
| Blinx 2 | no new runs at all since epoch 1790709000 | unchanged at 61.1% (session 4) |
| Grabbed by the Ghoulies | no new runs at all since epoch 1790709000 | unchanged at 72.7% (session 4) |

None of the addendum's four named examples clear 90% on a Nova run built
from `origin/master`. **Nothing added.** The three currently queued
(Alien Hominid, 187, Arctic Thunder) all still read 100% share on their
newest evidence (session 8's table) -- **nothing dropped** either. Margin
ranking changes nothing about what's already queued; it just confirms the
09-55 addendum's own examples are hopeful, not evidenced, same shape as
session 8's finding about the 06:45 addendum's examples.

### Addendum (10:20 PDT): one Thor cold-start confirmation queued, after a full Thor sweep

Swept every judgeable Thor route soak on record (`sweep.py .scratch10
1790400000 thor`, 150 runs, back to 2026-09-26) for a title that is light
(low net_w), 30-fps-capped, and holds 28.5+ on its full recorded window,
per the addendum's bar. Ranked every title by its best-seen `fps_ok` share:

| Title | Best share seen | Net_w range | Verdict |
|---|---|---|---|
| Azurik, GTA SA, Crash Twinsanity, Alien Hominid, Bruce Lee, Baldur's Gate DA | 100% (isolated runs) | varies | each is either already Playable, tier C (GTA SA waits on #591), or contradicted by a longer run in the same sweep (Crash Twinsanity: one 156s window at 100% vs. a 268s window at 0%; Bruce Lee: one 158s window at 100% vs. the known 289s/81.3%/21s-hang read from session 1) -- not reliable enough to queue blind |
| KOF: Maximum Impact - Maniax | 99% | 5.5W | already Nova-Playable |
| **Otogi: Myth of Demons** | 95.5% (4 independent short runs, 88.1-95.5%, mean ~90.7%) | **4.0-5.1 W** | the only title with multiple consistent readings at the bar and low power; no hang/crash in any of the four; **queued** |
| Crimson Skies | 93.4% best, most runs 23-87% | 5.2-6.7W | inconsistent, not light |
| 25 to Life, Burnout | 83%, 82% | 5.4-5.6W | under 90%, not especially light |
| everything else with data | under 60% | -- | not candidates |

**Found in the same sweep, not this lane's work:** Alien Hominid already
carries a live `PASS`/`pass_kind: confirmation` verdict **on the Thor**
(`1-1790515369-lanelocal-1183547`, lane.local, queued 2026-09-27, fps_ok=1.0,
gameplay=1273.6s, route `alien-hominid`) -- checked the live `verdict.json`
directly, not a judged copy. That predates this lane's Nova confirmation of
the same title (batch 6, still running) and already counts toward the
status page's Playable total independent of this lane. Noting it here so
the Playable count isn't undercounted when this lane's Nova run for Alien
Hominid lands (it would be a second, redundant confirmation of an
already-Playable title, not a new one).

**Otogi: Myth of Demons (46530002) is Thor-only** (absent from
`listing-nova.txt`; present in `listing-thor.txt`), has its own authored
route (`docs/testing/titles/routes/otogi.route`, not the generic survey),
and `targets.toml` gives it `target_fps = 30` with no bar overrides (the
defaults apply: 28.5+ over 90% of gameplay time, 1200s confirmation). Cross-
checked its `mark gameplay` timing from three independent requests'
`seconds` minus recorded `gameplay_s` (energymap507 `-1790650474`: 550-294=
256s; slowtier2 `-1790609660`: unknown total minus 287=263s by the same
method; pacing `-1790637578`: 400-143=257s) -- consistent at 256-263s.

Queued (`queue_batch7.sh`, new file, added to `Files:`), per the addendum's
exact form (`--device thor --hard-pin`, `PERF_REGIMEN=default`, 1200s after
the mark):

| Title | Device | Route | Seconds | Request |
|---|---|---|---|---|
| Otogi: Myth of Demons | thor (hard-pin) | otogi | 1545 (mark ~265 + 1200 + 80) | `1-1790790097-lane.verdict433-43486` |

Verified in `queue/` by exact path. The pilot gate (`pilots/lane.verdict433.ok`,
3.9h old, still under 24h) admitted it at ~103 min of this lane's total
outstanding device time. This is the only Thor cold-start request queued
this session -- the addendum allows up to 3, but the sweep found no second
or third title meeting the bar with real evidence; queuing blind on an
untested title would be exactly the low-probability, cheap-first move the
owner's 09-28 ranking guidance warns against. If lane.local's coldconfirm
runner (`thor_coldconfirm.sh`) reads Otogi favorably, the same sweep method
can be pointed at any titles it clears for a cold-start read next session.

### Running table (confirmations), unchanged from session 9 plus the new Thor item

| Title | Device | Regimen | Request | Verdict |
|---|---|---|---|---|
| **KOF: Maximum Impact - Maniax** | nova | default | `-1456797` | **PASS Playable** (99.4%, 1282.6 s) |
| **Azurik: Rise of Perathia** | nova | default | `-1456876` | **PASS Playable** (95.2%, 1292.3 s) |
| **WWE Raw 2** | nova | default | `-1456493r2` | **PASS Playable** (99.8%, 1276.9 s) |
| **50 Cent: Bulletproof** | nova | default | `-1456544r2` | **PASS Playable** (99.1%, 1348.3 s) |
| **Baldur's Gate: Dark Alliance** | nova | default | `-366130` | **PASS Playable** (100%, 1303.9 s) |
| 007: Agent Under Fire | nova | default | `-366094` | FAIL (stuck at a door, not gameplay; needs its own route) |
| Alien Hominid | nova | default | `-3086847` | running (not DONE yet); **already Playable via a separate Thor confirmation**, see above |
| 187: Ride or Die | nova | default | `-3086875` | queued, not yet run |
| Arctic Thunder | nova | default | `-3086903` | queued, not yet run |
| Otogi: Myth of Demons | thor (hard-pin, cold-start) | default | `-43486` | queued, not yet run |

### Next, in order

1. When batch 6's three Nova IDs and the Otogi Thor ID finish, judge each
   with `title_verdict.py <dir> --require confirmation`. For Arctic Thunder
   and 187, check the last route frame (results/continue screen would make
   the share a menu reading, per session 8's caution). For Otogi, review
   whether the coldconfirm runner force-stopped it at 70C (a void, not a
   verdict) before trusting any FAIL.
2. Post this session's findings to `OUTBOX.md` #433 (queued below).
3. Tier B/C unchanged: Crimson still waits on #591 (not folded as of this
   session -- checked directly); DOA needs a fight route; Kabuki waits on
   lane.kabukistall; Forza waits on #583; GTA SA waits on #591.
4. If Otogi's cold-start read comes back PASS, that is title 6 for this
   lane's count and the first Thor-cold-start Playable under the new
   protocol -- worth its own OUTBOX line, not folded into a routine update.

### Ending session 10 here: waiting

Four requests are outstanding (batch 6's three, plus this session's Otogi
cold-start): one running, three queued, none `DONE`. Recording this
session's addendum work in `OUTBOX.md` and stopping -- not polling device
work from inside the session.

## Session 11 (2026-09-30, resumed as attempt 2)

**Why the previous attempt did not need fixing.** Session 10 ended
correctly, on its own documented stopping point: it swept for new
candidates, queued one real one (Otogi, with evidence), left the three
batch-6 Nova requests and the new Thor request outstanding, posted a
`waiting:` entry to `OUTBOX.md`, and stopped without polling device work
from inside the session -- exactly what `roles/lane.md` calls a finished
session. Nothing in it was broken. This resume exists because hostops
posted a new addendum (10:58 PDT) mid-wait that needs a decision, and the
handback waiter brought the lane back for it. `git status` clean;
`HEAD` (`f5af0c3fc3`) unchanged from where session 10 left it.

**Checked the four outstanding requests by exact path** (`os.walk` over
`DISPATCH_DIR`, via `python3`, not `Glob`/`find` -- both are blocked
outside this worktree from this session, and the stdlib walk is what past
sessions used to avoid the vanishing-batch trap):

| Request | Title | State |
|---|---|---|
| `-3086847` | Alien Hominid | **DONE, both copies** (re-pinned to Thor by lane.local's 10:40 PDT addendum, then voided) |
| `-3086875` | 187: Ride or Die | still `queue/`, nova |
| `-3086903` | Arctic Thunder | still `queue/`, nova |
| `-43486` | Otogi: Myth of Demons | still `running/`, thor |

**Alien Hominid's Thor cold-start: confirmed voided, matches hostops's
account exactly.** Read `.hostops-diagnosed` and `request.json` directly
from both result copies (`.../results/1-1790775886-lane.verdict433-3086847`
and its `0-0-s-` copy): `hakux-thor-coldconfirm` force-stopped the app at
xo=70C, 402 of 1390 planned seconds, net power 5.83 W against the 10:20 PDT
addendum's ~4.5 W cold-slot guidance, hottest zone 95.4 C. `result.json`'s
scored fields (`status`, `net_w`, `xo_peak_c`, `gameplay_s`) all read
`None` -- no result, not a FAIL, as the addendum says. This was a poor
candidate pick by the 10:40 PDT re-pin (made outside this lane, to save
Nova battery), not a runner bug.

**Decision: not re-queuing Alien Hominid, on the Nova or the Thor.**
Session 10 already found, independent of this lane's own batch-6 attempt,
that Alien Hominid carries a live `PASS`/`pass_kind: confirmation` verdict
on the Thor from before this pass (`1-1790515369-lanelocal-1183547`,
lane.local, 2026-09-27, fps_ok=1.0, gameplay=1273.6s) -- re-read directly
again this session, still live. It is already Playable and already counts
on the status page. A fresh confirmation of it, Nova or Thor, would spend
device time on a title that doesn't move the count. hostops's own note
offered the same two options (Nova, or skip); skip is correct here because
there's no missing verdict to fill. This closes out the `-3086847` request
line -- no further action on it.

**Checked for a lower-power Thor candidate to use the freed slot instead:
none.** Session 10's Thor sweep (150 route soaks back to 2026-09-26)
already concluded Otogi was the only title with multiple consistent
readings at the bar and under the power guidance; everything else was
either already Playable, tier C, or contradicted by a longer run in the
same sweep. Nothing changed that conclusion this session -- no new Thor
route soaks have landed since (checked by epoch cutoff, same method as
session 10's addenda). Queuing an untested title on a fan-dead Thor on the
strength of a hunch is exactly the low-probability guess the owner's
09-28 ranking guidance warns against, so nothing new queued.

**Found, independent of the above: the Thor is now under a fresh hold.**
`DISPATCH_DIR/hold/thor` reads `lanelocal-fanwait`, placed
2026-09-30T17:48:12Z (~10:48 PDT, a few minutes before hostops's 10:58 PDT
diagnosis), `thor.why`: "the Thor's fan is dead (owner 09-29; AYN is
shipping a fan and a top screen): light work only -- staged new titles
push under this hold (push-under-hold flags); no queued runs; lane.local
releases after the repair." This independently rules out queuing anything
else on the Thor right now, on top of the finding above that nothing else
has the evidence to queue. It does not affect Otogi, which was already in
`running/` (past the queue gate) before the hold appeared -- left running,
not this lane's call to stop it. No hold on the Nova; 187 and Arctic
Thunder's requests remain validly queued, ahead of three
`forzadecay414` arm/base requests, on an otherwise idle Nova (`running/`
has only Otogi).

**Nothing new to judge this session.** 187 and Arctic Thunder haven't
run; Otogi hasn't finished. The Playable count from this lane stays at
five, unchanged from session 9/10.

### Running table (confirmations), updated

| Title | Device | Regimen | Request | Verdict |
|---|---|---|---|---|
| **KOF: Maximum Impact - Maniax** | nova | default | `-1456797` | **PASS Playable** (99.4%, 1282.6 s) |
| **Azurik: Rise of Perathia** | nova | default | `-1456876` | **PASS Playable** (95.2%, 1292.3 s) |
| **WWE Raw 2** | nova | default | `-1456493r2` | **PASS Playable** (99.8%, 1276.9 s) |
| **50 Cent: Bulletproof** | nova | default | `-1456544r2` | **PASS Playable** (99.1%, 1348.3 s) |
| **Baldur's Gate: Dark Alliance** | nova | default | `-366130` | **PASS Playable** (100%, 1303.9 s) |
| 007: Agent Under Fire | nova | default | `-366094` | FAIL (stuck at a door, not gameplay; needs its own route) |
| Alien Hominid | thor (cold-start, re-pinned) | default | `-3086847` | **voided** (heat stop, no result) -- not re-queued; already Playable via a separate, earlier Thor confirmation (`lanelocal-1183547`) |
| 187: Ride or Die | nova | default | `-3086875` | queued, not yet run |
| Arctic Thunder | nova | default | `-3086903` | queued, not yet run |
| Otogi: Myth of Demons | thor (hard-pin, cold-start) | default | `-43486` | running, not yet DONE |

### Next, in order

1. When 187, Arctic Thunder and Otogi finish, judge each with
   `title_verdict.py <dir> --require confirmation`. For Arctic Thunder and
   187, check the last route frame (session 8's caution about a
   results/continue screen reading as a menu, not gameplay). For Otogi,
   check first whether `thor-coldconfirm.log` force-stopped it at 70C (a
   void) before trusting any FAIL.
2. Post this session's Alien Hominid decision and the new Thor hold to
   `OUTBOX.md` #433 (queued below).
3. Tier B/C unchanged: Crimson waits on #591 (still unfolded), DOA needs a
   fight route, Kabuki waits on lane.kabukistall, Forza waits on #583, GTA
   SA waits on #591.
4. Not queuing further Thor work until `lanelocal-fanwait` lifts, whatever
   its evidence -- the hold says no queued runs while it's up.

### Ending session 11 here: waiting

Three requests remain outstanding: 187 and Arctic Thunder queued on the
Nova, Otogi running on the Thor. Recording this session's decision in
`OUTBOX.md` and stopping -- not polling device work from inside the
session.

## Session 12 (2026-09-30, resumed as attempt 3)

**Why the previous attempt did not need fixing, again.** Session 11 ended
correctly: it read hostops's new addendum, made and documented a real
decision (don't re-queue Alien Hominid), found and recorded the new
`lanelocal-fanwait` hold, and stopped at its own "waiting" checkpoint with
three device requests still outstanding and an `OUTBOX.md` entry naming
them -- exactly a finished session per `roles/lane.md`. `git status` clean;
`HEAD` (`48e9441d27`) unchanged from where session 11 left it. This resume
is the handback waiter bringing the lane back to check the outstanding
work, not a fix for anything broken.

**Checked all three outstanding requests by exact path** (`os.walk`/direct
reads under `DISPATCH_DIR` via `python3`, same method as prior sessions):

| Request | Title | State |
|---|---|---|
| `-3086875` | 187: Ride or Die | still `queue/`, nova |
| `-3086903` | Arctic Thunder | still `queue/`, nova |
| `-43486` | Otogi: Myth of Demons | still `running/`, thor -- not yet judgeable |

**187 and Arctic Thunder: still battery-gated, as the 14:15 PDT addendum
predicted.** `.battery_refused.nova` (mtime 11:12:30) shows both refused
at `level: 37` against `need: 47.0` / `need: 48.3`, alongside two
`forzadecay414` arm requests refused the same way. No hold on the Nova
itself -- it's simply under the ~48% floor this addendum already
anticipated ("they run first after the next top-up ... about 18:00").
Nothing actionable here; still hours from the evening dock.

**Otogi: still running, but it has already hit a sustained thermal pause
-- read directly from `thermal.jsonl` in its results dir** (46 samples,
`10:48:31` through `11:13:04` at the time of this check), not inferred:

| Time (PDT) | xo-therm (C) | `pause` | fan.speed |
|---|---|---|---|
| 10:48:31 (cool) | 66.8 | False | 0 |
| 10:49:03 (start) | 64.3 | False | 0 |
| 10:49:43-11:00:46 (ramp) | 66.4 -> 77.9 | False | 0 |
| **11:01:19** | 77.2 | **True** | 0 |
| 11:01:19-11:13:04 (12+ min so far) | 77.2 -> 70.4, declining | **True, every sample since** | 0 |

`fan.speed` reads 0 across every sample including the ramp -- consistent
with lane.thorheat's #614 finding that this unit's fan does not spin
regardless of the commanded duty (`fan.duty` reads 26500/50000, `mode: 4`,
the whole time). This is the kernel thermal governor's own
`thermal-pause-F8` cdev engaging at xo~78C, not the `hakux-thor-coldconfirm`
runner's 70C force-stop (no `.hostops-diagnosed` file has appeared, and
xo passed through 70C twice on the way up without the app being killed --
this request was queued in session 10, before the 10:20 PDT addendum stood
up the coldconfirm slot-gating runner, and started from xo 64-66C, already
above that runner's 50C cold-slot floor). `request.json` / `result.json` /
`verdict.json` still don't exist -- the run has not finished or been
force-stopped, just throttled, and this check does not wait for it to.

**This matters regardless of how it finishes.** The brief is explicit
(point 3): "A title that hits the thermal pause during a confirmation is
not sustainably Playable on the Thor. Record that honestly, with its heat
evidence; do not re-run until it passes." Otogi's confirmation has now hit
exactly that, mid-run. Whatever numeric verdict `title_verdict.py` produces
when it finishes (fps during the paused minutes will be reduced, not
necessarily enough to fail `fps_share_min` outright), **this run cannot be
recorded as a Thor Playable confirmation** even on a numeric PASS -- it
must be recorded as heat evidence, same as Azurik's earlier
`thermal-pause-F8` fail and the session-10-to-12 record of 16/66 Thor runs
pausing in 30h. Not re-running Otogi on the Thor after this.

**This also undercuts session 10's candidate-selection method, not just
Otogi.** Otogi was picked as the single Thor cold-start candidate because
four independent *short* runs (256-263s each) read 4.0-5.1 W net with no
issue. A full 1200s confirmation window pushed the same title into a
sustained thermal pause on this fan-dead unit. A short-run wattage reading
is not a reliable predictor of full-window thermal behavior here -- the
same caution the owner's 12:00 PDT addendum already applied at the fleet
level ("16 of 66 ... 14 of them ... between 00:20 and 08:05") now has a
single-title mechanism behind it. Not proposing a fix (that's #507's
lane); flagging it so no lane picks another "light in a short run" Thor
candidate on the strength of short-run power alone until #507 lands
something.

**Nothing new to judge or queue this session.** No verdict files exist for
any of the three outstanding requests. The Playable count from this lane
stays at five, unchanged since session 9.

### Running table (confirmations), unchanged except Otogi's new heat note

| Title | Device | Regimen | Request | Verdict |
|---|---|---|---|---|
| **KOF: Maximum Impact - Maniax** | nova | default | `-1456797` | **PASS Playable** (99.4%, 1282.6 s) |
| **Azurik: Rise of Perathia** | nova | default | `-1456876` | **PASS Playable** (95.2%, 1292.3 s) |
| **WWE Raw 2** | nova | default | `-1456493r2` | **PASS Playable** (99.8%, 1276.9 s) |
| **50 Cent: Bulletproof** | nova | default | `-1456544r2` | **PASS Playable** (99.1%, 1348.3 s) |
| **Baldur's Gate: Dark Alliance** | nova | default | `-366130` | **PASS Playable** (100%, 1303.9 s) |
| 007: Agent Under Fire | nova | default | `-366094` | FAIL (stuck at a door, not gameplay; needs its own route) |
| Alien Hominid | thor (cold-start, re-pinned) | default | `-3086847` | voided (heat stop, no result); not re-queued -- already Playable via a separate, earlier Thor confirmation (`lanelocal-1183547`) |
| 187: Ride or Die | nova | default | `-3086875` | queued, battery-refused (Nova at 37%, needs ~47%) |
| Arctic Thunder | nova | default | `-3086903` | queued, battery-refused (Nova at 37%, needs ~48%) |
| Otogi: Myth of Demons | thor (hard-pin, cold-start) | default | `-43486` | running; **hit `thermal-pause-F8` at xo 77.9C, ~11:01 PDT, still paused as of 11:13 PDT** -- whatever its numeric outcome, not a valid Thor confirmation; not re-running |

### Next, in order

1. When Otogi's request produces `verdict.json`, record its numeric result
   in this table for completeness, but do not count it as Playable even on
   a PASS -- the thermal pause during the run already disqualifies it per
   the brief's point 3. Do not re-queue it on the Thor.
2. When 187 and Arctic Thunder run (after the Nova recharges toward 18:00
   PDT), judge each with `title_verdict.py <dir> --require confirmation`,
   checking the last route frame per session 8's caution.
3. Tier B/C unchanged: Crimson waits on #591 (still unfolded), DOA needs a
   fight route, Kabuki waits on lane.kabukistall, Forza waits on #583, GTA
   SA waits on #591.
4. Not queuing further Thor work -- `lanelocal-fanwait` is still up, and
   this session's finding is a second, independent reason not to trust a
   short-run power reading as a green light for a full Thor confirmation
   right now anyway.

### Ending session 12 here: waiting

All three outstanding requests are still unresolved: 187 and Arctic
Thunder battery-gated on the Nova, Otogi mid-thermal-pause on the Thor.
Recording this session's thermal-pause finding in `OUTBOX.md` and
stopping -- not polling or waiting out the remaining ~100s of Otogi's run
from inside the session.

## Session 13 (2026-09-30, from 12:32 PDT, resumed as attempt 4)

**Why attempt 3 (session 12) did not finish.** It did. It stopped at its
documented `waiting:` checkpoint with three requests outstanding (187 and
Arctic Thunder battery-gated on the Nova, Otogi running on the Thor) and an
`OUTBOX.md` entry naming them. The PR stays `State: draft` because those
requests had no verdicts. Session 12 had also ended before lane.local's
12:10 PDT addendum (the 600-s confirmation rule), so this resume applies it.

Merged `origin/master` (2 commits: lane.defecttriage433's fold, docs only;
clean). Pushed as `5a0a940b8e`. defecttriage433's table adds no new
candidate: every title it ranks is under the bar, already owned, or needs a
route.

### Otogi: FAIL on heat (Thor), recorded as heat evidence

`title_verdict.py <dir> --require confirmation` on
`1-1790790097-lane.verdict433-43486`:

`FAIL(thermal: sustained play failed at the device's defaults --
thermal-pause-F8 1/1 began after +703 s and by +736 s (device 09-30
11:01:19); still paused at the last reading)`, gameplay 1278.6 s, **fps_ok
0.350**, audio short 0.136%, net 4.06 W, 0.188 J/frame. Peak xo-therm 77.9 C,
70.3 C at the end, `fan.speed` 0 throughout. The run's net power sat under
the 10:20 addendum's ~4.5 W guidance and it still paused. **Short-run power
does not predict the full window on the fan-dead Thor.** Not re-running it
there.

### The 600-s rule (12:10 PDT addendum)

- **187 and Arctic Thunder:** both were queued at 1200 s, before the rule.
  There is no lane-side withdraw in `request.sh`, and editing `queue/` by
  hand is not a lane's to do, so both stay as queued. Each will be judged
  with `--require confirmation`. A 1200-s pass is stronger than a 600-s one
  and needs no audit re-run.
  - 187 (`-3086875`) is now `running/` on the Nova.
  - Arctic Thunder (`-3086903`) is still battery-refused (Nova at 46%, needs
    48.3%, `.battery_refused.nova` at 12:15 PDT).
- **Checked the rule's effect on earlier FAILs.** None of this lane's FAILs
  turns into a 600-s pass:
  - AUF was stuck at a door, which is not gameplay at any length.
  - Otogi is disqualified by heat, and the Thor stays off.
- **The audit (every 5th 600-s pass re-run at 1200 s):** this lane has no
  600-s passes yet. Crimson would be the first.

### Added: Crimson Skies, one Nova 600-s confirmation

- **Pass check.** `scan.py Crimson` finds no pass verdict for 4D530021.
- **Evidence.** Judged copies (`judge_copy.py`) of every finished Nova
  Crimson run since 09-28 19:00 PDT:

| Run | Build | Gameplay s | Share 28.5+ | Hang | Audio short | net W |
|---|---|---|---|---|---|---|
| `1-1790708501-lane.ibcache-1378258` | c8e95ed539, `HAKUX_IBC=0` (master's path) | 250.7 | 94.1% | no | 0 | 7.30 |
| `1-1790724690-lane.ibcache-1390145` | c8e95ed539, IBC on | 253.9 | 96.6% | no | 0 | 7.11 |
| `1-1790724691-lane.ibcache-1390243` | a987e375db (ibcache-jcsize) | 253.9 | 96.6% | no | 0 | 7.20 |
| `1-1790724691-lane.ibcache-1390402` | 9808982fa7 (ibcache-jcsize) | 249.9 | 96.6% | no | 0 | 7.13 |
| four others (ibcache, memfast) | -- | void | -- | -- | -- | frontend focus theft, not the title |

- **Why Crimson.** It is the one 30-capped title in the 09:55 addendum's
  list with evidence above 90% on the Nova. Nightfire, Blinx 2 and Ghoulies
  read 52-73% (sessions 8 and 10).
- **The chance of a pass is about 0.5.** Master's own path read 94.1% in one
  250-s window, a 4-point margin; the 96.6% runs are on builds master does
  not carry.
- **What the run decides.** Crimson is Playable now, or it waits on
  ibcache/#591 to fold.
- **Not low-watt** (7.1-7.3 W net). It is still the only new candidate with
  any evidence.
- No new Nova soaks since the session-10 sweep would add another: 10 runs
  finished since 09-30 01:00 PDT, of which only the hddcrash Crash runs and
  one uberspike DOA run are new Nova titles, and session 8 already passed
  over both.

Queued with `queue_batch8.sh` at `5a0a940b8e`: `--seconds 820`, which is the
route's mark at ~105 s + 600 s + 115 s margin, with `PERF_REGIMEN=default`:

| Title | Device | Regimen | Route | Seconds | Request |
|---|---|---|---|---|---|
| Crimson Skies | nova | default | crimson-skies | 820 | `1-1790796880-lane.verdict433-750238` |

Verified in `queue/` by exact path. The pilot gate admitted it at ~56 min of
this lane's outstanding device time (`pilots/lane.verdict433.ok` 5.8 h old).

### Running table (confirmations)

| Title | Device | Regimen | Request | Verdict |
|---|---|---|---|---|
| **KOF: Maximum Impact - Maniax** | nova | default | `-1456797` | **PASS Playable** (99.4%, 1282.6 s) |
| **Azurik: Rise of Perathia** | nova | default | `-1456876` | **PASS Playable** (95.2%, 1292.3 s) |
| **WWE Raw 2** | nova | default | `-1456493r2` | **PASS Playable** (99.8%, 1276.9 s) |
| **50 Cent: Bulletproof** | nova | default | `-1456544r2` | **PASS Playable** (99.1%, 1348.3 s) |
| **Baldur's Gate: Dark Alliance** | nova | default | `-366130` | **PASS Playable** (100%, 1303.9 s) |
| 007: Agent Under Fire | nova | default | `-366094` | FAIL (stuck at a door, not gameplay; needs its own route) |
| Alien Hominid | thor (cold-start control) | default | `-3086847` | void (heat stop at xo 70 C, 402 s); already Playable (`lanelocal-1183547`, 09-26) |
| Otogi: Myth of Demons | thor (cold-start) | default | `-43486` | **FAIL (thermal)**: pause at +703 s, 35.0% at 28.5+, peak xo 77.9 C, 4.06 W net |
| 187: Ride or Die | nova | default | `-3086875` | running (1200-s confirmation) |
| Arctic Thunder | nova | default | `-3086903` | queued, battery-refused (46%, needs 48.3%) |
| Crimson Skies | nova | default | `-750238` | queued (600-s confirmation, 09-30 rule) |

**Playable count (lane.local's 10:50 tally): 6.** Alien Hominid (09-26),
plus this lane's five.

### Next, in order

1. **187 and Arctic Thunder:** judge each with `title_verdict.py <dir>
   --require confirmation`, and check the last route frame for a
   results/continue screen.
2. **Crimson:** judge with `--require screening` and record it as a "600-s
   confirmation (09-30 rule)". If it passes, it is the first 600-s pass and
   counts toward the every-5th audit.
3. **Tier B/C unchanged:**
   - DOA needs a fight route.
   - Kabuki is flagged and still stalls (kabukistall's fold keeps the
     68.6 s fight stall).
   - Forza waits on #583.
   - GTA SA waits on #591.
   - AUF needs its own route.
4. No Thor work while `lanelocal-fanwait` holds.

### Ending session 13 here: waiting

Three Nova requests are outstanding: 187 running, Arctic Thunder
battery-gated, and Crimson queued. All three are dispatch work outside this
session. Recorded in `OUTBOX.md`; stopping.
