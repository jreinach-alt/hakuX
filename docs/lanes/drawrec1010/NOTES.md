# lane.drawrec1010 -- per-draw recording at the NFS Most Wanted race start (#433, 0.5)

Step 3 of `docs/lanes/nfs30plan1010/PLAN.md` (on lane/nfs30plan1010): cut the PFIFO
thread's per-draw recording cost by about a third. The census decides what gets built.

## 1. What is on master before this lane (read from the code)

`begin_pre_draw_inner()` takes one of three paths per draw:

- **SFP**, the super-fast path: nothing changed that it checks; no uniform update, no
  descriptor work.
- **MFP**: `update_shader_uniforms()` + `update_descriptor_sets()` only.
- **Full**: `create_pipeline()` (early hit if no generation moved; else bind textures if
  their generations moved, `bind_shaders()` if the shader generation moved, else
  `update_shader_uniforms()`; then `check_pipeline_dirty()`, `init_pipeline_key()` +
  memcmp against the bound pipeline, `fast_hash()` + LRU lookup), then setup and
  `update_descriptor_sets()`.

### 1.1 `shader_bindings_changed` is sticky (a candidate cost, to be measured)

- Set only in `pgraph_vk_bind_shaders()` when the state really differs
  (`hw/xbox/nv2a/pgraph/vk/shaders.c:2202`).
- Cleared only at the entry of `pgraph_vk_bind_shaders()` (`shaders.c:2149`), and
  saved/cleared/restored around the draw-queue replay (`draw.c` ~7516-7770).
- `bind_shaders()` runs only when `shader_state_gen` moved, the primitive mode changed,
  or `program_data_dirty`. So after a shader change, every following draw until the next
  shader-generation bump enters with the flag still true, and each of them:
  - misses SFP (`draw.c:5515`, `sfp_miss_shader_changed`) and MFP (`draw.c:5727`);
  - misses the `create_pipeline()` early hit (`draw.c:2463`);
  - has `check_pipeline_dirty()` true (`draw.c:2184`), so builds the key and memcmps it
    (a same-key hit);
  - has `need_new_ubo_set` true in `update_descriptor_sets()` (`shaders.c:906`, `:972`),
    so writes a fresh UBO descriptor set (`vkUpdateDescriptorSets`) every draw. The UBO
    binding is `UNIFORM_BUFFER_DYNAMIC` with range = the layout's total size, so a set
    written for a binding stays valid while the binding is the same; only the dynamic
    offsets move.
- The census measures this directly: `shc_in` (draws entering with the flag set),
  `shc_stale` (of those, the shader binding did not change), `shc_stale_full` (and the
  draw took the full path), and `ubo_sets_samesb` (a UBO set written though the binding
  did not change).

### 1.2 First cut from data already on disk (no new device time)

Run `1-1791649387-nfs30plan1010-2138210` (lane.nfs30plan1010, perflog, master at
ab1acc4154 in hw/, race start, route `nfs-mw-quickrace`). Per-60-frame `xemu-sfp`
counters, two windows at the race start:

| window | draws | SFP hits | first miss = shader changed | = uniforms | = non-dynamic regs |
|---|---|---|---|---|---|
| 1 | 85,037 | 355 (0.4%) | 41,536 (49%) | 26,088 (31%) | 10,245 (12%) |
| 2 | 118,814 | 504 (0.4%) | 50,047 (42%) | 39,554 (33%) | 21,991 (19%) |

Same run, `xemu-work` per frame: BE 947 draws, PBnd 196 (pipeline rebound on ~21%
of draws), SBnd 940. Phase (ms/frame): Draw 12.3 [Syn 2.5, Pipe 4.6 (Tx 1.3, Sh 2.8,
Lu 0.4), Desc 1.8, Setup 1.0, Mfp 1.0], Fin 12.6. `ubosz`: the vertex constants
c96-c107 were uploaded 52-72k times per 60 frames.

Reading: half the SFP misses are "shader changed" while only ~21% of draws rebind the
pipeline, which is what a sticky flag would produce. The census separates that from
real shader changes.

## 2. The census instrument (`HAKUX_DRAWCENSUS=1`, default off)

