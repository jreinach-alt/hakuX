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

