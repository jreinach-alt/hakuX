## hakuX harness -- live status

_Rewritten 2026-09-26 16:24 PDT by `status.sh` on the host. Every time on this page is PDT. Sections that could not be computed say so._

_Next roll-up due by 2026-09-26 16:54 PDT. A clock older than that means `status.sh` has stopped: a roll-up that is not running cannot say so itself._

### Lanes running (cap 24)

| lane | issue | attempt | model | running for | PR |
|---|---|---|---|---|---|
| claimrace | #420 | 2 | claude-opus-5-5 | 41m ago | #446 draft |
| pilotgate | #397 | 3 | claude-opus-5-5 | 17m ago | #420 open |
| relprio432 | #432 | 1 | claude-opus-5-5 | 45m ago | #447 draft |
| titlestate | #397 | 2 | claude-opus-5-5 | 53m ago | #442 draft |

### Lanes: every row on the board (PDT)

> [!WARNING]
> **1 lane idle with no work:** perfregimen. Unit stopped, nothing queued or running on a device, and its PR is a draft or absent -- nothing will wake it.

| lane | state | issue | PR | last session ended | it said |
|---|---|---|---|---|---|
| perfregimen | **:warning: IDLE, NO WORK** |  | #444 draft | 09-26 16:18 | The regimen is in: title soaks switch to MAX performance and fan before the app starts and... |
| arms | job (hakux-arms.timer) |  | none | never |  |
| aufire412 | PR ready, awaiting a label | #412 | #416 open | 09-26 16:24 | PR #416 is marked ready, but it does not fix #412. The code change works as designed, and ... |
| blinx372d | blocked: #372 IN FLIGHT (job.board 2026-09-26T21:55Z): lane.blin... | #372 | #396 merged | 09-26 13:12 | PR #396 is marked ready for review. Two things are still outstanding: CI on the new head `... |
| buildflags427 | waiting on device (0 running, 2 queued) | #427 | #435 draft | 09-26 13:41 | The build flags are in and verified in the symbol table, but the before/after fps number d... |
| claimrace | running |  | #446 draft | 09-26 15:33 | The full selftest is still running; the monitor will report its FAIL lines and summary whe... |
| doa413b | waiting on device (0 running, 4 queued) | #413 | #440 draft | 09-26 15:27 | I found where the DOA2U fight's `surface_update` time goes and pushed a fix for it, but it... |
| flatlm13 | blocked: #13 IN FLIGHT (job.board 2026-09-26T21:55Z): lane.flat... | #13 | #401 merged | 09-26 13:18 | PR #401 is now marked ready. The arm passed, and the magnitude check matched the offline p... |
| fmv303c | blocked: #303 after 0.5: the 0.5-first policy (owner 2026-09-26,... | #303 | #439 draft | 09-26 14:53 | Lane fmv303c is blocked, not finished. The Thor soak hasn't run, so #303 has no answer yet... |
| fold | job (hakux-fold.timer) |  | none | never |  |
| forza414 | blocked: #414 FILE HELD (job.board 2026-09-26T21:55Z): lane.forz... | #414 | #418 merged | 09-26 13:53 | PR #418 is marked ready. It carries analysis only: no code change, and no prediction becau... |
| jcache425 | waiting on device (0 running, 8 queued) | #425 | #443 draft | 09-26 15:11 | I've finished the pilot, added counters and queued the A/B arms, but there is no verdict y... |
| pilotgate | running |  | #420 open | 09-26 15:58 | PR #420 still can't fold. Merging master cleared the out-of-date failure, but the new head... |
| relprio432 | running | #432 | #447 draft | never |  |
| ring53impl | folded (row not yet retired) | #53 | #395 merged | 09-26 13:48 | PR #395 is done and marked ready. The device test (the "arm") comparing the ring against c... |
| tbchurn424 | waiting on device (0 running, 9 queued) | #424 | #434 draft | 09-26 13:37 | I've written and queued the fix for #424, but nothing is measured on a device yet: ten Tho... |
| titlestate | running | #397 | #442 draft | 09-26 15:20 | Phase 1 is finished and posted on #397. Phase 2 can't start until I get a device grant, so... |
| toolsmith | folded (row not yet retired) | #94 #95 | #361 merged | 09-26 04:27 | I fixed defect 27 in PR #386, which is marked ready and labelled `needs-audit-1`. Defect 2... |
| triage | standing, nothing in flight |  | none | never |  |
| vcpuprime428 | folded (row not yet retired) | #428 | #437 merged | 09-26 16:09 | Pinning the emulated CPU thread to the Thor's prime core (`HAKUX_PLACE_VCPU=prime`) is ref... |
| yuv10 | PR needs remediation | #10 | #419 open | 09-26 14:47 | PR #419 is out of draft and marked ready, on head `9536845ce5`. The device test confirmed ... |
| vshcpu345 | retired 09-26 13:40 |  | #402 merged | 09-26 12:45 | The patched vector-shader evaluator now matches the Xbox console on every row it targets, ... |
| doa413 | retired 09-26 13:40 |  | #417 merged | 09-26 13:09 | PR #417 is now ready for review. It separates the two problems in #413, but proposes no fi... |
| cull13 | retired 09-26 13:40 |  | #403 merged | 09-26 13:04 | PR #403 is marked ready and goes to audit because it touches `hw/`. The device test of the... |
| foldcancel | retired 09-26 13:15 |  | #415 merged | 09-26 12:26 | I've pushed the fix as PR #415 and marked it ready for review. A fold tick whose final tru... |
| titleplay | retired 09-26 12:35 |  | #399 merged | 09-26 12:10 | PR #399 is marked ready for review. It's pushed at `08ad953514` with `origin/master` merge... |
| fmv303b | retired 09-26 11:50 |  | #398 merged | 09-26 10:45 | Turning the tier1 JIT tier off does not change Spikeout's FMV green, so tier1 is not the c... |
| armsscope | retired 09-26 11:20 |  | #409 merged | 09-26 10:59 | The fix is in and PR #409 is marked ready: `arms.sh` now counts only a PR's own prediction... |
| boardpushgate | retired 09-26 10:58 |  | #408 merged | 09-26 10:43 | The board push gate is built and PR #408 is out of draft. The jobs selftest passed (1827 c... |
| pshaniso284 | retired 09-26 10:40 | #284 #315 | #393 merged | 09-26 07:20 | PR #393 has both fixes, both device tests passed, CI is green on the current head (329df5e... |
| surfwatch382 | retired 09-26 07:14 | #382 | #387 merged | 09-26 05:34 | The fix works: with it, 50 Cent: Bulletproof's intro movies play at full speed on the Nova... |
| fmv303 | retired 09-26 07:14 | #303 | #317 merged | 09-25 20:31 | PR #317 is now marked ready. It ends as an analysis-only outcome: the green is in the game... |
| zrtz272 | retired 09-26 06:50 | #272 #275 | #364 merged | 09-26 04:36 | Arm 3 passed and PR #364 is ready for review. |
| ring53 | retired 09-26 06:50 | #53 | #391 merged | 09-26 06:08 | Lane ring53 is finished but blocked: no emulator code landed. PR #391 is now ready (analys... |
| dpforce345 | retired 09-26 06:50 | #345 | #383 merged | 09-26 04:47 | PR #383 is now marked ready. The re-registered prediction passes on the device: all 291 ch... |
| blinx372c | retired 09-26 06:50 | #372 | #388 merged | 09-26 05:40 | I found the site behind Blinx's two surface-download waits per frame in the attract demo, ... |
| y16bump10 | retired 09-26 04:40 | #10 | #367 merged | 09-26 04:11 | PR #367 is finished and I made no new commits this session. The previous session did get t... |