All in `hw/xbox/nv2a/pgraph/vk/draw.c`; no other file. Off, the cost is a byte store
per path taken in `begin_pre_draw_inner()`/`create_pipeline()` (which path, which
outcome) and one predictable branch per draw. On, a wrapper around `begin_pre_draw()`
snapshots state before and diffs it after, against the previous drawn draw:

- the shader and pipeline binding, vertex attribute/binding descriptions, the four
  bound textures (and direct surface views), the colour/zeta surface, the primitive;
- every PGRAPH register word, grouped: combiners/shader program/clip mode (rc), texture
  (rt), CSV0/CSV1 + point size (rl), blend/depth/raster static bits (rb), the bits in
  `pgraph_reg_dynamic_mask_table` (rd), uniform-fed (factors, fog, bump, eye: rf),
  window clip (rw), anything else (ro, with its top addresses);
- c[] by row; lighting/material by hash; the uploaded uniform bytes by hash of both
  layouts (the bytes `uniform_copy` produced).

Class per draw (first that applies): surf, shader, pipe, tex, reg, uni, dyn, same.
Decision per the brief: same+dyn+uni >= 50% -> reuse; else same >= 40% -> batching;
else stop.

Printed once per 60 frames under `hakuX-stall` (`census`, `census-bits`, `census-path`,
`census-cost`, `census-crow`, `census-mask`, `census-ro`); read with
`docs/lanes/drawrec1010/censusread.py <result dir>` (default window: mark-2 .. mark+13
for each `mark gameplay|goN`).

Cost when on: a diff of the 2,048-word register file (strided in `regs_`) and 192 c[]
rows per draw, ~2-3 us/draw estimated; it is a classification run, not a timing run.
Type-checked with host gcc and the dispatcher's NDK clang (NV2A_PERF_LOG 0 and 1).

## 3. simpleperf of the PFIFO thread

The brief asks for one `simpleperf record` of the PFIFO thread on the plain build over
two race starts. No lane-reachable path runs it: request.sh has no profiler option,
route.sh has no hook, and profile_guest.sh drives the device directly (lanes may not).
Asked on the board (`board-requests/drawrec1010.md`); no answer by the end of attempt 2.
It was not needed for the decision: the perflog phase split plus the `[rdc]` TLB-walk
counters below name the largest per-draw cost directly (section 5.3).

## 4. Runs

| id | what | build | result |
|---|---|---|---|
| 1-1791656193-drawrec1010-4097387 | census, race start, 12 starts, HAKUX_UNI_BULK/UBERCACHE/FOGCACHE=1 | perflog @ e7f2e720c8 | DONE; 12 marks, 68 windows, section 5 |
| 1-1791661636-drawrec1010-950252 | pixels B: 27-suite disc, F1-F3 + HAKUX_DRAWREC=1 | plain @ b10dcdb737 | DONE; section 10.1 |
| 1-1791661643-drawrec1010-951834 | pixels A: 27-suite disc, F1-F3 | plain @ b10dcdb737 | DONE; section 10.1 |
| 1-1791661643-drawrec1010-951926 | NFS race start, F1-F3 + HAKUX_DRAWREC=1, 500 s | perflog @ b10dcdb737 | DONE; section 10.2 |
| 1-1791661644-drawrec1010-952014 | NFS race start, F1-F3, 500 s | perflog @ b10dcdb737 | DONE; section 10.2 |
| 1-1791670433-drawrec1010-3707918 | NFS race start plain 1/4, off | plain @ b10dcdb737 | queued |
| 1-1791670434-drawrec1010-3708043 | NFS race start plain 2/4, ON | plain @ b10dcdb737 | queued |
| 1-1791670441-drawrec1010-3708870 | NFS race start plain 3/4, ON | plain @ b10dcdb737 | queued |
| 1-1791670442-drawrec1010-3709079 | NFS race start plain 4/4, off | plain @ b10dcdb737 | queued |
| 1-1791670443-drawrec1010-3709316 | pixels A recheck, 27-suite disc, runs 2 | plain @ b10dcdb737 | queued |
| 1-1791670444-drawrec1010-3709731 | pixels B recheck, 27-suite disc, runs 2 | plain @ b10dcdb737 | queued |

