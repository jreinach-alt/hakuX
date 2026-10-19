# fpsdata1018 NOTES (#433)

Lane: fpsdata1018. Brief: `/home/justin/hakux-work/briefs/fpsdata1018.md` (owner 2026-10-18 ~22:00 PDT): find the
causes of the FPS dips in the owner's 4-title capture (`/home/justin/hakux-work/captures/fps-owner-1018/`, master
perflog 72af9cb92c, Nova, PurpleVK) and land fixes.

## Attempt log

- **Attempt 1** (session 4431cc4c, 2026-10-19 04:39-04:51Z): committed nothing. It added two candidates to
  `fpsdiag.py` (`c2b_fin_sub_renderthread_wait`, `c9_surf_download_wait`), bumped the 99-fpsdiag candidate count
  10 -> 12, regenerated the four `<title>.analyze.txt` files in the capture dir, and was cut off while running the
  99-fpsdiag selftest fragment in the foreground. Its lane log (`logs/lane/fpsdata1018.20261019T043934Z.json`) is
  0 bytes: the session ended with no closing words, so handback resumed it as idle. Why it did not finish: it went
  to the tool before Step 0, never wrote NOTES.md, and the session ended (12 minutes in) before its first commit.
  Its two edits are kept (they read the capture correctly, checked below). This attempt commits Step 0 first.
- **Attempt 2** (this session): Step 0, then the mechanism account (G2), then fixes.

## Step 0: Already-tried (G1)