_40 more rows retired in the last 24 h are not listed._

- **lane.xbox** (interactive session; the console): last `[lane.xbox]` comment 09-26 14:14 on #397: A label correction to the pass-1 table: the row "DOA Ultimate (DOA2U)" is the **Dead or Alive 1 Ultimate** dis...; **no host answer after it**. Device requests: none queued or running. console meter: ON, 66.2 W (read 0s ago).
- **lane.remote** (cloud session, one-way): last `` `[lane.remote]` `` comment 09-26 15:11 on #426: **Taking lane.local's queue (5850280192) in order.** Items 1 and 2 become one instrument PR while the Thor soa...; host answered 09-26 15:44.
- **host ops tick** (`hakux-hostops.timer`, every 20 min): last tick 09-26 15:39: ectly flags the claimrace log.

### Window budget (the account's five-hour and weekly windows)

- dispatching normally. Lanes and audits start as work allows; expanding is the default.
- week from 2026-09-20 17:00 PDT (85% elapsed, reserve from 2026-09-26 07:24 PDT), 565 run(s), spend 1132.1 of no declared budget, 0 usage-limit hit(s) this week (0 in the reserve); the weekly reserve is NOT armed: there is no declared WEEK_SPEND_BUDGET in $WORK/limits.env, and this fleet has been refused 0 time(s) since the reserve began (2 arms it).
- no session has ever been refused by the account's window on this host. That is the only first-hand evidence of a closed window there is: **the remaining five-hour and weekly balance cannot be queried from here**, so the weekly reserve arms on that evidence, or on `WEEK_SPEND_BUDGET` if the owner declares one in `$WORK/limits.env`. Unknown means open, by design.

