# lane.uberdefault569: the ubershader on by default (#569, #672)

Brief: `briefs/uberdefault569.md` (owner decision 2026-10-02 ~16:25 PT: turn the uber ladder on
by default, add a toggle, warn when it is off). Offline protocol in force. Base: origin/master @
9550493846.

## 1. What changed

| file | change |
|---|---|
| `hw/xbox/nv2a/pgraph/vk/instance.c` | `HAKUX_GPL_DEFAULT` 0 -> 3. The env var still overrides (0-4). |
| `MainActivity.kt` | `ubershaderEnabled()`: an `HAKUX_GPL=` line in the env_vars pref decides (0-2 = off); else the per-game override; else the global pref `ubershader`, default **true**. Off -> `nativeSetenv("HAKUX_GPL","0")` before the emulator starts, and a banner. Logs `hakuX-build: ubershader: ON|OFF (#569)`. |
| `MainActivity.kt` | `showUbershaderOffBanner()`: "Ubershader is disabled. Loading some scenes may be delayed." Top centre, white on translucent black, not clickable or focusable, fades out at 6 s and removes itself. Shown at game load, while the title boots. |
| `SettingsActivity.kt`, `activity_settings.xml`, `strings.xml` | An "Ubershader" switch in the graphics section beside "Async shader compilation", default on (`boolDefaults`). |
| `PerGameSettingsManager.kt`, `PerGameSettingsActivity.kt` | `ubershader` is per-game overridable. Per-game fell out of the existing mechanism: `SettingsActivity`'s per-game mode and `applyRuntimeOverridesToEditor` handle every key in `overridablePreferenceKeys`. `addBoolPicker` gained a `globalDefault` so its "Global:" line reads Enabled for this default-true key. |

How the setting reaches the emulator: `MainActivity.onCreate` runs before SDL starts the
emulator thread, and `xemu_android.cpp` applies the env_vars pref later with overwrite, so a
request's `--env HAKUX_GPL=N` still wins over the setting. The app sets nothing when the
setting is on, so the compiled default (3) is the one mechanism for "on", and the arms test it.

**Not built, by the brief:** the first-launch "expected delay" notice.

**Desktop builds** take the same compiled default. Nothing here measures desktop; the uber stage
was checked on lavapipe by uberspike569 (BUILD.md 4.1).

## 2. Evidence before this lane

- uberspike569 (BUILD.md 12): Kabuki fight creates 133 s -> 27 ms, longest flip gap 5.0 -> 0.7 s;
  DOA1U creates 26.2 -> 2.7 s; uber stage held (mode 4) 1317/1317 captures byte-identical on 36
  suites; held GPU cost up to 3.8x per frame, 0.79x median gfps over a cold DOA1U play span.
- #672 runs 6/7 read with this lane's judge (`judge.py`): run 6 (GPL 0) dpc 49.8 s, 21 stall
  windows, 3 shader hitches in the first 120 s, **hang**; run 7 (GPL 3) dpc 3.0 s (0.059x), 4
  stall windows, 0 hitches, no hang. Run 7's shader-module cache was kept from run 6, which
  favours it; the pipeline cache file was wiped in both.
