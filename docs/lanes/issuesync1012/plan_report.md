issue_mirror plan -- 2026-10-12 19:02:54 PDT
GitHub: 626 items (min 1 max 629)
Forge:  960 items (min 1 max 960)

=== 0. Mirror-down: GitHub-only numbers needing a forge twin ===
count: 0

=== 1. Backfill: forge-only numbers beyond GitHub max (629) ===
count: 331 (range 630-960)
  PR    closed: 123
  PR    open  : 17
  issue closed: 14
  issue open  : 177

estimated GitHub requests at 4/min (240/hr) pacing:
  without historical comments: 471 requests, ~2.0 hours
  with historical comments:    639 requests (168 comments), ~2.7 hours
  historical-comment recommendation: mirror going forward only (`sync` picks up any comment posted after
  the backfill cutover); backfilling 168 historical comments now costs ~0.7 extra hours nobody is waiting on.

=== 2. State conflicts on common numbers: 22 ===
  #16   gh=closed  fg=open    kind=issue -- Depth surface readback converts incorrectly
  #34   gh=closed  fg=open    kind=issue -- Vulkan validation layer: four open findings from the desktop lane
  #66   gh=closed  fg=open    kind=issue -- GL renderer: one stale GL_INVALID_FRAMEBUFFER_OPERATION aborts the des
  #71   gh=closed  fg=open    kind=issue -- GL surface-to-texture fast path is wrong for every format that exercis
  #74   gh=closed  fg=open    kind=issue -- Android FP JIT: FIST/FISTP truncate where x86 rounds per the control w
  #81   gh=closed  fg=open    kind=issue -- tcg tier-1: promotion requests multiply instead of occupying a slot, a
  #87   gh=closed  fg=open    kind=issue -- Surface_pitch::Swizzle: with the race out, the 10,240-px residual is t
  #89   gh=closed  fg=open    kind=issue -- Color_zeta_overlap/Swap_ZB: 141,125 px on the desktop lane, exactly 0 
  #90   gh=closed  fg=open    kind=issue -- tcg tier-1: the anti-churn tier-hint restore is compiled out on Androi
  #92   gh=closed  fg=open    kind=issue -- SurfaceShape carries no address, so framebuffer_dirty() cannot see a D
  #99   gh=closed  fg=open    kind=issue -- Stencil: three ZERO captures regressed 0 -> 100,000 px between 2501f35
  #439  gh=closed  fg=open    kind=PR    -- lane.fmv303c: #303 surface write-back probe for Spikeout's FMV green
  #513  gh=closed  fg=open    kind=issue -- Foreground guard reads dumpsys input's stale ANR block: every Thor tit
  #557  gh=closed  fg=open    kind=issue -- Thermal adaptation: step quality down before the 78 °C thermal pause (
  #583  gh=closed  fg=open    kind=PR    -- lane.forzadecay414: clear an invalidation stamp when its slot's fence 
  #591  gh=closed  fg=open    kind=PR    -- lane.ibcache: inline indirect-branch cache + return-address stack (#50
  #592  gh=closed  fg=open    kind=issue -- Soak foreground watch voids runs when a dumpsys read hangs (adb timeou
  #598  gh=closed  fg=open    kind=issue -- thor dispatch worker is dead: 17 requests stuck, oldest 21h
  #605  gh=closed  fg=open    kind=PR    -- tcg: #424 range test on by default (tcg424flip)
  #607  gh=closed  fg=open    kind=PR    -- lane.litcompile569: #569 B1 gate 4, the cold DOA soak read
  #618  gh=closed  fg=open    kind=PR    -- lane.uberspike569: uber libraries under GPL, a first draw with no crea
  #627  gh=closed  fg=open    kind=PR    -- hddperm: dev_push sets 660 on what it pushes (titles.qcow2 crash-loop)
  resolution (round 2, applied by `seed`): close all 22 on the forge to match GitHub, including #583 --
  lane.local read it: it is forzadecay414's PR, last comment 09-30, the fix shipped; the 10-12 updated_at
  is metadata churn, not activity.

=== 3. Content divergences on common numbers: 3 ===
  #1: gh='Fix launching and exiting a game from an external frontend, and ship v' fg='#1: not recovered'
  #161: gh='territory.toml lists hw/xbox/nv2a/nv2a.c as both [free] and [lane.vbla' fg='#161: not recovered'
  #568: gh='lane.remote: #557 audit LOWs fixed ahead of the hook' fg='#568: not recovered'
  resolution (round 2, applied by `seed`): #1/#161/#568 copy GitHub's title+body onto the forge (the forge
  import never recovered the original content there). #107 stays in NEVER_SYNC (two independently-useful
  things at the same number, not a conflict).