One row per lever or theory a prior lane tried or measured. A candidate this lane proposes that is already a row is
dropped unless the row's "what is different" is stated where it is proposed.
Sources: `L/` = `docs/lanes/`; README = `captures/lanexbox-fps1018/README.md`; instr = the gta3instr1018 worktree
NOTES (newer than master's); ralli = `wt/ralli2audio1018/docs/lanes/ralli2audio1018/`.

| # | Lever / theory | Title | What moved (as written) | Control / spread | Verdict | Source |
|---|---|---|---|---|---|---|
| 1 | R1: skip the #474 drain (folded 4a504d9aaa; `HAKUX_S2T_DRAIN=1` restores) | GTA III | Nova parked +1.9 (b2), +2.7 (b5) fps, ~50 -> ~46 ms/frame; desktop drains/flip 1.86 -> 0 | b2 palindrome P A B C C2 B2 A2 P2; b5 W P A A2 P2 | works, small; folded | `L/gta3fps1017/NOTES.md` 2.4; README |
| 1a | R1 driving | GTA III | 29.80 vs 29.77 fps | scenes not aligned | confounded | `L/gta3fps1017/NOTES.md` 2.5 |
| 2 | R2 `HAKUX_S2T_WIDEN=1` (remove all copies/flip) | GTA III | copies 133.2/69.8 -> 0/0; fps vs R1 -0.3 (b2), -0.9 (b4) | b2, b4 palindromes | **falsified** (copy theory) | README; `L/gta3fps1017b/NOTES.md` 2.2 |
| 3 | R3 `HAKUX_S2T_SHARE=1` | GTA III | share 0.00, dup 0 | b2 | inert | README |
| 4 | Copies cause the parked dip | GTA III | RP/frame 54.6 / 52.5 / 53.5 at 133 / 0 / 0 copies | b3 arms | falsified (parked) | `L/gta3dip1018/FINDINGS.md` 1.1 |
| 5 | R1-R3 on Blinx 2 | Blinx 2 | `[s2c]` cp 0 idle and moving | bc-A | inert (nothing to act on) | README |
| 6 | Cold shader/pipeline compile | GTA III, Fable | explains GTA's 1.46 s / 3.89 s single stalls and one Fable 3.78 s frame; not the sustained dips (counters flat during them) | per-capture timeline | ruled out for sustained dips | `L/gta3dip1018/FINDINGS.md` 2; `L/fabledip1018/FINDINGS.md` 1b |
| 7 | GPU saturation | all four | busy 55-72 % GTA/R2, 25-29 % others in this capture; earlier ~34 % flat | dip/good classes | refuted (c1-A1 in-car 90/43 % tension open) | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.1 |
| 8 | TLB/texture-dirty walk cost | all four | 0.3-0.6 % of render-thread CPU (this capture); 0.4-2 % earlier | 4+4 captures | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.2 |
| 9 | ART GC pause | all four | 0 GC lines | 167 + this capture's dip windows | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.8 |
| 10 | Fin/Fen fence wait = #796 queue depth | GTA III | parked G/Fin 48.1/14.7 ... 33.2/3.3; in car fen 15.57 = rotfen 11.03 + stale 4.00; c1-A1 Fen 13.6 vs 2.5 | within-arm windows | correlate supported; mechanism not isolated; never A/B'd | `L/gta3dip1018/FINDINGS.md` 1.5; `L/gta3car1018/NOTES.md` 4.1 |
| 10a | Fen queue depth | Fable | 1.4 vs 0.1 ms (owner-play-1018c) | 56/57 windows | refuted | `L/fpsdiag1018/FINDINGS.md` 4 |
| 10b | RalliSport 2 Fin split | RalliSport 2 | Fen 0.1-0.5 flat; Fin 11-26 ms "almost all Sub" | 36 phase lines | Sub, not Fen | ralli `FINDINGS.md` "New telemetry" |
| 11 | `hakuX-rpbrk` / `RPBreaks:` per-window breakdown | GTA III | two tids write it; ~4900 <-> ~9500 | -- | instrument racy; replaced by `[dipwin]` | `L/gta3dip1018/FINDINGS.md` 1.3; instr 1.1 |
| 12 | `[dipwin]` pass attribution, in car | GTA III | 151.65 rp/flip, 141.43 `bnd` copy_surface_to_texture; ms/flip = 30.89 + 0.1309 x rp (r^2 0.66) | 46 windows | measured: feedback-loop copy per draw | `L/gta3car1018/NOTES.md` 4.1 |
| 13 | `HAKUX_S2T_FB=1/2` (texture.c) | GTA III in car | O1 24.8 fps / 57.11 rp; F1 26.8 / 20.15; S1 27.9 / 38.20; F2 22.6 / 33.67 | one run per value, not a palindrome | cuts passes; fps confounded; 30 not reached | `L/gta3car1018/NOTES.md` 6 |
| 14 | Page-granular stale vertex copy (vtxstale1018) | GTA III | selftest bytes 891.6 M -> 118.5 M; in car stale ~4 ms | selftest only | not device-measured | `L/fpsdiag1018/NOTES.md` 0 |
| 15 | Vertex hazards (~0.3/flip), pgraph.lock (lw 0), compile <= 2 ms, guest 23.3 ms | GTA III pilot 343857 | as written | one pilot | ruled out there | `L/gta3fps1017/NOTES.md` 0 |
| 16 | redo/shc volume | Fable, Blinx 2 | Fable redo/dirty 2.0-2.8x flat; Blinx 2 3.16 -> 4.87 | counts only | cost never timed | `L/fabledip1018/FINDINGS.md` 1 |
| 17 | Df "deferred flushes" | all | VBLANK-governor retry count | code read | downstream metric, not a lever | `L/gta3dip1018/FINDINGS.md` 1.2 |
| 18 | RalliSport 2 audio (`vp.c` direct read, `HAKUX_APU_PRIO`, `prod:` model) | RalliSport 2 | starve 0.000153; fps_ok 0.8618 | pilot + 2 bar runs | audio fixed; fps not | ralli `FINDINGS.md` Status |
| 19 | RalliSport 2 fps cliff ~59 -> 25-50 at 180-240 s | RalliSport 2 | 59.0 (0-150 s) -> 38.3 (240 s) | 4 runs, prio on/off | not the audio change; thermal/sustained load suspected, handed off | ralli `NOTES.md` attempts 14-15 |
| 20 | Faster clock / governor / perf mode / sysmem | any | -- | -- | forbidden (owner) | memory `investigate-the-wait-not-the-clock` |
| 21 | Scripted gameplay navigation (6 GTA routes) | GTA III | all VOID | -- | do not repeat | `L/gta3fps1017/NOTES.md` 0 |
| 22 | texscan: GPU copy of draw-dirty whole-face CUBE surfaces into the texture instead of download + upload (`HAKUX_TEXSCAN`) | NFS MW cube | range 4.03 -> 0.00 ms/frame, but fps -1.4 / period +2.6 ms alone: the wait moved to the #804 report fence | NFS arms | works when paired with REPORT_ASYNC; default-on in fastpaths with it | `L/texscan1010/NOTES.md` 5-11 |

Correction carried from the research pass: `L/fpsdiag1018/FINDINGS.md` 2 item 4 credits "R3 -0.9 fps"; README gives
-0.3 (b2) and -0.9 (b4) both to R2 vs R1, and R3 no fps number (dup 0, inert).

Proposed by prior lanes, never built or never A/B'd (candidates for this lane only with what is different stated):
#796 deferred-finish queue depth (draw.c RCMD_FINISH path); the PRESENTING finish (display.c `render_display`);
deferred surface download ending passes (surface.c `download_surface_record_deferred`); in-pass feedback-loop layout;
the c4/c5/c6/c8 OS candidates (sampler never run). **No prior lane looked at `Sub` (RalliSport 2 / Fable) or at
`dfF` / the Surf phase (Blinx 2).**

## G2: mechanism account, every title

Line numbers are in the per-title splits beside `full-session.txt` (`ralli2.txt`, `gta3.txt`, `fable.txt`,
`blinx2.txt`). Per-window rows were joined from the `[dipwin]`, `hakuX-phase`, `[sdcall]`, `txr`/`txdl` and `[tsc]`
lines of each 60-flip block, for every window in each split, not a picked frame. ms figures are per frame
(window ms / 60) unless marked.

**First question (G3): is Fin one cause or three?** Not one, not three: two of the three Fin titles share a cause
and the third is a different one. In RalliSport 2 and Fable, Fin is `Sub`, the finish's own submit-and-wait
(`Fen` 0.1-0.3 in RalliSport 2, 1.6-4 in Fable), and the finish is `fin=sdown`: a SURFACE_DOWN sync inside
`create_texture`, because the texture the guest binds is not the shape of the render target it reads, so
surface-to-texture (s2t) refuses it and the surface is downloaded to guest memory and read back. GTA III's swing is
`Fen` (the rotation fence and the `stalled` finish) on frames whose GPU time doubles. Blinx 2's is `Surf` (a
deferred-download fence wait), not Fin.

