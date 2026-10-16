# lane.fps1015 NOTES

Brief: `/home/justin/hakux-work/briefs/fps1015.md`. Issues #986 (MKSM), #992 (Top Spin + Brian Lara),
#995 (Batman Begins), #993 (Prince of Persia), #994 (Halo 2 stalls). Offline tonight: the Nova is held by
lane.local's overnight chain until ~06:00 PDT 10-16.

## Status

[lane.fps1015] working:
- #986 MKSM: cause found, serialization on 16-bit render-to-texture downloads. Lever WAITING on vk/texture.c.
- #992 Top Spin: the same cause, 24-32 downloads a frame.
- #992 Brian Lara: a different shape, unexplained. Next step: one perflog run.
- Next: #995 Batman Begins.

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

Batman takes its one download in the 29-fps baseline dump as well as in the slow rooms, so it does not explain the
slow windows. The lever still removes one finish a frame there.

WAITING: `hw/xbox/nv2a/pgraph/vk/texture.c` (withheld). The lever's gate (`check_surface_to_texture_compatiblity()`)
and its call site (`create_texture()`, `copy_surface_to_texture()`) are both in it. The conversion kernel can live in
vk/surface.c, which is in this lane's territory. Needed: a grant of vk/texture.c for a default-off `HAKUX_S2T_CVT`
switch, and its golden arm and A/B.

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
it is one lever, `HAKUX_S2T_CVT` (WAITING on vk/texture.c, above).

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