=== 4. Three sample backfill bodies, exactly as they would be posted ===
--- forge #630 -> POST /issues (kind=issue, state=closed, labels=['github-import', 'reserved-number', 'backfill']) ---
title: #630: reserved (no GitHub record)
body:
  <!-- forge-import:github#630 -->
  No GitHub issue or PR #630 is known. The highest known is #629. Numbers up to the import ceiling are reserved, so that a GitHub number found later cannot collide with a forge-native one. Forge-native issues and PRs start above the ceiling.
  
  <!-- hakux-mirror:v1 src=forge#630 -->
  (then PATCH /issues/<returned-N> {"state": "closed"})

--- forge #641 -> POST /issues (kind=PR, state=closed, labels=['backfill']) ---
title: [PR] bf2ubosize433: size Battlefield 2's per-draw uniform-block churn before the push-constant fix (#433)
body:
  Forge PR #641, branch `lane/bf2ubosize433`.
  Status: merged into master @ e602b6f684.
  
  # bf2ubosize433: size Battlefield 2's per-draw uniform-block churn before the push-constant fix (#433)
  
  State: ready
  
  Lane: bf2ubosize433            Issue: #433
  Base: master @ 66bce0c222
  Files: docs/lanes/bf2ubosize433/NOTES.md, docs/lanes/bf2ubosize433/OUTBOX.md, docs/lanes/bf2ubosize433/PR.md, docs/lanes/bf2ubosize433/ubosz_read.py, docs/lanes/bf2ubosize433/ubosz_selftest.py, docs/testing/predictions/bf2ubosize433-bf2-ubosz.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/shaders.c
  Prediction: docs/testing/predictions/bf2ubosize433-bf2-ubosz.json (registered before the run; judged PUSH -- F16 0.917, R16 0.413, see NOTES.md section 6)
  Needs device: yes (one Nova soak, done: 1790958948-lane.bf2ubosize433-1976093)    Needs NDK: yes (perflog build)
  
  ## What this adds
  
  A perflog-only counter of how much of the uniform block changes between
  consecutive uploads (`ubosz[...]` on hakuX-stall, every 60 flips). It reports
  histograms of changed 16-byte chunks of the VS+PS layouts and of changed
  vertex-constant rows, the binding switches, a replayed 8/16-vec4
  push-constant policy, and UBO binds. It is checked on the host
  (`ubosz_selftest.py`), and the judge (`ubosz_read.py`) is checked against a
  synthetic logcat. See NOTES.md sections 1-3.
  
  ## Result
  
  One Nova soak (bf2mc route, 420 s, ref d9729d6250, no `hw/` change since)
  judged **PUSH**: in BF2's heavy views, 92% of same-binding uniform uploads
  change <= 16 vec4 (median 3-4), and even counting shader-binding switches
  (36% of uploads) a 16-vec4 push-constant policy would leave only 41% of
  uploads still forcing a UBO rebind. The push-constant fix bf2stall433 named
  is justified. This lane does not build it: a successor brief is posted to
  `OUTBOX.md` (forge #656) naming the files, the budget (Nova
  `maxPushConstantsSize`, believed 256 B, unverified), the concrete registers
  that churn (`c112`-`c115`, `c96`-`c105`, the `ltc*` uniforms), and the
  switch-share caveat. NOTES.md section 6 has full numbers.
  
  Release note (none): instrumentation, compiled only in NV2A_PERF_LOG builds.
  
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  
  <!-- hakux-mirror:v1 src=forge#641 -->