All F1-F3 runs carry `HAKUX_UNI_BULK=1 HAKUX_UNI_UBERCACHE=1 HAKUX_UNI_FOGCACHE=1`.
The first four were the pilot (24.7 min by the gate's estimate; ~8-9 min each on the
device). Its verdict is in `$DISPATCH_DIR/pilots/drawrec1010.ok`; the plain NFS runs went
in the order off, ON, ON, off (section 9), and the pixel recheck is section 10.1's.

## 5. Census result (run 1-1791656193-drawrec1010-4097387)

Reader output, whole: `census-1-1791656193.md` in this directory
(`censusread.py`, default window mark-2..mark+13 for each of the 12 marks). The player
is moving: `s1-g11.png` shows 64 mph, `s8-g11.png` 76 mph.

68 windows (4,080 frames), 4,749,007 draws, 1,164 draws/frame.

### 5.1 Class of each draw against the previous one (first that applies)

| class | % of draws | cum % |
|---|---|---|
| same (nothing changed) | 24.4 | 24.4 |
| dyn (dynamic state only) | 0.0 | 24.4 |
| uni (uniforms only) | 38.6 | 63.0 |
| reg (a key-feeding register) | 9.5 | 72.6 |
| tex | 15.6 | 88.2 |
| pipe | 0.2 | 88.4 |
| shader | 9.9 | 98.3 |
| surf | 1.7 | 100.0 |

**Decision: same+dyn+uni = 63.0% >= 50% -> step 2, reuse.** (same alone 24.4%, under
the 40% batching bar.)

Inputs changed, % of draws: shader binding 11.4, pipeline binding 11.6, vertex layout
8.3, texture 27.4, surface 1.7, primitive 1.2, c[] 57.8, uploaded uniform bytes 67.8;
registers: combiners 5.8, texture 27.4, CSV/point 9.5, blend/depth 3.0, dynamic-only
6.4, uniform-fed 0.3, window clip 0.7, other 21.8 (0x0FC4 CHEOPS_OFFSET 20.2,
0x0B10 3.1). c[] rows changed per draw: none 42.2%, 9-16 rows 46.6% (block c96-111 on
51% of draws: a per-draw transform). Commonest masks: c[]+uniform bytes 35.5%, nothing
24.4%, c[]+bytes+other reg 7.8%, texture 5.6%.

### 5.2 What the recorder does with them

| | % of draws |
|---|---|
| path SFP / MFP / full | 0.5 / 31.4 / 68.1 |
| create_pipeline: not entered / not dirty / same key / LRU / miss | 31.9 / 8.2 / 48.3 / 11.6 / 0.0 |
| bind_shaders called | 42.0 |
| entered with `shader_bindings_changed` set | 37.2 |
| ... binding had not changed (stale flag), all on the full path | 31.0 |
| UBO descriptor set written / ... binding unchanged | 37.2 / 25.8 |
| uniform bytes uploaded / ... same bytes, same binding | 72.0 / 4.1 |
| a same/dyn/uni draw on the full path | 36.1 |
| a "same" draw that missed SFP | 23.9 |

SFP first miss (same run, `xemu-sfp`): shader changed 36.6%, uniforms 32.9%,
non-dynamic register generation 24.1%, primitive 4.3%, no render pass 1.7%.

Reading: the stale `shader_bindings_changed` flag (section 1.1) is real and large:
31% of all draws take the full path and write a fresh UBO set only because of it. The
uniform change is inherent (a per-draw transform in c96-c111 on half the draws), so
"upload only dirty ranges" saves little at this scene; the reuse that is available is
in the path choice, not in the upload.

### 5.3 The largest per-draw cost is the vertex sync's TLB walk, not the key

Clean baseline, no census: lane.perdrawon1010's runs `1-1791645060-perdrawon1010-726861`
and `1-1791645063-perdrawon1010-728778` (perflog, F1-F3 on, `nfs-mw-quickrace`),
read with phaseread.py by that lane:

| window | Draw ms/frame | draws/frame | us/draw | Syn | Pipe (Sh) | Desc | Setup | Mfp | pace ms |
|---|---|---|---|---|---|---|---|---|---|
| countdown | 12.2 | 1,578 | 7.7 | 4.0 | 3.7 (1.7) | 0.5 | 1.0 | 1.0 | 44.2 |
| GO..+11.5 s | 9.4 | 1,085 | 8.7 | 2.9 | 3.2 | | | | |