- `glsl/` is unchanged since leg E's ref (`git diff 6bec23c3f4..d4a02e2060 -- hw/xbox/nv2a/pgraph/glsl`
  is empty). The vk/ changes since are the pre-build pool (#569 P3), a perflog counter and
  bf2push656 (reverted).

## 3. Predictions and arms

Registered at c66c5bc207, before any run:
- `docs/testing/predictions/uberdefault569-soaks.json`: legs V/H/S1/S2/F, judged by `judge.py`
  (its `--selftest` covers both sides of every threshold).
- `docs/testing/predictions/uberdefault569-pixels.json`: the 36 suites of leg E, one build,
  B default (3) vs A `--env HAKUX_GPL=0`.

Arms, all ref d4a02e2060 on the Nova, cold (`HAKUX_PREBUILD=0 HAKUX_PLC_WIPE=1`):

| # | arm | request | result | expected |
|---|---|---|---|---|
| 1 | Kabuki B | 1-1790990144-uberdefault569-532413 | queued 18:16 PDT | creates near zero in the fight, no hang |
| 2 | Tron B | 1-1790990144-uberdefault569-532476 | queued 18:16 PDT | past the second card, no hang |
| 2b | Tron B rerun | 1-1790994313-uberdefault569-990012 | queued 19:32 | as 2 |
| 3 | Kabuki A | 1-1790994318-uberdefault569-990124 | queued 19:32 | creates tens of seconds (uberspike A: 133 s) |
| 4 | DOA3 B | 1-1790994320-uberdefault569-990204 | queued 19:32 | creates <= half of A's |
| 5 | DOA3 A | 1-1790994322-uberdefault569-990282 | queued 19:32 | |
| 6 | ToeJam B | 1-1790994325-uberdefault569-990361 | queued 19:32 | creates <= half of A's 15.6 s; fps share within 0.10 of A's 0.99 |
| 7 | pixels B | 1-1790994329-uberdefault569-990475 | queued 19:32 | every capture same as A or in band |
| 8 | pixels A | 1-1790994333-uberdefault569-990621 | queued 19:32 | |
| 9 | banner | 1-1790994336-uberdefault569-990675 | queued 19:32 | the banner in the frames at 1-6 s, gone by ~7 s |
| 10 | head smoke | after the last commit | | finishes, not void |

Two A arms come from runs already on disk, to keep the Nova budget at 10 (it is shared with
lane.memfast and lane.vcpuwait433): ToeJam's first play on the Nova (1790970734-lanelocal-1022425,
GPL 0, shader cache cleared, `[pb569] jobs=0`) and Tron's #672 run 6.

DOA3 is `54430001-Dead_or_Alive_3.xiso.iso` on the Nova; the `doa3` route was written for the
Thor copy and has never been played on the Nova, so leg H asks for gameplay only where A reached
it. A fifth title was not added: the budget is spent.

The pilot was first queued plain (`1790990082-...-525888`, `1790990086-...-526161`) because
request.sh reads #569's release label with `gh`, which fails offline. Both were moved to
`queue/withdrawn/` with a `.why` and re-queued with `HAKUX_RELEASE_PRIO=1`, the tier
uberspike569's #569 arms ran at.

## 4. The pilot (read 19:30 PDT)

- **Kabuki B** (`...-532413`): `ubershader: ON (#569)`, `[gpl569] requested=3 mode=3` with no
  HAKUX_GPL in the env, so the compiled default is what ran. Cold (cache cleared, PLC absent,
  `[pb569] enabled=0`). Reached gameplay, no hang, fps_ok 0.933 (median 59.94). Draw-path creates
  2.8 s over the whole run, 3 stall windows; `[uber569]` links 769, cold 94, uncovered 0.
  12 hitches in the first 120 s of the fight, 9 classed shader, worst 734 ms. Each of those has
  dpc_ms <= 22.5 ms: hitch_report classes a window shader when it shows any cache miss
  (`dsm > 0`), and under the ladder a miss is a ~5 ms link, so the class does not say these
  were compile stalls. What they are is read against A.
- **Tron B** (`...-532476`): **guest kernel BugCheck 0xA, 13 s into boot**, before the first
  flip: a NULL write at kernel EIP 0x80019e0e called from title code (ret 0x162b15), then the
  halt loop at 0x800151ed. 3 uber links and 0 ms of creates by then. A search of 524 result
  logcats from the last five days finds one other BugCheck 0xA, `1790933948-titleroutes-171701`
  (Conker, Nova, GPL 0, the same halt EIP). Tron's own GPL 3 run 7 booted. Read as a boot flake
  and re-run once (2b); if 2b crashes the same way, the flake reading is wrong.
- `judge.py` now computes verdict.json in memory (the harness's `title_verdict.judge`, writing
  nothing) when a soak path did not write one: Kabuki B had none. Legs and factors unchanged.