### RalliSport 2 (race, 21:22:15-21:22:53)

| Window line | s / 60 flips | gfps | Fin (Sub) | GPU | `fin=sdown` count / ms | `txdl` | `[tsc]` |
|---|---|---|---|---|---|---|---|
| 1926 | 2.937 | 20 | 22.4 (22.3) | 21.4 | 60 / 1529.5 | dim60 | sdl60 `#0` |
| 2407 | 2.459 | 25 | 18.1 (18.0) | 17.2 | 60 / 1150.0 | dim60 | sdl60 `#0` |
| 2645 | 2.471 | 24 | 21.5 (21.4) | 20.4 | 60 / 1214.9 | dim60 | sdl60 `#0` |
| 3268 | 3.127 | 18 | 26.3 (25.9) | 24.7 | 60 / 1581.9 | dim60 | sdl60 `#0` |
| 1155 (menu, good) | 0.983 | 59 | 0.3 | 14.2 | none | 0 | 0 |

Every race window from 1926 to 3664 (16 windows) has exactly 60 `sdown` finishes per 60 flips, 10-26 ms each
(sum 0.43-0.52 of the window), and no other large finish. The download is one surface: `[tsc] new #0 sdl act base
s2t=dim` (1746): texture @3e78000 640x480 linear A8R8G8B8 pitch 2560, surface @3e78000 260x260 pitch 2560, offset +0
(earlier 640x380, 865/866). 39000 K per window = 60 x 260 rows x 2560. `tobuf` itself never finishes (`fin0
pre55-59`, 2036-3652): the cost is the download's own finish (`surface.c:2705`) waiting for the GPU to drain the frame
so far. Fin tracks GPU to within 1 ms in every race window (the sync waits for the whole frame's GPU work).
Natural experiments in the same session: 1155-1686 (menus/replay, no `sdown`) 53-60 fps at GPU 12-14 ms.

Mechanism: the guest renders a 260x260 view (a mirror or a screen-in-screen) into a pitch-2560 surface and samples it
as a 640x480 linear texture. s2t needs the same extent, so it refuses (`txdl794 why=dim`), and texscan (row 22)
takes cube maps only.

### Fable (gameplay, 21:29:58-21:31:39)

| Window line | s | gfps | Fin (Sub/Fen) | GPU | `sdown` n / ms | `tobuf` | `surfupd` | `[tsc]` |
|---|---|---|---|---|---|---|---|---|
| 5169 (`[dipwin]` 5175) | 3.910 | 16 | 35.6 (33.5/1.9) | 30.9 | 420 / 2266.3 | fin60 dl537 1647.2 ms | fin60 380.7 ms why=inv60 | sdl120 dl240 `#0-#5` |
| video (2002, good) | 1.0 | 59 | 0.2 | 1.0 | none | -- | -- | 0 |

Every gameplay window from 2629 on: `[tsc]` `cls[base mip]` only, entries `#0-#5`. These are two textures (@187d080
and @18a7080, 128x128 SZ_A8R8G8B8, 3 levels, len 86016; 2454-2467). Each LEVEL is its own render surface at the
level's offset: 128x128 at +0, 64x64 at +65536, 32x32 at +81920. All six are drawn and bound every frame. s2t refuses
(`why=levels`), texscan refuses (not a cube), so per frame: two SDL downloads, four range-scan downloads, and their
syncs. Per frame at 5175: `tobuf` 27.5 ms is the first sync, and it pays the GPU backlog. It completes 9 deferred
downloads, 6 of them evictions (`evict[dl:360]`). `surfupd` 6.3 ms is a forced completion on a zeta upload
(`why=inv60`, `su_upl=60`). Range finishes add 0.8 ms and the own finishes 3 x ~1 ms. Fin is 35.6 of a 65 ms frame.

The second Fable mechanism is the zeta churn: the zeta at 0x019b4000 is re-shaped for each level size (`[surf92]`
shapedirty, 5160-5165), so each change evicts and downloads the old shape (6/frame) and re-uploads (`why=inv`). These
eviction downloads are not syncs by themselves. They are recorded and completed at the next sync, today the
texture's.

### GTA III (21:24:09-21:26:20)

Dip windows (13-21 fps): Fen 20-35 ms, GPU 29-48 ms, `rotfen` 0.6-1.4 s per window and `fin=stalled:50-79` / 0.7-1.5 s
(windows ending 21:24:32.001, 21:24:41.538, 21:25:28.674). Good windows (29 fps): Fen 2-4, GPU 14-24, `rotfen`
~1 ms/frame. Fen tracks GPU growth: the frame is GPU-bound in dips and the wait sits where the CPU next blocks
(rotation fence, `stalled` finish). No `sdown` in any window. What raises GPU time is the measured per-pass cost
(row 12, 0.13 ms per render pass, 151 rp/flip in car) plus the stale vertex copy (row 14). The levers there are rows
13/14. This lane has nothing new on GTA III's mechanism beyond "GPU-bound, waited at the fence", and does not claim a
fix for it here.

### Blinx 2 (21:32:41-21:33:51)

| Window line | gfps | Surf | dfF | GPU (R) | RP | `surfupd` | Finish |
|---|---|---|---|---|---|---|---|
| 3054 | 15 | 41.7 | 39.2 | 39.6 (39.2) | 45 | fin0 fence62 2343.5 ms | stl61 stlDef70, `sd[cDefC62]` |
| 1738 | -- | 22.2 | -- | 20.8 | 44 | | |
| 2682 (good) | -- | 2.9 | -- | 13.7 | 31 | | |

Surf tracks GPU in every gameplay window (41.7/39.6, 38.4/35.8, 22.2/20.8, 27.2/27.3). It is one fence wait per frame
in `pgraph_vk_surface_update` (`surface.c:6219-6227`, `cDefC62`). Two surfaces per frame are detached and evicted
with a download (`evict[dl:120 unshelve:120]`, surfgpu `detach=120`, 3043/3037). The `stalled` finish (61/60
flips, 1.1 ms) submits them, which sets `deferred_downloads_frame`, and the next `surface_update` waits on their
fence: the whole frame's GPU work. Removing that wait leaves the frame GPU-bound at 20-40 ms (~2460 draws, 45 RP per
frame at 3054), so the ceiling for that fix alone is ~25 fps at 3054, from 15.