F1-F3 already took Desc from 2.7 to 0.5 and Mfp from 3.9 to 1.0, so the brief's
Pipe/Desc/Mfp targets (written from the pre-F1-F3 runs 1-1791649387/88) are stale.
`Syn` (the vertex sync) is now the largest phase, and the `[rdc]` counters say what it
is. `vtx=` is the TLB walk that `sync_vertex_ram_buffer()` runs through
`physical_memory_dirty_bits_cleared()` each time a vertex range is found dirty
(calls/us/pages/entries reset), per 60 flips, first windows after `mark go2`:

| run | walks/60 flips | us | walks/flip | ms/flip | us/walk | entries reset/walk |
|---|---|---|---|---|---|---|
| 726861 (no census) | 14,379 | 232,528 | 240 | 3.88 | 16.2 | 1.0 |
| 726861 | 12,325 | 202,318 | 205 | 3.37 | 16.4 | 1.0 |
| 726861 | 9,453 | 160,257 | 158 | 2.67 | 17.0 | 1.0 |
| 726861 (warm) | 4,740 | 77,328 | 79 | 1.29 | 16.3 | 1.0 |
| 4097387 (census) | 14,543 | 225,634 | 242 | 3.76 | 15.5 | 1.0 |
| 4097387 | 12,061 | 189,214 | 201 | 3.15 | 15.7 | 1.0 |

Each walk scans every live TLB entry (~8,272; `HAKUX_TCG68_RD` already limits it to the
live modes) to re-arm about one entry. At the cold start that is 3.4-3.9 ms per flip of
the 4.0 ms `Syn`, a third of the 12.2 ms recording. lane.dirtytlb (#575) priced the
span and live-mode variants of the walk and left "one walk per flip with a pending
bitmap" unpriced; that is what step 2 adds.

## 6. Step 2 plan, ranked by expected impact (probability x win at the race start)

| part | what | win if it works | P | evidence for P |
|---|---|---|---|---|
| V | vertex sync: clear the bits and copy, but owe the TLB re-arm to a pending bitmap walked once per flip (or after a re-upload budget); a page owed a walk is re-copied on every touch until walked, and once more after | ~2.5-3.5 ms/frame cold, ~1 ms warm | 0.6 | the walk is 3.4-3.9 of 4.0 ms Syn (5.3); the unknown is how often a page is re-touched before the flip, which the new counters measure |
| R1 | clear the stale `shader_bindings_changed` once the full path has consumed it | ~0.5-1 ms/frame | 0.6 | 31% of draws on the full path for it alone (5.2); what they save is the key build + memcmp, setup and a UBO set write each |
| R3 | texture-only changes skip the shader-state rebuild | ~0.3-0.5 ms/frame | 0.3 | 27% of draws change texture, 11% change binding; needs the glsl state code, outside territory |
| R4 | CHEOPS_OFFSET off the generations | ~0 | | its draws also change uniforms, so they miss SFP anyway (5.1) |

V and R1 go behind `HAKUX_DRAWREC=1` with per-part disables
(`HAKUX_DRAWREC_VTX=0`, `HAKUX_DRAWREC_SHC=0`). Push constants for the dynamic offsets:
not built, the dynamic-only class is 0.0%.

## 7. Why attempts 1 and 2 did not finish

Attempt 1 built the census instrument and reader, queued the census arm
(1-1791656193) and ended correctly on `WAITING` with that run id: a headless session
cannot wait 90 minutes for a device run. The run is DONE; attempt 2 starts from its
result.

Attempt 2 read the census (section 5), built step 2 (section 8, b10dcdb737), registered
both predictions (section 9, f789451fec), queued the pilot runs (section 4) and ends on
`WAITING` with their ids, for the same reason.

Attempt 3 found all four pilot runs DONE. Attempt 2 had not failed: it ended on a
`WAITING` naming four dispatch runs, which is a finished session for a headless lane, and
lanewaker resumed it when they were DONE. Attempt 3 read them (section 10), queued the
plain A/B and the pixel recheck, and builds the walk-cost follow-up (section 11) while
those run.

## 8. Step 2 as built (b10dcdb737, draw.c only)

`HAKUX_DRAWREC=1`, default off; `HAKUX_DRAWREC_VTX=0` and `HAKUX_DRAWREC_SHC=0` turn
one part off alone. Logcat (`hakuX-stall`): `[drawrec1010] drawrec=%d vtx=%d shc=%d`
once at start, and every 60 flips with the switch on
`[drawrec] f=<flips> vtx dirty=<ranges> redo=<REDO-only copies> redoKB= walks=<FLIP>+<BUDGET> runs= pages= shc=<flags consumed>`.

- **VTX.** `sync_vertex_ram_buffer()` still test-and-clears `DIRTY_MEMORY_NV2A` over
  each range and copies it. It no longer calls `physical_memory_dirty_bits_cleared()`
  per range; the range's pages go into two bitmaps, OWED (bits cleared, TLB not yet
  re-armed) and REDO (copy on every touch whatever the bits say, because until the
  re-arm a guest store may set no bit). OWED is walked once per flip (first sync after
  `g_nv2a_stats.frame_count` moves) and early when REDO-only copies pass 32 copies or
  256 KB, in runs merged across gaps of <= 16 pages, at most 8 runs per batch (the rest
  one span). A page copied after its walk with its bits clean leaves REDO.
  `has_dirty_vertex_pages()` reports a REDO page as dirty.
