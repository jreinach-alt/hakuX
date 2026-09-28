# lane.flip474: Turnip's sysmem render mode (#474, Addenda 7 and 8)

This file is #516's notes. `NOTES.md` has a pointer to it (section 17).

**Outcome (2026-09-28): the global default does not ship, and #516 no
longer carries it** (`1a8f16ef16` is reverted by `d0efa4c1f3`). The gain is
real where a title is rendered twice: AUF 16 -> 24 gfps, DOA 13 -> 21.
Whether sysmem moves pixels is **not settled**: the env run on the Thor
printed a different ZPASS report in all 36 `ZPass_pixel_count` captures, and
the default build's arm on the Nova, which sets the same flag, printed the
base's in all 36 ("The second pair", below). The env run was also the only
one with a kept shader cache, so its 37 moved captures have two candidate
causes. Results are in "Results" below; the policy section is corrected in
place.

The per-title default is lane.rendermode474's (board wave 271), keyed by
title id, below user overrides. The ZPASS report's constant is #527.

## Why the last session did not finish, and this one (resumed 2026-09-27 22:38Z)

The last session ended on a wait, correctly: #504 (the timestamp period)
had every device leg judged and waited on the arms job's pgraph pair
(`1-1790547698-arms-flip474-base-1028880` done on the Thor, `-fix-1029105`
still queued at 22:40Z). Addendum 7 (15:12 PDT) reached that session after
it had started and was not acted on. This session starts Addendum 7 on a new
branch, `lane/flip474-sysmem`, from master `09fdca3ba1`; #504 stays as it is.

## What decides the render mode (read in lane.turnipfork's Mesa tree, `4c18636110`)

That tree is the series the bundled driver ("PurpleVK", Mesa 26.3.0-devel
git-62ac221a33) is built from, not the binary itself.

- `TU_DEBUG` is parsed once, in `tu_env_init` (`tu_util.cc:130-176`, a
  `call_once`), which `tu_CreateInstance` calls (`tu_device.cc:1971`).
- The `sysmem` flag is read in one place: `use_sysmem_rendering`
  (`tu_cmd_buffer.cc:1419`). It picks the render mode and nothing else.