--- forge #643 -> POST /issues (kind=PR, state=closed, labels=['backfill']) ---
title: [PR] hddcrash: titles disk mode 660; a request's HAKUX_TITLES_DISK wins (#397)
body:
  Forge PR #643, branch `lane/hddcrash`.
  Status: labeled `folded` on the forge, but the forge has not recorded it as merged yet (state is still open, unmerged) -- a pre-existing forge-side inconsistency, not something this tool invented.
  
  # hddcrash: titles disk mode 660; a request's HAKUX_TITLES_DISK wins (#397)
  
  State: ready
  
  Lane: hddcrash            Issue: #397
  Base: master @ a3681ccb0b0eb2cc445fd59dc501473f51b8ce92
  Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-hdd-split.sh, docs/lanes/hddcrash/NOTES.md, docs/lanes/hddcrash/PR.md, docs/lanes/hddcrash/OUTBOX.md
  Prediction: none: no arm (a harness fix; the proof is a title soak, after the fold)
  Needs device: yes    Needs NDK: no
  
  Release note (none): harness title-disk builder
  
  ## Cause: the disk's file mode, not its bytes
  
  `adb push` leaves `titles.qcow2` at mode 0644. The app reaches files in `files/x1box` through a group, so it can read the disk but not open it read-write. `rollback_release.sh:89` documented this failure for hdd.img on 09-12. #622's `dev_push` never set the mode.
  
  What happens at start-up:
  1. `xemu_check_file` (system/vl.c:2536) only opens the disk `"rb"`, so the `-drive` is added.
  2. `configure_blockdev` (system/vl.c:2103, `&error_fatal`) fails with "Could not open ...: Permission denied" and calls `exit(1)` on the qemu thread.
  3. The render thread still holds GL, so the process dies in `libGLESv2_adreno.so` (SIGSEGV, `si_addr=0x0`) or on "pthread_mutex_lock called on a destroyed mutex". That happens 2-7 ms after `sdl2_display_early_init`, before stderr reaches logcat.
  
  There is no NULL bug in xemu itself.
  
  | evidence | result |
  |---|---|
  | early crashes, all Nova/Thor logcats 09-28 00:00 to 09-29 20:05 | hdd.img: ~190 runs, 0. titles.qcow2: 10 of 11 runs died (21 of 22 starts) |
  | desktop xemu 8d72e2d4af, hdd = copy of `nova-52e09d0361a3.qcow2` | opens it: gets past `configure_blockdev` to "Failed to load BIOS" |
  | the same copy at mode 0444 | `Could not open '...': Permission denied`, exit 1 |
  | the "170 MB image" | the same b634 disk after the one run that booted it (18:42) wrote 168 MB to it |
  
  The builder (`saves.py` / `titlestate.py` / `make_xbox_hdd.py`) is unchanged: its output is a valid qcow2 that qemu opens.
  
  ## Fix (dispatcher.sh)
  - `dev_push` sets 660 on the `.new` file before the rename and reads the mode back. This also covers `hdd_img_guard`'s hdd.img reset, which pushes through the same function.
  - `titles_disk_prepare` makes a **kept** disk 660 before every title run. This is needed because 52e0, the disk now on the Nova, plans `keep` and would never be pushed again. If the disk can't be made 660, the request fails before hddPath is set. hdd.json now records `mode_found`, `mode` and `split_from`.
  - A request's own env `HAKUX_TITLES_DISK` beats the worker's kill switch, in both directions.
  
  ## Selftest
  New legs in 99-hdd-split. The fake push leaves 0644, as the real one does. The legs cover:
  - the pushed disk is 660;
  - a kept 0644 disk is repaired, with its bytes unchanged;
  - a chmod failure fails the prepare;
  - the override works in both directions;
  - the reset hdd.img is 660.
  
  Results: 61 pass on this branch. Against master's dispatcher.sh, 9 of them fail.
  
  ## Local checks (no CI while GitHub is suspended)
  
  - `SELFTEST_ONLY=99-hdd-split docs/testing/jobs/selftest.sh`: 61 passed, 0 failed.
  - full `docs/testing/jobs/selftest.sh`: **incomplete, 0 FAIL in what ran.** On 09-29 ~22:30-23:00 PDT the host sat at load ~260
    and the fragments crawled: four `SELFTEST_SHARD=k/4` shards, detached, finished 29 of 116 fragments with 0 FAIL
    (10-arms-list, 55-affinity-offpool, 56-desktop-worker, 57-vsh-disc, 58-pull-verify, 65-*, 66-*, 67-status-measured,
    70..76-cloud/fold/nv2a/pr-sweep/x1a7, 79-stop-hook-hold, 80-labels, 84-perf-regimen, 85-fold-ci, 86/87-nightly, 87-fold-stale-ci,
    88-sweep-cover). Attempt 2's whole run got through the arms chain 10..50 and 51-dispatch-hardening A-E2 (52 ok, 0 FAIL)
    before it died. The fragments that drive dispatcher.sh, where the change is, are 99-hdd-split and 51-dispatch-hardening,
    plus the arms chain. All of those ran green. The rest of the full run is left to `offline_fold.py`'s selftest.sh gate.
  
  ## Device proof: after the fold
  
  Not in this PR. The worker runs `$DISPATCH_DIR/bin`, a snapshot of master, so the chmod and the per-request override are not live until this folds and the dispatcher tree is updated. After that, the three Nova requests listed in NOTES.md "Device proof" run, and lane.local removes the `titlesdisk-off.conf` drop-in once they are green.
  
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  
  <!-- hakux-mirror:v1 src=forge#643 -->

=== 5. check-style summary ===
max numbers: github=629 forge=960 (forge ahead by 331, accounted for by backfill above)