### Lane sessions finished (last 24h)

| when (PDT) | lane | model | turns | min | result | PR | said |
|---|---|---|---|---|---|---|---|
| 09-26 14:51 | visual404 | opus-5-5 | 11 | 0 | ok | #436 draft | I didn't resume the work, because #404 is still parked until after the 0.5 release. The ow |
| 09-26 14:53 | fmv303c | opus-5-5 | 9 | 1 | ok | #439 draft | Lane fmv303c is blocked, not finished. The Thor soak hasn't run, so #303 has no answer yet |
| 09-26 15:11 | jcache425 | opus-5-5 | 93 | 10 | ok | #443 draft | I've finished the pilot, added counters and queued the A/B arms, but there is no verdict y |
| 09-26 15:16 | vcpuprime428 | opus-5-5 | 27 | 27 | ok | #437 merged | I've stopped here, waiting for the host to release the last four runs. PR #437 is still a  |
| 09-26 15:20 | titlestate | opus-5-5 | 125 | 19 | ok | #442 draft | Phase 1 is finished and posted on #397. Phase 2 can't start until I get a device grant, so |
| 09-26 15:27 | doa413b | opus-5-5 | 72 | 9 | ok | #440 draft | I found where the DOA2U fight's `surface_update` time goes and pushed a fix for it, but it |
| 09-26 15:33 | claimrace | opus-5-5 | 49 | 16 | ok | #446 draft | The full selftest is still running; the monitor will report its FAIL lines and summary whe |
| 09-26 15:58 | pilotgate | opus-5-5 | 42 | 36 | ok | #420 open | PR #420 still can't fold. Merging master cleared the out-of-date failure, but the new head |
| 09-26 16:03 | pri432 | opus-5-5 | 146 | 72 | ok | #438 merged | PR #438 is ready for review. CI is green on 1d99bcb5d9 (both builds and the jobs selftest) |
| 09-26 16:09 | vcpuprime428 | opus-5-5 | 37 | 36 | ok | #437 merged | Pinning the emulated CPU thread to the Thor's prime core (`HAKUX_PLACE_VCPU=prime`) is ref |
| 09-26 16:18 | perfregimen | opus-5-5 | 175 | 76 | ok | #444 draft | The regimen is in: title soaks switch to MAX performance and fan before the app starts and |
| 09-26 16:24 | aufire412 | opus-5-5 | 38 | 3 | ok | #416 open | PR #416 is marked ready, but it does not fix #412. The code change works as designed, and  |

_result: ok = ended on its own; MAXTURNS = cut at the turn cap, work kept; ERR = the session errored. A lane that ended without a ready PR is resumed by the board (attempts 1-3 on claude-opus-5-5, then claude-fable-5-1, then decision-needed)._

### Cloud-class sessions (hourly, on the host; last 24h from their `[job.cloud]` comments)