- **SHC.** After a full-path draw whose `create_pipeline` exit was SAMEKEY, or LRU with
  a valid pipeline, `shader_bindings_changed` is cleared after
  `update_descriptor_sets()`. That is what a no-change `bind_shaders()` leaves; the
  flag is set again by the next real binding change.

Why the deferred re-arm is safe (read from the code, not measured): the NV2A client's
bits are the only ones the walk re-arms for the vertex sync. `surface.c`'s NV2A
test-and-clear is unreachable under TCG; the texture path (`NV2A_TEX`) does its own walk;
code pages are protected by `tlb_protect_code` independently. A store the deferred walk
lets through without a bit lands on a REDO page, which is copied on its next touch.

Host gcc and NDK clang build it clean (the `-Wshift-negative-value` warnings are the
existing `TARGET_PAGE_MASK` lines).

## 9. Predictions and the judge

- `docs/testing/predictions/drawrec1010-pixels.json`: the 27-suite disc, switch on vs
  off, byte-identical (`must_not_move` every suite). Known noisy captures (Stencil
  REPLACE*, GeometrySuperscreen_*) are named in the prose with a 3-run recheck if they
  move. Judge: `ab_compare.py --a <A> --b <B> --expect` it, and the switch line in both
  logcats.
- `docs/testing/predictions/drawrec1010-nfs.json`: the NFS race start, F1-F3 on in both
  arms, one perflog run and two plain runs per state, judged by `drawread.py` here.
  Legs: V (12 marks, no fatal, switch line matches the env, >= 15 countdown pace lines
  per state); R (`[rdc]` vtx walks/flip ON <= 20, OFF >= 100); U (perflog us/draw ON/OFF
  in [-35%, -15%], ON Syn <= 2.0 ms/frame); P (plain warm pace ON - OFF in [-7, -1]
  ms/frame); H (plain warm v2 share +5 points or more); T (the brief's numbers: warm ON
  <= 38, cold ON <= 52, v2 +10) reported, not judged. P(R) 0.8, P(U) 0.6, P(P) 0.5,
  P(H) 0.5. The brief's -30% us/draw is the top of U's range, not its point: F1-F3 already
  took Desc and Mfp (5.3), so what is left for this lane is Syn's walks and the SHC paths.
- Baseline read with `drawread.py` from perdrawon1010's perflog runs 726861 + 728778:
  warm countdown pace 43.5 ms/frame, v2 41.6%, `[rdc]` 161 walks/flip warm (2.58 ms),
  234 cold (3.82 ms); 7.72 us/draw at 1,578 draws/frame.

Both are env A/Bs on one ref, which `arms.sh` skips (a_ref == b_ref); the lane queues
them itself.

## 10. Pilot results (attempt 3)

### 10.1 Pixels, 27-suite disc (A 1-1791661643-drawrec1010-951834, B 1-1791661636-drawrec1010-950252)

`ab_compare.py --a A --b B --expect drawrec1010-pixels.json`: 1,060 captures each, 1,053
byte-identical, 7 moved, so the verdict is FAIL as written:

