# GTA III dip, post-R1/R2/R3: where the frame goes, the two owner stalls, and the next lever (#1049, #433)

Analysis-only. All figures below come from finished runs/captures, read-only, no device time this lane.

## 1. Decomposing the parked frame: `runs/b3-A` (R1), `b3-B` (R1+R2, copies 0/flip), `b3-C` (R1+R3)

Windows are the parked-phase device-clock range from each arm's `arm.log` (`PARK_START` to `RT_DOWN`), read from each
run's `logcat.txt`. The single reliable per-60-flip emitter for this is `hakuX-perf: gfps=...` / `hakuX-phase: ...` /
`xemu-gpu: GPU: ...` -- confirmed by grep to come from exactly one thread id per run (14006/B's 20298/C's 26459),
never racing. The `hakuX-stall: RPBreaks:.../Finish:...` lines (same `opt_stats_log_and_reset()` family as the
`hakuX-rpbrk` reason breakdown) are **not** used for per-window citation here; see 1.2.

Per-window means over each arm's parked phase (ms unless noted; RP = render passes/frame; n = windows):

| arm | switches | n | G (game frame) | Tot (PGRAPH CPU) | GPU Tot (Rnd+Xfr) | Fin (of which Fen) | Draw | RP/frame |
|---|---|---|---|---|---|---|---|---|
| A | R1 | 7 | 54.9 | 31.8 | 33.6 | 17.5 | 11.3 | 54.6 |
| B | R1+R2, copies 0/flip | 12 | 38.1 | 21.0 | 25.1 | 7.8 | 8.9 | 52.5 |
| C | R1+R3, dup 0/flip | 11 | 40.2 | 20.3 | 26.4 | 7.3 | 9.5 | 53.5 |

(A's own first window, the load spike at PARK_START, G:190.8, is excluded; it is the shader/pipeline cold-compile
spike explained in 1.4 below, not steady park.)

**B is the arm the brief asks about: 0 copies/flip, and the frame is still 33-46 ms (mean 38.1).** Across every
window in every arm, GPU Tot and Tot (CPU) run in parallel Vulkan tracks and neither alone reaches G: G exceeds both.
Within GPU Tot, `R` (render) dominates over `X` (transfer/copy) in every sampled line (example, B,
01:29:26.868: `GPU:28.1(R:20.5 X:7.6 ...)`) -- expected once copies are at/near 0, but true in A too (copies still
cost CPU time to record and a GPU transfer, not the dominant GPU share even there).

### 1.1 Render passes per frame do not move with the copy count

RP/frame is 54.6 (A, 133/flip copies), 52.5 (B, 0/flip), 53.5 (C, 0 dup/flip): a 2-4% spread, not proportional to the
133-to-0 swing in copies. This matches `gta3fps1017b` section 3.1's reading that R2 removes the copy but not the
render-pass break `bind_surface_as_texture`'s barrier (`pgraph_vk_begin_nondraw_commands`) causes, and extends it:
R3 (dup sharing) removes neither the copy nor the break for GTA III's driving scene, because dup is 0 here (already
established). **~53-55 passes in a single parked frame is itself notable: it is roughly double pilot 343857's
22-30 passes/frame measured while actually driving** (gta3drive1017 NOTES 6.2) -- a static, parked scene is not a
low-render-pass scene here, which argues against "camera motion" or "world streaming" as the source of the pass
count.

### 1.2 Df is not "deferred flush": a correction to the carried-over framing

The brief's "already established" section (borrowed from `gta3fps1017b` NOTES section 5) reads `Df` as "deferred
flushes." Reading `hw/xbox/nv2a/pgraph/profile.c` (`nv2a_profile_get_pacing_str()`, format string
`"...Df:%u Vd:%.1f..."`) and `hw/xbox/nv2a/nv2a.c` (~1100-1178, the VBLANK pacing governor: `defer_cap`,
`poll_interval`, `in_deferral_window`, `g_nv2a_stats.pacing.defers_total++` at line ~1162) shows **`Df` is
`defers_total`: a count of VBLANK-IRQ-delivery deferrals by the frame-pacing governor**, incremented once per
deferred VBLANK fire (and the governor can retry a deferral multiple times per frame under `defer_cap`, so `Df` can
exceed 60 in a 60-flip window -- it is an event count, not a per-frame flag). It is downstream of a frame already
running long, not an independent measure of GPU/render work. The x4.5 Df jump (dip vs good) that `gta3fps1017b`
section 5 treats as part of a "shared dip signature" is, by this reading, mostly the governor reacting to the same
slowness G already reports, not a second, independent symptom. Carry the correction forward; do not cite Df as a
workload metric.