- 09-25 16:49 #325  claimed for audit2 (unit hakux-lane-cloud-audit2-325, model claude-opus-5-5, attempt 1 of 4).
- 09-25 16:50 #244  claimed for audit1 (unit hakux-lane-cloud-audit1-244, model claude-opus-5-5, attempt 1 of 4).
- 09-25 16:50 #289  claimed for audit1 (unit hakux-lane-cloud-audit1-289, model claude-opus-5-5, attempt 1 of 4).
- 09-25 16:51 #290  claimed for audit1 (unit hakux-lane-cloud-audit1-290, model claude-opus-5-5, attempt 1 of 4).
- 09-25 16:53 #325  the audit2 session for this PR ended without setting a next state, so `needs-audit-2` stays and the outlet w
- 09-25 17:12 #244  claimed for audit2 (unit hakux-lane-cloud-audit2-244, model claude-opus-5-5, attempt 1 of 4).
- 09-25 17:34 #289  claimed for audit2 (unit hakux-lane-cloud-audit2-289, model claude-opus-5-5, attempt 1 of 4).
- 09-25 17:56 #290  claimed for audit2 (unit hakux-lane-cloud-audit2-290, model claude-opus-5-5, attempt 1 of 4).
- 09-25 18:19 #325  claimed for audit2 (unit hakux-lane-cloud-audit2-325, model claude-opus-5-5, attempt 2 of 4).
- 09-25 18:30 #310  claimed for audit1 (unit hakux-lane-cloud-audit1-310, model claude-opus-5-5, attempt 1 of 4).
- running now: 

```
09-26 15:49 cloud-audit2-401 claude-opus-5-5 turns=17 81s ok PR #401 passes audit pass 2 with nothing left open, and it is now labelled `fold
09-26 15:53 cloud-audit1-419 claude-opus-5-5 turns=22 171s ok I finished the first audit pass of PR #419 (head `c3d401ad6b`). It found one MED
09-26 16:12 cloud-remediate-419 claude-opus-5-5 turns=20 78s ok I fixed the one medium finding from the first audit of PR #419 and pushed it as 
09-26 16:14 cloud-audit2-419 claude-opus-5-5 turns=18 98s ok I finished pass 2 on PR #419 and moved it to `needs-remediation`, not `fold-read
```

### Board job (every 20 min)

```
  FAIL: 1 lane PR(s) are READY and carry no pipeline label: #437. A ready PR with no needs-audit-*/needs-remediation/fold-ready/folded label is stalled -- nothi
2026-09-26 16:13:32 PDT capacity: 6/24 lanes running and 2 startable issue(s):
  #429 [0.5] [game] Performance: smaller translation blocks on often-rewritten pages  [0.5]
  #433 [0.5] [impact 0 px, measured] 0.5 release: the first tested-titles list for the Thor and Nova (target 2026-09-28)  [0.5]
2026-09-26 16:13:32 PDT ready PRs with no state label:
  #437 lane.vcpuprime428: #428 vCPU thread on the prime core, Crimson gameplay A/B