### Hypothesis table

| # | Hypothesis | Titles | Evidence (line) | Reach (ms/frame) | Likelihood | Status |
|---|---|---|---|---|---|---|
| H1 | Texture of a different shape than its render surface (linear sub-rect; per-level surfaces) is downloaded and synced in `create_texture` | RalliSport 2, Fable | R2 1926-3664 `sdown 60` + `s2t=dim`; Fable 5175 `tobuf`/`sdl`/`scdl`, `s2t=levels` | R2 17-26; Fable 27.5 + 4 (first sync) | high (counter names the call site in both) | **Fix #1** |
| H2 | Zeta re-shaped per level: eviction downloads + forced `surfupd` completion | Fable | 5175 `evict[dl:360]`, `why=inv60` | 6.3 now; it absorbs H1's wait once H1 is gone | medium | next |
| H3 | Detach/eviction downloads waited at the next `surface_update` | Blinx 2 | 3054 `dfF 39.2`, `cDefC62`, `detach=120` | up to 39, capped by GPU 39.6 | high for the wait, gain capped | next |
| H4 | GPU time per frame (per-pass cost, draw count) | GTA III, Blinx 2 | GTA GPU 29-48 in dips; Blinx R 39 for 45 RP | the floor under H3, and GTA's whole dip | medium | rows 12-14 |
| H5 | Fence queue depth (#796) | GTA III | row 10 | -- | low (Fen tracks GPU) | not this lane |
| H6 | Thermal / clock | RalliSport 2 | row 19 | -- | ruled out for race windows: Fin = GPU = sdown | dropped |

Divergence noted, not explained: Fable's `dirtyIf180` counts three `download_if_dirty` calls per frame against two SDL
downloads (`txr dl120`). The third is outside `create_texture` (blit/surface callers). It is small (~1 ms) and stays
after Fix #1.

## G3: Fix #1 prediction (written before the build)

**Change.** texscan (row 22) takes non-cube 2D textures, behind `HAKUX_TEXSCAN` (default-on through fastpaths), with
`HAKUX_TEXSCAN2D=0` as its own off switch:
- swizzled, with each level a whole draw-dirty surface at the level's offset (`get_texture_layout`'s level loop,
  `texture.c:431-521`), copied into that mip level;