### 1.3 The `RPBreaks`/`Finish`/`stlDef` counters race across threads in exactly this regime

`opt_stats_log_and_reset()` (draw.c, printing `hakuX-stall RPBreaks:.../Finish:...` and `hakuX-rpbrk`) reads and
resets a single global, non-atomic `struct OptBisectStats g_opt_stats` (draw.c:39), and is called from
`pgraph_vk_finish()` whenever `finish_reason` is `VK_FINISH_REASON_FLIP_STALL` *or* `VK_FINISH_REASON_PRESENTING`
(draw.c ~5391-5427) -- two reasons that can fire from different threads once the deferred-finish path is active
(draw.c ~5560-5679, the `#796` render-thread mechanism: a `RCMD_FINISH` command handed to a separate render thread
that submits and waits its own fence without holding `pgraph.lock`). Confirmed by grep: in the steady 30 fps menu
phase only tid 14006 ever prints this line; **in every one of A/B/C's park windows, both 14006 and a second thread
(14008 in A) print it, interleaved, and the values are non-monotonic** (observed swinging between ~4900 and ~9500
and back within the same window in A). This is a genuine instrumentation-reliability finding for exactly the
regime the brief asks about: **the per-window RPBreaks/Finish/stlDef breakdown cannot be cited quantitatively for
the park/dip phase.** It is reliable only in the steady 30 fps state, where it is not needed. (Stop-rule entry,
NOTES.md section 0.)

### 1.4 b3's own confound: arm A pays a cold-shader/pipeline-compile tax that B and C do not

`batch.log` clears the shader cache once, immediately before arm A; B and C are the same APK install, relaunched
with only env vars changed (no reinstall, no cache clear). `[uber569]` (`cold=`, `lib_ms=` cumulative
pipeline-library compile time):