```

last model ticks:
```
09-26 15:32 board claude-sonnet-5 turns=16 51s ok The tick made no board edits, so nothing was pushed to `board`. I resumed one la
09-26 15:52 board claude-sonnet-5 turns=21 52s ok Nothing dispatched this tick, and I made no board edits or pushes because none w
09-26 16:14 board claude-sonnet-5 turns=16 49s ok Nothing to push or dispatch this tick, so I made no board edits, comments or lab
```

board branch: e62d272ea7 10 minutes ago -- hostops: #428 closed as refuted (PR #437); release lane.vcpuprime428's files at ready

### Handhelds and arms

- adb: bdc158a5(device) ee317437(device) 
- dispatcher: active, workers: 2
- queue: 23 waiting, 99 idle-tier z-* behind them, 0 running; holds: nova thor 
- dispatcher last line: `09-26 16:19:50 HELD by /home/justin/hakux-work/dispatch/hold/nova; claiming nothing until it is removed`
- affinity: lanes serving `desktop` -- an A/B pair queued now is pinned to one of them
- affinity notes, last 24h (a pair named here may span two devices and cannot isolate run-to-run variation):
  - `1790459680-arms-tbchurn424-fix-65417`: no poolable device lane is registered in /home/justin/hakux-work/dispatch/lanes, so f427c521c5ded1cf8b6c77990c4d744a8e6fb2169b578dea6dbee70f005393f1.json could not be pinned at all; if this is one arm of an A/B its partn
  - `1790459680-arms-tbchurn424-fix-65417`: prediction f427c521c5ded1cf8b6c77990c4d744a8e6fb2169b578dea6dbee70f005393f1.json was pinned to nova, which is not serving; freed this request, so the pair may span two devices and cannot isolate run-to-run variation 
  - `1790455261-arms-buildflags427-fix-4129802`: no poolable device lane is registered in /home/justin/hakux-work/dispatch/lanes, so 50d2bebef4a9e15133b6df8bdc4c87c3b5b67f0ac0d9f73d83b4fe4b3b2604b6.json could not be pinned at all; if this is one arm of an A/B its partn
  - `1790455260-arms-buildflags427-base-4129766`: no poolable device lane is registered in /home/justin/hakux-work/dispatch/lanes, so 50d2bebef4a9e15133b6df8bdc4c87c3b5b67f0ac0d9f73d83b4fe4b3b2604b6.json could not be pinned at all; if this is one arm of an A/B its partn
  - `1790463182-arms-doa413b-fix-1083874`: no poolable device lane is registered in /home/justin/hakux-work/dispatch/lanes, so 46210a732072550562fca3b7eb3cb2cf601b8701d4e2fb763e2fc4bfff75f8d4.json could not be pinned at all; if this is one arm of an A/B its partn
- arms job: 72 pair(s) queued or running and not yet judged; 71 judged; 46 skipped (see `arms.sh list`); watermark 2026-09-18 13:00 PDT (stored as `2026-09-18T20:00:00Z`: arms.sh compares that UTC string to registered_utc, so the file stays UTC and only this rendering is local)

last verdicts:

- `267b4c5752` lane/aufire412:docs/testing/predictions/aufire412-uboring-goldens.json: VERDICT: PASS -- all 100 registered checks hold.
- `545e0dc3c5` lane/yuv10:docs/testing/predictions/yuv10-csc.json: VERDICT: PASS -- all 84 registered checks hold.
- `3e0a694efe` lane/ring53impl:docs/testing/predictions/ring53impl-ring.json: VERDICT: PASS -- all 172 registered checks hold.
- `f34d19d9b3` lane/flatlm13:docs/testing/predictions/flatlm13-orient.json: VERDICT: PASS -- all 417 registered checks hold.
- `b002f5ac0b` lane/blinx372d:docs/testing/predictions/blinx372d-mnm2.json: VERDICT: PASS -- all 102 registered checks hold.

```
2026-09-26 15:53:02 PDT   queued base 1790463182-arms-doa413b-base-1083820 fix 1790463182-arms-doa413b-fix-1083874
2026-09-26 15:53:03 PDT   skip 93732f6edc40a6268b3357fbf39e22bcbb68d901fa42456c4d0d4c5e2e55b1bd: lane/perfregimen:docs/testing/predictions/perfregimen-pilot-nov
2026-09-26 16:24:10 PDT   skip b4d19e0e04c045efcfcd13373e78d36b242fd796b5f2f86cd0d7ec2cfebe7883: lane/perfregimen:docs/testing/predictions/perfregimen-pilot-tho
2026-09-26 16:24:15 PDT judged 267b4c57521edc602f50e3c400134396cb19dd2f524c0664b8b38c08d2e313ec: VERDICT: PASS -- all 100 registered checks hold. (lane/aufire41
```

last refusals, in full (a refusal is recorded once; delete the file under `$WORK/arms/skipped/` to retry):

- `b4d19e0e04` lane/perfregimen:docs/testing/predictions/perfregimen-pilot-thor.json: no a_ref/b_ref (a soak or a hand-read prediction)
told=2026-09-26T23:24:11Z
- `93732f6edc` lane/perfregimen:docs/testing/predictions/perfregimen-pilot-nova-fan5.json: no a_ref/b_ref (a soak or a hand-read prediction)
told=2026-09-26T22:53:04Z
- `66d9557131` lane/vcpuprime428:docs/testing/predictions/vcpuprime428-soak.json: a_ref == b_ref, nothing to compare
told=2026-09-26T22:22:26Z

### Fold job (every 30 min)

- fold-ready: ; needs-rebase: #420; needs-remediation: #419
- awaiting audit: needs-audit-1 ; needs-audit-2 
```
2026-09-26 16:20:31 PDT   deleted origin's lane/vcpuprime428 @ 49dd45e305 (every commit is on HEAD) and its tracking ref
2026-09-26 16:20:31 PDT   local refs/heads/lane/vcpuprime428 KEPT: error: cannot delete branch 'lane/vcpuprime428' used by worktree at '/home/justin/hakux-work/
2026-09-26 16:20:31 PDT     (if that lane is finished: lane.sh rm vcpuprime428)
2026-09-26 16:20:31 PDT tick: repaired none; folded #437; handed back none; waiting none
```
- master: 916c246260 5 minutes ago -- fold: PR #437 lane/vcpuprime428 -- lane.vcpuprime428: #428 vCPU thread on the prime core, Cr

### Open lane PRs

- #447 (draft) `lane/relprio432` lane.relprio432: 0.5 device requests queue ahead of other requests (#432) -- labels: none
- #446 (draft) `lane/claimrace` cloud.sh: never claim a number whose unit is running, and never undo a running u -- labels: none
- #444 (draft) `lane/perfregimen` lane.perfregimen: MAX perf+fan during title soaks, REST on every exit -- labels: none
- #443 (draft) `lane/jcache425` lane.jcache425: #425 fewer jump-cache flushes and an inline indirect-branch prob -- labels: none
- #442 (draft) `lane/titlestate` lane.titlestate: #397 first-run/returning routes and per-device title state -- labels: none
- #440 (draft) `lane/doa413b` lane.doa413b: #413 price and cut DOA2U surface_update cost -- labels: none
- #439 (draft) `lane/fmv303c` lane.fmv303c: #303 surface write-back probe for Spikeout's FMV green -- labels: blocked:after-0.5
- #436 (draft) `lane/visual404` lane.visual404: #404 reference-free visual scoring of scripted-play frames -- labels: blocked:after-0.5
- #435 (draft) `lane/buildflags427` Performance: native TLS, inline LSE atomics and no intra-library PLT for libxemu -- labels: none
- #434 (draft) `lane/tbchurn424` lane.tbchurn424: #424 translation-cache code-write invalidation and dirty re-arm -- labels: none
- #420 `lane/pilotgate` pilotgate: refuse a device batch over 30 min without a reviewed pilot -- labels: needs-rebase
- #419 `lane/yuv10` lane.yuv10: #10 SET_CONTROL0 colour-space conversion as silicon measured it -- labels: needs-remediation, verified
- #416 `lane/aufire412` lane.aufire412: #412 Agent Under Fire flat 16 fps split -- labels: verified

### Job errors (last 24h, from the units' logs)

- **board** (`/home/justin/hakux-work/logs/board/systemd.log`):
```
509:python3: can't open file '/home/justin/hakux-work/board-wt/docs/testing/jobs/summarise_run.py': [Errno 2] No such file or directory
555:python3: can't open file '/home/justin/hakux-work/board-wt/docs/testing/jobs/summarise_run.py': [Errno 2] No such file or directory
846:python3: can't open file '/home/justin/hakux-work/board-wt/docs/testing/jobs/summarise_run.py': [Errno 2] No such file or directory
```
- **arms** (`/home/justin/hakux-work/logs/arms/systemd.log`):
```
3:2026-09-19T02:56:34Z   skip e7d2d7398fa68af98650c6b1514d29fcda61b6a112336558f20fe7d37100d218: lane/blitsafe:docs/testing/predictions/issue89-clear-pad-alpha-shape.json: request.sh refused the base a
```
- **fold** (`/home/justin/hakux-work/logs/fold/systemd.log`):
```
2489:2026-09-26 15:56:35 PDT   local refs/heads/lane/flatlm13 KEPT: error: cannot delete branch 'lane/flatlm13' used by worktree at '/home/justin/hakux-work/wt/flatlm13'
2497:2026-09-26 16:05:34 PDT   local refs/heads/lane/pri432 KEPT: error: cannot delete branch 'lane/pri432' used by worktree at '/home/justin/hakux-work/wt/pri432'
2503:2026-09-26 16:20:31 PDT   local refs/heads/lane/vcpuprime428 KEPT: error: cannot delete branch 'lane/vcpuprime428' used by worktree at '/home/justin/hakux-work/wt/vcpuprime428'
```

### Host

- checkout `/home/justin/hakuX` on master, 13 behind origin/master (jobs run the fetched trunk regardless)
- timers: arms next -; board next 16:33:18 PDT; comments next 17:17:00 PDT; dx next 09:23:00 PDT; fold next 16:50:58 PDT; foldpace next 16:25:00 PDT; handbackpace next 16:32:00 PDT; hostops next -; issue-sweep next 19:41:51 PDT; jamcheck next 16:30:00 PDT; manifest next 16:30:00 PDT; nightly next 00:30:00 PDT; pr-sweep next 18:13:59 PDT; status next 16:53:23 PDT
- attempts: aasample=3 armlabel=1 armpin=1 armsscope=1 armsskip=3 aufire412=2 backlogstate=3 blankrule297=2 blendarm50=1 blendrace50=2 blinx372=1 blinx372b=1 blinx372c=2 blinx372d=1 blit83b=1 blit84=1 blitsafe=2 boardgate=4 boardprio=3 boardpushgate=1 branchprune=2 brdf315=1 brdf315b=1 buildflags427=1 ciskip=1 claimrace=2 cloud-audit1-181=1 cloud-audit2-163=1 cloud-audit2-308=2 cloud-issue-10=1 cloud-issue-111=1 cloud-issue-112=1 cloud-issue-13=1 cloud-issue-188=3 cloud-issue-189=1 cloud-issue-200=2 cloud-issue-271=2 cloud-issue-278=1 cloud-issue-279=1 cloud-issue-282=3 cloud-issue-283=1 cloud-issue-284=4 cloud-issue-286=1 cloud-issue-297=1 cloud-issue-34=1 cloud190=1 cloudclaim=1 cloudtail=1 cloudterritory=1 clrpad164=2 clrsurf91=3 clrvk184=1 clrwb91=4 clrwin88=1 cull13=1 cullnf276=2 desktopchannel=2 diagdump77=2 diagsoak77=1 dmasurf277=1 doa413=1 doa413b=1 dpforce345=2 draftstrand=3 drvab77=1 fix311=1 flatlm13=1 fleetreg=2 fmv303=1 fmv303b=2 fmv303c=1 fog278=1 foldcancel=1 foldci=3 foldflow=2 foldindex=1 foldregress=2 forza414=1 fps382=1 fulldisc50=1 g8b8285=1 gamecheck=1 ghoul311=4 glchannel=1 glerr86=1 goldencorr287=1 goldovr287=1 handback=3 handbackresolved=1 handbackstrand=1 hilodot10=1 indexcheck=1 indexloc=2 jcache425=1 laneshape=1 linecap13=2 localtime=1 nanattr281=1 nanfix281=1 nightlynotes=3 nightlytrunk=1 notespath=1 perfarch=2 perfbase=1 perfregimen=1 pilotgate=3 pmc188=3 pri432=2 primpv13=4 pshaniso284=2 pshqueue=3 regs200=1 relprio432=1 remotechannel=1 ring53=1 ring53impl=3 selftest86=1 selftestsplit=2 shade224=1 shadeflat224=4 shadetie224=1 shadetie224b=2 sphere273fix=1 spheremap273=1 stalecheck=2 statusdash=1 statusfresh=1 statuspage=1 surfwatch382=1 swatchorder50=1 sweepcover=2 sweepremote=1 sweeps=1 swizzle87=1 tbchurn424=1 tcgchurn=2 texvol283=1 tie282c=1 tiecode282=2 titleplay=1 titlerun=3 titlestate=2 toolsmith=3 turncap=1 turnipfork=2 vblank65=1 vcpuprime428=2 visual404=1 vklayer34=1 vkpointsize34=4 vol283r=1 vshconst=3 vshcpu345=1 vshnobegin242=2 vshr12280=1 vshsubneg255=1 vtxarr262=1 wbuf31fix=3 wbuf31sel=1 wbufclip=2 wbufdepth24=1 windowbudget=2 wparam223=1 wparamclip223=2 wparamcode223=1 wparamff223=1 wparamgeom223=1 x1a7271=1 y16bump10=2 yuv10=1 zclamp276=1 zdepth272=1 zetaswap275=1 zrtz272=4 
