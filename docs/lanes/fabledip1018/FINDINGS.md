# lane.fabledip1018: Fable and Blinx 2 -- what the frame spends its time on (#433)

Offline analysis only. No device time, no code changes. See `NOTES.md` for
the Already-tried table and the `[drawrec]`/`[rdc]` field reference this
write-up leans on throughout.

## 1. Per-window decomposition

### 1a. Fable, owner's second launch (`captures/fable-owner-1018/ring-dump-0725.txt`, pid 29046)

Baseline (video, 07:18:47-07:19:05): `gfps=29 G:33.4 Ri:32.6 Tq:2`. The
renderer thread is ~98% idle (`Ri` tracks `G` almost exactly) -- it is
vsync-paced with nothing to do, not CPU- or GPU-bound.

Gameplay (from 07:20:47): `gfps` 29 -> 16-26 (mostly 21-23), `G` 33.4 ->
40-57ms, **`Ri` 32.6 -> 0.6-5.3ms**, `Tq` 2 -> 700-1728, `Df` 0 -> 70-108,
vblank jitter `J` 0 -> 5-7.5. The renderer thread goes from almost entirely
idle to almost entirely busy at the same moment gameplay starts -- this is
exactly the G-up/Ri-down/Tq-up signature gta3fps1017b's section 5 found on
GTA III, GTA:SA and Blinx 2.

`[drawrec]` across the same window (`hw/xbox/nv2a/pgraph/vk/draw.c`,
`drawrec_tick()`, one line per 60 flips):

| time | dirty | redo | redoKB | walks(flip+budget) | runs | shc |
|---|---|---|---|---|---|---|
| 07:21:02 | 697 | 1914 | 20196 | 60+31 | 379 | 8882 |
| 07:21:08 | 1855 | 3585 | 35580 | 59+114 | 988 | 16973 |
| 07:21:21 | 927 | 2206 | 25120 | 60+67 | 515 | 10666 |
| 07:21:38 | 1129 | 2392 | 34540 | 60+102 | 563 | 14623 |
| 07:21:48 | 874 | 2471 | 36536 | 60+120 | 467 | 14591 |

`redo/dirty` sits at 2.0-2.8x throughout the dip and does not trend up or
down with it -- the REDO-only tax (`drawrec_vtx_copied()`, pages copied
because their walk is owed, not because the guest is proven to have
rewritten them since the last copy) is a roughly constant multiplier on top
of whatever the guest is genuinely dirtying, not something that grows as
the dip deepens. That argues the dip's *size* is set by genuine dirty
volume (gameplay simply touches far more vertex data per frame than a
cutscene), with the redo mechanism adding a steady ~2-3x tax on top, not by
the tax itself running away.

The one `[rdc]` line that lands inside a `[drawrec]` window (`system/physmem.c`,
`rdc_tick()`, 07:21:08.521, matching the f=60 window ending 07:21:08.341):

```
[rdc] f=60 dt=3445 tid=29101 tcpu=1167.2 rdo=1545 rdous=7886
      vtx=927/4076/15908/1584 tex=618/3810/44995/38
      v=3234 dx=0 vr=770 tm=0 ovh=3543/24 tk=58
```

`dt=3445ms/60f` = 57.4ms/frame, matching `G`. `tcpu=1167.2ms/60f` = 19.45ms
of render-thread CPU per frame (34% of the frame). But the walk time itself
(`vtx`+`tex` us, which is what `rdous` sums to) is **7886us over 60
frames = 131us/frame** -- 0.03% of the frame, 0.7% of the render thread's
own CPU. `vr=770` of `927` vtx walks (83%) repeat within the *same*
vertex-sync call -- exactly the "one walk per run, not per batch" cost
drawrec1010's R leg found and could not get under budget. `tex`'s hit rate
is 38/44995 = 0.08%: almost every texture-dirty walk in this window finds
nothing to re-arm.

