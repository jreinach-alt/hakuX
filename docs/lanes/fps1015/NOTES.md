# lane.fps1015 NOTES

Brief: `/home/justin/hakux-work/briefs/fps1015.md`. Issues #986 (MKSM), #992 (Top Spin + Brian Lara),
#995 (Batman Begins), #993 (Prince of Persia), #994 (Halo 2 stalls). Offline tonight: the Nova is held by
lane.local's overnight chain until ~06:00 PDT 10-16.

## Status

[lane.fps1015] waiting: the #986 A/B of `HAKUX_S2T_CVT` on f5a67ba52c, four Nova requests 1792163875-fps1015-716177
(pixel B), 1792163881-fps1015-716411 (pixel A), 1792163888-fps1015-716638 (MKSM soak on1) and
1792163893-fps1015-717142 (MKSM soak off1), behind the owner's hands-on hold on the Nova (`lanelocal-ownerplay`).
Their four results resolve it; reading them is in "The A/B, queued" at the end.
- #986 MKSM: cause found, serialization on 16-bit render-to-texture downloads (3 a frame in the cutscene). Lever
  `HAKUX_S2T_CVT` built (default off) and checked by reading; its A/B is registered and queued.
- #992 Top Spin: the same cause, 24-32 downloads a frame. Same lever; its A/B needs an admissible route (no golden
  profile yet, and `fps786-topspin` is a first-run route without `mark profile-saved`).
- #992 Brian Lara: a different shape, unexplained. Next step: one perflog run.
- #995 Batman Begins: partly explained. GPU or wait-bound. The one download a frame serializes the previous
  frame's GPU work against the PFIFO thread. Fill against draw count needs a perflog + `vtx256` run.
- #993 Prince of Persia: reduced to a bound. The fog room's PFIFO-thread frame is 33-36 ms against the 33.4 ms
  two-vblank budget of a 30-fps title, so every frame takes three vblanks (19 fps). Nine shadow-map `cvt` downloads
  a frame are in that time; the same lever applies.
- #994 Halo 2: explained. Every fps-to-0 (5.2, 3.9 and 2.1 s frames) is first-time pipeline compilation on the
  draw thread: cold monolithic creates while a 3.4-4.6 s ubershader library builds, plus inline fragment libraries.
  The lever is #569's (vk/compile_worker.c), not this lane's.
- `HAKUX_S2T_CVT`: built in 6cbcb60bc7 (vk/texture.c lent by lane.x1port1012, board 104fac8e98); a one-shot
  `[s2tcvt] first` log added so a run shows the path fired. Census, checks and the A/B are at the end of this file.

Attempt 1 (10-15 22:41 to 23:29 PDT) ended at the 300-turn cap, not on a finding or a block. It had committed
#986, #992 and #995 and written the #993 pre-read section, uncommitted, with the fog-room dump read under way
(`scratch_pop_ws.csv`, `scratch_popseq.py`). Attempt 2 (10-16 05:41 PDT) commits that section and continues at
#993. Too many small tool calls spent the turns; attempt 2 batches its reads into scripts.

Attempt 2 (10-16 05:41 to 06:26 PDT) also ended at the 300-turn cap, not on a finding or a block. It committed
#993, #994 and `HAKUX_S2T_CVT` (6cbcb60bc7, 06:11), promoted MKSM's first golden (save 08a35d4fc120, the
fps1008-shaolin run's harvest) so a route headed `any` passes the profile gate, and was writing the census
(`cvtcensus.py`) and the A/B route when the cap fell; those were left uncommitted. The turns went on one-line reads
of texture.c while checking the lever by hand. Attempt 3 (10-16 07:53 PDT) commits them, registers the A/B and
queues it.

## #986 Mortal Kombat Shaolin Monks: step 1, the offline split (written before the read)

Run `ownerplay/runs/4D570029-1013-2232-9402/logcat.txt` (debug 0.5.0-1013-08f1fb4a90, plain build, no
frametrace). The always-on lines in it that split a frame, per 60-flip `hakuX-pace` window:

| quantity | source | meaning |
|---|---|---|
| period | `hakuX-pace` `ms` / 60 | flip-to-flip, ms |
| vCPU busy | `[rr425w]` `busy_us / (idle_us + busy_us)` x period | guest on the vCPU outside the kernel idle loop at 0x8001b02e |
| vCPU busy after an NV2A wake | `[rr425w]` keys `33.*` busy | guest work readied by a PGRAPH/PCRTC interrupt |
| PFIFO thread CPU | `[rdc]` `tcpu / dt` x period, `tid` constant | the thread that parses methods and records draws (rdc_tick runs on the non-vCPU thread that resets TLB dirty ranges) |
| PFIFO parked for the guest | `Ri` (EMA, ms/frame) | `renderer_idle_acc_ns`: parked with no `fifo_kick` |
| PFIFO backlog | `fifoskew` `drain` (p50 51.25 = overflow bin, > 51.2 ms) | how long a guest submission sits before PFIFO reaches DMA_PUT |

What each outcome looks like, before reading:

- **vCPU-bound** (the Mission: Impossible shape in fpsbelow1012): vCPU busy per frame close to the period
  (idle share under ~20%), PFIFO parked (`Ri`) a large part of the frame, small backlog.
- **PFIFO CPU-bound** (the NFS race-start shape in reportasync1010): PFIFO thread CPU per frame close to the period,
  `Ri` near 0, the backlog large, the vCPU idle waiting on it.
- **GPU or wait-bound**: the vCPU AND the PFIFO thread both well under the period, `Ri` well under the
  remainder, a standing backlog: the PFIFO thread is off-CPU and not parked, which leaves GPU fence waits,
  flip/vblank stalls and lock waits. The logcat cannot split those three; that needs `HAKUX_FRAMETRACE`
  on the save state.

