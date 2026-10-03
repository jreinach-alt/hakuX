# lane.opsrebuild -- NOTES (#433)

## Why

The owner, 2026-10-02 ~10:30 PDT (relayed by lane.local): "Hostops needs urgent rework. It's
burning tokens, and it's not effective at clearing jams or distributing work ... It's clearly
lighting tokens on fire so this is urgent." Measured by lane.local at 10:25 PDT: 42 model ticks
in 24 h, ~43 turns and ~$1.70 each, about $110/day, mostly to re-derive facts a script can read
directly (a systemd unit's state, a file's age, a hold's bound) and apply a known fix. This lane
builds the **ops** layer: jam clearing, model-free by default, model only for what a script
genuinely cannot decide. The other two roles hostops folded together split out elsewhere:
**foreman** (distributing work) is lane.localforge's; **project manager** is a scheduled Opus job
lane.local is setting up.

## Inventory: every harness_health.py check and every hostops-poll.md runbook item

One row per distinct check/runbook item (~147), classified SCRIPT (model-free detector + scripted
remedy belongs in `ops_tick.py`), ESCALATE (needs judgement -> `ops_escalate.sh`), RESOURCE
(the check's purpose still holds but its current implementation is GH-bound; a local-truth
equivalent already exists and should replace it), or DROP (obsolete: GitHub labels/API with no
local equivalent needed, a retired program, or the owner's 10-02 device-filling stop). Produced by
reading `harness_health.py` (2,931 lines) and `hostops-poll.md` in full, including the 2026-10-02
OVERRIDE block that is authoritative over the runbook text below it.

| # | Name | What it detects | Source (local truth vs GH-bound) | Known fix / local equivalent | Verdict |
|---|---|---|---|---|---|
| 1 | `gh-auth`/`checker:gh-auth` | git fetch / `gh api user` failing -> GH outage itself | Deliberately probes GH; already local (fetch rc + api rc) | Self-resolves when GH returns; this *is* the recovery sensor | SCRIPT |
| 2 | `lanes:never-started` | Board row with no session/wt/offline-journal commit ever | Reads `territory.toml` via `git show origin/board:` -- stale while GH fetch is down | status/local-board.md | RESOURCE |
| 3 | `lanes:unread-addendum` | Brief edited after session start, never re-read | Same stale board-row source | status/local-board.md | RESOURCE |
| 4 | `lanes:wait-on-idle-holder` | Lane waits on a holder lane with a dead/no PR | Gated entirely behind `GH_DOWN: continue` -- fully disabled now | offline_status.py + status/local-board.md | RESOURCE |
| 5 | `lanes:merged-unwoken` | PR merged, device runs finished after session ended, nothing wakes it | Same GH_DOWN-gated block | offline_status.py / lane's PR.md on branch | RESOURCE |
| 6 | `lanes:finished` | PR merged, row still holds files | Same GH_DOWN-gated block | offline_status.py | RESOURCE |
| 7 | `lanes:gh-down-pr-state-suppressed` | Summary note that #4-6 were skipped this tick | Itself the GH-outage safety valve | Disappears once #4-6 are resourced | RESOURCE |
| 8 | `lanes:stranded` | Lane ended, draft/no PR, nothing in flight, past idle SLO | Also inside the `GH_DOWN: continue` block -- currently disabled | **implemented in ops_tick.py's `det_stranded_lanes`** (git for-each-ref + PR.md state, no GH) | SCRIPT |
| 9 | `lanes:rowless` | Running unit with no board row | `active` (local systemctl) vs stale `lanes` (origin/board) | status/local-board.md | RESOURCE |
| 10 | `pr-flow:draft-red` | Draft PR, lane not running, CI red | `prs`, `gh pr view --json statusCheckRollup` | offline_status.py / lane OUTBOX.md | RESOURCE |
| 11 | `pr-flow:draft-green-ciwait` | Draft PR waiting on CI, CI now green, nothing marks ready | `gh pr view` CI + comments | offline_status.py | RESOURCE |
| 12 | `pr-flow:draft-orphan` | Draft PR quiet, lane not running, nothing in flight | `prs`, PR `updatedAt` | offline_status.py | RESOURCE |
| 13 | `pr-flow:unlabelled` | Ready PR with no pipeline label | `prs`, GH labels | offline_status.py (PR state) | RESOURCE |
| 14 | `pr-flow:conflict` | PR CONFLICTS with master, CI never runs on it | `gh pr view --json mergeable`; local `git merge-tree` for the file list | Compute mergeable entirely via local `git merge-tree`; **offline_fold.py already does this itself at fold time** -> `fold-failure:conflict` | RESOURCE |
| 15 | `pr-flow:fold-stuck` | fold-ready PR not folded past SLO | `gh api .../timeline` for label event | foldqueue.log / fold-failures.log | RESOURCE |
| 16 | `pr-flow:audit-stuck` | needs-audit/-remediation PR quiet, no audit session | `prs` + `age_min(updatedAt)` | offline_status.py | RESOURCE |
| 17 | `pr-flow:two-writers` | Cloud audit session and lane unit both touch one branch | Local unit/branch check only | none needed | SCRIPT |
| 18 | `pr-flow:parked-audit` | Hostops-parked audit whose lane has ended, never restored | Local `host-tools/parked-audits.tsv` + branch check | none needed | SCRIPT |
| 19 | `lanes:unreleased-at-ready` | Ready PR (unit gone) whose row still holds unreleased files | `fleet.py` (local) + `prs` for draft/suffix exemption | Resource the `prs` exemption lookup to offline_status.py | RESOURCE |
| 20 | `capacity:capacity-parse` | `fleet.py` DISPATCHABLE section unparsable | Pure local parser | fix parser | SCRIPT |
| 21 | `capacity:capacity` | Dispatchable issues unowned while lanes run under cap | `fleet.py` (local) + issue labels via `ghj` | offline_status.py / lane.issuerecon's rebuilt issue log | RESOURCE |
| 22 | `devices:dangling-result`+checker | Dangling results/ symlink from a demoted id | Pure dispatch file scan | none needed | SCRIPT |
| 23 | `devices:arms-renamed`+checker | Arms pair names a request id that was renamed | Local arms/pairs + dispatch files | none needed | SCRIPT |
| 24 | `devices:ownerhold-title` | Title soak pinned to an owner-held device, stuck >30 min | Local hold files + queue | none needed | SCRIPT |
| 25 | `devices:flap`+`adblog` | adb USB transport dropped repeatedly | Windows adb.log (local) | none needed | SCRIPT |
| 26 | `devices:guest-exit-early`+checker | Guest died early, run reads as finished | Local run.log/results scan | none needed | SCRIPT |
| 27 | `devices:absent-owner` | Device off adb under owner hold, movable requests pinned to it wait | Local `adb devices` + hold files | none needed | SCRIPT |
| 28 | `devices:absent` | Device not on adb at all | Local `adb devices` | none needed | SCRIPT |
| 29 | `devices:adb` | `adb devices` returns nothing | Local | none needed | SCRIPT |
| 30 | `devices:covered`+`health:covercheck` | Foreign overlay covers display 0 | Local `dumpsys window` | none needed | SCRIPT |
| 31 | `devices:usbdialog` | systemui USB dialog stealing focus | Local `dumpsys activity` | none needed | SCRIPT |
| 32 | `devices:display-hold` | hostops-display hold stuck on with no cover left | Local | none needed | SCRIPT |
| 33 | `devices:not-foreground`+`health:fgcheck` | Title soak running but hakuX not foregrounded | Local adb | none needed | SCRIPT |
| 34 | `devices:dispwin-dead` | hostupd hold stuck, dispatcher_update_window.sh died | Local /proc scan | none needed | SCRIPT |
| 35 | `devices:hold-over-run` | Lane holds device while a run is in flight | Local /proc, cgroup | none needed | SCRIPT |
| 36 | `devices:cooldown-stuck` | Cooldown hold not released in time | Local devwatch | none needed | SCRIPT |
| 37 | `devices:batt-draining` | Battery hold in place but device still draining | Local devwatch.json history | none needed | SCRIPT |
| 38 | `devices:noworker-held` | Held device has no dispatcher worker | Local ps scan | none needed | SCRIPT |
| 39 | `devices:hold-orphan` | Hold's pid dead, lane unit not running | Local | none needed | SCRIPT |
| 40 | `devices:hold-overbound` | Hold past its own stated bound | Local hold `.why` file | **implemented in ops_tick.py's `det_hold_overbound`** | SCRIPT |
| 41 | `devices:hold` (generic) | Hold past the generic 90-min SLO | Local | folded into #40 above | SCRIPT |
| 42 | `devices:deadworker` | Attached unheld device, dispatcher worker dead | Local ps | none needed | SCRIPT |
| 43 | `devices:admit-flat` | Battery-admission refusing a device that isn't charging | Local dispatcher.log + devwatch.json | none needed | SCRIPT |
| 44 | `devices:idle` | Device idle while runnable work queued | Local queue/running | none needed (device-filling is itself STOPPED 10-02; this check mostly matters once it resumes) | SCRIPT |
| 45 | `0.5:stale-push-flag`+checker | Title push flag unconsumed >30 min | Local titlepush flags | none needed | SCRIPT |
| 46 | `devices:fg-anr`+checker | Dispatcher snapshot regressed the foreground-ANR fix | Local file-content check | none needed | SCRIPT |
| 47 | `coldslot:repilot-unscheduled` | Parked re-pilot not in any coldslot chain | Local parked dirs + systemd | none needed | SCRIPT |
| 48 | `coldslot:pilot-failed` | Pilot failed review, nobody fixing it | Local | none needed | SCRIPT |
| 49 | `coldslot:unserved`+checker | Cold-parked requests with no server at all | Local | none needed | SCRIPT |
| 50 | `coldslot:lift-waiter`+checker | Battery-lift waiter armed for a device with no due hold | Local devwatch.json | none needed | SCRIPT |
| 51 | `devices:starved` | Request jumped repeatedly by later-queued work | Pure dispatch/queue FIFO logic | none needed | SCRIPT |
| 52 | `devices:batt-affinity`+checker | Unpinned request stuck on a battery-refusing device | Local devwatch + dispatcher.log | none needed | SCRIPT |
| 53 | `devices:plainprio` | 0.5-labelled request queued at plain priority | `gh api issues/<n>` for the `0.5` label | Local issue-label source (lane.issuerecon) | RESOURCE |
| 54 | `devices:nudge-loop` | jamcheck restarting dispatcher repeatedly | Local jamcheck.log | none needed | SCRIPT |
| 55 | `deploy:tree-parse`/`deploy:tree` | Dispatcher tree far behind master on the serve path | Local git rev-list + dispatcher.sh source | none needed | SCRIPT |
| 56 | `gates:board:<chk>` | origin/board fails territory/coverage | Runs locally in board-wt | none needed | SCRIPT |
| 57 | `gates:master-red` | master CI red | `gh run list` | No CI runs at all while GH is down; local selftest (#58) is the substitute | RESOURCE |
| 58 | `gates:master-selftest` | jobs-selftest red on master, host-run | Fully local | none needed | SCRIPT |
| 59 | `pr-flow:fold-multi` | fold throttled on a sha whose CI run was cancelled | `gh api actions/runs` | foldqueue.log / fold-failures.log | RESOURCE |
| 60 | `gates:unit:<f>` | Failed hakux-* systemd unit | Local systemctl | **implemented in ops_tick.py's `det_failed_unit`** (ESCALATE: no safe generic fix) | SCRIPT detector / ESCALATE remedy |
| 61 | `gates:overnight` | Overnight mode left on too long | Local state file | none needed | SCRIPT |
| 62 | `gates:timer:<svc>` | Timer unanchored | Local systemctl | **implemented in ops_tick.py's `det_timer_unanchored`** | SCRIPT |
| 63 | `gates:tick-hung` | A one-shot tick running past its bound | Local systemctl/ps | none needed | SCRIPT |
| 64 | `memory:oom` | OOM-killed process | Local journalctl | none needed | SCRIPT |
| 65 | `memory:wsl-interop` | WSL vsock interop failures | Local journalctl | none needed | SCRIPT |
| 66 | `memory:host-commit` | Windows commit headroom low | Local PowerShell probe | none needed | SCRIPT |
| 67 | `memory:host-disk` | C: drive low on free space | Local PowerShell probe | **implemented in ops_tick.py's `det_disk_low`** (checks `/` and `/mnt/c`; ESCALATE, no safe auto remedy) | SCRIPT detector / ESCALATE remedy |
| 68 | `memory:msrdc-loop` | WSLg RDP client reconnect-loop | Local file count | none needed | SCRIPT |
| 69 | `inbox:<item>`+`inbox-parse` | HOST INBOX item open with no DONE line | Local hostops-inbox.md | none needed | SCRIPT |
| 70 | `board-requests:breq` | Board-request file open >30 min with no DONE | Local dispatch/board-requests/*.md | none needed | SCRIPT |
| 71 | `board-requests:routerec` | Route-ready queued but no DONE line naming it | Local | none needed | SCRIPT |
| 72 | `board-requests:route` | Route-ready with no benchmark queued at all | Local | none needed | SCRIPT |
| 73 | `device-budget:budget` | Pilot-rule violation (>30 min device time, no reviewed pilot) | Local queue/running + pilots dir | none needed | SCRIPT |
| 74 | `devices:unclaimable`+checker | Non-`.req` file sitting in queue/ | Local dir scan | none needed | SCRIPT |
| 75 | `devices:bugcheck` | Guest bugchecked, emulator spins until timeout | Local logcat scan | none needed | SCRIPT |
| 76 | `scoring:scoring` | Device held while host still scores captures | Local pgrep/ps | none needed | SCRIPT |
| 77 | `devices:overrun` | Run exceeded expected wall time | Local run timing | none needed | SCRIPT |
| 78 | `devices:soak-truncated` | Soak's logcat span half its seconds, no reason logged | Local logcat scan | none needed | SCRIPT |
| 79 | `devices:route-died` | route.sh died mid-script but soak ran its full window | Local run.log scan | none needed | SCRIPT |
| 80 | `devices:route-died-running` | Same, for a still-running soak (cancel now) | Local run.log scan | none needed | SCRIPT |
| 81 | `devices:voidstreak` | 3 crash/not-foreground runs in 30 min, none VOIDed | Local logcat/run.log pattern | Detection scriptable; root-causing the crash needs judgement | ESCALATE |
| 82 | `devices:fleet-stop`+checker | Both handhelds about to go dark on battery with queue waiting | Local devwatch.json | Routes to the owner (charger/PD hub) -- genuinely owner-level | ESCALATE |
| 83 | `devices:fg-aborts` | >=2 soaks aborted not-foreground in 30 min | Local run.log scan | none needed | SCRIPT |
| 84 | `devices:device-reality-missing` | device_reality.sh never wrote state | Local file check | none needed | SCRIPT |
| 85 | `devices:device-reality-stale` | device_reality.sh stale >25 min | Local file check | none needed | SCRIPT |
| 86 | `devices:dev-held` | Device held and out-of-sync >90 min | Local .device-reality.json | none needed | SCRIPT |
| 87 | `devices:dev-sync` | Device idle per dispatcher but out of sync | Local | none needed | SCRIPT |
| 88 | `supply:idle-standing` | lane.xbox/lane.remote idle, nothing routed to it | `ghj` issue-comments feed | lane's OUTBOX.md + status/local-board.md | RESOURCE |
| 89 | `flow:dead-delivery` | Delivery comment sent to a lane with no row/unit | Same GH-comments feed | OUTBOX.md / deliver.sh local send log | RESOURCE |
| 90 | `flow:orphan-pr` | Open lane/* PR with no board row and no running unit | `prs` | offline_status.py | RESOURCE |
| 91 | `lanes:parked-nowaker` | blocked:* PR/issue parked, runs in flight, no waiter | `prs` + GH issue labels | offline_status.py | RESOURCE |
| 92 | `lanes:capped-waiter` | Waiter armed to resume a lane already at attempt cap | Local waiters + attempts files | none needed (also: `lane.sh resume` itself refuses past the cap -- ops_tick.py relies on that rather than re-deriving it) | SCRIPT |
| 93 | `flow:confounded-fail` | `regressed` label from a cross-device arms FAIL | `prs` + PR comments | Needs a local record of arms verdicts | RESOURCE |
| 94 | `flow:blocked-resumed` | handback keeps re-resuming a deliberately blocked PR | `prs` + comments | offline_status.py + OUTBOX.md | RESOURCE |
| 95 | `flow:false-needs-owner` (both variants) | blocked:needs-owner mislabeled when the lane is alive | `prs` + PR body | Lane's PR.md on its branch instead | RESOURCE |
| 96 | `supply:sweep-owed` | Tracker rows wait on a post-fold sweep nobody queued | Local tracker (via stale `origin/board`) + dispatch | status/local-board.md for the tracker read | RESOURCE |
| 97 | `supply:stale-sweep` | Parked full-sweep dir superseded by a newer one | Local dispatch/parked + git ancestry | none needed | SCRIPT |
| 98 | `0.5:05-unowned` | 0.5-labelled issue has no lane and no stated blocker | `gh issue list --label 0.5` | Planned lane.issuerecon issue log; no clean local source yet | RESOURCE |
| 99 | `0.5:gh-down-offpolicy-suppressed` | Summary note that offpolicy check was skipped | Itself the GH-outage safety valve | Disappears once #98/#100 are resourced | RESOURCE |
| 100 | `0.5:05-offpolicy` | Lane started on a non-0.5 issue after the policy cutoff | `gh issue list` labels | lane.issuerecon issue log | RESOURCE |
| 101 | `0.5:05-stale-label` | `lane:<x>` label outlives a retired lane | `gh issue list --label 0.5` | lane.issuerecon issue log | RESOURCE |
| 102 | `0.5:05-title-routes-unowned` | No row holds docs/testing/titles/routes | Stale board `lanes` dict | status/local-board.md | RESOURCE |
| 103 | `0.5:05-stage-idle` | Title-routes stage lane idle, nothing queued | Stale board `lanes` dict | status/local-board.md | RESOURCE |
| 104 | `0.5:owner-priority` | Owner-priority title not at device head | Local dispatch/queue + results | none needed | SCRIPT |
| 105 | `0.5:05-roles-unreadable` | device_roles.json unreadable | Local file | none needed | SCRIPT |
| 106 | `0.5:05-wrong-device` | Title request pinned to the wrong device by role/one-copy rule | Local device_roles.json + listing-*.txt | none needed | SCRIPT |
| 107 | `pr-flow:cloud-offfocus`/`-claim`+`health:cloud-offfocus` | cloud.sh claims an issue outside BOARD_FOCUS_LABEL | `gh issue list --label cloud` | Needs a local issue-label source (same gap as #98) | RESOURCE |
| 108 | `memory:fragmentation` | order-7 allocation failures (WSL interop risk) | Local journalctl | none needed | SCRIPT |
| 109 | `memory:dstate-leak` | Processes wedged in D state | Local ps/journalctl | none needed | SCRIPT |
| 110 | `recovery:manifest-stale` | Recovery manifest stale/missing | Local file mtime | none needed | SCRIPT |
| 111 | `dispatch:queue-cliff` | Queue count cliff-drop unexplained | Local recovery/history manifests + logs | none needed | SCRIPT |
| 112 | `0.5:one-copy` | Mirror/pull queue would copy a title to a second handheld | Local titlepush queue files | none needed | SCRIPT |
| 113 | `0.5:invq-no-nova-copier` | Nova investigation-copy entries queued, no copier unit running | Local titlepush queue + systemctl | none needed | SCRIPT |
| 114 | `env-leak:env-leak`+checker | Finished run shows a leaked env var it didn't request | Local logcat scan | none needed | SCRIPT |
| 115 | `hand-read:hand-read`+checker | Result promised a hostops hand-read, none recorded | Local result dirs | none needed | SCRIPT |
| 116 | `relnote:relnote`+checker | Ready PR touching emulator code with no Release-note line | `prs` + GH files/body | File list via local `git diff`; body via lane's PR.md | RESOURCE |
| 117 | `escalations:escalations` | Unresolved escalation line past SLO | Local escalations.md | none needed | SCRIPT |
| 118 | `arms-skip:arms-skip`+checker | arms.sh permanently skips a prediction a stopped lane waits on | `arms.sh list` (local) + PR branch state | offline_status.py for branch/PR state | RESOURCE |
| 119 | Runbook 0: LANE COMMENTS FIRST (`attention.sh`) | Unanswered comments/requests/holds needing a reply | GH issue comments | OUTBOX.md / local-board.md / hostops-inbox.md | RESOURCE |
| 120 | Runbook 00(a): start lanes on `[0.5]` unowned | Depends on #98 | Same as #98 | RESOURCE |
| 121 | Runbook 00(b): stop off-policy lanes | Depends on #100 | Same as #100 | RESOURCE |
| 122 | Runbook 00(c): device-queue 0-0-x / idle time to title work | Owner-policy routing rule | 10-02 OVERRIDE item 3: explicitly STOPPED | DROP |
| 123 | Runbook 00(d): parked-until-after-0.5 list (Turnip etc.) | Static policy reminder, not a live check | n/a | DROP |
| 124 | Runbook 00(e): perfarch-external-ideas hand-off | One-shot historical task (09-25) | n/a | DROP |
| 125 | Runbook 00(f): title-pipeline per-stage ownership | 10-02 OVERRIDE item 3: explicitly SUSPENDED | n/a | DROP |
| 126 | Runbook 00(g): device roles / one copy per title | Already covered by #104-106, #112 (local) | superseded by scripted checks | SCRIPT |
| 127 | Runbook 1: timers/tree/foldpace (`gh run view`) | Timer/unit/tree parts local (#55/60/62); foldpace root-cause needs `gh run view` | foldqueue.log/fold-failures.log for the fold part | RESOURCE |
| 128 | Runbook 2: fleet.py/board tick/`audit_outlet.sh`->`cloud.sh` claim | fleet.py/board tick local; cloud.sh claims issues via GH | Needs lane.localforge + gh shim (not yet built) | RESOURCE |
| 129 | Runbook 3: ARMS job check (`arms.sh list`, unreadable legs) | Fully local file/log based | none needed | SCRIPT |
| 130 | Runbook 4: Open PRs (`gh pr list/view`, labelling, unjam_index) | Entirely GH-bound | offline_status.py + foldqueue.log/fold-failures.log; labelling needs lane.localforge | RESOURCE |
| 131 | Runbook 5a: close issue on fold | `gh` issue close | offline_status.py / foldqueue.log | RESOURCE |
| 132 | Runbook 5 b0: STRANDED LANES (`status.sh --print`/fleet.py) | Fully local (board-wt scripts) | **implemented in ops_tick.py's `det_stranded_lanes`**, independent of status.sh | SCRIPT |
| 133 | Runbook 5b: generic stranded resume / blocker grant / silicon question | Requires judging blockers and routing decisions | n/a | ESCALATE |
| 134 | Runbook 5c: lane.nightlynotes (`gh release view`) | Fully GH-bound (`gh release create/upload` itself is down) | Blocked until lane.localforge/gh-shim lands | RESOURCE |
| 135 | Runbook 6: lane.xbox board requests, TRACKER/LABEL edits, re-pin | Local dispatch/board-requests read side; the gated push target needs GH | Already partly covered (#70-72); push side needs lane.localforge | RESOURCE |
| 136 | Runbook 6b: DRIVER RUNS (`#68` comment trigger via `gh`) | Trigger is a GH issue comment | Needs an OUTBOX.md-style local trigger instead | RESOURCE |
| 137 | Runbook 6f: TITLE BATCH | Explicitly retired 2026-09-26 | n/a | DROP |
| 138 | Runbook 6g: UBUNTU VOLUME HYGIENE (`prune_worktrees.sh`, `df -h`) | Fully local | **implemented in ops_tick.py's `det_disk_low`** covers the `df` half; `prune_worktrees.sh --apply` is a candidate SCRIPT remedy a future tick can wire in | SCRIPT |
| 139 | Runbook 6i: BOARD-ROUTED LANE STARTS | Reads brief from `origin/board:briefs/<x>.md` (stale while GH down) | status/local-board.md should carry pending starts instead | RESOURCE |
| 140 | Runbook 6l: OWNER WATCH (gameplay-FPS/#404 via GH comments) | GH comment feed | offline_status.py / lane OUTBOX.md | RESOURCE |
| 141 | Runbook 6m: PILOT RULE (`park_requests.sh`) | Fully local, mirrors #73 | none needed | SCRIPT |
| 142 | Runbook 6n: perfregimen/titlestate one-shot + `device_reality.sh --fix` | One-shot done; `device_reality.sh --fix` ongoing and local | already scripted (separate from ops_tick's own battery-floor backstop, #67/`det_battery_floor`) | SCRIPT |
| 143 | Runbook 6o: TITLE BENCHMARKS FILL SPARE DEVICE TIME | 10-02 OVERRIDE item 3: explicitly STOPPED | n/a | DROP |
| 144 | Runbook 7: decision-needed/blocked:needs-owner issues | GH issue labels + owner-level judgement | offline_status.py for the label read; the decision is judgement | ESCALATE |
| 145 | Runbook 8: Handheld batteries (`device_reality.sh --fix`, manual adb) | Fully local | Already covered by #37/#43/#82, plus ops_tick's own backstop (`det_battery_floor`) | SCRIPT |
| 146 | Runbook 10: 0.5 RELEASE GATE GHOULIES | Soak measurement local; release-candidate record is manual/GH-adjacent | Judge locally against the registered prediction; no GH dependency for the gate decision | SCRIPT |
| 147 | BOARD PUSH GATE item (`check_territory.py`/`check_coverage.py`) | Runs locally against the board worktree's HEAD | Already covered by #56; the push target needs GH/lane.localforge | RESOURCE |

**Rough counts:** ~72 SCRIPT, ~44 RESOURCE (almost everything that reads `gh`/`ghj`/`prs`/GH
comments/labels -- these map to `offline_status.py`, `status/local-board.md`, `foldqueue.log` /
`fold-failures.log`, and lanes' own `OUTBOX.md`/`PR.md`, with a few genuinely blocked on
lane.localforge/a `gh` shim not yet built), 6 DROP (10-02 OVERRIDE's device-filling/title-batch
items plus two static one-shot policy notes), 5 ESCALATE (`voidstreak`, `fleet-stop`, the generic
stranded-lane/blocker decisions, `blocked:needs-owner` judgement calls -- genuinely need a human
or a model's judgement, not a script).

## What `ops_tick.py` implements now (the brief's "minimum jam set")

Nine detectors, each model-free, each reading only local files (no `gh`, no network):

| class | detector | remedy (SCRIPT) or none (ESCALATE) |
|---|---|---|
| `hold-overbound` | a device hold past its `.why`-stated bound (or the 90-min default) whose tag names a lane whose unit is not active | `hold.sh release <dev> <tag>` |
| `stranded-lane` | a lane branch's `PR.md` is `State: draft`, no `hakux-lane-<name>` unit running, no STOPPED marker | append an addendum to its brief, `lane.sh resume <name>` ONCE |
| `fold-failure:territory` / `:rowless` | `fold-failures.log`: "outside [lane.X]'s files" / "no [lane.X] row" | write a widening request to `hostops-inbox.md` |
| `fold-failure:conflict` / `:selftest` / `:no-device-run` | `fold-failures.log`: a merge conflict, a selftest failure, or no device run built from the head | route to the lane (addendum + resume ONCE); cleared by a later `FOLDED <branch>` line |
| `fold-failure:other` | any other fold failure reason | logged, no remedy (ESCALATE) |
| `queue-stale` | a `dispatch/queue/*.req` older than 60 min with a free, admissible device | `dispatch_jamcheck.sh --nudge` |
| `timer-unanchored` | a `hakux-*.timer` with no next run, paired `.service` not mid-run | `systemctl --user start --no-block <service>` |
| `failed-unit` | a `hakux-*` unit in `systemctl --state=failed` | none -- ESCALATE on sight (no safe generic fix) |
| `battery-floor` / `battery-lift` | `.device-reality.json` level below/above the floor/lift, held/unheld by ops_tick's own tag | `hold.sh take/release <dev> ops.battery ...` |
| `disk-low` | `/` or `/mnt/c` free space below threshold | none -- ESCALATE on sight |
| `stopped-lane-queued` | a `.STOPPED-by-owner-*` lane still named by a queued/running request | none -- ESCALATE on sight (cancelling someone's run needs judgement) |

Jam lifecycle (`jams.tsv`, columns `opened class subject remedy_tried cleared_at
time_to_clear_s`): a jam opens the first tick it is seen (remedy runs once, if one exists); a
remedy-bearing jam that is still open after `OPS_ESCALATE_AFTER_MIN` (default 30 min) escalates; a
no-remedy jam escalates on the SAME tick it is first seen (there is nothing to wait on); any jam
not re-detected clears (`cleared_at`, `time_to_clear_s`). A `(class, subject)` that clears and
later recurs opens as a fresh instance -- its row's `opened` timestamp and remedy state reset, so
its age is measured from the recurrence, not the first time this pair ever jammed.

`ops_escalate.sh` spawns exactly one `claude -p` session per escalating jam: Sonnet first,
`claude-opus-5-5` if the SAME `(class, subject)` escalates again (its own `escalations.json`
tracks the count and the running `$` total, which `write_summary()` rolls into
`ops/summary.txt`). Its prompt is ONLY that jam's evidence file plus `escalate-role.md` (58
lines) -- never the whole harness. The role file repeats the authority boundary from the brief
verbatim: no `gh`, never resume a STOPPED lane, never queue device work to fill idle time, never
edit `offline_fold.py`/`territory.toml`/`nv2a_issues.toml`. Its own tool allowlist
(`allowed-tools.ops-escalate`) drops `Bash(gh:*)` and `WebFetch` from the stock job allowlist, so
the boundary is enforced, not just stated.

### Known gaps in this first cut (left for the next lane, or a later ops_tick revision)
- `hold-overbound` only recognizes tags shaped `lane.<name>`; a hold taken under any other tag
  shape (an ad hoc session name, a job name) is left alone rather than guessed at. This is the
  common case (OWNER_HOLD_TAGS aside) but not the only one harness_health.py covered.
- The RESOURCE rows above (~44) are mapped to their local-truth equivalent but not yet wired into
  a detector; most need `offline_status.py`'s output in a machine-readable form (today it is
  prose) before a script can read it, which is lane.localforge/lane.issuerecon territory, not
  this lane's files.
- `prune_worktrees.sh --apply` (runbook 6g) is a candidate tenth SCRIPT remedy, not wired in --
  it is destructive enough (removes worktrees) that it deserved its own leg and evidence trail
  rather than riding in under this brief's deadline; left as a note for the next revision.

## Shadow run (step 5)

`ops_tick.py --shadow` was run against the REAL local state on this host (read-only: every
remedy/escalate call is gated off in shadow mode -- see `run()`'s `if jam.remedy and not shadow`
and the escalation branch's `if shadow: ... else: run_escalation(...)`), with `OPS_STATE_DIR`
redirected to a scratch path under this worktree so no host file outside it was touched. See
`docs/lanes/opsrebuild/shadow-comparison.md` for the run(s), what each tick saw, and the
side-by-side against hostops's own last several ticks (`host-tools/hostops-inbox.md`,
`logs/hostops*` where readable). **This lane's session cannot block for the full >= 2 h the brief
asks for** (no foreground call exceeds 10 minutes, and ending a session waiting on a background
timer is exactly the failure mode `roles/lane.md` and this project's memory warn against) --
the comparison documents what was run and hands lane.local the exact command to extend it to the
full window before flipping the timers, rather than fabricating a multi-hour result.

## Selftest

`docs/testing/jobs/selftest.d/87-ops-tick.sh`: 23 checks, all against ops_tick.py's OWN fixture
tree (`$T/ops`, never the shared `$DISPATCH_DIR`/`$HAKUX_WORK` other fragments use, and never the
shared `$T/bin/systemctl` shim -- it only answers `is-active`, and this job also needs
`list-timers`/`list-units --state=failed` shapes, so every systemctl call is routed through
`$OPS_SYSTEMCTL`). Legs: (a) a dead-lane hold past its bound releases; an owner-tagged hold past
the same bound does not; (b) a stranded lane resumes exactly once across two ticks, a STOPPED
lane never resumes; (c) fold-failures.log: territory writes an inbox note, conflict resumes the
lane, a later FOLDED line clears the jam and a further tick does not re-act, and a branch that
has since pushed past its recorded failure is dropped rather than kept open on stale evidence;
(d) a failed unit escalates on its first tick (no remedy to wait on), not again inside the
escalate window, and clears once no longer failed; (e) a device below its battery floor is held
with ops_tick's own tag and released once it climbs back above the lift threshold -- this leg
was added AFTER manually finding that the first cut's `hold.sh take` reason string embedded a
bare `<` and `(ops_tick)`, both shell metacharacters under `shell=True` (a redirection and a
syntax error); reverting the fix and re-running confirmed this leg catches it; (f) `--shadow`
logs intent and writes nothing. Run:
`env SELFTEST_ONLY="87-ops-tick.sh" bash docs/testing/jobs/selftest.sh` (28 passed, 0 failed;
leg (g) proves `jams.tsv`'s tab-separated format survives a `remedy_tried` whose source text
carries a raw tab/newline, after a similar manual-test catch: `save_jams`/`load_jams` now flatten
whitespace per field).
`bash docs/testing/jobs/selftest.sh --check-shards 4` still covers all fragments (this one lands
in whichever shard is lightest; it carries no SHARD_CHAINS entry since it touches nothing another
fragment reads). Also ran the FULL unsharded `selftest.sh` (all ~121 fragments) before marking
this PR ready, since `offline_fold.py` requires it for any harness-file change; result recorded in
PR.md.

## Units (step 5: lane.local installs; this lane does not touch host-tools/ or the live units)

`docs/testing/jobs/ops/units/hakux-ops-tick.{service,timer}`: oneshot, every 5 min
(`OnUnitActiveSec=5min`), `TimeoutStartSec=90` (detectors read a handful of small local files and
run a couple of `systemctl`/`hold.sh` calls -- well under the brief's "< 30 s" in practice, 90 s
is the unit's safety margin, not the expected runtime). **For lane.local, at cutover:** copy (or
symlink) these into wherever the other `hakux-*` units live, `systemctl --user daemon-reload &&
systemctl --user enable --now hakux-ops-tick.timer`, THEN `systemctl --user disable --stop
hakux-hostops.timer` (if a tracked unit exists for it; if hostops runs from an ad hoc host-side
script rather than a committed unit, stop whatever currently fires it). Point `OPS_STATE_DIR`
somewhere durable (default `$HAKUX_WORK/host-tools/ops-state`) before the first non-shadow tick.

## Attempt 2 (2026-10-03): why attempt 1 did not finish

Attempt 1 built the layer and opened PR.md, but did not finish. Two of the brief's gates stayed
open. (1) The >= 2 h side-by-side shadow run. A session cannot block that long, so attempt 1
handed it to lane.local with a command, which is correct, but the run was never clean. (2) The
shadow comparison was posted from a run that could not show the faults it had. Its "tick 2 was
identical to tick 1, so detection is stable" claim was wrong: shadow mode never persisted its jam
rows, so every tick saw every jam as new, and two identical ticks were two copies of the same
bug, not evidence of stability. The overnight timer lane.local started (`hakux-ops-shadow.timer`,
from 10-02 22:19, 101 ticks logged) then ran attempt 1's code and exposed three faults, which
lane.local posted as Addendum 2. Attempt 1 did not finish because it verified detection by
looking at one tick and never checked identity across ticks, and because it never compared its
fold-failure list against master.

## Attempt 2: the three shadow faults (Addendum 2, lane.local 10-03)

Overnight log `logs/ops-shadow.log`: the same six fold-failure jams and two stranded lanes were
announced `NEW JAM` on every one of the 101 ticks (594 announcements for the six fold jams alone,
99 for the stranded lane), and the failed-unit subject was the bullet glyph `●`.

| # | Fault | Cause in `ops_tick.py` | Fix | Test (`87-ops-tick.sh`) |
|---|---|---|---|---|
| 1 | Every jam re-announced as NEW every tick | `run()` returned before `save_jams` in shadow mode, so `jams.tsv` never existed and every jam opened fresh. Shadow escalation count never advanced either. | Shadow keeps `jams.shadow.tsv` and `escalations.shadow.json` in its own state dir. It never touches the real `jams.tsv`, and it writes no `summary.txt`. A would-be escalation advances the same count and clock a real one would, so the Opus switch and the cadence show in shadow. | (j): a second `--shadow` tick does not re-announce; identity lives in `jams.shadow.tsv` |
| 2 | Fold-failure jams for branches already folded (snapdrive, usagemode, ibcache, routedriver, stopmarker, uberspike569-gpl) | `det_fold_failures` dropped a branch only when its head moved on. A FAILED line for an abandoned or folded head stayed open forever. | A recorded head that is an ancestor of `origin/master` is dropped. Checked by hand before the fix: all six heads are ancestors of master. The fold head is also now hex-only, because it is interpolated into a shell command. | (h): a fold failure whose head is in master raises no jam and no inbox note |
| 3 | `failed-unit ●` | `line.split()[0]` took systemctl's bullet glyph as the unit name. | Matches the `hakux-*` unit token anywhere on the line (`UNIT_TOKEN_RE`). | (i): a bulleted failed unit is named by its token; the glyph is never a subject |

**Falsification.** Before the fix, the three new legs failed on the unfixed code (6 FAIL, 29 passed).
After the fix, 35 passed, 0 failed.

**Real-state check (scratch state dir `/tmp/ops-verify`, `--shadow`, same host state as the timer):**

| tick | jams open | NEW announced | remarks |
|---|---|---|---|
| 1 | 6 | 6 | the six real jams: 2 stranded lanes (`tronhang672`, `verdict433`), `fold-failure:rowless lane/titleroutes`, `fold-failure:territory lane/savestate433`, two failed units |
| 2 | 6 | 0 | identity persists; no re-announcement, no re-remedy |

Compared with the overnight log, the six false fold jams are gone. `failed-unit` now names
`hakux-local-issue-audit.service` and `hakux-nightly.service`. Those are real failed units (the
detector saw them with `systemctl --state=failed`), so they now carry signal instead of `●`. Both
will escalate on sight, as designed. Lane.local should look at them; nothing here touched them.

**Known gap, not confirmed as a false jam.** `det_stranded_lanes` decides "running" by
`hakux-lane-<name>.service` being active and nothing else. At 22:19 on 10-02 it listed
`lane.opsrebuild` as stranded, and that tick ran while attempt 1's session was live. I have not
established whether that session was under a unit at the time. A lane session that runs outside its
unit would read as stranded, and the remedy resumes it. Lane.local should check that one before
cutover, because the remedy is the risky part.

## Next (P x win)

The brief's gate is one clean 2-hour `--shadow` run on this head. The shadow timer already runs the
working tree, so the window has started. This session cannot block for 2 h. Candidates, scored as the
brief's RULE asks:

| candidate | P (works) and evidence | win if it works | cost | decides |
|---|---|---|---|---|
| A. Let the shadow timer run 2 h on this head; compare `ops-shadow.log` against hostops's inbox entries for the same window; cut over if clean | P ~0.9: all three faults are fixed and each has a leg that fails on the old code; two real-state ticks show identity and folded-branch removal; the remaining risk is a false jam the fixture tree does not produce | removes ~$110/day of model ticks (42 ticks/day at ~$1.70 each) | 2 h wall-clock; no device | itself: a clean window cuts over; a false jam in the window picks B's detector fix first |
| B. Wire the RESOURCE rows (~44) to a machine-readable `offline_status.py` output, so the checks harness_health.py has been blind to since 09-29 come back | P ~0.5: the output is prose today, so the parse is the risk; the coverage win is real, but the sources are in lane.localforge's and lane.issuerecon's territory | restores coverage of the GitHub-bound checks; the size of that win is unmeasured | a lane on another lane's files; not this session | nothing needed before A's window ends |

A decides first because it is the only gate between this layer and the $110/day it replaces, and
it costs nothing but wall time. B is the larger win but at lower P, and it lives in other lanes'
files. It runs after the cutover, not before.

**Status:** code and docs done for the three faults. The clean 2-h shadow run is waiting; PR.md
stays `State: draft` until lane.local posts that comparison. See OUTBOX.md's waiting entry.