**Conclusion for this window: the walk's own CPU cost cannot be the 19ms/frame
render-thread cost, let alone the 57ms frame. Whatever the render thread
spends its budget on, it is not the TLB re-arm.** The remaining candidates
visible in these counters are the vertex-byte copy volume itself (20-43 MB
redone per 60 frames = 340-730 KB/frame of `pgraph_vk_update_vertex_ram_buffer`
work, `sync_vertex_ram_buffer()`) and the full-pipeline-path draw count
(`shc` 8882-16973/60f = 148-283 **full-path draws per frame**, each one a
pipeline-key build, compare, and a fresh UBO descriptor-set write per
`drawrec_shc_consumed()`'s own comment). Neither byte count nor draw count
is directly timed by anything in hand -- see section 4's measurement.

### 1b. Fable, cold-cache find-route run (`dispatch/results/z-1792331899-lanelocal-2723208/`, perflog APK, pid 14433)

Two distinct events, not one:

**Startup stutter, 07:00:06-07:00:40** (before any shader-link activity is
logged at all): `hakuX-pace` f=60 window ending 07:00:40.154: `max=2570.4
ms=8547.1` (one frame spiked to 2.57s; the 60-frame window averaged 142ms/frame).
`hakuX-audiocap` at 07:00:36.427: `starve: 91/119 callbacks short ...
738304/974848 bytes zero-filled = 75.7353%`; by 07:00:41.429 it is `0.6356%`,
and 0.0000% from 07:01:11 on. Through this entire stretch `Ri` stays at
34-58ms (`gfps=16 G:46.7 ... Ri:45.4` at 07:00:49.998) -- **the renderer
thread is not the busy one here.** The first `[gpl569]` pipeline-link line
in the whole capture (`hw/xbox/nv2a/pgraph/profile.c`'s pipeline-library
log) is at **07:01:43.441**, a full minute after this stutter has already
resolved. There is no shader-compile activity logged during the window the
brief asks about. The audio zero-fill clears (07:00:36 -> 07:00:41) at
almost the same moment the frame-time spikes start shrinking (07:00:40's
window max 2570.4ms -> 07:00:42's 130.7ms) -- both point at a shared,
one-time cold-start cost (asset/APK I/O after the cache-clearing swap, audio
ring-buffer warm-up) rather than at shader compilation.

**A second, separate, genuine compile stall at 07:01:43.682**: `gfps=15
G:62.4(11.6-3783.3) ... Tq:75` (Tq jumps from a flat 3 to 75 at the exact
frame this window's single-frame max is 3783ms), coincident with the first
`[gpl569] links=1` event. This one *does* look like a cold-cache pipeline
build stalling a frame. It is a single isolated spike, not a sustained
~40s stutter, and it is a different event from the opening one above.

**Village scene settling, from 07:01:14.355**: `hakuX-pace` window ms drops
from ~2750-2790 to 2103.3 (`max` 177.4 -> 95.5), and stays near 2.1s/60f
through 07:01:32. `[drawrec]` in the settled village scene (07:03:04.590):
`dirty=759 redo=1920 redoKB=19064 shc=8322` -- the same order of magnitude
as the owner capture's gameplay dip (section 1a), in a different scene,
confirming the redo/shc volume is a general property of Fable's draw
pattern, not specific to one location.

**What the brief's hypothesis gets right and wrong**: cold shader compile
is not shown by this data to explain the 07:00:06-07:00:40 stutter (no
compile activity logged, renderer thread idle throughout, shared timing
with the audio ring-buffer warm-up instead). It *does* explain the single
spike at 07:01:43. **The run that would settle the opening 34 seconds**:
the brief itself says the first launch (before this cache-cleared one) is
lost; a captured first launch, or a capture with per-flip asset-I/O/thread
timestamps for frames 0-2000, is the one thing that would show whether
APK/asset access or audio-driver warm-up is the real cause instead.

### 1c. Blinx 2, owner capture (`captures/owner-play-1018/logcat-nova-owner-play.txt`, pid 1876)

Before the first-door transition (07:28:17-07:32:54): `gfps` mostly 25-29,
`G` 33-43ms, **`Ri` already low and noisy (0.2-14ms)** -- unlike Fable's
video baseline, Blinx 2 never has an idle render thread even in its "good"
stretch. `Tq` 1800-4000. `[drawrec]`: `dirty` 2400-6100/60f, `redo`
4100-26000/60f, `redoKB` 15-107 MB/60f (mostly 35-55), `shc` 4200-11700/60f.

After 07:32:57 (`gfps=22 G:46.1 ... Tq:6314`, worsening through 07:33:00
`gfps=14 G:70.1 ... Tq:7445`, and staying at `gfps` 14-18 `G` 55-70ms
through 07:33:28): `Tq` 5400-7445 (vs 1800-4000 before), `redo` 14000-26000
(roughly flat vs before -- the increase is smaller here than redoKB's), **`redoKB`
58-97 MB/60f (vs 15-55 before, mostly ~1.5-2x)**, `shc` 10000-18000/60f (vs
4200-11700 before).

`redo/dirty` ratio *rises* after the door, unlike Fable's steady 2-3x:
`13551/4288=3.16` just before (07:32:54) to `19474/4214=4.62` right after
(07:32:58) to `23589/4838=4.87` at the peak (07:33:01). Here the REDO-only
tax is growing disproportionately to genuine dirty volume -- the opposite
of Fable's pattern. That is a **consequence** signature: the re-arm walk is
falling further behind actual dirtying after the door, not a proportional
jump in how much vertex data the guest is rewriting.

`[rdc]` across the same transition (`system/physmem.c`):

| time | dt(ms/60f) | tcpu(ms/60f) | vtx us/60f | vtx pages/hits |
|---|---|---|---|---|
| 07:32:54 | 2165 | 716.1 | 6762 | 4844/3723 |
| 07:32:57 | 2666 | 887.0 | 7913 | 4828/3359 |
| 07:33:00 | 3675 | 1253.5 | 8584 | 5739/3863 |
| 07:33:04 | 3820 | 1155.0 | **22544** | 5001/3517 |

`tcpu` rises ~60-75% across the door (716 -> 1155-1253ms/60f), tracking
`G`'s rise closely, while `vtx` walk time stays a small fraction of `tcpu`
except for one anomalous window (07:33:04, 22.5ms of walk time out of
1155ms tcpu -- still only 2%, but 3-5x this window's neighbors' walk cost
per page, worth a future lane's attention but not the main cost here
either). Same conclusion as Fable: **the walk's own time does not explain
the render thread's added CPU**, which again tracks `redo`/`shc` volume,
not walk count.

### 1d. Cause vs consequence, read together

Both titles show the gta3fps1017b dip signature (G up, Ri down or already
low, Tq up, redo/shc up) and both show that the TLB-walk re-arm mechanism's
own CPU time (`[rdc]`'s `vtx`+`tex` us) is 1-2 orders of magnitude smaller
than the render thread's total added CPU. The difference between them is
in the redo/dirty ratio's trend: **Fable's is flat (steady tax on genuine
dirty growth -- the guest is doing more real work); Blinx 2's climbs after
the door (the bookkeeping is falling behind -- the mechanism itself is
adding more relative overhead, not just carrying more real data).** Neither
title's dip is explained by the walk cost itself; both point at whatever
consumes the rest of the render thread's added CPU per redone vertex byte
and per full-path (`shc`) draw -- the copy/update and pipeline-key/descriptor
work in `sync_vertex_ram_buffer()`'s dirty branch and in the shader-bind
full path, neither of which either title's captures time directly.

## 2. Is Fable's opening 30s cold shader compile?

Answered in 1b: **not for the sustained ~34s stutter** (no compile line
logged before it resolves, renderer idle throughout, shared timing with the
audio ring-buffer's own warm-up). **Yes for one later, isolated spike**
(07:01:43.682, coincident with the first `[gpl569]` line and `Tq` jumping
3->75). The missing first launch is exactly what would show whether the
opening stutter is cold-cache-shader-compile on a launch that has *more*
compiles pending (the captured run is the *second* launch after an APK swap
that cleared the shader cache, per the brief, so this already is close to
the worst case for compiles -- yet shows none logged in the opening window).
**The run that would settle it**: a capture of a genuinely first-ever launch
with per-frame (not per-60-frame) shader/pipeline and asset-I/O timestamps
for the first 2000 frames, so a frame-by-frame cause can be assigned instead
of inferred from the absence of a periodic counter.

## 3. Do Fable and Blinx 2 share a cause? Ranked levers

Both titles' sustained dips match the same signature as GTA III/SA
(gta3fps1017b section 5), and in both, drawrec's own instrumentation rules
out the TLB-walk time itself as the direct cost (section 1d). That is a
real shared cause at the level of "which subsystem", but the two titles
differ in *how* the redo/shc volume is produced (flat ratio vs climbing
ratio), so a single fix is not guaranteed to help both equally.

Ranked by probability-weighted fps gain, each with the file/function that
owns it and the issue/lane covering it (none propose anything the
Already-tried table shows failed):

1. **Time the dirty-copy and full-path-draw CPU directly, not just count
   it** (`sync_vertex_ram_buffer()`'s dirty branch calling
   `pgraph_vk_update_vertex_ram_buffer()`, and `pgraph_vk_bind_shaders()`'s
   full path gated by `shader_bindings_changed` / `drawrec_shc_consumed()`,
   both in `hw/xbox/nv2a/pgraph/vk/draw.c`). Not yet built by any lane.
   **Highest-probability lever**: this is the one gap in every number
   gathered above -- both titles' render-thread CPU tracks redo/shc volume
   while the walk time does not, but nothing in hand times the copy or the
   pipeline-key/descriptor work itself. Until that exists, any fix aimed at
   *reducing* redo/shc counts is aimed at a correlate, not a proven cost.
   No fps estimate possible without this measurement; that is the point of
   building it first.
2. **`tlbmap.mbox`** (parked in drawrec1010 NOTES section 11: one TLB scan
   per *batch* instead of per *run*; needs a grant on `accel/tcg/cputlb.c`
   and `system/physmem.c`, outside drawrec's current territory). Section 1
   shows the walk time is already 0.03-2% of the frame in both titles --
   **this lever cannot deliver a meaningfully bigger win than it already
   isn't delivering**, since even removing 100% of walk time would not
   close a 20-40ms/frame gap. Do not build this for *this* dip; it remains
   correctly parked.
3. **Reduce REDO-only copy volume directly** by widening the REDO budget
   (`DRAWREC_VTX_REDO_N`/`_B` in `draw.c`) so fewer early walks fire per
   frame. This would cut `walks=...+B`'s second term and the per-flip run
   count, but drawrec1010's own NFS A/B already found walk-count reduction
   alone does not reach target (R leg refuted), and section 1 shows walk
   time is not the dominant cost anyway -- **low expected gain**, same
   reason `tlbmap.mbox` ranks low.
4. **HAKUX_ZETA_D24-style GMEM investigation for either title**: fpsbelow1012's
   title list does not include Fable or Blinx 2, and nothing in the
   captures here shows a Z24S8 zeta-format signature. Not ruled in without
   a capture showing it; not proposed as a lever without one.

## 4. The one lever first, and the measurement that would confirm it

**First: build the direct-cost instrument from lever 1 above** -- per-draw
or per-60-flip timing of (a) `pgraph_vk_update_vertex_ram_buffer()`'s copy
time and byte count (already counted in bytes by `redoKB`+`dirty`'s own
bytes, just not timed), and (b) the full shader-bind path's pipeline-key
build + descriptor-set-write time, keyed the same way `drawrec_shc_consumed()`
already counts `shc`. **Confirming measurement**: in the Fable gameplay
window, render-thread `tcpu` is 19.45ms/frame while TLB-walk time is
0.13ms/frame (section 1a); the new instrument should show the remaining
~19ms attributed mostly to these two paths in proportion to `redoKB` and
`shc`'s own per-frame counts. If it does not -- if the 19ms is somewhere
else entirely -- that redirects the whole lever, which is exactly why this
has to be measured before anything is changed.

**Two small, safe owner actions on the Nova, no perflog build needed**:

- Load Blinx 2's slot-0 save state (saved 07:33:37 in the slow spot,
  `ok=1` per the brief) and read the next `[drawrec]`/`[rdc]` 60-flip
  window immediately after load, then again after ~10s of standing still.
  If `redo`/`shc` are already elevated on load (before any new player
  input), the "after the first door" framing is about a persistent world
  state change, not an ongoing per-frame input-driven cost -- a materially
  different lever than if the numbers climb only while moving.
- Attach to Fable at the same 07:20:47 gameplay transition point (a fresh
  owner play-through, attach-never-launch) and read `[drawrec]`/`[rdc]`
  for ~10s standing still in the same spot versus ~10s moving. If `redo`/`dirty`
  stay similarly high standing still, the dirty volume is driven by the
  scene's own animated/dynamic objects, not by camera/player motion --
  narrows where in the engine to look for what is rewriting vertex data
  every frame.

## 5. Selftest

None -- analysis only, no code.