The fast windows of the same session (59 fps menus and the cutscene's first 12 s at 28-44 fps) are the comparison,
not another title.

## #986 result: the frame waits on three 16-bit render-to-texture downloads

### The split from the owner run (`winsplit.py`, plain build)

Per 60-flip window. "Off-CPU, not parked" = period - PFIFO thread CPU - `Ri`. The 22:34:37 window (1 fps,
a 120 ms period, `Ri` 551) is a one-off hitch and is left out.

| windows | fps | period ms | vCPU busy ms (share) | PFIFO CPU ms | `Ri` ms | off-CPU, not parked ms | `Tq` |
|---|---|---|---|---|---|---|---|
| 22:33:00-15, menu | 59-60 | 16.7 | 6.6-7.7 (0.39-0.46) | 0.8-0.9 | 14.8-15.2 | 0.5-1.0 | 2 |
| 22:33:28-40, cutscene opening | 28-44 | 23.9-34.2 | 23.9-34.2 (0.91-1.00) | 9.7-12.1 | 0.3-1.3 | 13.0-22.2 | 1095-1463 |
| 22:33:43-22:34:43, cutscene slow | 14-23 | 43.8-62.1 | 12.9-39.4 (0.22-0.90) | 11.5-16.8 | 4.4-14.4 | 21.3-31.3 | 907-2483 |

Against the outcomes written above:

- **Not vCPU-bound.** In the two slowest windows (22:34:11 and 22:34:15, 15 fps, 61-62 ms) the guest is outside its
  idle loop for 13.8-13.9 ms of the frame (share 0.22-0.23). The opening runs faster with the guest never idle.
  The busy share does not track frame time.
- **Not PFIFO CPU-bound.** The PFIFO thread is on CPU 11.5-16.8 ms of a 44-62 ms frame.
- **GPU or wait-bound**: 21-31 ms per frame with the PFIFO thread off CPU and not parked. The plain build cannot
  split that, so the perflog run below does.

### The wait, split (perflog run, `HAKUX_FRAMETRACE=1 HAKUX_GPUXFR=1`, same cutscene)

`dispatch/results/1-1791536100-fpstelemetry1008-943216` (10-09) shows the same signature: 19-22 fps, `Vpf` 3-4,
`Tq` 2200-2550. Per frame:

| window | fps | `Finish` per 60 frames | phase `Fin` ms (Sub/Fen) | GPU ms (render R / non-render X) | ft1 fence wait ms / count | PFIFO run ms | PFIFO blocked ms | p50 ms |
|---|---|---|---|---|---|---|---|---|
| gameplay 02:02:46-49 | 58 | 240 (sd 180, flip 60) | 8.3 (6.3/2.0) | 4.9 (4.6/0.3) | 5.8 / 3.0 | 10.9 | 6.5 | 17.2 |
| cutscene 02:00:55-58 | 30 | 240-243 (sd 180) | 10.9-15.9 | 7.4-12.2 (~7/0.4-5.2) | 9.2-13.3 / 3 | 15.4 | 10-15 | 25-30 |
| cutscene 02:01:33-35 | 20 | 258 (sd 180, flip 60, stl 18) | 24.9 (22.7/2.2) | 21.7 (12.4/9.2) | 21.6 / 2.9 | 23.8 | 28.3 | 50.4 |

`cblat` over the 20-fps window (40 flips): `SET_BEGIN_END` handling 40.5 ms/frame, of which finishes take 24.8 ms.

**The mechanism, from `[txdl794]` and the code.**

1. MKSM draws three linear X1R5G5B5 surfaces (320x240, 320x120 and 160x120) and samples each one the same frame as
   `LU_IMAGE_X1R5G5B5` (`[txdl794] why=cvt`, same extent and pitch).
2. Since #59 (f009555537, 09-12), 5551 and 565 textures are expanded to RGBA8 by bit replication on the CPU. So
   `check_surface_to_texture_compatiblity()` refuses the pair (vk/texture.c:1493).
3. `create_texture()` then downloads the surface (vk/texture.c:2806): a SURFACE_DOWN finish that submits and waits on
   the fence for all GPU work recorded so far. The surface is then decoded on the CPU and uploaded.
4. That is 180 `sd` finishes per 60 frames: 3 a frame in every window, fast or slow. The fence waits counted by ft1
   (2.9-3.0 a frame) match them. The flip adds none.

So the PFIFO thread's CPU work and the GPU's work run one after the other, and the frame is close to their sum:

- In gameplay both are small (PFIFO run 10.9 ms + GPU 4.9 ms; p50 17.2 ms).
- In the slow cutscene both roughly double. GPU rendering goes from 4.6 to 12.4 ms. Non-render GPU time goes from
  0.3 to 9.2 ms. PFIFO run goes from 10.9 to 23.8 ms, with draw recording at 14.1 ms of it.
- The sum of PFIFO run and GPU is ~45 ms of the 50 ms frame.

**Cause (#986): serialization.** Three surface-download finishes a frame make the PFIFO thread wait for the GPU, so
the GPU and the PFIFO thread never overlap. The frame is not limited by the guest vCPU, the report wait or vblank.
v3 dominates the slow windows because a 50 ms frame spans three vblanks, not because a vblank is being waited on.

Not attributed: the slow window's non-render GPU time.

- The phase line's `X` is 9.2 ms a frame. That is the command buffer's GPU span minus its render passes.
- xfr's own non-render figure is 2.16 ms a frame, and 2.11 of that is residual not tied to a timed transfer
  (download 0.04, tex_up 0.01).
- The two instruments disagree by ~7 ms, and neither names what that time is.

### The lever and its bound

Copy the 16-bit surface into the texture's RGBA8 image on the GPU, converting as it goes:

- Read the surface texel and recover the 5- or 6-bit integer.
- Write `(v << 3) | (v >> 2)` (or `(v << 2) | (v >> 4)` for 6 bits) over 255, which is #59's replication exactly.
  The GPU's own UNORM conversion is not: 4 of 32 five-bit values and 10 of 64 six-bit values differ by one step.
- Write alpha = 1 for X1R5G5B5 and R5G6B5, and the stored bit for A1R5G5B5.
- Record the copy inline, as `copy_surface_to_texture()` already does for the formats it accepts: no finish, no
  download, no CPU decode.

Bound, not a value: with the three finishes gone, the 20-fps window loses up to 21.6 ms of fence wait a frame. Its
floor becomes max(PFIFO run, GPU, guest) rather than the sum, so 50.4 - 21.6 = ~29 ms (~34 fps) if nothing else
waits in their place. Only the A/B gives the value.

### The same refusal in the other titles (`s2tscan.py` over the owner's frame dumps)

`s2tscan.py` counts textures that sample a surface drawn earlier in the same frame, and re-derives
`check_surface_to_texture_compatiblity()`'s refusal reason for each.

| title (issue) | source | refused render-to-texture reads a frame | surface -> texture |
|---|---|---|---|
| MKSM (#986) | perflog `[txdl794]`, `Finish sd` | 3 | X1R5G5B5 linear 320x240, 320x120, 160x120 -> `LU_IMAGE_X1R5G5B5` |
| Top Spin (#992) | lane.async794 perflog, 10-04 (`txdl[]`) | 27 | 64x128 swizzled 2 bpp -> `SZ_R5G6B5` |
| Prince of Persia fog room (#993) | `ownerplay-1014/pop-fog`, 30 frames | 9 (9 distinct surfaces) | R5G6B5 256x256 swizzled -> `SZ_R5G6B5` |
| Batman Begins (#995) | `batman-baseline`, `-room`, `-room2` | 1 in all three dumps | R5G6B5 512x512 swizzled -> `SZ_R5G6B5` |
| Halo 2 (#994) | `halo2-flicker` | 0 | (all 32-bit; 9 bound reads a frame) |

Every refusal in all five dumps is `cvt`, the #59 guard. No other reason appears. The 32-bit render-to-texture reads
in the same frames (PoP 24 a frame, Batman 8, Halo 2 9) are all bound on the GPU. #59's own design doc predicted this
cost (`docs/investigations/packed-texel-expansion.md`, "A 565 surface sampled as a texture ... is the expensive one")
and said no title had been counted. These are the first counts.

Batman takes its one download in the 29-fps baseline dump as well as in the slow rooms. The download alone does not
make a window slow. Its wait covers the previous frame's whole GPU work, so in the heavier scenes the GPU's frame
and the PFIFO thread's frame run one after the other (#995 result below).

vk/texture.c was withheld when this was written. lane.x1port1012 lent it (board 104fac8e98) and the switch is built:
see "`HAKUX_S2T_CVT`: built and checked" at the end of this file.

## #992 Top Spin: what the slow frames wait on (written before the read)

Two runs:

- The owner run `ownerplay/runs/4D530035-1014-1417-23868` (debug 0.5.0-1014-76bef8b162, plain build). It has the
  winsplit columns but no finish counts.
- lane.async794's perflog control `dispatch/results/1791135713-lane.async794-3678571` (master 5e4196fefd, 10-04,
  990 s of a live exhibition match). It carries `Finish`, the phase line, `txw[]` and `cblat`.

The brief's three candidates, and what each looks like:

- **GPU report wait** (the reportasync1010 shape): the `[sdrfin]`/report counters climb in the slow windows, and the
  PFIFO thread is parked or blocked on a query, not on a surface download.
- **Vblank**: the guest flips late against a vblank it is waiting for. The PFIFO thread is parked (`Ri` large), the
  guest is idle in its wait, and the frame quantizes to whole vblanks with no PFIFO or GPU work to fill it.
- **Submit queue / finishes**: the PFIFO thread is never parked (`Ri` ~0), `Finish` counts are high, phase `Fin`
  is a large share of the frame, and the frame time tracks the finish count across windows of one session.

The comparison is the same session's windows against each other. `dlrate.py` pairs each 60-frame `Finish` line with
the nearest `gfps` and phase lines, and fits frame time on downloads per frame.

- A hit: frame time rises with downloads per frame, with a slope near the per-download cost that `txw[]` measures
  (~0.4 ms).
- A miss: a flat slope, or slow windows at the play-time download count.

## #992 result, Top Spin: the same serialization as #986, nine times the downloads

### The split from the owner run (`winsplit.py`, plain build)

| windows | fps | period ms | vCPU busy ms (share) | PFIFO CPU ms | `Ri` ms | off-CPU, not parked ms | `Df` | `Tq` |
|---|---|---|---|---|---|---|---|---|
| 14:17:50-56, front end | 59 | 16.7 | 16.6-16.7 (1.00) | 0.9-1.1 | 12.7-13.9 | 1.8-3.1 | 0 | 1 |
| 14:18:21-50, menus | 59 | 16.7 | 16.4-16.7 (0.98-1.00) | 3.6-5.2 | 11.6-13.1 | -0.5-0.9 | 0-1 | 424-516 |
| 14:19:08-12, arena intro | 14 | 43.6-67.6 | 12.1-18.9 (0.28) | 12.9-19.3 | 0.1 | 30.6-48.2 | 92-115 | 894-933 |
| 14:19:27-14:21:00, match play (42 of 49 windows) | 26-37 | 26.7-37.8 | 9.7-11.6 (0.29-0.37) | 9.3-12.8 | 0.1 | 17.2-24.9 | 85-120 | 701-814 |

The match-play row leaves out seven windows:
- 14:19:27, 14:20:33 and 14:20:37: guest busy 13.8-15.4 ms (0.43-0.47).
- 14:20:35: guest busy 24.4 ms (0.71), `Ri` 13.7.
- 14:19:44, 14:19:46 and 14:21:00: `Ri` 3.0-6.8.

In the other match-play windows the PFIFO thread is never parked, and the guest is idle 63-71% of the frame. The
PFIFO thread is off CPU, not parked, for 17-25 ms of a 27-38 ms frame. That is the "submit queue / finishes"
outcome. Off-CPU in the negative rows is an artefact: the PFIFO thread's 100 us spin before a park counts in both its
CPU and `Ri`.

The 59-fps rows show the guest busy 98-100% while the PFIFO thread is parked 12-14 ms a frame and every flip lands
on one vblank. A guest with work to fill exactly 16.7 ms for minutes at a time is not plausible: the title waits for
the vblank by polling, not in the kernel idle loop. So a busy share near 1.00 does not by itself mean vCPU-bound for
this title.

### The wait, split (lane.async794's perflog control, same title, live match)

| windows | fps | `sd` finishes a frame | phase `Fin` ms (Sub) | `txw` download ms (count) a frame | GPU ms | `G` ms |
|---|---|---|---|---|---|---|
| match play | 31-39 | 24-32 | 11.3-15.0 (10.3-13.8) | 12.1-14.2 (29-35) | 9.8-10.9 | 25.8-31.5 |
| 18-fps scene, `Tq` 933 (the owner's arena intro has the same `Tq`) | 18 | 58.7 | 27.7-29.0 | (67-80) | 17.0 | 52.8-53.9 |

Of the session's 1628 finishes counted, 1568 are `sd` (surface download) and the rest are the flip. There are no
report finishes.

**Dose-response across the session (`dlrate.py`).** Each 60-frame `Finish` line is paired with its `gfps` and phase
lines, and frame time is fitted on downloads per frame:

| fit | slope ms per download a frame | intercept ms | r | windows |
|---|---|---|---|---|
| all rendering windows (gfps >= 5), `G` | 0.477 | 16.8 | 0.77 | 763 (0-60.1 a frame) |
| same, `Fin` | 0.478 | 0.3 | 0.96 | 763 |
| windows with downloads (>= 2.6 a frame), `G` | 0.661 | 11.6 | 0.68 | 489 |
| same, `Fin` | 0.451 | 1.1 | 0.81 | 489 |

Frame time rises with downloads at 0.48-0.66 ms per download a frame, which is at or above the 0.45-0.48 ms each one
spends in `Fin` itself (the `txw` cost was ~0.4 ms). Where `G`'s slope is above `Fin`'s, that fits serialization: a
finish also stops the GPU and the PFIFO thread from overlapping, beyond its own wait.

**Against the three candidates:**

- **GPU report wait: no.** No report finishes, and the PFIFO thread waits on surface downloads.
- **Vblank: no.** `Ri` is 0.1 ms in play, and the guest is idle two thirds of the frame. v2/v3 flips are 30-50 ms
  frames spanning whole vblanks, not a vblank being waited for.
- **Submit queue / finishes: yes.** It is the #986 mechanism. 24-32 downloads of 64x128 swizzled R5G6B5 render
  targets a frame (`cvt`, `s2tscan.py` row above) each submit and wait on the fence. The arena intro's 59 a frame
  takes the frame to 53 ms.

**Cause (#992, Top Spin): serialization on 16-bit render-to-texture downloads.** It is the same cause as #986, so
it is one lever, `HAKUX_S2T_CVT` (built; see the end of this file).

**Bound, not a value.** The most the lever can take from a match-play frame is its finish time, 11.3-15.0 ms of a
25.8-31.5 ms frame. In the 18-fps scene it is 27.7-29.0 ms of 53 ms. The fits' intercepts (11.6-16.8 ms at no
downloads) are extrapolations, not floors. Only the A/B gives the value.

**"Slow motion".** In match play 0-25 of each 60 flips land on one vblank (v1 = 60 - v2 - v3 - v4). So the title
presents when a frame is ready and targets 60. A game that steps its simulation once a frame then runs at its frame
rate over 60: 0.4-0.6x at 23-37 fps. This is an inference from the pace line. The owner's report fits it, but nothing
here measures the simulation step.

## #992 result, Brian Lara (434D004E): a different shape, unexplained

Logcat `/mnt/d/hakux-staging/ownerplay-1015/logcat-434D004E-ownerplay-raw.txt` (plain build, 08:06-08:08 of the
owner's session). The slow windows come with the ball in play.

| windows | fps | period ms | vCPU busy share | PFIFO CPU ms | `Ri` ms | off-CPU, not parked ms | `Df` | `Tq` | NOP callbacks a frame |
|---|---|---|---|---|---|---|---|---|---|
| 08:06:11-16, 08:07:24-27, slow | 27-35 | 26.9-35.2 | 0.93-0.98 | 12.0-14.7 | 4.5-5.7 | 9.5-15.2 | 93-124 | 467-603 | 479-554 |
| 08:06:43-45, slow | 37 | 26.5-27.5 | 0.98 | 11.8-12.3 | 4.4-4.7 | 10.3-10.5 | 95-99 | 502 | 427 |
| 08:06:22-28, 08:07:16-22, fast A | 52-60 | 16.6-17.5 | 0.98-0.99 | 7.9-8.0 | 2.6-2.9 | 5.9-6.9 | 59-63 | 370-392 | 253-277 |
| 08:06:55-58, 08:07:08-14, fast B | 59 | 16.7 | 0.98-1.00 | 3.6-4.3 | 12.9-13.5 | ~0 | 0 | 177-328 | 42-104 |

"NOP callbacks a frame" comes from `irqrate.py`. It counts `[rr425w]` wakes and busy-time interrupts on key
`33.44`: the NV2A vector with PGRAPH's ERROR bit pending. That is the interrupt `NV097_NO_OPERATION` with a nonzero
parameter raises (pgraph.c:2567), the guest's push-buffer callback.

- **14,500-16,000 callbacks a second, whatever the frame rate.** 29-32 thousand per 2 s window in every slow and
  fast-A window, so ~250 a frame at 60 fps and ~500 at 30. lane.flip474 measured 1.7 a frame for Agent Under Fire and
  14 for Blinx. Each one parks the PFIFO thread until the guest acknowledges it. `Ri` per callback is 9-10.5 us in
  both slow and fast-A windows, so `Ri` here is almost all callback round trips, not the vblank.
- **Not vblank.** The guest is idle 2-7% of the frame, and `Ri` is accounted for by the callbacks.
- **Report wait: not measurable from this log.** The plain build carries no `Finish` counts or report counters.
- **Submit queue: not decided.** The PFIFO thread is active (CPU plus off-CPU, not parked) for 84% of the frame in
  both the slow and fast-A windows: 29.5 of 35.2 ms and 14.1 of 16.7 ms. Per second, the slow windows look like
  fast-A. Per frame, everything doubles: CPU, off-CPU time, callbacks, and 1.5x `Tq` (texture polls a frame). So the
  slow frame carries more work, but this log cannot say which side sets the frame.
- **The guest's busy share is not readable as CPU-bound.** Fast B has the guest busy 98-100% while the PFIFO thread
  is parked 13 ms a frame and every flip lands on one vblank. That is the same polling-wait signature as Top Spin's
  menus.
- Off-CPU time tracks the callback count: 20-30 us per callback in the slow and fast-A rows. That is a correlation,
  not a split. Each callback takes the BQL on the PFIFO thread (pgraph.c:2571), which could account for it. So could
  the downloads, if Brian Lara has them, and with no frame dump, its `cvt` count is unknown.

**Brian Lara is unexplained.** Ruled out: the vblank. Not measured: finishes and report waits. Next step, one
perflog run of a ball in play, about 6 minutes of Nova time, which carries three instruments:

1. `cblat` gives the callback params (which callback this is) and the kick-to-dispatch split (`mdraw`, `pnop`,
   `dl`, `fin`).
2. `Finish sd` counts per frame; a hit for the Top Spin class looks like 20+ a frame tracking `G`.
3. A frame dump for `s2tscan.py`.

A hit for the callback class is `pnop` plus BQL wait above ~25% of the frame, with `sd` under 5 a frame.

## #995 Batman Begins: what the slow windows are bound by (written before the read)

Runs:

- The owner run `ownerplay/runs/45410389-1014-2139-27899` (debug 0.5.0-1014-76bef8b162, plain build, 21:39-21:51).
  It has 372 `gfps` windows. Most run at 29 fps with every flip on two vblanks, so the title caps itself at 30. The
  slow windows run at 14-23 fps.
- The reload run `-2152-3129` (21:52-21:54, 29 fps throughout). It is the same-title comparison.

What the frame dumps carry: per-draw state, blend, surfaces and vertex ranges (`vr`). They carry no vertex data
(`vtx: 0`) and no timing (`per_draw_finish: false`). So blended pixel area cannot be computed from them, and neither
can GPU time per draw.

The first step is the plain-build split, as for #986. What each outcome looks like:

- **vCPU-bound**: the guest busy share rises toward 1.00 in the slow windows from a lower share in the 29-fps windows,
  and the PFIFO thread is parked (`Ri` > 0) waiting for it. This rules out fill without a GPU instrument.
- **PFIFO CPU-bound**: PFIFO thread CPU close to the period, `Ri` near 0.
- **GPU or wait-bound**: PFIFO thread off CPU and not parked for most of the frame, `Ri` near 0, the guest idle part
  of the frame. Fill is one candidate here. The others are finishes and fence waits. Batman has 1 `cvt` download a
  frame in all three dumps, the 29-fps baseline included, so downloads alone would not make the slow windows slow.

The dumps then test whether draw count or blended work is what grows. Blended pixel area is not in the dump. The
proxies that are:

- blended draws a frame and their primitive counts;
- the blend state (`rs.blend`);
- the colour target size.

A per-pass GPU split needs `HAKUX_GPUXFR=1` on a device run (per-render-pass GPU time, vk/draw.c:4211), and per-draw
GPU time has no instrument.

## #995 result: the scene's GPU work outgrows what the 30-fps cap hides, and one download a frame stops it overlapping

### The split from the owner run (`winsplit.py`, plain build)

| windows | fps | period ms | vCPU busy ms (share) | PFIFO CPU ms | `Ri` ms | off-CPU, not parked ms | `Df` | `Tq` |
|---|---|---|---|---|---|---|---|---|
| reload run 21:52:38-21:54:04 (`batman-baseline` dump at 21:52:34) | 29 | 33.3-33.4 | 19.2-25.3 (0.58-0.76) | 11.7-12.0 | 19.5-20.5 | 1.0-2.0 | 0 | 850 |
| 21:42:39-21:43:09, smoke room (`batman-room` dump at 21:43:13) | 26-27 | 37.0-41.2 | 14.3-17.8 (0.37-0.43) | 13.1-14.2 | 4.1-7.0 | 17.5-21.1 | 50-56 | 1124-1188 |
| 21:50:14-35, fire room (`batman-room2` dump at 21:50:21; its window left out) | 26-29 | 33.7-40.1 | 15.4-31.7 (0.43-0.94) | 13.1-16.8 | 5.9-16.8 | 3.5-18.4 | 5-61 | 973-1403 |
| 24 of the 30 windows under 24 fps | 14-23 | 35.6-65.6 | 14.0-29.2 (0.37-0.64) | 13.6-22.1 | 0.2-13.1 | 11.1-37.8 | 13-79 | 1074-2100 |

The last row includes the two windows that hold a dump (21:43:14 and 21:50:22). There the dump's own work puts
PFIFO CPU at 20.7-22.1 ms and `Ri` at 0.2-0.3. It leaves out six windows with shader or pipeline-cache work:

- 21:39:16, 21:39:23, 21:44:26 and 21:45:36 compile shaders (`[shd413]` `dpc_ms` 74-206 in the window).
- 21:47:07 and 21:47:46 load 10-14 shaders from the cache (0.3-0.4 ms) next to a 217-221 ms `[plc569]` save.

Against the outcomes written above:

- **Not vCPU-bound.** The guest is outside its idle loop for 37-64% of a slow frame, less than in the 29-fps
  reload windows (58-76%).
- **Not PFIFO CPU-bound.** The PFIFO thread is on CPU for 13.6-22.1 ms of a 36-66 ms frame. In the smoke room it
  is 13.1-14.2 ms, against 11.7-12.0 at baseline.
- **GPU or wait-bound.** Off CPU and not parked goes from 1.0-2.0 ms a frame at baseline to 17.5-21.1 ms in the
  smoke room, and to 11.1-37.8 ms across the slow windows. `Ri` falls from ~20 ms to 4-7.

### What the PFIFO thread waits on (the dumps and the code)

All three dumps have exactly two submits a frame ("submits frame-to-frame" 2.0 in `dumpstat.py`, min 2, max 2): the
flip and the one `cvt` download. No other finish runs in any of the three scenes. The two finishes differ:

- The flip's finish (`VK_FINISH_REASON_FLIP_STALL`) is deferred. It submits, signals the stall-chain semaphore and
  returns (vk/draw.c:5534-5538, 5627-5643).
- The download's finish (`SURFACE_DOWN`) is not deferred. Its submission waits on that semaphore, and the PFIFO
  thread waits for the fence (vk/draw.c:5652-5686).

So the download waits for everything submitted before it, the whole of frame N-1 included, wherever in frame N it
falls. In all three dumps it falls early. The 512x512 R5G6B5 target is drawn at draw 33 and read at draw 41
(baseline), 53-56 (fire room) or 75 (smoke room), of 687-1005 draws.

Inferred from the code, not measured: per frame, the GPU renders frame N-1 while the PFIFO thread is parked or
records frame N's first 41-75 draws. The PFIFO thread then waits for the GPU to finish. It records the rest of
frame N while the GPU has nothing queued. Past the download, the two frames do not overlap.

- **At baseline this costs nothing visible.** `Ri` is 20 ms a frame, the GPU finishes frame N-1 inside it, and
  the download's wait shows as 1-2 ms of off-CPU time.
- **In the slow scenes `Ri` falls to 4-7 ms.** The off-CPU, not-parked time is 17.5-21.1 ms in the smoke room.
  The MKSM perflog run measured that time as the fence wait (#986: ft1 fence wait = the off-CPU share). If it is
  the same here, the GPU still had at least that much work left when the download came. The frame is then PFIFO
  CPU plus the GPU's remainder, not the larger of the two.

How much of Batman's off-CPU time is the fence wait has not been measured. The plain build carries no fence counter.

### Draw count against blended work (`dumpstat.py`)

| dump (scene, fps) | draws | vertices | blended draws (inline_array) | blended vertices | alpha (sa, 1-sa) | additive (sa, 1) | off-CPU, not parked ms |
|---|---|---|---|---|---|---|---|
| baseline (29) | 687 | 131.8k | 405 (155) | 37.8k | 149 | 183 | 1.0-2.0 |
| fire room (26-29) | 846 | 144.9k | 432 (219) | 31.6k | 202 | 156 | 3.5-18.4 |
| smoke room (26-27) | 1003 | 158.2k | 662 (311) | 61.1k | 398 | 185 | 17.5-21.1 |

Every blended draw class is a triangle strip, except 44 `1+1` quads a frame in all three dumps. Of the blended draws,
354-611 a frame go to the two alternating 640x480 colour targets, and 36 to a 160x120 to 20x15 chain.

- **Smoke room**: 257 more blended draws than baseline, almost all alpha-blended strips (+249). It waits 15.5-20.1 ms
  more a frame.
- **Fire room**: 27 more blended draws and fewer blended vertices than baseline. It waits 1.5-17.4 ms more.

If the off-CPU time is GPU time, the GPU's cost does not follow blended draw count or vertex count across the three
scenes. For the fire room that leaves per-pixel work (fill, overdraw, fragment cost) as the candidate. This is weak
evidence, for three reasons:

- The off-CPU time is not GPU time. At baseline the GPU's frame hides under `Ri`, so its size is unknown.
- The fire room's windows vary 3.5-18.4 ms.
- The dumps carry no positions (`vtx` 0), so blended pixel area is not computed.

### Cause, lever and next step (#995)

**#995 is partly explained.**

Measured:
- The slow windows are not vCPU-bound or PFIFO CPU-bound.
- The PFIFO thread is off CPU and not parked for 11-38 ms a frame.
- The frame's only fence wait is the one `cvt` download, and from the code that wait covers the previous frame's
  GPU work.

Not measured:
- what share of the off-CPU time is that wait;
- what grows the GPU's frame (blended pixel area or draw count).

**The lever is `HAKUX_S2T_CVT`**, WAITING on vk/texture.c (see the #986 section). It removes Batman's only per-frame
fence wait, so the GPU's frame can overlap the PFIFO thread's.

Bound, not a value:
- The title caps itself at 30 fps, so the most the lever can do for a slow window is bring its period down to
  33.4 ms. A window gets there only if its GPU frame and its PFIFO frame each fit in 33.4 ms.
- Where the off-CPU time is the fence wait, the GPU frame is at least that long. In 21:43:45 (65.6 ms, off-CPU 37.8)
  that is ~38 ms, above the cap.

**Next step: one perflog run in the smoke room**, about 6 minutes of Nova time, with:

- `HAKUX_FRAMETRACE=1 HAKUX_GPUXFR=1`;
- a frame dump with `XEMU_FRAME_DUMP` spec `30 noimages vtx256`, plus `afterNN` to reach the scene. `vtx256`
  covers every particle strip; `images` would add a fence wait a frame.

What each result looks like:

- **Serialization, a hit**: about one ft1 fence wait a frame, close to the off-CPU time (17-21 ms), with the GPU's
  ms a frame (GPUXFR R + X) at or above it.
- **Fill, a hit**: GPU ms a frame tracks blended pixel area (covered pixels x layers, recomputed from the `vtx256`
  dump) across the smoke room, the fire room and a 29-fps scene, not draw count. The 640x480 pass in GPUXFR's
  census carries the growth.
- **A miss for both**: a fence wait well under the off-CPU time, which leaves lock waits or preemption. The
  next instrument there is the `probe1010` split (`nd`/`rot`, vk/draw.c:2750).

## #993 Prince of Persia: the fog room (written before the read)

Run `ownerplay/runs/5553001D-1014-2057-14415` (debug 0.5.0-1014-76bef8b162, plain build, 20:57-21:17). There is
one frame dump, `ownerplay-1014/pop-fog`, taken in the fog room at about 21:16:37 (30 frames). There is no dump of a
30-fps room. `s2tscan.py` counts 9 refused render-to-texture reads a frame in the fog room, all R5G6B5 256x256
swizzled, refused as `cvt`.

Step 1, the plain-build split (`winsplit.py`): the fog-room windows against the same session's 29-fps windows.

- **#986 class (serialization on downloads).** A hit: the PFIFO thread off CPU and not parked for most of the
  frame, `Ri` near 0, the guest idle part of the frame. In the dump, ~10 submits a frame (9 downloads plus the flip).
- **GPU-bound without serialization.** The off-CPU share is large, but the dump has few finishes a frame. The wait
  is then the flip's rotation fence or something outside the finishes.
- **Not GPU or wait (vCPU or PFIFO CPU).** The same outcomes as #986 and #995.

Step 2, the fog pass state from the dump (`dumpstat.py`, `scratch` position read), before any shader. For each
16-bit target:

- its size and format;
- the draws into it: count, blend, primitive, and whether depth is tested or written;
- where its read falls in the frame.

A full-screen fog layer on the 640x480 target shows as a few large blended quads or strips. A render-to-texture
fog shows as draws into the 256x256 targets, then a read of each one.

## #993 result: the fog room's frame is ~1-3 ms over two vblanks, and its nine shadow maps each force a download

### The split from the owner run (`winsplit.py`, plain build)

"PFIFO thread busy" = period - `Ri`: the PFIFO thread's CPU plus its off-CPU, not-parked time a frame.

| windows | fps | period ms | vCPU busy ms (share) | PFIFO CPU ms | `Ri` ms | off-CPU, not parked ms | PFIFO thread busy ms | `Df` | `Tq` |
|---|---|---|---|---|---|---|---|---|---|
| 21:08:00-21:10:04, light rooms (59 windows; 21:08:49 at 52.0 ms and 21:09:44 at 73.2 ms left out) | 27-29 | 32.9-34.1 | 11.6-18.7 (0.3-0.6) | 5.8-12.6 | 0.8-22.8 | 2.7-20.7 | 10.3-33.3 (median 14.3) | 0-100 | 345-1179 |
| 21:13:19-21:15:23, the heaviest 29-fps stretch (59 windows; 21:14:58 at 89.3 ms left out) | 26-29 | 33.4-38.3 | 16.7-19.0 (0.4-0.6) | 11.4-12.8 | 3.1-7.3 | 15.1-22.9 | 26.9-34.5 (median 30.0) | 44-60 | 869-874 |
| 21:15:57-21:17:19, fog room (27 windows; dump window 21:16:40 left out) | 19-21 | 48.1-50.1 | 20.2-23.7 (0.40-0.47) | 16.4-18.1 | 13.5-16.7 | 16.1-19.6 | 33.3-36.4 (median 34.7) | 6-26 | 1153-1262 |

In the fog room 53-60 of every window's 60 flips land on three vblanks (`v3`; 60 in 21 of 27 windows). The title presents every
second vblank elsewhere (`v2` = 60 at 29 fps), so a frame that misses the second vblank waits for the third.

A FLIP_STALL that is waiting for the vblank parks the PFIFO thread (the puller stalls on `waiting_for_flip`, pfifo.c:1940,
and the thread parks, pfifo.c:2475), so that wait is in `Ri`, not in the busy time. The busy time is what the PFIFO
thread has to do between two flips, and over all 510 rendering windows of the session it decides the frame rate:

| PFIFO thread busy a frame | windows | period median ms | windows at >= 40 ms |
|---|---|---|---|
| under 26 ms | 373 | 33.4 | 1 |
| 26-32 ms | 88 | 33.9 | 7 |
| 32-34 ms | 17 | 49.9 | 12 |
| 34-38 ms | 29 | 50.0 | 27 |
| 38 ms and over | 3 | 73.2 | 3 (stall windows) |

Below 32 ms busy, 453 of 461 windows run at 29 fps; from 32 to 38 ms, 39 of 46 run at 19-20. The 412
29-fps windows (period under 34 ms) peak at 32.6 ms busy (p95 29.9).

- **Not vCPU-bound.** The guest is outside its idle loop for 40-47% of the fog-room frame.
- **Not the GPU's throughput alone, and not the vblank.** The frame is 50 ms because the PFIFO thread's 33-36 ms
  of work misses a 33.4 ms budget by 0-3 ms, and the title's two-vblank present interval rounds it up to three. `Ri`
  (13.5-16.7 ms) is the wait for that third vblank.
- The busy time splits into PFIFO CPU 16.4-18.1 ms and off-CPU, not parked 16.1-19.6 ms. In MKSM's perflog run,
  the off-CPU time was the fence wait of the surface downloads.

### What the fog-room frame carries (`dumpstat.py`, `s2tscan.py`, the dump's draw sequence)

The dump `ownerplay-1014/pop-fog` (30 frames, 884-900 draws, 246k vertices, 415-423 blended draws a frame) has
**12 submits a frame**: nine at the first read of each shadow map (`cvt` downloads), two at draw 876 and one
between frames.

The nine downloads are projected shadows, one per shadow caster in the room:

1. Draws 450-487 render each caster twice: into the 640x480 colour target with depth test and write, then the same
   index count into its own 256x256 R5G6B5 surface (depth off, no blend, no texture). There are nine
   surfaces (0x37e0000-0x38e0000); 0x38e0000 is also drawn at 129-131 and 418-449.
2. Draws 488-523 then multiply each surface onto the scene (`0 + (1 - src colour)`, depth test, no depth write),
   sampled as `SZ_R5G6B5`.
3. Each surface is refused as `cvt` at its first read, and the download submits and waits on the fence. The first of
   the nine waits for everything submitted before it: frame N-1 and frame N's first 488 draws. Each of the next eight
   waits for the 1-7 draws since the previous one, and adds its own readback, CPU decode and upload.

The rest of the frame is 195 multiply-blended draws a frame (`0 + src colour`), 126 alpha-blended
(`sa + 1 - sa`) and 37 `0 + (1 - src colour)` (36 of them the shadow reads), on three 640x480 targets the frames rotate through. No fog pass draws into
a 16-bit target. With no dump of a 29-fps room, the draw count and the blended work cannot be compared across
rooms.

### Cause, lever and next step (#993)

**#993 is reduced to a bound, not explained.**

Measured:
- The fog room is a 33-36 ms PFIFO-thread frame (median 34.7) against a 33.4 ms two-vblank budget. That is not a
  19-fps workload: it is a 30-fps one that misses by 0-3 ms and pays a whole vblank.
- The frame carries nine downloads, each a fence wait, at draws 488-521 of ~890.

Not measured: what the nine downloads cost on PoP. Top Spin's fit gives 0.45-0.48 ms of `Fin` per 64x128 download;
PoP's surfaces have eight times the texels. That is an inference from another title, not a PoP measurement.

**The lever is `HAKUX_S2T_CVT`** (built; see the end of this file). It needs to take 1-4 ms from the PFIFO
thread's frame to put the fog room's busy time under the 32 ms that every 29-fps window of the session stays below.
If it does, the fog room runs at the title's 30-fps cap, 19 -> 29 fps. A bound: only the A/B gives the value.

Next step, before or beside the lever's PoP A/B: one perflog run in the fog room (`HAKUX_FRAMETRACE=1 HAKUX_GPUXFR=1`, about
6 minutes of Nova time). A hit for the downloads: `Finish sd` 9 a frame, phase `Fin` at or above the 1-4 ms the
budget needs.

## #994 Halo 2: what each stall is (written before the read)

Scope: the multi-second stalls and the fps-to-0 only. The title-screen flicker is #939 (lane.x1port1012).
Data: the owner's two plain-build runs, `ownerplay/runs/4D530064-1014-2118-21342` (21:18-21:21, past the title
screen) and `4D530064-1014-2129-25179` (21:29-21:30, title screen only). The tracker row says the 5.2 s and 3.9 s
stalls of the first run coincide with bursts of pipeline-library compiles. That is a coincidence in time, not a
cause yet.

Instrument: `winsplit.py` over each run, then every window with gfps under 10 or a period over 100 ms, read
against the log lines inside it. For each stall:

- **A shader or pipeline compile stall looks like:** `[shd413]`/`[plc569]`/`[gpl569]` compile lines inside the window
  whose summed compile time is a large part of the stall, on the thread that records draws (the PFIFO thread is on
  CPU, `Ri` near 0). The vCPU then idles or spins on a fence (busy share low, or a busy-wait at 1.0 with no flips).
- **A submit-queue stall looks like:** `Tq` or the drain time climbing through the window, with the PFIFO thread off
  CPU, not parked, and no compile lines.
- **A storage stall looks like:** `[ide425]` read lines with long latencies in the window, vCPU idle, PFIFO parked
  (`Ri` near the period).
- **A vCPU stall looks like:** busy share near 1.0 with the PFIFO thread parked and no compile, IDE or queue lines.
- **An audio-side stall looks like:** APU or audio-thread lines (zero-fill, underrun) that rise in the window while
  the graphics columns stay normal. Audio dropouts alone do not stop frames.

A miss is a stall in which none of these rises. Its window is then reported with every column, and the next step
is a device run with the instrument that column lacks.

## #994 result: every multi-second stall is pipeline compiles on the thread that records draws

Instrument: `stallscan.py` (this directory), which reads the window of every `hakuX-pace` line whose `max=` (longest
frame) is 200 ms or more. `[gpl569]` and `[uber569]` print running totals, so the script takes deltas; `[shd413]`'s
`d*` fields are already per window. "PFIFO CPU" is `winsplit.py`'s per-frame PFIFO thread CPU times 60 flips.

Run 1 (`4D530064-1014-2118-21342`, past the title screen), every window with a frame of 400 ms or more:

| window end | window s | longest frame ms | gfps | inline pipeline misses (`dpm`) | create ms on the draw thread (`dpc_ms`) | fragment-stage libraries (new / ms) | cold monolithic creates (`ub_cold`) | GLSL -> module ms | uber library ms (worker) | PFIFO CPU s | longest IDE op ms | audio zero-fill |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 21:18:38 | 5.2 | 3535 | 29 | 12 | 6 | 14 / 6 (all four kinds) | 1 | 439 | 0 | n/a | 6 | 17.5% |
| 21:19:02 | 8.0 | **5240** | 3 | 48 | 5139 | 22 / 1248 | 14 | 446 | 3382 | 5.4 | 8 | 0.7% |
| 21:19:47 | 3.3 | 1086 | 47 | 11 | 1500 | 7 / 744 | 2 | 129 | 0 | 2.0 | 9 | 0.0% |
| 21:20:40 | 8.0 | **3910** | 1 | 54 | 6157 | 26 / 2250 | 11 | 644 | 4082 | 6.7 | 5 | 0.0% |
| 21:20:43 | 3.5 | 627 | 28 | 9 | 805 | 8 / 805 | 0 | 82 | 4128 | 1.3 | 8 | 0.0% |
| 21:21:01 | 3.1 | 582 | 37 | 15 | 804 | 8 / 804 | 0 | 102 | 0 | 1.3 | 6 | 0.0% |
| 21:21:10 | 2.6 | 466 | 29 | 9 | 599 | 7 / 599 | 0 | 92 | 0 | 1.1 | 166 | 0.0% |
| 21:21:18 | 8.5 | **2088** | 12 | 67 | 4124 | 23 / 2494 | 5 | 587 | 4442 | 5.8 | 7 | 0.9% |
| 21:21:22 | 4.2 | 1121 | 31 | 26 | 918 | 5 / 611 | 1 | 116 | 4640 | 1.8 | 5 | 0.9% |

Against the outcomes written above:

- **Shader and pipeline compile: a hit in every in-game stall.** In the three fps-to-0 windows (5.2, 3.9 and 2.1 s
  frames), 4.1-6.2 s of the window is spent inside pipeline creates on the draw thread. The PFIFO thread is on CPU
  for 5.4-6.7 s of the same window, and the driver's cache hit none of them (`dfbh` 0). The 1.1-s and 0.4-0.6-s
  frames have the same signature at 0.6-1.5 s of creates.
- **Storage: no.** The longest single IDE operation in any stall window is 5-9 ms (166 ms once, in a 466-ms window).
- **Submit queue: no.** `Tq` falls in the two longest stalls (340 at 21:20:40, 2184 at 21:19:02), because the draw
  thread is compiling, not submitting.
- **vCPU: no**, except the first window of each run (21:18:38, 3.5 s; 21:29:22, 3.4 s in run 2). That window is the
  title's boot: there are no creates, the guest is busy (share 0.98) and no flip comes for 3.4-3.5 s. It is a boot load,
  not an in-game stall.
- **Audio: no.** Zero-fill is 0-0.9% in the stall windows. The 17.5% is the boot window.
- Small ones: the 301-ms and 203-ms frames (21:19:34, 21:21:07) coincide with pipeline-cache saves of 353 and 301 ms
  (`[plc569]`). They do not reach the fps-to-0 threshold.

Run 2 (`4D530064-1014-2129-25179`, title screen only) has no in-game stall: its boot window (3.4 s) and one 431-ms
frame, in which 90 creates took 349 ms.

### What is compiled, and why on the draw thread (vk/compile_worker.c)

The build runs #569's mode 3 (`[gpl569] mode=3`): an ubershader pre-raster library, plus a specialized fragment
stage per state.

- **Cold misses.** When a draw's ubershader pre-raster library is not built yet, `pgraph_vk_gpl_uber_create_pipeline()`
  queues the library to the compile worker and creates a monolithic pipeline inline (compile_worker.c:1201-1209). The
  create time that is not fragment libraries is 3.9 s in the window of the 5.2-s frame (14 cold creates) and 3.9 s in
  the window of the 3.9-s frame (11), so 280-380 ms per cold create. That is an upper figure: other inline creates,
  such as clears, are in the same remainder. The worker meanwhile spends 3.4-4.6 s building each
  uber library. Every draw keyed to it until then is a cold monolithic create.
- **Fragment-stage libraries.** `gpl_get_lib()` creates a missing fragment-shader library on the draw thread
  (draw_path = true, compile_worker.c:448-491), at 57-122 ms each in these windows: 0.6-2.5 s per stall window. The
  vertex-input and fragment-output parts take under 1 ms in total.
- Turnip's per-stage feedback over the 5.2-s window: vertex 486 ms, geometry 1661 ms, fragment 2477 ms.

The window is the instrument's resolution. Which of a window's creates fall inside its longest frame is not
measured; the 5.2-s and 3.9-s frames hold at most the 5.1 and 6.2 s of creates of their windows.

**Cause (#994): explained.** Each fps-to-0 is first-time pipeline compilation on the draw thread. Most of it is cold
monolithic creates during the 3.4-4.6 s it takes the worker to build a new ubershader pre-raster library; the rest is
fragment-stage libraries created inline. Not storage, queue, vCPU or audio.

### Lever and next step (#994)

The lever is the #569 work, not a lane.fps1015 file (vk/compile_worker.c). Ranked by expected impact:

1. **No cold monolithic create while an uber library builds.** For example, wait on the queued library when it is
   already running, or draw with an already-built uber library of the same vertex shader. That removes up to 3.9 s
   of create time from each of the two longest stall windows; the uber library itself is off the draw thread already. It is bounded by
   the worker's 3.4-4.6 s per library: the draws keyed to it must still be drawn with something.
2. **A fragment ubershader.** It removes the 0.6-2.5 s of inline fragment-library compiles per window, and the small
   stalls (0.4-1.1 s) with them. It is the larger change.
3. A bigger prebuild list (`[pb569] records=545 jobs=9 unresolved=536` at start) helps a second session of the same
   build only. Run 2 already shows the driver cache making repeated content cheap.

Next step: hand this to the #569 owner. The measurement needed is already in the logs. A device run is needed only
for the A/B of whichever of 1-2 is built.

## `HAKUX_S2T_CVT`: built and checked

The shared lever of #986, #992, #993 and #995. Default off; off, it costs one `getenv` at first use.

With `HAKUX_S2T_CVT=1`, `check_surface_to_texture_compatiblity()` (vk/texture.c) accepts a 5551/565 texture over a
2-byte colour surface. `copy_surface_to_texture()` then calls `pgraph_vk_s2t_cvt_copy()` (vk/surface.c). That
function records three steps inline in the frame's command buffer:

1. Copy the surface image to a scratch buffer as 16-bit words.
2. Run a compute pass that writes one RGBA8 texel per word with #59's replication (`(v << 3) | (v >> 2)`,
   `(v << 2) | (v >> 4)`), and alpha by format: 1 for X1R5G5B5 and R5G6B5, the stored bit for A1R5G5B5.
3. Copy the buffer to the texture image.

There is no finish, no download and no CPU decode. The scratch buffer grows to the largest copy (at least 4 MB) and
is freed at shutdown. The first copy logs `[s2tcvt] first WxH fmt 0xNN` once per process; the switch logs
`[s2tcvt] on` when read.

Checked by reading and on the host (no device run yet):

- **Decode.** The compute pass matches the CPU rule on all 65536 words in all three formats (glslc, then a host
  comparison).
- **Formats.** The surface host formats keep the guest bit layout: X1R5G5B5 maps to `A1R5G5B5_UNORM_PACK16` with the
  pad alpha, R5G6B5 to `R5G6B5_UNORM_PACK16`. The copy reads the raw words, never the UNORM conversion. The textures
  are `R8G8B8A8_UNORM` (converted).
- **Pad alpha.** The override (texture.c ~2980) is computed from `surface_is_texture_source` whatever the
  compatibility check says, so it is the same in both paths.
- **Direct bind.** It is never taken for these formats. `surface_view_decodes_as_texture()` compares the surface's
  16-bit vk format with the texture's RGBA8 one, so the copy path is the only path.
- **HAKUX_TEXSCAN.** `texscan_shape_ok()` excludes converted formats, so the two switches do not meet.
- **Extent.** The texture image is scaled by the surface scale (texture.c ~3370), as the copy is. The Nova runs
  `surface_scale=1`.
- **Descriptors.** The pass uses the shared compute descriptor pool (4096 sets, reset at each finish), and its layout
  matches the shader's bindings.
- **Build.** NDK `-fsyntax-only` with the Android build's flags is clean on surface.c and texture.c.

What it costs when on: per refused texture, one 2-byte buffer copy, one compute dispatch over the texels and one
4-byte buffer copy, all on the GPU. The GPU time is not measured; the A/B's `GPU` column reports it.

### Which titles take the downloads (`cvtcensus.py`, 169 perflog results on disk)

`txdl cvt` counts the textures refused by #59's guard per 60-frame window, so 60 a window is 1 a frame.

| title | perflog runs | windows with `cvt` | `cvt` a window, median | max |
|---|---|---|---|---|
| Top Spin (#992) | 4 | 190-503 of 511-776 | 0 (three menu-heavy runs); 1350 (lane.async794, live match) | 2880-3675 |
| Fuzion Frenzy | 3 | 219-386 of 565-695 | 0-60 | 120-240 |
| MKSM (#986) | 1 | 574 of 659 | 180 | 180 |
| ToeJam & Earl III | 2 | 98-99 of 154-155 | 53-55 | 60 |
| surfgpu1009's golden suites (Clear, Color zeta overlap, Depth buffer fixed function, Image blit, ...) | 6 | 1-2 of 3-4 | 0-4 | 5-9 |
| NBA Live 07 | 8 | 7-11 of 217-231 | 0 | 1 |

PoP and Batman have no perflog run. Their counts come from the frame dumps (the #986 table above: 9 and 1 a frame).

## The A/B (written before any run)

Two legs on one build, the pushed head named in each prediction (`a_ref` = `b_ref`). The arms differ only by env:
A has none, B has `HAKUX_S2T_CVT=1`. The lane queues them, because the arms job skips `a_ref == b_ref`. The arm
with the shipped setting (A) goes last, because the device keeps a request's env until the next request.

### Pixel leg: `docs/testing/predictions/fps1015-pixels.json`

- **Suites.** texscan1010's 29 texture and surface suites, plus Clear, Color_zeta_overlap,
  Depth_buffer_fixed_function and Image_blit. Those four are surfgpu1009's, which take `cvt` downloads.
  `Texture_render_target::RenderTextureLoop` is skipped, as the arms job skips it.
- **Prediction.** Every capture is the same between the arms or inside the run-to-run band, and B's logcat has
  `[s2tcvt] on` and `[s2tcvt] first`.
- **A hit:** B equals A on every capture, with `[s2tcvt] first` in B.
- **A moved capture** refutes the bit-exact decode, or the pad-alpha reading. It blocks the switch until explained
  region by region.
- **No `[s2tcvt] first` in B:** the leg shows the switch inert where it does not fire, but it does not exercise the
  decode. MKSM's route frames are then the only pixels judged.

### Soak leg, #986: `docs/testing/predictions/fps1015-mksm.json`

- **Setup.** Route `docs/lanes/fps1015/routes/fps1015-mksm.route`: fps1008-shaolin's steps 1-28, then three attack
  passes. `--seconds 330 --perflog`. Judge: `s2tread.py` (this directory).
- **Order.** On, off first, as a pilot pair. On, off again once the pair passes the V leg.
- **Baseline.** `s2tread.py` reads the fps1008-shaolin perflog run (1-1791536100-fpstelemetry1008-943216, flag off)
  as an off run: 34 cutscene windows, `sd` 3.00 a frame, `cvt` 180 a window, median `G` 43.2 ms, 22.0 fps, phase
  `Fin` 18.5 ms, `GPU` 15.2 ms. Gameplay median 52.0 fps over 514 windows.

What a hit looks like in the on runs' cutscene windows:

- `sd` 0.1 a frame or less, `cvt` 0, and `s2tc` near 180 a window (R).
- Median `G` down 6-22 ms (P). Point -10: 43 to ~33 ms, the two-vblank frame. The bound written in the #986 section
  is ~29 ms if nothing else waits.
- Median gfps up by 5 or more (F). Point +8: 22 to ~30.
- Gameplay median gfps no more than 3 below off (N).

Readings of a miss:

- **R fails** (the downloads are still there with the switch on): the copy path was not taken for these surfaces.
  Read `[s2tcvt] first` and the `txdl[]` reason columns.
- **R passes, P or F fails:** the downloads are gone but the frame does not follow. The waits were covering GPU time
  (median 15.2 ms) or PFIFO work (`Draw` 10-14 ms), or another wait takes their place. The on run's phase columns
  say which.
- **N fails:** the decode costs gameplay frames. Read the `GPU` column.
- **V fails:** the run is void, not a refutation. The route's menu steps were recorded on a disk with no MKSM profile.
  The disk now carries the golden, the same run's harvest from after gameplay. If the title skips its brightness
  screen or offers to continue a story, the blind presses land elsewhere. Shots s05-s13 show where it diverged, and
  the pilot pair shows it before the second pair is queued.

### #992 Top Spin's A/B: what it needs

Top Spin has the most downloads (24-32 a frame in match play, 59 in the 18-fps arena intro) and the largest bound
(11-15 ms of a 26-31 ms frame), so its A/B carries the largest possible gain. It cannot be queued as the title
stands:

- Top Spin has no golden profile.
- `fps786-topspin` is a first-run route without `mark profile-saved`, which the profile gate refuses (R2).

The way through is MKSM's: promote the save harvested after `mark gameplay` (23b5be4cf466, from
1-1791525007-lane.profileddefault1008-4018033) and head a copy of the route `any`. The route was recorded on a disk
with no profile, so a desync is more likely than on MKSM: Top Spin's menus include profile creation. MKSM's A/B goes
first because it decides whether removing the downloads moves the frame at all. If its R leg passes and P fails,
Top Spin's A/B is not worth the route work.

Top Spin's match play also breaks the render pass about 100 times a window for occlusion queries. Its A/B should
carry `HAKUX_REPORT_ASYNC=1` in both arms (texscan1010's lesson), so that a report wait cannot take the downloads'
place and hide the gain. MKSM's cutscene breaks for no queries, so its A/B runs the switch alone.

## The A/B, queued

Both predictions name f5a67ba52c (`a_ref` = `b_ref`), the merge of master 0e5fab6bef into this branch. Its diff
from 36c77086de is `s2tread.py`'s printout, `status_html.py` and another lane's PR.md: no emulator code. Registered 2026-10-16 15:16Z, committed and pushed in 465cfd2f57 before any queue. All four requests
are pinned to the Nova and queued by the lane (`--who fps1015`, 2 x 150 s + 2 x 420 s = 19 min, under the pilot
gate's 30). They run in id order, which is the order below; the Nova is held by `lanelocal-ownerplay` until the
owner says done.

| request | leg | arm |
|---|---|---|
| 1792163875-fps1015-716177 | pixel | B, `HAKUX_S2T_CVT=1` |
| 1792163881-fps1015-716411 | pixel | A, no env |
| 1792163888-fps1015-716638 | soak, MKSM | on1, `HAKUX_S2T_CVT=1` |
| 1792163893-fps1015-717142 | soak, MKSM | off1, no env |

Reading them, in this order:

1. Pixel: `python3 docs/testing/ab_compare.py --a <A result> --b <B result> --expect
   docs/testing/predictions/fps1015-pixels.json --allow-same-binary`, then grep B's logcat for `[s2tcvt] on` and
   `[s2tcvt] first`. A moved capture stops the soak reading until it is explained region by region.
2. Soak pilot: `python3 docs/lanes/fps1015/s2tread.py <on1> <off1>` (add `--windows` for the rows). If both runs
   pass V, queue on2 then off2 with the same two commands (purpose "on2"/"off2"), and judge all four together. If
   either fails V, read shots s05-s13 of the failing run for where the route diverged; the run is void, and the
   route is what changes, not the prediction.
