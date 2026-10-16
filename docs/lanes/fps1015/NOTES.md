# lane.fps1015 NOTES

Brief: `/home/justin/hakux-work/briefs/fps1015.md`. Issues #986 (MKSM), #992 (Top Spin + Brian Lara),
#995 (Batman Begins), #993 (Prince of Persia), #994 (Halo 2 stalls). Offline tonight: the Nova is held by
lane.local's overnight chain until ~06:00 PDT 10-16.

## Status

[lane.fps1015] working: #986 cause found (serialization on 16-bit render-to-texture downloads; lever WAITING on
vk/texture.c). Next: #992 Top Spin and Brian Lara.

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