| capture | A (off) | B (ON) | reading |
|---|---|---|---|
| Stencil/Stencil_ZERO_ST | 0 | 30,000 | not named as noise in the prediction; explained below |
| Vertex_shader_rounding_tests/GeometrySuperscreen_0.0010 | 800 | 400 | named noise; better |
| .../GeometrySuperscreen_0.4999 | 0 | 800 | named noise |
| .../GeometrySuperscreen_0.5000 | 0 | 400 | named noise |
| .../GeometrySuperscreen_0.5626 | 570 | 0 | named noise; better |
| .../GeometrySuperscreen_0.9990 | 0 | 285 | named noise |
| .../GeometrySuperscreen_1.0000 | 0 | 285 | named noise |

Stencil_ZERO_ST, region by region: the 30,000 px are three quarters of the 200x200 test
square (rows 140-339, cols 220-419), red (the golden) in A and black in B. That is the
same flip, the same size and the same place as the named Stencil_REPLACE* noise. Over the
35 earlier 27-suite runs in `results/` without this switch (11 apks), this capture read
30,000 in 32 and 0 in 3, and the 0s came from apks that also read 30,000 in other runs
(ba0eafaead0a 8/1, 8d38739bc784 6/1, d71bf14ee8af 1/1). B has the usual value; A has
the rare one. The prediction's own rule is a runs=3 recheck for named-noise moves, so both
arms were requeued with runs 2 each (3 per arm with the pilot): 3709316 (A), 3709731 (B).
Logcat: B `[drawrec1010] drawrec=1 vtx=1 shc=1`, A `drawrec=0 vtx=0 shc=0`.

### 10.2 NFS perflog (ON 1-1791661643-drawrec1010-951926, off 1-1791661644-drawrec1010-952014)

Both: 12 marks, no fatal signal, switch line agrees with the env, and a moving car in
every `s*-g11.png` (30-96 mph). Same cars, barriers, road and HUD in each frame, ON and
off. `drawread.py`, countdown windows [mark-2, mark+1.5]:

| state | draws/frame | us/draw | Draw | Syn | Pipe (Sh) | Desc | Setup | Mfp | warm pace ms (n) | v2 | [rdc] vtx walks/flip, ms/flip |
|---|---|---|---|---|---|---|---|---|---|---|---|
| off | 1,603 | 7.77 | 12.45 | 3.97 | 3.84 (1.75) | 0.53 | 1.06 | 0.98 | 42.9 (12) | 46.0% | 157 warm, 2.47 |
| ON | 1,614 | 6.16 | 9.93 | 1.91 | 2.96 (1.11) | 0.21 | 1.05 | 1.77 | 41.9 (14) | 49.3% | 64 warm, 0.96 |

Cold start (one window per run): off 65.6, ON 43.4 ms/frame; n=1 each, not read.

Legs (the pilot is one perflog run per state, so V is VOID until the plain runs land):
U PASS (-20.8%, Syn 1.91 <= 2.0); R FAIL ON (64-66 walks/flip, predicted <= 20);
P PASS on perflog (-1.0 ms/frame, the edge of [-7, -1]); H FAIL on perflog (+3.3 points).

What R's failure says. The `[drawrec]` line (ON, n=134 windows, per flip): dirty 136.5
ranges, REDO-only copies 288.2 (1,555 KB), walks 0.78 at the flip + 8.61 by budget, runs
52.1. The budget walks are the walk cost left: each batch makes ~5.5
`physical_memory_dirty_bits_cleared()` calls, one per run, and each call scans the
whole TLB (~15 us) whatever its length. So the walks fell from 157 to 64 per flip, not
to ~1: the forced re-copies of owed pages trip the 32-copy budget ~9 times a flip, and
each batch pays one scan per run. This is the refutation the prediction named for R
("the budget walks fire as often as..."), in part: they fire less often than the walks
they replace, but far more than once per flip.

SHC moved draws from the full path to MFP as intended: Pipe -0.88, Desc -0.32, Mfp +0.79
ms/frame; net ~-0.4.

## 12. Do not repeat

- Do not `cd` out of the worktree in a Bash call: the session's working directory follows.
- `phaseread.py` takes `--window=-2,13` (with the equals sign); `-2,13` as a separate
  argument is read as an option.
- The vertex-sync counters `Vsyn` are on the overlay only, not in logcat; the `[rdc]`
  line is the logcat source for the walk cost.
