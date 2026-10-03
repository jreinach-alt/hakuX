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
