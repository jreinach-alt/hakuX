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