| arm | first `cold=` | last `cold=` seen | final `cold` count | final cumulative `lib_ms` |
|---|---|---|---|---|
| A | 01:25:51.300 (cold=1) | 01:28:16.131 (into A's own hold phase) | 49 | **50445.1 ms** (50.4 s) |
| B | 01:28:27.751 (cold=1) | 01:30:21.101 | 14 | 0.6 ms |
| C | 01:31:02.032 (cold=1) | 01:33:00.436 | 16 | 0.7 ms |

A alone pays ~50 s of cumulative synchronous shader/pipeline-library compile, continuing past its own park window
into its hold phase; B and C reuse the on-disk pipeline cache A just built and see essentially nothing. **This fully
accounts for A's higher park-phase means (G 54.9 vs B 38.1, C 40.2) in this one run** -- it is not evidence that R2
or R3 sped anything up. b3 is a single, non-palindromic A-then-B-then-C pass sharing one install; it is not a
controlled comparison between arms, unlike the palindrome batches (b2/b4) that already gave the authoritative R2/R3
fps verdict (-0.3, -0.9: no gain). **Do not use b3's cross-arm absolute numbers as a second opinion on R2/R3.** Use
it only for what this section uses it for: the shape of a frame within one arm, and the cold-compile signature
itself (which turns out to explain the owner's two stall frames directly -- section 2).

### 1.5 What tracks the window-to-window wobble inside one arm

RP/frame is nearly flat within each arm (A: 52-57 across its 7 windows; B: 42-57 across 12; C: 45-57 across 11), so
it cannot explain why G itself swings 45-70 ms (A) or 33-48 ms (B/C) window to window inside one otherwise-static
scene. `Fin` (and specifically its `Fen` -- fence-wait -- sub-field) does: in B's 12 aligned windows, every
high-`G` window is a high-`Fin` window and every low-`G` window is low-`Fin`, with no exception (`G`/`Fin` pairs:
48.1/14.7, 41.5/12.0, 33.4/4.2, 35.9/6.3, 33.5/4.3, 33.2/3.3, 33.3/3.5, 41.7/12.9, 45.9/9.7, 33.4/6.2, 36.5/6.0,
40.9/10.1); A's 7 windows show the same direction (highest G/Fin pairs 69.5/34.0 and 61.2/24.5; lowest 44.8/10.6).
`Fin` is the CPU thread's own submit+fence-wait time (`Sub`+`Fen`), and it is the largest-swinging single
sub-component of `Tot` in every arm (3x range within B alone, vs Draw's comparatively flat 7.5-11.2 ms). This reads
as GPU-queue-depth/backlog variation frame to frame -- consistent with the `#796` deferred-finish mechanism
(render thread completions queueing unevenly) -- rather than a fixed per-pass or per-copy cost. The per-window
`stlDef` count that would confirm this mechanistically is part of the same racy counter family as 1.3 and is not
citable per-window; the `Fin`/`Fen` ms figure (reliable emitter) is the evidence here, not the deferred-finish count.

### 1.6 Texture-dirty walks, shader-cache lookups, page walks, upload bytes (pilot 343857, re-read)

Not re-measuring gta3drive1017's own conclusion (texture dirty walks are microseconds, `[rdc]`), but filling in the
tags the brief names that weren't already pulled:

- `[tsc]` (texture-scan stats, also `opt_stats_log_and_reset()` family -- same reliability caveat as 1.3): during
  the driving burst (e.g. 15:40:00-15:40:50), `scans` runs 33798-70313 per 60-flip window (560-1170/flip), but
  `dlscan`/`nodl` time stays at 0.07-0.17 **ms total per 60-flip window** -- confirms gta3drive1017's "texture dirty
  walks: microseconds" even at this much higher scan rate. `miss`/`dl`/`sdl` are 0 throughout the sampled burst.
- `[drawrec]` (vertex-sync accounting): early in the pilot (cumulative, f=1797), `pages=59 shc=3908`; inside the
  driving burst (one 60-flip window, f=60 at 15:42:44), `pages=78573 shc=19609` (both per-window, not cumulative, at
  this point in the run), `redo=132 redoKB=1408` (~23.5 KB/flip of vertex re-upload). This is the same metric family
  the owner capture shows (brief: "shader-cache count 18-25k and pages walked 117k-217k per window") -- confirms the
  owner's numbers are not anomalous, they are this title's normal driving-burst range for this counter. No ms figure
  is printed alongside `pages`/`shc` in this line, so a cost (not just a count) for this path is not established by
  either capture; flagged as open in section 3.

## 2. The owner capture's two single-frame stalls: both are the title's own cold shader/pipeline-library compile, both resolved inside the first 90 s, neither present in the sustained dip

`captures/owner-play-1018/logcat-nova-owner-play.txt`, pid 5782 (GTA III, release build, R1 on):

- **1.46 s frame, 07:37:23.763**: `gfps=29 G:38.1(7.9-1457.8)`. In the same ~1 s, `vsh-uber: family module 2:
  44708 bytes GLSL, 19.6 ms` and `[uber569] mode=3 links=8 cold=4 ... queued=2` -- a cold shader module is compiling
  and a pipeline link is queued, 2 s after `init: pipelines` (07:37:20.423) and `Shader module warm-up: 285/285
  modules enqueued` (07:37:20.416): this is the title's own post-boot shader/pipeline warm-up, not an in-game event.
- **3.89 s frame, 07:37:53.997**: `gfps=23 G:46.8(0.6-3888.2)`. In the same window, `[uber569] ... cold=10..17
  libs=7 lib_fail=0 lib_ms=8736.6 next_ms=1651.2-2101.2 ... queued=3-6` -- multiple cold pipeline-library links,
  cumulative `lib_ms` already at 8.7 s and climbing, each `vsh-uber` module compile logged taking 9-39 ms
  synchronously on the same thread (5836) that also prints the frame stats.
- **Both stalls are inside the title's single active cold-compile window.** `cold` climbs 1 -> 18 and cumulative
  `lib_ms` climbs to 24585.5 ms between 07:37:20 and 07:38:23, then **both go flat for the rest of the capture**:
  the last `cold=`-incrementing line in the GTA III window is at 07:38:23.104 (`cold=18`); every later line,
  including inside the sustained dip windows the brief names (07:38:34 `cold=18`, 07:38:52.789 `cold=18`), shows
  `cold=18 lib_ms=24585.5`, unchanged. The sustained 16-22 fps dip (07:38:34, 07:38:44-55, 07:39:14-30) runs with
  **no active shader/pipeline compile** -- it is a different, ongoing cost (section 1), not a slow version of the
  startup stall.
- **Present in the earlier (b3) runs too, same mechanism, same window**: section 1.4's arm A shows the identical
  signature (`cold` climbing, `lib_ms` climbing into the tens of seconds) in its own first ~90 s after its cache
  clear, and goes quiet once warm (arm A's `cold` count stops moving at 49, `lib_ms` flat at 50445.1, well before
  A's hold phase ends). The owner's capture and b3-A agree: this is the build's cold-start cost, paid once per
  process cold-start (or once per shader-cache clear), not a per-session or per-location cost while driving.

**One-stall verdict for the owner:** both multi-second frames are the Vulkan shader-module/pipeline-library warm-up
that runs once after boot; they are not evidence of a new per-session stall, and they are already over by the time
the sustained dip (the subject of this lane) starts.

## 3. Dominant cost and ranked levers

Nothing proposed here repeats a row already shown to fail or already folded (NOTES.md section 0): not the #474
drain (R1, folded), not R2/R3's copy/dup remedies (already measured no-gain on the controlled batches), not sysmem
mode or a faster clock (GPU is not the bottleneck; owner forbids these anyway), not vertex hazards, pgraph.lock, or
pipeline compile as an ongoing-dip cause (section 2 shows compile is a one-time startup cost, already over).

**Dominant cost, as measured here:** the CPU-side thread's own fence-wait time (`Fin`, mostly `Fen`) is the
largest-swinging, best-correlated-with-G component in every arm's park phase (1.5), on top of a render-pass count
(~53-55/frame) that stays high regardless of copy elimination (1.1) and does not by itself explain the window-to-
window wobble. Ranked candidates, each excluding already-failed levers:

| rank | lever | P(helps) x est. fps gain | file / function | issue / lane |
|---|---|---|---|---|
| 1 | Reduce render-pass breaks directly (not via R2/R3's copy angle): find and remove the non-copy nondraw/clear/query triggers that hold the count at ~53-55/frame in a static scene, since R2 already proved the copy is not what's forcing most of these breaks | 0.35 x 2-4 fps (half of R1's own +1.9/+2.7, since the break's barrier/sync cost -- not the copy's bytes -- is what R2 left untouched) | `pgraph_vk_begin_nondraw_commands` / `rp_break_nondraw` and `rp_break_clear`/`rp_break_query` sites, draw.c:5966/6395/7188-7205/7506; `bind_surface_as_texture`, texture.c:1175 | #433 (this umbrella); no open issue names the non-copy break causes yet -- would need a board request |
| 2 | Investigate GPU-queue-depth / finish-ordering so `Fin`/`Fen` does not swing 3x window to window (the `#796` deferred-finish mechanism, draw.c ~5560-5679) -- not the #474 drain, which is already gone | 0.25 x 2-3 fps (Fin's swing alone is 3-30 ms/flip in the data above; even halving its upper range moves G visibly) | `pgraph_vk_render_thread_enqueue` / `RCMD_FINISH` path, draw.c ~5560-5679 | #796 (folded for a different symptom -- NBA Live/CS -- not yet checked against GTA III's own finish ordering) |
| 3 | Cost out the vertex-sync page-walk / shader-cache-lookup path during a driving burst (`pages`/`shc` in `[drawrec]`, section 1.6): counts are large (hundreds/flip) but no ms figure exists yet in either capture, so this is unranked by impact until a perflog run adds per-call timing to that line | 0.15 x unknown (no cost measurement exists) | `hw/xbox/nv2a/pgraph/vk/draw.c` vertex-sync walk (the `[drawrec]` print site) | none yet; would need an instrument change before it is even a candidate, let alone a lever |

## 4. The one lever a fix lane should take first, and the confirming measurement

**Take lever 1 first: find and remove the non-copy render-pass-break triggers that hold the parked-scene pass count
at ~53-55/frame.** It ranks above lever 2 because it is a structural count already isolated by R2/R3's own result
(the copy is gone, the break mostly is not) and it is visible in the controlled, parked phase -- lever 2's Fin/Fen
swing is real but its root cause (deferred-finish queue depth) is not yet isolated to a single trigger the way the
break count is, so a fix lane would need an extra diagnostic pass before it even has a target. Lever 1 already has
one.

**The confirming measurement, before writing any code:** add (or re-enable, if already present and gated out)
the `hakuX-rpbrk` reason breakdown (`RP:%d(fin%d fb%d qry%d clr%d nd%d srf%d)`) on a **single, non-racy emitter** --
either move its print to the same thread/gate as `hakuX-phase` (confirmed single-threaded in this lane, 1.3), or
make `g_opt_stats`'s relevant counters atomic/thread-local so the existing print site stops racing once the
deferred-finish path is active. Then, in the **parked** phase of a b3-style arm (controlled, no driving-induced
scene variance): expect `rp_break_nondraw` and/or `rp_break_clear`/`rp_break_query` to account for the bulk of the
~53-55 passes/frame, since the copy-driven `rp_break_surface`/transfer path is at or near 0 in arm B already. If
instead `rp_break_finish` dominates, that points back toward lever 2 (the deferred-finish mechanism) rather than a
nondraw-command cause, and the ranking above should flip. Either outcome is decided by the **parked** window count
(stable, controlled) -- not by an RT-held fps mean, which this lane's own data (and the brief) already show varies
~8 fps run to run for identical code.