- linear, one level, with one draw-dirty surface inside the texture at the same pitch, copied into the
  rectangle it covers.

The texture is uploaded from guest memory as today and the surface texels are copied over it on the GPU in the
frame's command buffer. No download, no sync. Bytes: the colour download writes the surface's `width * bpp` per row
into guest memory unconverted (`surface.c:2723`), and the upload of an unconverted format reads them back
unconverted, so the copy gives the same texels.

**Why this works.** RalliSport 2: `create_texture`'s SDL block (`texture.c:3737-3749`) is the only `sdown` source
in race windows (`[tsc] sdl60 #0`, `txdl dim60`), and texscan's plan runs ahead of it and skips it
(`ts_taken`, `texture.c:3726-3729`). Fable: all six downloads are the `#0-#5` level surfaces, which the per-level
plan covers, so the SDL block and the range scan are skipped, and with them `tobuf`, the own finishes and the range
finishes.

**Predicted delta.**

| Title | Counter now | Predicted | fps now | Predicted fps |
|---|---|---|---|---|
| RalliSport 2 race | `fin=sdown` 60/window, 17-26 ms/frame; Fin 18-26 | `sdown` 0 in race windows; Fin < 2; `ts[bind]` ~60/window | 18-27 | 35-50 (frame becomes max(GPU 17-25, CPU 12-20)) |
| Fable gameplay | `sdown` 420/window, 37.8 ms/frame; `tobuf` 27.5 | `tobuf` and range `sdown` 0; `surfupd` grows from 6.3 to 10-25 ms (it is now the first sync) | 11-24 | +3 to +8 |
| GTA III | no `sdown` | unchanged | -- | 0 |
| Blinx 2 | `txr dl0`, `s2td600` | unchanged | -- | 0 |

**Cannot help:** GTA III and Blinx 2. Neither downloads for a texture in any gameplay window.

**Falsifiers.**
- RalliSport 2 race windows still show `fin=sdown` > 5 ms/frame, or `ts[bind]` 0 with `txdl dim60`. The plan
  then did not take the bind.
- The race fps does not rise while `sdown` falls. The wait moved: look for a new large `fin=` reason or `Fen`.
- Fable: `surfupd` ms rises by as much as `tobuf` falls. Then H1 is real but Fable's gain needs H2 as well.
- Any pixel change on the goldens (the must-not-move legs).