- Without it, the autotuner decides per pass (`tu_autotune.cc`). Its default
  for a pass it cannot tune is SYSMEM (`:1831`, "an incorrect decision
  towards SYSMEM tends to be far less impactful than an incorrect decision
  towards GMEM"). DOA's heavy pass is tuned, and gets GMEM.
- The driver's own driconf already sets `tu_autotune_algorithm=prefer_sysmem`
  for DXVK and vkd3d, "DX games almost always tend to prefer SYSMEM"
  (`00-turnip-defaults.conf:36-40`). It matches on the engine name, and the
  other options on that engine entry change rounding and alpha-to-coverage,
  so borrowing it is not an option.
- `TU_AUTOTUNE_ALGO=prefer_sysmem` is the supported spelling in this tree.
  Whether the bundled binary has it is not known; `TU_DEBUG=sysmem` is the
  one measured on the device (NOTES.md section 16), so that is the one used.

hakuX has one `vkCreateInstance` (`instance.c`, `create_instance`), and the
`env_vars` pref is applied before it (`xemu_android.cpp:796-806`). So a
`setenv` just before the instance is created reaches the driver, and a
`TU_DEBUG` the user or a request set wins.

## Policy

**Corrected 2026-09-28. This section first said per title "is not open to
hakuX", and that was wrong.** The flag is read once per process, but the
Android app starts one emulator process per game and already has per-game
overrides: `PerGameSettingsManager.kt` carries 21 keys (`gpu_driver`,
`skip_occlusion_queries`, ...) that are written as `runtime_override_*`
prefs before the emulator starts, and `xemu_android.cpp:796-810` applies
`env_vars` before the instance exists. A render-mode key there is a
per-title policy. It was not looked for before the change was written.

The three policies, after the data:

| policy | verdict | why |
|---|---|---|
| global sysmem (what `1a8f16ef16` did) | **no** | pixels are not shown identical: the env run moved 37 captures and the default build's arm moved none of them, and the two are not reconciled ("The second pair"); Blinx and Crimson read 2 gfps lower, not separated from scene and run order |
| per title | **the one the data supports** | AUF 16 -> 24 and DOA 13 -> 21 gfps, both X/R 1.0; AUF ends no render pass for a query in its window, DOA in 3 of 56 lines |
| per pass | the driver's | Turnip's autotuner chooses; a fix is in lane.turnipfork's Mesa tree, and so is the sysmem occlusion count |

Per title is lane.rendermode474's since board wave 271; it is not
implemented here. It needs files this lane does not hold:
`PerGameSettingsManager.kt`,
`PerGameSettingsActivity.kt`, `activity_per_game_settings.xml`,
`strings.xml` and `xemu_android.cpp`. Its default is "the driver's choice",
so it moves no pixel for a title nobody set. Those overrides are keyed by
the game's path and set by the user; a default shipped for DOA and AUF
needs a table keyed by title id, which does not exist yet.

Until then `TU_DEBUG=sysmem` in the `env_vars` pref, or `request.sh --env
TU_DEBUG=sysmem`, reaches the driver on any build. A benchmark run that way
measures a setting the user does not have by default, and should say so.

## Registered before any arm ran

| file | what | arms |
|---|---|---|
| `flip474-sysmem-pgraph.json` | 27 pgraph suites, no env against `TU_DEBUG=sysmem`, ref `09fdca3ba1`, the Nova. Every capture byte-identical (75%) | `1-1790549038-flip474-1817562` (A), `1-1790549039-flip474-1817704` (B) |
| `flip474-sysmem-auf.json` | AUF, X/R 1.01: GPU <= 0.75 x, gfps +2 (55%) | the next two in `.queue_sysmem.log` order: base, sysmem |
| `flip474-sysmem-blinx.json` | Blinx, X/R 0.13: GPU 0.80-1.15 x, no loss | base, sysmem |
| `flip474-sysmem-forza.json` | Forza, X/R 0.25: GPU 0.70-1.10 x, no loss | base, sysmem |
| `flip474-sysmem-crimson.json` | Crimson on the Thor, capped at 30: gfps within 1 | base, sysmem |
| `flip474-sysmemfix-pgraph.json` | the change itself, master `09fdca3ba1` against `1a8f16ef16`, the same 27 suites | the arms job |
| `flip474-sysmemfix-doa.json` | the change on DOA, no env: the `init: TU_DEBUG=sysmem (default` line, X/R <= 0.25 | `1-1790549110-flip474-1833747` |

The ten env requests, in queue order: `1-1790549038-flip474-1817562`,
`1-1790549039-flip474-1817704` (pgraph A, B), `-1817992`, `-1818193` (AUF
base, sysmem), `-1818394`, `-1818597` (Blinx), `-1818830`, `-1819047`
(Forza), `-1819312`, `-1819530` (Crimson, Thor). Each id's prefix is
`1-17905490NN-flip474-`.

The judge scripts are in `docs/lanes/flip474/`. `sysmemjudge.py` prints
every number the soak legs name for a run over one window; `capgroups.py`
groups N pgraph runs' captures by content; `zpassread.py` says whether
every ZPass capture of a run prints the report value of one read by eye.

## Results (judged 2026-09-28, attempt 4)

The change is Android-only (`#ifdef __ANDROID__`), so the desktop pgraph
suites cannot see it; its pixel check is the device pair below and the arms
job's pair for `flip474-sysmemfix-pgraph.json`.

**The device is read back from each `result.json`, not from the
prediction.** The pgraph pair, Blinx and Forza were registered for the Nova
and ran on the Thor: hostops moved them while the Nova was on its battery
hold. Each pair still ran both arms on one device with one binary, so each
ratio stands; the X/R figures the predictions quote for Blinx (0.13) and
Forza (0.25) are the Nova's, and the Thor reads 0.01 and 0.21.

### Step 1, pixels: `flip474-sysmem-pgraph.json` is REFUTED

A `0-0-x-1790549038-flip474-1817562` (no env), B
`0-0-x-1790549039-flip474-1817704` (`TU_DEBUG=sysmem`), Thor, `09fdca3ba1`,
apk `6d334facad15`, 1059 captures each. 1013 are byte-identical and 46 are
not (`capgroups.py`).

| captures | n | what differs | cause |
|---|---:|---|---|
| `ZPass_pixel_count::*` | 36 | the printed ZPASS report: `0xA000 (40960)` in all 36 of A, `0x10000 (65536)` in all 36 of B (`zpassread.py`) | something B alone had: the env or its kept shader cache (first written here as "the render mode"; see "The second pair") |
| `Stencil::Stencil_{REPLACE,ZERO}_*` | 5 | 30,000 to 40,000 px, in both directions (A wrong in one, B in two) | run to run: the lost draw of #39/#75, band [0, 40000] |
| `Blend_tests::#spot_0_ADD` | 1 | A is 16,384 px off its golden; B is exact and equals six earlier GMEM runs | run to run, in A |
| `Vertex_shader_rounding_tests::GeometrySuperscreen_{0.5000,0.5626}` | 2 | 0.5000 has three contents over eight runs of one mode | run to run |
| `Antialiasing_tests::GPUAAWriteAfterCPUWrite` | 1 | 134 against 138 px | moves with the ZPass block, in B alone (classified by the second pair) |
| `Surface_pitch::Swizzle` | 1 | 5607 against 6144 px | run to run (classified by the second pair) |

So 37 captures moved in B alone and 9 move run to run. This pair cannot
say what in B moved the 37: B had the env, and B was the second run of one
apk, so the dispatcher kept A's shader cache for it (`shader_cache: kept`,
260 modules warmed up at start). A started from a cleared cache.