- Pilot verdict written to `pilots/uberdefault569.ok`; the remaining eight requests queued.
- Budget: the Tron rerun makes this 11 Nova runs with the head smoke, one over the brief's 10.

## 5. Results (read 21:20 PDT)

All arms ref d4a02e2060, Nova, cold. `judge.py` output: `judge-soaks.json`; pixel comparison:
`ab-pixels.txt` / `ab-pixels.json`.

| title | arm | result | draw-path creates | stall windows | freezes (verdict hang gaps) | shader hitches, first 120 s (worst) | fps_ok | median fps |
|---|---|---|---|---|---|---|---|---|
| Kabuki | A off | 1-1790994318-uberdefault569-990124 | 141.3 s | 47 | 22.5, 10.7, 60.9 s | 9 (4681 ms) | 0.72 | 59.9 |
| Kabuki | B on | 1-1790990144-uberdefault569-532413 | 2.8 s | 3 | none | 9 (734 ms) | 0.93 | 59.9 |
| DOA3 | A off | 1-1790994322-uberdefault569-990282 | 122.7 s | 35 | 11.0, 19.0, 12.7 s | 11 (7265 ms) | 0.63 | 47.3 |
| DOA3 | B on | 1-1790994320-uberdefault569-990204 | 2.9 s | 4 | none | 3 (271 ms) | 0.82 | 45.9 |
| ToeJam | A off | 1790970734-lanelocal-1022425 | 15.6 s | 13 | none | 8 (435 ms) | 0.99 | 59.9 |
| ToeJam | B on | 1-1790994325-uberdefault569-990361 | 3.1 s | 2 | none | 0 | 0.88 | 53.9 |
| Tron 2.0 | A off | 0-1790978946-tronhang672-3184149 (#672 run 6) | 49.8 s | 21 | 18.2, **226.3 s (the hang)** | 3 (3816 ms) | 0.48 | 47.3 |
| Tron 2.0 | B on | 1-1790994313-uberdefault569-990012 | 3.2 s | 4 | none | 0 | 0.82 | 36.9 |

| leg | registered | measured | verdict |
|---|---|---|---|
| V | each pair: B mode 3 with uber links, A mode 0, both cold | 4/4 valid | **PASS** |
| H | no B hangs, crashes, or misses gameplay its A reached | 4/4 (Tron B's first run crashed at boot, see 4) | **PASS** |
| S1 | per title B creates <= 0.50 x A | 0.020, 0.024, 0.198, 0.065 | **PASS** |
| S2 | sum of first-120 s shader hitches B < A, each B <= A + 1 | 12 vs 31; Kabuki 9 vs 9 | **PASS** |
| F | per title (not Tron) B fps_ok >= A - 0.10 | Kabuki +0.21, DOA3 +0.19, **ToeJam -0.11** | **FAIL** |
| pixels | every capture same or in band | 1317/1317 same, every one byte-identical; B linked 1321 draws through the uber stage | **PASS** |

**A correction to the registered soak file.** Its ToeJam entry says 6b0c4a131f differs from
d4a02e2060 by "bf2push656, folded with its overlay reverted". `git diff --stat` says otherwise:
the emulator code differs by the default flip and bf2ubosize433's uniform-churn counter
(`vk/draw.c`, `vk/shaders.c`, under `NV2A_PERF_LOG`). 16f09aa346 (Tron's A) also carries #672's
spin probe (`accel/tcg/cpu-exec.c`, `target/i386/tcg/system/seg_helper.c`). The file stays as
registered.

**What the numbers say.**
- With the ubershader off, three of four titles froze on a cold first launch: Kabuki for 61 s in
  one gap, DOA3 for up to 19 s, Tron for good (226 s, #672). With it on, none froze, and draw-path
  pipeline creation fell to 2.8-3.2 s per run on every title.
- Kabuki's first-120 s hitch count did not fall (9 vs 9), but its worst hitch fell from 4.7 s to
  0.73 s. Each of B's hitches has dpc_ms <= 22.5 ms: hitch_report classes a window as shader on
  any cache miss, and under the ladder a miss is a ~5 ms link, so the count does not separate a
  compile stall from a frame that merely saw a miss.
- **F fails on ToeJam by 0.01 beyond the band** (0.99 -> 0.88). It does not look like the stand-in.
  ToeJam B's ladder finished inside the first minute (`[uber569]` links 97, next 96/0/95, no
  later line), yet its slow stretches come at 420-540 s and 600-720 s (37-43 fps against A's
  50-60 in 60 s bins). B started 5 C warmer (xo-therm 48.6 vs 43.7 C), and A is a different
  session at a different ref. So the miss is real as registered, and its cause is not shown.
  The same-ref ToeJam A queued as the head run (section 6) separates the two.
- On Kabuki and DOA3, where A froze, fps_ok rose by about 0.2.

**Pixels.** Leg E's 36 suites, same build, B default (3) against A (`HAKUX_GPL=0`): better 0,
worse 0, same 1317, noise 0, and the byte-level check finds every capture identical. B's logcat:
`[uber569] mode=3 links=1321 cold=786 ... uncovered=0`. The uber stage replaces the vertex stage
only; the register-combiner (fragment) stage is the specialised library in both modes, so these
suites check the vertex stage against the combiner paths they feed, not a second combiner
implementation. **Not checked:** `NoContraction` is still absent (uberspike569 4.1: 1-2 ulp on 22%
of random vertex programs on lavapipe); no capture here shows it, and a title's own program could.
Under mode 3 such a pixel would differ only until its pipeline swaps.

**Banner.** `1-1790994336-uberdefault569-990675` (Kabuki, 45 s, `--env HAKUX_GPL=0`, a frame a
second). The app logs `ubershader: OFF (#569)`. The banner is in frames f00007-f00011, from the
first frame of the app window through the Crave logo, and gone at f00012, so it is on screen for
about 6 s. It sits over the boot logos, not gameplay. `banner-nova.png` is f00011. The run sets
the env var, not the setting; both paths call the same `ubershaderEnabled()`, and the setting
path was type-checked, not run on the device.

## 6. Next, ranked by P x win

1. **Persist the uber combinations and pre-build them at boot** (`briefs/uberpersist569.md`,
   drafted by stallmeasure569). P 0.8: the mechanism is shaderprebuild569's shipped pool and
   per-title records, applied to the (family, GS, raster, formats) keys. Win: the creates left on
   a first launch, 2.8-3.2 s and 2-4 stall windows per title here, all of which come from cold
   combinations (`[uber569] cold=` 94 Kabuki, 17 DOA3, 12 Tron). Cost: one lane, ~4 Nova runs.
2. *(superseded by section 8, which ranks the ToeJam cost first)*
3. **Cut the stand-in's GPU cost.** uberspike569 G read 3.8x GPU ms held (uber stage plus a
   non-LTO link, never split). Split the two with one arm (GPL 1 held against 0), then LTO-link
   the uber pipeline on the worker or tune the interpreter. P 0.6 for a useful split. Win: the
   cold-span fps dip, and F if (2) blames the ladder. Cost: 2-3 runs, then a build lane.
4. **`NoContraction` on both paths**, with its own pixel arm. P 0.9 that it is pixel-inert on the
   suites, as E and this leg were. Win: removes the one known exactness gap. Cost: 2 runs.
5. **Watch the boot BugCheck.** Tron B's first run hit BugCheck 0xA 13 s into boot; 1 other in 524
   recent runs (GPL 0). If it recurs at GPL 3 more often than at GPL 0, it is the ladder's timing.
   P low (0.1). Cost: none; a grep over results.

## 7. Do not repeat

- `request.sh` reads the issue's release label with `gh`. Offline that read fails and a #569
  request queues plain, behind every release-tier request. Pass `HAKUX_RELEASE_PRIO=1`.
- Not every soak path writes `verdict.json` (Kabuki B had none); `judge.py` falls back to
  `title_verdict.judge()` in memory.
- hitch_report's `shader` class is "the window saw a cache miss". Under the ladder that is not a
  compile stall; read dpc_ms beside it.
- `--frames-every 1` catches the banner. The frame mtimes are host clock and logcat is device
  clock; place frames by content, not by time.

## 8. The ToeJam check (head run at effb0d001b, read 22:08 PDT)

`1-1791001364-uberdefault569-1888217`: ToeJam & Earl III, same route and env as B,
`HAKUX_GPL=0`, built from effb0d001b (emulator code = d4a02e2060). Cold (cache cleared, PLC wiped).

| arm | ref | start xo-therm | fps_ok | median | fps per minute after mark |
|---|---|---|---|---|---|
| A1 off (first play) | 6b0c4a131f | 43.7 C | 0.992 | 59.9 | 40 41 57 59 50 57 58 60 60 60 51 54 60 |
| **A2 off (this run)** | effb0d001b | 35.0 C | **0.996** | 59.9 | 42 51 58 57 60 60 60 60 60 60 60 60 |
| B on | d4a02e2060 | 48.6 C | 0.881 | 53.9 | 38 32 55 53 52 54 49 38 39 53 42 44 54 |

- **F fails again against the same build: 0.996 -> 0.881.** The "different session" reading in
  section 5 is gone. Two off arms at 0.99+ against one on arm at 0.88.
- **The deficit is not the cold span.** B's ladder linked 92 pipelines by 23 s after the mark and
  100 by 201 s, and none after. Its misses after the first minute are 0-3 a minute with 0-22 ms
  of creates. Yet its slowest minutes are 7-8 and 10-11. In mode 3, a pipeline that has swapped
  should draw the same as A's monolithic one. So either something in mode 3 costs every frame
  (a pipeline still on the uber stage, the swapped pipeline not being what A builds, or bind-path
  overhead), or B's warmer start (48.6 C against 35-44 C) cost it 0.1 by itself.
- **It matters for ratings.** 0.881 is under the Playable bar (>= 0.90 of gameplay at 30+ fps).
  Both off arms pass it. If the cost is the ladder's, the default flip could drop a Playable title
  below the bar.
- **What this does not show:** GPU ms per frame. No arm ran `--perflog`, so B's slow minutes
  cannot be split into GPU time and anything else here.

**Next, re-ranked by P x win** (replaces section 6's order; 6's items 1, 3, 4 stand behind it):
1. **Find ToeJam's steady-state cost.** One ToeJam pair, on then off, back to back from a matched
   start temperature, both `--perflog`. Read GPU ms per frame and `[gpl569]`/`[uber569]` per
   window in the slow minutes. P 0.6 that the ladder causes it: same-build off 0.996 vs on 0.881,
   with the ladder idle while it happened. Counter-evidence: a 13 C warmer start, and A1 shows
   content dips to 50 fps. Win: whether the default holds Playable titles at Playable. If the
   GPU ms are higher, check that swapped pipelines are the monolithic ones and that none stays on
   the uber stage. If GPU ms are equal and fps lower, it is the bind path or thermals.
   Cost: 2 Nova runs, ~35 min.
2. Persist the uber combinations and pre-build them at boot (section 6 item 1). P 0.8. Win: the
   last ~3 s of creates per first launch.
3. Split and cut the stand-in's GPU cost (section 6 item 3). P 0.6.
4. `NoContraction` (section 6 item 4).

**The default stays on, as the owner decided.** The trade on these four titles: three cold-launch
freezes of 11-226 s removed and fps_ok up 0.19-0.34 where the off arm froze, against ToeJam's
0.996 -> 0.881. The setting turns the ubershader off, globally or per game, if a title shows
the ToeJam pattern.

The fold's head run is a short DOA3 smoke queued after this commit (purpose `#569 head run`), because
this section moved the head off effb0d001b. That makes 12 Nova runs, two over the brief's 10:
the Tron rerun and this smoke.
