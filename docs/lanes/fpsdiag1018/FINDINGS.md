# fpsdiag1018: GTA III, Blinx 2, Fable -- what we know, what it is not, what it could be (#433)

Owner's order (2026-10-18 ~15:15 PDT, verbatim in `docs/lanes/fpsdiag1018/NOTES.md` section 0 and the brief): one
lane, one page of what we know, a list of what the problem is not, a ranked list of what it could be, and a
diagnostic tool -- no more gameplay navigation. This file is that page. Every number below carries its source file;
anything without one is marked `untraced`. Nothing here is a new device run: every figure is read from a capture or
a write-up already on disk.

## 1. Known: measured fps, per title

### 1.1 GTA III (title id `5454000E`, target 30 fps, bar 28.5 = 30 x 0.95 tolerance, `docs/testing/titles/targets.toml` lines 24-30/369-374)

| where | device | n windows | fps (median or mean) | source |
|---|---|---|---|---|
| Golden route, full gameplay, driving | Nova | one run, 453.6 s | `fps_ok=0.9804` (98.0% of gameplay time at/above bar) | `targets.toml:373`, golden sha `9153c63300da` |
| Driving burst, pilot 343857 | Nova | dip frame cited directly | dip frame: G 47 ms (~21 fps); GPU busy 21.9 ms of the 47 ms frame | `gta3drive1017/NOTES.md` section 6.2, D3 row, re-cited in `gta3dip1018/NOTES.md` section 0 |
| RT held from a save state, driving (`gta3-rthold60-savestate-5454000e-12836`) | Nova | 54 windows / 150.6 s | 46.0% time >= bar; median 29.2, p5 16.1; dip class (n=17) G 50.5 ms; good class (n=28) G 33.2 ms | `gta3fps1017b/NOTES.md` section 5.1 |
| RT held, baseline (`gta3-rthold-baseline-5454000e-7467`) | Nova | 14 windows / 40.4 s | 0.0% time >= bar; median 22.5, p5 11.9; dip class (n=14) G 43.6 ms | `gta3fps1017b/NOTES.md` section 5.1 |
| Parked, three env-var arms (`runs/b3-A/B/C`) | Nova | A: 7, B: 12, C: 11 windows | mean G: A 54.9 ms, B 38.1 ms, C 40.2 ms -- **confounded** (A alone pays ~50 s of cold shader/pipeline compile the others reuse; not an R2/R3 fps comparison) | `gta3dip1018/FINDINGS.md` section 1, 1.4 |
| Owner free-play, release build (`captures/owner-play-1018/...`, pid 5782) | Nova | two single-frame stalls + sustained dip 07:38:34-07:39:30 | 1.46 s and 3.89 s single frames (both inside the title's post-boot cold-compile window, over by 07:38:23); sustained dip afterward 16-22 fps, no active compile | `gta3dip1018/FINDINGS.md` section 2 |

Methodology note on provenance: `captures/owner-play-1018/...` has **zero** `xemu-vulkan` lines (checked by grep
this lane, `grep -c xemu-vulkan` = 0) -- the one-time GPU-driver-identification line is absent because this is an
attach-style host capture that began after the app's own startup prints had already scrolled past. This capture is
still a PurpleVK run: it is the same pid (5782) and session every prior lane (`gta3dip1018`, this lane) has already
cited as a Nova capture, and the Nova runs no other driver by device policy. **An attach-style capture's absence of
`xemu-vulkan` is not evidence of the stock driver** -- `fpsdiag.py capture` is written below to avoid this gap for
new captures (section on the GPU-driver check in `fpsdiag.py`'s own doc comment).

### 1.2 Blinx 2 (title id `4D530065`, target 30 fps explicit, `targets.toml:220`)

| where | device | n windows | fps | source |
|---|---|---|---|---|
| Island, driving/moving (`blinx2-island-4D530065`, pid 23672, from 23:14:55) | Nova | 30 windows / 68.1 s | 32.4% time >= bar; median 26.4, p5 20.2; dip class (n=12) G 41.6 ms, Tq 3842; good class (n=11) G 33.4 ms, Tq 2556 | `gta3fps1017b/NOTES.md` section 5.1 |
| Owner free-play, release build, before/after a door transition (`captures/owner-play-1018/...`, pid 1876) | Nova | before 07:28:17-07:32:54; after 07:32:57-07:33:28 | before: gfps mostly 25-29, G 33-43 ms, Ri 0.2-14 ms (never idle, unlike Fable's video baseline); after: gfps 14-22, G 46-70 ms, Tq 5400-7445 (vs 1800-4000), redoKB 58-97 MB/60f (vs 15-55) | `fabledip1018/FINDINGS.md` section 1c |

Blinx 2 has no own-title `targets.toml` entry beyond `target_fps=30`; the note at `targets.toml:219` records the
30 fps figure as sourced from a low-confidence web citation ("targeting 30 frames per second... complex sequences
with multiple effects can cause noticeable slowdown"), not from a device measurement -- flagged `untraced` as a
*target*, though the dip measurements above are directly measured.

### 1.3 Fable (no `targets.toml` entry; judged on `[defaults]`: target 30, bar 28.5)

| where | device | window | fps | source |
|---|---|---|---|---|
| Owner's second launch, video/menu baseline (`captures/fable-owner-1018/ring-dump-0725.txt`, pid 29046, 07:18:47-07:19:05) | Nova | one 60-flip window | gfps=29, G 33.4 ms, Ri 32.6 ms (renderer ~98% idle: vsync-paced, not bound) | `fabledip1018/FINDINGS.md` section 1a |
| Same capture, gameplay from 07:20:47 | Nova | several 60-flip windows | gfps 16-26 (mostly 21-23), G 40-57 ms, Ri 0.6-5.3 ms, Tq 700-1728 | `fabledip1018/FINDINGS.md` section 1a |
| Cold-cache find-route run (`dispatch/results/z-1792331899-lanelocal-2723208/`, perflog APK, pid 14433), opening stutter 07:00:06-07:00:40 | Nova | one window | window mean 142 ms/frame (one frame spiked to 2.57 s) | `fabledip1018/FINDINGS.md` section 1b |
| Same run, village scene settling from 07:01:14.355 | Nova | several windows | window ms drops 2750-2790 -> 2103.3 (max 177.4 -> 95.5), holds near 2.1 s/60f through 07:01:32 | `fabledip1018/FINDINGS.md` section 1b |

No golden/pathfound route exists for Fable (`titles05`/`routedriver` lanes have not reached it); every Fable figure
above is from an owner free-play or find-route capture, never a controlled A/B batch. That is itself a known gap,
not just a missing nicety: **nothing above is a repeatable measurement for Fable** -- a second capture of the same
spot could legitimately read differently, and FINDINGS.md's "could be" ranking below treats Fable's evidence as
weaker than GTA III's or Blinx 2's for that reason.

### 1.4 The shared signature (GTA III, GTA:SA for comparison, Blinx 2 -- release-build captures, `tools/dip_table.py`, dip = window < 26 fps, good = window >= 29 fps)

| title | G (dip-good) | Df (x) | Tq (x) | Ri (dip-good) | tc (dip-good) |
|---|---|---|---|---|---|
| GTA III | +17.3 ms | x4.5 | x1.29 | -13.9 ms | +4.7 ms |
| GTA: SA (comparator; not one of this lane's three titles) | +10.1 ms | x1.41 | x1.89 | -7.1 ms | +4.0 ms |
| Blinx 2 | +8.2 ms | x1.39 | x1.50 | -6.2 ms | +3.0 ms |

Source: `gta3fps1017b/NOTES.md` section 5.2. In every title's dip windows: the game frame stretches (G up), the
renderer idles less (Ri down), the PGRAPH thread spends more CPU per frame (tc up), there are more deferred
VBLANK-governor retries (Df up, see section 2.3 below for why this is not an independent symptom) and more
texture-dirty queries (Tq up). **This is a class, not a cause** -- magnitude differs per title (GTA III's Df jump
is far larger; Blinx 2's Tq is 2-3x the GTA titles' in both classes) and the table does not by itself identify a
mechanism. Fable is not in this table (no perflog/release capture with this exact tooling run against it yet); its
own `Ri`/`Tq` figures in section 1.3 show the same direction (Ri drops from 32.6 to 0.6-5.3 ms the moment gameplay
starts) by a separate reading, not this joined table.

## 2. Not: ruled out, each with its falsifying measurement, its scope, and what it does NOT cover

A theory counts as ruled out here only where the measurement cited could actually have shown it wrong, and is
scoped to exactly the title(s)/window(s) it was measured in. Carrying a refutation from one title to another
without its own measurement is the exact mistake this lane was told to avoid (brief, `NOTES.md` falsifier-discipline
row).

1. **GPU raw render/compute saturation (100% busy) is not the GTA III/SA/Blinx 2 dip cause.** Falsifying measurement:
   `busy%` barely moves between dip and good windows in any of the three titles in the section 1.4 table (GTA III
   ~34%, SA ~36-38%, Blinx 2 ~29-31%, dip and good alike) -- if the GPU were saturated, busy% would read near 100%
   and would rise sharply in dip windows; it does neither. Separately, pilot 343857's single dip frame on GTA III
   measured GPU busy 21.9 ms of a 47 ms frame (idle more than half the frame). Source: `gta3fps1017b/NOTES.md`
   5.1-5.2; `gta3drive1017/NOTES.md` 6.2 D3. **Scope: GTA III, SA, Blinx 2's driving/island windows only.** Now also
   tested for Fable, via `fpsdiag.py analyze owner-play-1018c` (section 4): busy 34% dip vs 3% good (n=56/57) --
   neither saturated, ruled out for Fable too, in this capture. **Open tension, not resolved by this lane:**
   `fpsdiag.py analyze` against `gta3car1018/runs/c1-A1` (a different, perflog-tier, in-car GTA III capture) finds
   busy 90% dip vs 43% good (n=19/43) -- not flat, and far closer to saturated than the ~34% flat reading this item
   is built on. `c1-A1`'s window set spans a parked segment and a driving segment (RT held) in one file
   (`gta3car1018/NOTES.md` section 4's per-arm timestamps); the swing may track park-vs-drive content instead of
   saturation as a cause, but this lane did not split the windows by that boundary to check (`fpsdiag.py` has no
   `--since`/`--until`; see section 4). **Do not read this item as closed for GTA III's in-car/driving condition** --
   the next pass should split `c1-A1`'s windows at the RT-down timestamp and re-run `analyze` on each half before
   either extending or narrowing this item's scope.
2. **The TLB/texture-dirty-walk's own CPU time is not the dominant render-thread cost, for Fable and Blinx 2.**
   Falsifying measurement: `[rdc]`'s `vtx`+`tex` microsecond fields sum to 0.03%-2% of the render thread's own
   `tcpu` in every sampled window of both titles (Fable: 131 us of 19.45 ms/frame tcpu, 0.7%; Blinx 2: at most 22.5
   ms of 1155 ms tcpu per 60-flip window, 2%, in the single highest-walk-cost window observed) -- a walk cost that
   dominated tcpu would show up as most of it, and in every window it is a small fraction. Source:
   `fabledip1018/FINDINGS.md` 1a, 1c, 1d. Separately ruled out for GTA III's driving pilot (343857): "texture dirty
   walks in microseconds" (`gta3drive1017/NOTES.md` 6.2). **Scope: Fable, Blinx 2, and GTA III's pilot-343857
   driving burst specifically.** Now also re-measured, via `fpsdiag.py analyze` (section 4): GTA III's owner-play
   sustained dip (`owner-play-1018`, pid 5782, n=23) reads 1.1%; `gta3car1018/runs/c1-A1`'s in-car dip windows
   (n=19) read 0.5%; Blinx 2's owner-play dip (n=79) reads 0.9%. All three stay in the same small-fraction range as
   Fable's figure above -- ruled out there too, closing the gap this item previously left open.
3. **Cold shader/pipeline-library compile is not the cause of GTA III's sustained dip, nor of Fable's opening ~34 s
   stutter -- but it IS the cause of four other, separate, single-frame/short events.** Falsifying measurement for
   the sustained claims: in GTA III's owner capture, `[uber569]`'s `cold`/cumulative `lib_ms` counters climb then go
   completely flat at 07:38:23 (`cold=18`, `lib_ms=24585.5`unchanged for the rest of the capture), while the
   sustained 16-22 fps dip runs from 07:38:34-07:39:30 -- after compile activity has already stopped; a compile-driven
   dip would show the counters still climbing during the dip, and they do not. In Fable's cold-cache run, the
   renderer thread's own idle metric (`Ri`) stays high (34-58 ms) through the entire opening stutter and the first
   `[gpl569]` pipeline-link line in the whole capture does not appear until a full minute after the stutter has
   already resolved -- a compile-bound frame would show the renderer busy and a compile line active during the
   stutter, and neither is true. Confirmed, separately, as the cause of: GTA III's two owner-capture single-frame
   stalls (1.46 s, 3.89 s, both inside the one active compile window); the b3-A parked-phase mean running higher
   than B/C (one-time ~50.4 s compile tax from a shader-cache clear immediately before A, not present in B/C); and
   one isolated 3.78 s Fable frame at 07:01:43.682 coincident with the first `[gpl569] links=1` event. Source:
   `gta3dip1018/FINDINGS.md` 1.4, 2; `fabledip1018/FINDINGS.md` 1b, 2. **Scope: GTA III's owner-capture sustained
   dip and Fable's opening-34s stutter only. Not measured against Blinx 2's door-transition dip at all -- no lane
   has checked `[gpl569]`/`[uber569]` timing against that window, so this stays `untraced` for Blinx 2, not ruled
   out.**
4. **The S2T copy-elimination switches (R1/R2/R3) do not move GTA III's fps, on the one controlled (palindrome)
   comparison that exists.** Falsifying measurement: batches b2/b4, same scene, arms swapped in both directions
   (A-B-B-A), R2 -0.3 fps, R3 -0.9 fps, R3's `dup` count measured at 0 (the lever had nothing to act on, so its
   null result is a genuine refutation, not an inert lever masquerading as one -- `dup=0` was itself read from the
   same run). Source: `captures/lanexbox-fps1018/README.md`, re-cited `gta3dip1018/NOTES.md` section 0. **Scope:
   GTA III driving, this one palindrome pair, only. Explicitly not extensible to SA (on-foot census run, driving
   census never run -- `gta3fps1017b/NOTES.md` 5.3-5.4) or to Blinx 2 (same section: the perflog APK would need
   building against the release package id to keep Blinx 2's save, and lane.local has not done this). Fable:
   never measured with this switch at all.**
5. **Vertex-hazard finishes, `pgraph.lock` contention on the PFIFO side, and "the guest CPU is slow" are not the
   dominant cost in GTA III's driving pilot 343857.** Falsifying measurement: vertex-hazard finishes ~0.3/flip flat
   (not rising with the dip), `pgraph.lock`'s PFIFO-side wait (`lw`) = 0, pipeline compile <= 2 ms/flip, guest work
   23.3 ms < the 33 ms frame budget it was compared against. Source: `gta3drive1017/NOTES.md` 6.2, re-cited
   `gta3dip1018/NOTES.md` section 0. **Scope: this one pilot capture, GTA III driving, only.**
6. **Not a ruled-out cause, but a documented instrument failure that could be mistaken for one**: the
   `hakuX-stall RPBreaks:/Finish:` and `hakuX-rpbrk` per-window breakdown is racy once the deferred-finish render
   thread is active -- two threads (confirmed by tid in the b3 runs: 14006 and a second, 14008 in arm A) write and
   reset the same non-atomic global struct, and the series goes non-monotonic within a single window. **This
   counter cannot be cited quantitatively in exactly the park/dip regime this lane studies.** It is reliable only
   in the steady 30 fps state, where it is not needed. Source: `gta3dip1018/FINDINGS.md` 1.3, `NOTES.md` stop-rule
   entry. `fpsdiag.py analyze` must not report a confirm/refute verdict keyed on this counter inside a dip window;
   section 4 below confirms `c1_rpbrk_nondraw_breaks` reads "not measured" in every capture checked, never
   "refuted," for exactly this reason.
7. **`Df` ("deferred flushes") is not an independent workload symptom -- it is downstream of the frame already
   running long.** Reading `hw/xbox/nv2a/pgraph/profile.c`'s `nv2a_profile_get_pacing_str()` and `nv2a.c`'s VBLANK
   pacing governor (`g_nv2a_stats.pacing.defers_total++`) shows `Df` counts VBLANK-IRQ-delivery deferral *retries*
   by the governor, which can fire more than once per frame under `defer_cap` -- it moves because G already moved,
   not as a second, separately-caused cost. This corrects `gta3fps1017b` section 5's framing (carried into the
   brief) of Df as part of an independently-acting "shared dip signature." Source: `gta3dip1018/FINDINGS.md` 1.2.
   Not a cause to rule in or out; a metric this lane's tool must not double-count as a separate confirming signal.
8. **Android ART/Dalvik GC pause is not the cause of any dip window measured by this lane.** Falsifying measurement:
   `fpsdiag.py analyze` (section 4) found zero ART GC log lines in all four captures checked -- GTA III's owner-play
   dip (n=23), Blinx 2's owner-play dip (n=79), Fable's owner-play dip (n=56), and GTA III's in-car perflog dip
   (n=19) -- a GC pause landing inside any of those 167 combined dip windows would print a line this check would
   have caught. This closes candidate 7 (section 3) as the cheap, no-new-code, no-device-time check it was flagged
   to be. **Scope: these four captures' dip windows only** -- not a claim that no GC pause has ever happened in any
   run of any of these three titles, only that none coincided with a measured dip in the capture this lane read.

## 3. Could be: ranked candidate causes

Ranked by probability the lever helps times the size of the win at scale, per the project's standing ranking rule
(owner, 2026-09-28: balance, do not reach for cheap-and-unlikely first). Candidates 1-3 come from the existing
lanes' own ranked levers (not re-derived, cited); candidates 4-8 are **new**, proposed by this lane, because the
brief requires the list not just copy the old shortlist. "Instrument" says whether a counter that would measure it
already exists in the capture formats this lane has read.

| rank | candidate | title(s) it could explain | confirming measurement | refuting measurement | instrument exists? |
|---|---|---|---|---|---|
| 1 | GTA III: non-copy render-pass breaks (`rp_break_nondraw`/`rp_break_clear`/`rp_break_query`, not the copy-driven `rp_break_surface`) hold the parked-scene pass count at ~53-55/frame regardless of R2/R3's copy elimination | GTA III | a fixed, single-threaded `hakuX-rpbrk` emitter (moved off the racy counter, section 2.6) in a parked arm shows `rp_break_nondraw`/`clr`/`qry` accounting for most of the ~53-55 passes, with the copy-driven reason at or near 0 | the fixed emitter instead shows `rp_break_finish` dominating -- points at candidate 2 (queue depth) instead, and this ranking should flip | partial: `hakuX-rpbrk`'s format already carries `fin`/`fb`/`qry`/`clr`/`nd`/`srf` sub-reasons (`hw/xbox/nv2a/pgraph/vk/draw.c` ~1048); the racy-emitter problem (2.6) must be fixed first for a dip-phase reading to be trustworthy |
| 2 | GTA III: GPU-queue-depth / finish-ordering variance (the async render-thread `#796` deferred-finish mechanism) drives the window-to-window `Fin`/`Fen` (CPU submit+fence-wait) swing, the best-correlated-with-G quantity measured so far | GTA III | in every arm's parked windows, high-G windows are high-Fin/Fen and low-G windows are low-Fin/Fen, with no exception (already shown, `gta3dip1018/FINDINGS.md` 1.5); a per-window `stlDef` (deferred-finish count) that tracked the same swing would mechanistically confirm it | the per-window `stlDef` count (once de-raced, same fix as candidate 1) stays flat across the Fin/Fen swing -- the swing would then be unexplained by queue depth and the next candidate to check is scheduler/thermal (candidates 6-7 below) | partial: `Fin`/`Fen` ms is already a reliable per-window figure (`hakuX-phase`); `stlDef`'s own count is part of the same racy family as candidate 1 |
| 3 | Fable + Blinx 2: the vertex-dirty-copy and full-shader-bind-path CPU cost (`sync_vertex_ram_buffer`'s copy, `pgraph_vk_bind_shaders`'s full path) is the real render-thread cost the `redoKB`/`shc` counters correlate with but do not time | Fable, Blinx 2 | a new per-60-flip timer on these two code paths shows their summed time tracking the render thread's added `tcpu` in proportion to `redoKB` and `shc` (Fable: tcpu 19.45 ms/frame vs walk-time 0.13 ms/frame already isolates the walk as NOT the cost -- this is the next step, not yet measured) | the new timer shows most of tcpu elsewhere entirely -- redirects the lever | no: nothing in hand times either path directly; both titles' counts (`redoKB`, `shc`) exist, their costs do not |
| 4 | **(new)** Competing process CPU: another app/service/service thread stealing a core from the render or PGRAPH thread during a dip window, uncorrelated with the title's own code | GTA III, Blinx 2, Fable (any) | `dumpsys cpuinfo` or a full `/proc/*/stat` process snapshot taken per window shows a non-hakuX process's CPU share rising specifically during dip windows, on the same cluster as the render/PGRAPH thread | the same snapshot shows no other process above idle-level CPU on that cluster during any dip window measured so far | no: no capture read by this lane includes a whole-system process list, only hakuX's own threads. The brief's own capture spec asks for "foreground package list + top CPU consumers" -- not yet built |
| 5 | **(new)** Memory/page-cache pressure: a dip coincides with free-memory dropping low enough to trigger reclaim, or a minor-fault storm on the render/PGRAPH thread (`/proc/<pid>/stat` `minflt`/`majflt` deltas) | GTA III, Blinx 2, Fable (any) | `minflt` or `majflt` rate on the hot thread spikes in dip windows vs good windows, coincident with free/cached memory (`/proc/meminfo`) dropping | fault rate and free memory stay flat across dip and good windows | no: no capture read by this lane logs `/proc/meminfo` or per-thread fault counts over time. The brief's capture spec asks for a "page-cache/free-memory line" -- not yet built |
| 6 | **(new)** Thread/core migration: the scheduler moves the render or PGRAPH thread between CPU clusters (e.g. Adreno's companion "big" cores to "LITTLE") mid-dip, paying a cache-cold penalty each migration | GTA III, Blinx 2, Fable (any) | `/proc/<pid>/task/<tid>/stat` field 39 (`processor`, last-run CPU) sampled at a stated period shows the hot thread's assigned CPU changing often during dip windows, rarely during good windows | the hot thread's assigned CPU stays constant (or changes at the same rate) in both dip and good windows | partial: `/proc/<pid>/task/*/stat` is already readable and already asked for by the brief's capture spec (per-thread CPU), but no capture read by this lane has sampled the `processor` field specifically |
| 7 | **(new)** Android ART/Dalvik GC pause on a hot JNI-callback path (even a native-heavy app makes some JNI calls per frame for input/audio/surface events; a stop-the-world or even a concurrent GC pause on that thread would show as a frame stall with no NV2A-side cause at all) | GTA III, Blinx 2, Fable (any) | a GC log line (`art` tag, "Background concurrent copying GC" or similar, or `dumpsys meminfo`'s GC-pause counters) lands inside a dip window's timestamp range | no GC log line appears within several seconds of any dip window's start in the captures checked | yes, checked: `fpsdiag.py`'s `gc` stream reads the `art` tag directly from logcat. Run against all four captures this lane has (section 4) -- zero matches in any -- refuted there, now ruled out as section 2 item 8 |
| 8 | **(new)** SurfaceFlinger/compositor backpressure: the dip is not inside hakuX's own render pipeline at all, but a wait for the Android compositor to accept the next buffer (`dequeueBuffer`/`queueBuffer` stall), which would show up as `Fin`/`Fen` rising for a reason outside this lane's own code | GTA III, Blinx 2, Fable (any) | `dumpsys SurfaceFlinger --latency <layer>` (or its frame-latency histogram) shows a queueing delay coincident with a dip window, on a layer matching hakuX's own surface | the same dump shows flat queue depth/latency through the dip window | no: no capture includes a `dumpsys SurfaceFlinger` snapshot; would need to be added to the capture spec as a periodic external read, not a logcat tag |

Candidates 4 and 7 are the cheapest to check **because an existing capture can answer them today, with no new
code and no device time** (`dumpsys`/GC log lines are not present in any logcat so far, but their simple absence or
presence across an already-captured dip window is a one-grep check) -- that is why `fpsdiag.py gaps` (section 4)
flags them first, not because they are more likely to be the cause. Per the ranking rule, the ordering above is by
probability-weighted size of the win, not cheapness: candidates 1-2 rank above 4-8 because they are grounded in a
measured, title-specific correlation already narrowed by three prior lanes' direct data (Fin/Fen's clean swing,
the flat RP/frame floor), where 4-8 are plausible but currently **unmeasured against any of these three titles'
captures** -- they could turn out to explain nothing. A low-probability new candidate is not promoted over a
higher-probability known correlate just for being novel or cheap to check.

## 4. Tool validation against real captures (`fpsdiag.py analyze`/`gaps`)

`docs/testing/perf/fpsdiag/fpsdiag.py` (step 2, committed separately) was run read-only against four real,
unmodified capture files already on disk -- no device touched, no capture altered. `MIN_WINDOWS = 3` is the floor
below which the tool refuses any candidate a verdict; every run below cleared it by a wide margin (19-134 scored
windows per run). Bar = 28.5 fps (30 x 0.95 tolerance) in every case; none of the three titles' own `targets.toml`
overrides change that figure except Blinx 2's explicit `target_fps=30`, which resolves to the same bar.

| capture | title (scope) | windows scored/refused | dip/good split | notable verdicts |
|---|---|---|---|---|
| `owner-play-1018/logcat-nova-owner-play.txt` | GTA III (`--pid 5782`) | 48 scored, 1 refused (boot/warmup marker) | 23 dip / 25 good | `tlb_walk_cost` refuted (1.1%); `c7_art_gc_pause` refuted (0 GC lines); `gpu_saturation`/`c1`/`c2`/`c4`-`c6`/`c8` not measured (perflog tags absent from this release build, or need `capture`'s periodic samples) |
| `owner-play-1018/logcat-nova-owner-play.txt` | Blinx 2 (`--pid 1876`) | 134 scored, 0 refused | 79 dip / 55 good | same pattern: `tlb_walk_cost` refuted (0.9%), `c7` refuted (0 GC lines), perflog/capture-only candidates not measured |
| `owner-play-1018c/logcat-nova-fable-owner-play.txt` | Fable | 113 scored, 1 refused (boot/warmup marker) | 56 dip / 57 good | `gpu_saturation` refuted (34% dip vs 3% good -- not saturated); `tlb_walk_cost` refuted (0.4%); `c2_fin_fen_queue_depth` refuted (1.4ms dip vs 0.1ms good -- flat, no swing); `c7` refuted (0 GC lines) |
| `gta3car1018/runs/c1-A1/` (2 files: `logcat.txt`, `arm.log`) | GTA III, perflog-tier | 62 scored, 2 refused (boot/warmup marker; save-state load) | 19 dip / 43 good | `gpu_saturation` **supported** (90% dip vs 43% good -- see tension below); `c2_fin_fen_queue_depth` **supported** (Fen 13.6ms dip vs 2.5ms good); `tlb_walk_cost` refuted (0.5%); `c7` refuted (0 GC lines) |

Three results independently corroborate, or newly extend, findings already in sections 1-2:

- **`c2_fin_fen_queue_depth` supported in a fresh capture.** `gta3dip1018/FINDINGS.md` 1.5 established Fin/Fen as
  GTA III's best-correlated-with-G quantity from its own arms. `gta3car1018/runs/c1-A1` is a different capture,
  from a different lane, taken for a different purpose (the in-car A/B) -- `fpsdiag.py analyze` finding the same
  swing there (13.6ms vs 2.5ms) independently reproduces the earlier result rather than re-reading the same data.
- **`tlb_walk_cost` now closes the scope gap section 2 item 2 left open.** That item was explicitly scoped away
  from "GTA III's owner-capture sustained dip or for any parked window." This lane's own tool reading that exact
  condition (1.1% of render-thread CPU) closes it; section 2 item 2 above has been edited to say so.
- **`gpu_saturation` closes the scope gap section 2 item 1 left open for Fable** (34% dip vs 3% good, not
  saturated) -- but **opens a new, unresolved tension for GTA III itself**: item 1's own GTA III figure is ~34%,
  flat between dip and good; `c1-A1`'s GTA III figure swings from 43% to 90%. `c1-A1`'s window set spans a parked
  segment and a driving segment (RT held) within one file, per `gta3car1018/NOTES.md` section 4's per-arm
  timestamps -- the swing may be real saturation, or it may be the driving segment's own, legitimately heavier
  scene pushing both busy% and fps at once, with the dip/good split just tracking which segment a window fell in
  rather than a saturation effect independent of content. `fpsdiag.py` has no `--since`/`--until` time-range
  filter to split `c1-A1` at the RT-down boundary and check which explanation holds; **this is named here as an
  open question for the next analysis pass, not resolved by this lane.** Section 2 item 1 above states this
  explicitly rather than either extending or quietly ignoring the contradiction.
- **`c7_art_gc_pause` refuted in all four captures**, closing it at the cost of one grep per capture, exactly as
  predicted in section 3's note that candidates 4 and 7 are the cheapest to check. Section 2 item 8 (above) records
  this as a new ruled-out item, scoped to these four captures' dip windows only.

`fpsdiag.py gaps`, run against the same `owner-play-1018` GTA III scope, correctly omits `tlb_walk_cost` and
`c7_art_gc_pause` from its output (both got a real verdict, not a gap) while listing every candidate that is
either perflog-tag-absent or needs `capture`'s periodic system samples -- confirming `gaps` is reading the same
verdicts `analyze` produces rather than a separate, divergent list. Run with no path argument, `gaps` prints the
full candidate list with a pointer to section 3's instrument column, for a user who has no capture in hand yet.

`gaps` was also run against the perflog-tier `gta3car1018/runs/c1-A1` capture specifically, to check whether
anything is a genuine gap even at the richest tier this lane has on disk. It names six: `c1_rpbrk_nondraw_breaks`
(the racy-emitter problem, section 2 item 6 -- no logcat tag fixes this, the emitter itself needs rebuilding
first), `c3_redo_shc_copy_bind_cost` (correlates but nothing times the copy/bind path), and
`c4_competing_process_cpu`/`c5_memory_page_cache_pressure`/`c6_thread_core_migration`/
`c8_surfaceflinger_backpressure` (all four need `fpsdiag.py capture`'s periodic `dumpsys`/`/proc` sampling, which
no capture on disk -- perflog or otherwise -- carries; a logcat alone, however detailed its perflog tags, cannot
answer them). None of the six is a free logcat-tag addition behind the perflog build tier: the first two need a
code fix (the racy emitter, a new timer) and the other four need the `capture` subcommand's own sampling, not a
new tag. **This is the step-5 trigger's answer**: there is nothing to add behind the perflog tier and queue a
build/run request for; the real next steps are (a) a fix lane for the racy `hakuX-rpbrk` emitter, named already as
the next lane's brief in section 5 below, and (b) an owner-play capture taken with `fpsdiag.py capture` itself
(`CAPTURE.md`, step 6), which exists precisely to produce the periodic samples c4/c5/c6/c8 need.

## 5. What this file does not do

Per the brief: this lane does not propose starting a fix. Candidates 1 and 2 (GTA III) are the closest to
"ready for a fix lane" -- candidate 1 already has a concrete file/function and a stated confirming measurement
(`gta3dip1018/FINDINGS.md` section 4); it is named here as the next lane's brief, not started. Everything else
needs the measurement in its own "confirming" column, taken by `fpsdiag.py analyze` against a real capture, before
any candidate is strong enough to hand to a fix lane.