**What the ZPass captures show** (filed as #527). The report is one value
per run, whatever the test draws: `ZPassPointSize-0x0040` expects 16,448 and
`ZPassLineWidth-0x0040` expects 16,896, and both print 40,960 in A and
65,536 in B. `ZPass` itself expects 40,960, so it prints `[PASS]` in A and
`[FAIL]` in B; the other 35 print `[FAIL]` in both. 65,536 is four whole
128 x 128 quads: `ZPass` draws four, one hidden behind another and one half
off the screen. So the report was already wrong on master in 35 of 36
tests, and in B it is wrong in the 36th and is another value in all of
them. This lane did not find why either value is constant.
hakuX begins and ends its occlusion queries outside render passes
(`draw.c:4606-4622`), and on this GPU Turnip closes such a query with a
pair of `ZPASS_DONE` events (`tu_query_pool.cc:1128-1152`, `:1574-1586`);
that is where to look, in whichever mode.

**Which titles read the report** (`hakuX-rpbrk`'s `qry`, render passes
ended for a query, in each run's window):

| title | lines with `qry` > 0 | most in one line |
|---|---:|---:|
| Blinx, base and sysmem | 40 of 40, 39 of 39 | 1815, 1847 |
| DOA, the default | 3 of 56 | 36 |
| DOA base, AUF, Forza, Crimson | 0 | 0 |

### The second pair: `flip474-sysmemfix-pgraph.json` (judged 2026-09-28 02:30Z)

The arms job's pair, both on the Nova, each from a cleared shader cache:
base `1-1790549941-arms-flip474-base-2298159` (`09fdca3ba1`, apk
`6d334facad15`, the binary of A and B above) and fix
`1-1790549941-arms-flip474-fix-2298254` (`1a8f16ef16`, apk `77fb07c81a93`,
the default). 1059 captures each; 1053 byte-identical, 6 not.

By the letter the prediction FAILS: every suite is in `must_not_move`, and
six captures moved. All six are in the run-to-run set:

| capture | base, px off its golden | fix |
|---|---:|---:|
| `Blend_tests::#spot_0_ADD` | 0 | 16,384 |
| `Stencil::Stencil_REPLACE` | 40,000 | 0 |
| `Stencil::Stencil_ZERO_DT` | 40,000 | 0 |
| `Stencil::Stencil_REPLACE_ST_DT` | 0 | 30,000 |
| `Stencil::Stencil_REPLACE_ST_DT_ZB` | 0 | 30,000 |
| `Surface_pitch::Swizzle` | 0 | 4,838 |

Its "if and only if" is refuted too, and that is the finding: the env pair
moved 37 captures that this pair did not.

**The four runs, capture by capture** (`capgroups.py`; columns Thor A, Thor
B with the env, Nova base, Nova fix; runs that share a letter are
byte-identical). 49 captures are not the same in all four:

| pattern | n | captures | reading |
|---|---:|---|---|
| `abaa` | 37 | the 36 `ZPass_pixel_count` captures, `GPUAAWriteAfterCPUWrite` | moved in Thor B alone |
| `abba`, `abbb`, `aabb`, `aaba`, `abca` | 10 | Stencil (8), `#spot_0_ADD`, `GeometrySuperscreen_0.5626` | run to run; see below for `aabb` |
| `abcc` | 1 | `GeometrySuperscreen_0.5000` | run to run |
| `abcd` | 1 | `Surface_pitch::Swizzle` | run to run |

**The two captures the first pair left open:**

- **`Surface_pitch::Swizzle`: run to run.** Four runs, four contents. The
  two runs of one binary with no env differ from each other: Thor A is
  5,607 px off the golden and the Nova's base is exact. The other two are
  6,144 (Thor B) and 4,838 (Nova fix) off. Both sysmem runs are off and one
  of the two others is, so four runs do not say whether the mode changes
  how often it fails.
- **`Antialiasing_tests::GPUAAWriteAfterCPUWrite`: not run to run. It
  moves with the ZPass block**, in Thor B alone. Nine runs on disk from
  2026-09-26 09:26Z hold this capture, over both handhelds and seven apks.
  Eight are one content, the Nova's fix arm among them; the ninth is Thor B
  (`caphistory.py`). It is 134 px off its golden in the eight and 138 in
  Thor B.

Two Stencil captures split by handheld (`aabb`: `Stencil_REPLACE_ST`,
`Stencil_REPLACE_ST_ZB`). Every Stencil capture here is 0, 30,000 or 40,000
px off its golden, which is the lost draw of #39/#75, and six others flip
inside one handheld. Four runs cannot tell a split by handheld from two
flips that fell that way.

**The 37 did not move under the default.** The Nova's fix arm prints
`0xA000 (40960)` in all 36 ZPass captures, byte-identical to its base and to
Thor A. That is not what "the render mode moves them" predicts, so what is
known about that arm matters:

| question | answer | how it was read |
|---|---|---|
| Is the default in that binary? | yes | `77fb07c81a93`'s `libxemu.so` holds the `init: TU_DEBUG=sysmem (default` string; `6d334facad15`'s holds no `TU_DEBUG` |
| Was `TU_DEBUG` already set, so the default stood aside? | no | no `env:` line in its logcat, and the request's env is empty |
| Does the driver honour the default on the Nova? | yes, on DOA | the perflog build of the same ref (`230d78fd17ea`) reads X/R 0.02 with no env |
| Did the driver render **this** run in sysmem? | **not shown** | the arm is not a perflog build, so it prints no `hakuX-phase` line, and the start-up line is under `xemu-vk`, which the logcat list does not hold |
| Same GPU and driver as the Thor? | yes | Adreno 740 and PurpleVK git-62ac221a33 in all four logcats |

**What Thor B alone had.** Two things, not one:

| | Thor A | Thor B | Nova base | Nova fix |
|---|---|---|---|---|
| sysmem asked for | no | the env pref | no | `setenv` in `create_instance` |
| shader cache at start | cleared | **kept, 260 modules warmed up** | cleared | cleared |
| ZPASS report | 40,960 | 65,536 | 40,960 | 40,960 |

Since 2026-09-26, 13 runs on disk hold the ZPass suite, over both handhelds
and nine apks. 11 print one content, one is an older ref's
(`8e683b3a26`), and one is Thor B. Thor B is the only one that started from
a kept cache, and the only one with the env. No run on disk separates the
two. For `GPUAAWriteAfterCPUWrite` two runs of that suite alone started
from a kept cache (35 modules) with no env and printed the usual content,
so a kept cache by itself did not move that capture there. No such run
exists for ZPass.

So the first pair's "36 captures move with the render mode" was a cause
named from one run that differed in two ways. What stands: the ZPASS report
is a constant whatever the test draws (#527), and one run printed another
constant.

**The two runs that separate it**, `ZPass_pixel_count` and
`Antialiasing_tests` only, master, one handheld, queued in this order:

1. `--env TU_DEBUG=sysmem`, as the first run of its apk on the device
   (`shader_cache: cleared`).
2. no env, straight after it (`shader_cache: kept`).

| run 1 | run 2 | reading |
|---|---|---|
| 65,536 | 40,960 | the env moves the report. Then the default build's arm either was not in sysmem or `setenv` differs from the pref, and a perflog build of the default on the same two suites says which |
| 40,960 | 65,536 | the kept shader cache moves it. Then sysmem is not shown to move any pixel, and every pair whose B arm reuses A's apk has this confound |
| 65,536 | 65,536 | both can; run the no-env arm again from a cleared cache |
| 40,960 | 40,960 | neither alone; Thor B was something else, and the full 27-suite disc is the next thing to repeat |

Read `shader_cache` in each `result.json` before reading the captures: a
request of another apk that lands between the two clears the cache and
makes run 2 a plain repeat. They are not queued from here: both handhelds
have a queue of soaks and arms, and this lane has no session left to read
them. They are small (two suites, about two minutes each).

### Steps 2 and 3, the soaks (`sysmemjudge.py`, each over its registered window)

| title, device | arm | GPU | X/R | Tot | gfps median | smallest gfps / median |
|---|---|---:|---:|---:|---:|---:|
| AUF, Nova | base `-1817992` | 24.9 | 1.01 | 51.6 | 16 | 0.88 |
| | sysmem `-1818193` | 13.2 | 0.02 | 34.4 | 24 | 0.92 |
| Blinx, Thor | base `-1818394` | 22.2 | 0.01 | 47.6 | 16 | 0.56 |
| | sysmem `-1818597` | 23.2 | 0.00 | 48.0 | 14 | 0.57 |
| Forza, Thor | base `-1818830` | 26.9 | 0.21 | 57.4 | 14 | 0.86 |
| | sysmem `-1819047` | 24.6 | 0.12 | 54.6 | 15 | 0.00 |
| Crimson, Thor | base `-1819312` | 4.5 | 0.10 | 28.9 | 29 | 0.66 |
| | sysmem `-1819530` | 4.5 | 0.10 | 29.0 | 27 | 0.52 |
| DOA, Nova, 151-288 s | base `795ea6b3af`, `-398286` | 36.0 | 1.00 | 67.1 | 13 | 1.00 |
| | the default `1a8f16ef16`, `1-1790549110-flip474-1833747` | 19.2 | 0.02 | 40.3 | 21 | 0.14 |

GPU, R and X are as printed, so only the ratios inside a pair are read.
No run has a crash marker, and every run prints to its end.

| file | legs | verdict |
|---|---|---|
| `flip474-sysmem-auf.json` | S1 X/R 0.02 PASS; S2 0.53 x PASS; F1 +8 PASS; L1 PASS; M0, E0, T0 PASS; H0 FAILS as written in the base (3.7 s) | **holds**, H0 aside |
| `flip474-sysmem-blinx.json` | S2 1.05 x PASS; L1 FAILS (14 against 16); T0 voids both arms | **not judged**: the KILL's "like scene" is not shown |
| `flip474-sysmem-forza.json` | S2 0.91 x PASS; L1 PASS (+1); T0 voids the sysmem arm by the letter | **holds in the race**, see below |
| `flip474-sysmem-crimson.json` | C2 1.00 x PASS; C1 FAILS downward (27 against 29) | **C1 refuted**; the KILL is not judged |
| `flip474-sysmemfix-doa.json` | D1 X/R 0.02 PASS; F1 21 PASS; D0 FAILS as written | **the default reached the driver**; the line did not reach the log |

What is behind each leg that failed as written:

- **H0's 3 s bound was wrong.** `hakuX-perf` prints a gfps line every 57
  to 60 frames, not every 2 s: AUF's base has 34 lines in 121 s at 16 gfps
  and its sysmem arm 50 at 24. Under about 19 gfps the gap is over 3 s with
  nothing hung. Blinx's 6.6 s gaps are its 9 gfps stretches.
- **Blinx.** The survey route is blind, and the two arms are in the same
  level at the same game clock (0'54") looking at different walls. gfps
  runs from 7 to 31 inside each arm, in the same order of stretches. By
  stretch: about 300-325 s base 17-31 and sysmem 16-26; about 330-380 s
  base 9-16 and sysmem 11-15. The medians' 2 gfps cannot be told from the
  view.
- **Forza.** The registered window (125-240 s) came from the Nova. On the
  Thor the race starts at 152 s in the base and 165 s in the sysmem arm, and
  the lines before it are loading (0 to 2 gfps). The sysmem arm also began
  under the Thor's thermal pause, which lifted between 140 and 174 s. In
  the race, base 12-20 and sysmem 12-21.
- **Crimson.** Both arms sit on the 29 cap in the same stretches and dip
  together at 162-190 s. Where neither is capped, sysmem is 2 to 3 lower
  (101-145 s: mean 25.7 against 23.7; 162-190 s: 23.9 against 20.7), with
  GPU and Tot equal. No thermal pause in either window; the sysmem arm's
  last two lines (14, 4) are a pause that began at about 240 s. Two earlier
  GMEM runs of this route read 29 and 28 (`-1235863`, `-1235910`), so 27 is
  1 below anything GMEM has read. The sysmem arm ran second and started at
  80 C against 68 C. One run an arm does not separate mode from order.
- **DOA's D0.** `instance.c` logged the line under the tag `xemu-vk`. The
  dispatcher's logcat is a list of tags that ends in `*:S`
  (`dispatcher.sh:1386`), and `xemu-vk` is not on it; `hakuX-vk` is. D1 is
  what shows the default took effect: X/R 0.02 with no env, against 1.00
  on the base.
  The default run's smallest line (3 gfps at 237 s) is the end of the
  fight; the series reads 30 to 60 from 254 s.

## Waiting (from 2026-09-27 22:46Z)

At 22:46Z the Nova was under hostops' battery hold (13%, lifted at 80% on
a 500 mA port, hours), so the Nova requests wait for that.

On the eleven requests above, all outside this session, and the arms job's
pair. When they land: judge each file's legs, post the table on #474 and
#462, and take #516 to ready only if both pgraph pairs are byte-identical
and no breadth soak meets its KILL leg.

## Attempt 2 (resumed 2026-09-27 ~23:00Z)

Attempt 1 did not finish because it ended waiting on the device, which was
the right call. At 22:51Z the arms job then refused `flip474-sysmemfix-pgraph.json`.
Its skip was spelled `Texture render target::RenderTextureLoop`, with spaces,
because it was copied from the env pair. That pair was queued by hand with
spaced suite names. The arms job passes the prediction's underscored suites,
and `request.sh` matches the skip's suite against those literally.
Attempt 2 respells the skip `Texture_render_target::RenderTextureLoop`
(`make_test_iso.py` maps `_` to a space, so the disc is the same). The refs
stay the same and nothing was rebased. The arms job picks up the new sha on its next tick.

At 23:00Z none of the eleven requests had run. The Nova is still under the
battery hold, and the Thor is held for lane.xbox's title push. The wait below still holds.

## Attempt 3 (resumed 2026-09-27 23:03Z)

Attempt 2 did not finish because it ended waiting on the device again, and
that was the right call: none of its eleven requests had started. At 23:05Z
the Nova is running the first one, pgraph A `0-0-x-1790549038-flip474-1817562`
(the host moved the batch to the device head as `0-0-x-`). The other nine env
requests, DOA `1-1790549110-flip474-1833747`, and the arms job's pair for
`flip474-sysmemfix-pgraph.json` (`1-1790549941-arms-flip474-base-2298159`,
`-fix-2298254`) are queued. #516's CI is green on `eb473c8377`, and its
`Files:` line matches the diff.

Side items, and why none are this lane's:
- The texture-bind drain (lane.local's 15:46 addendum) went to its own lane,
  lane.drain474, which holds vk/texture.c (board, hostops 15:48 PDT).
- #504 waits on its fix arm `1-1790547698-arms-flip474-fix-1029105`,
  which is still queued. Hostops marks it ready when the arms job PASSes it.

The wait is the same one: judge the legs when the requests land.

## Attempt 4 (resumed 2026-09-28 01:02Z)

Attempt 3 did not finish because it ended waiting on the device, and that
was the right call: eleven requests were queued or running. All twelve
finished by 00:59Z and this attempt judged them (Results, above).

What this attempt did:

- Merged master (`fc932afaa3`; #504 had folded) and reverted the default
  (`d0efa4c1f3`). The predictions' refs are untouched and still on the
  branch.
- Judged every leg, added `sysmemjudge.py`, `capgroups.py`, `zpassread.py`.
- Corrected the policy section in place.

**Waiting on** the arms job's pair for `flip474-sysmemfix-pgraph.json`,
`1-1790549941-arms-flip474-base-2298159` and `-fix-2298254`, still in the
queue at 01:10Z. It is a second run of each mode on the 27-suite disc, so
it classifies the two captures the env pair could not
(`GPUAAWriteAfterCPUWrite`, `Swizzle`) and says whether the 36 ZPass
captures move again. Its verdict is expected to be a FAIL on
`ZPass_pixel_count/*`: that is this file's finding, not a new one. #516 is
marked ready after it, as the record of a measured change that was taken
back.

(That expectation was wrong: the pair is byte-identical in every ZPass
capture. See "The second pair".)

## Attempt 5 (resumed 2026-09-28 01:57Z)

Attempt 4 did not finish because it ended waiting on the arms job's pair,
which was in the queue behind lane.drain474's. That was the right call. The
pair finished at 01:42Z and 01:56Z, both arms on the Nova.

What this attempt did:

- Read the pair and grouped it with the first ("The second pair", above).
  `Swizzle` is run to run. `GPUAAWriteAfterCPUWrite` moves with the ZPass
  block.
- Found that the block did not move under the default, and that the env
  run was also the only run from a kept shader cache. Corrected "the render
  mode" to "something B alone had" wherever this file named the cause.
- Added `caphistory.py`, merged master (`d34b77d76d`).
- Did not queue the two runs that separate the causes: they are named
  above for whoever holds the render mode next (lane.rendermode474) or
  #527.

**What would make a global default right**, in order:

1. The two runs of "The second pair" say what moved the 37 captures.
2. If it is the mode: the ZPASS report (#527) prints the value each test
   expects, in both modes, and `GPUAAWriteAfterCPUWrite` is explained.
3. A pgraph pair with the sysmem arm first, both arms from a cleared
   cache, byte-identical outside the run-to-run set.
4. Blinx and Crimson on the Thor with the sysmem arm first, from a cool
   start, both arms in the same view: sysmem within 1 gfps.

## Do not repeat

- Do not write "hakuX cannot do this per title" without looking at the
  app: it starts a process per game and has per-game overrides.
- Do not log a line a prediction's leg depends on under a tag that is not
  in the dispatcher's `LOGCAT_SPEC` (`dispatcher.sh:1386`). `xemu-vk` is
  not, so the leg that was to prove the default ran could not be read.
- Do not bound a hang by seconds between `hakuX-perf` lines: they are
  printed every 57 to 60 frames. Bound it in frames, or scale by gfps.
- Do not take a soak window from one handheld to the other: Forza's race
  starts 27 to 40 s later on the Thor than the Nova's window assumes.
- Do not run both arms of a pair in one order on a device at 95 C and read
  a 2 gfps difference. Alternate the order, or run each arm twice.
- Do not read `ZPass_pixel_count::ZPass` printing `[PASS]` as the report
  working: it prints the same 40,960 in tests that expect 16,448.
- Do not name a cause from a pair whose second arm reuses the first arm's
  apk. The dispatcher keeps the shader cache for it, so the second arm
  differs in the cache as well as in what was set. Read `shader_cache` in
  both `result.json` files; run the changed arm first, or the control twice.
- Do not leave a pixel finding on one run when a second run of the same
  setting is already queued: the first pair's cause was posted, filed
  (#527) and acted on 35 minutes before the pair that contradicts it
  finished.
- Do not judge a change that a non-perflog arm cannot see taking effect:
  the fix arm prints nothing that says which mode it rendered in.
- Do not copy a skip spec from a hand-queued request (spaced suite names)
  into a registered prediction (underscored): the arms job's `request.sh`
  gate compares them literally and refuses.

- Do not borrow a driconf engine entry to get one option: DXVK's entry in
  Turnip's defaults also changes texture-coordinate rounding and
  alpha-to-coverage.
