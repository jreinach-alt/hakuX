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
| 1-1791670433-drawrec1010-3707918 | NFS race start plain 1/4, off | plain @ b10dcdb737 | DONE; 12 marks |
| 1-1791670434-drawrec1010-3708043 | NFS race start plain 2/4, ON | plain @ b10dcdb737 | DONE; 12 marks |
| 1-1791670441-drawrec1010-3708870 | NFS race start plain 3/4, ON | plain @ b10dcdb737 | DONE; 12 marks, section 14 |
| 1-1791670442-drawrec1010-3709079 | NFS race start plain 4/4, off | plain @ b10dcdb737 | DONE; 12 marks, section 14 |
| 1-1791670443-drawrec1010-3709316 | pixels A recheck, 27-suite disc, runs 2 | plain @ b10dcdb737 | DONE; section 15 |
| 1-1791670444-drawrec1010-3709731 | pixels B recheck, 27-suite disc, runs 2 | plain @ b10dcdb737 | DONE; section 15 |
| 1-1791672296-drawrec1010-4030728 | Addendum 1 probe, NFS race start, base | plain @ bf43e8c4ef | DONE; section 16 |
| 1-1791672298-drawrec1010-4031146 | Addendum 1 probe, NFS race start, SNAPQ=1 | plain @ bf43e8c4ef | DONE; section 16 |
| 1-1791672299-drawrec1010-4031484 | Addendum 1 probe, NFS race start, NULLREC | plain @ bf43e8c4ef | DONE; section 16 |
| 1-1791672301-drawrec1010-4032023 | Addendum 1 probe, NFS race start, SNAPQ=2 | plain @ bf43e8c4ef | DONE; section 16 |
| 1-1791672303-drawrec1010-4032671 | Addendum 1 probe, NFS race start, SNAPQ=2 | plain @ bf43e8c4ef | DONE; section 16 |
| 1-1791672305-drawrec1010-4033552 | Addendum 1 probe, NFS race start, NULLREC | plain @ bf43e8c4ef | DONE; section 16 |
| 1-1791672307-drawrec1010-4034091 | Addendum 1 probe, NFS race start, SNAPQ=1 | plain @ bf43e8c4ef | DONE; section 16 |
| 1-1791672308-drawrec1010-4034875 | Addendum 1 probe, NFS race start, base | plain @ bf43e8c4ef | DONE; section 16 |

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

Attempt 3 did not finish for the same reason: it built the Addendum 1 probes (section
13), registered their prediction, and queued 12 runs (2 plain NFS, 2 pixel rechecks,
8 probe arms; section 13's status line says 11, but `WAITING` lists 12). About 2 h of
Nova time cannot fit in one headless session, so it ended on `WAITING` with their ids.
Attempt 4 found all 12 DONE. It merged master (b74cff74ed), read them (sections 14-16),
wrote the verdicts and recommendations (section 17), removed `WAITING`, and marks the
PR ready.

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

## 11. Walk-cost follow-up: one TLB scan per batch (`tlbmap.mbox`, parked, not measured)

R's failure (10.2) is the cost of one `tlb_reset_dirty()` scan per merged run: the scan
visits every live TLB entry (~8,300) and tests each against `[start, start+length)`, so
a 1-page run costs the same ~15 us as a 4 MB one. The batching already decides WHEN to
walk; what is left is that each batch walks ~5.5 times.

`tlbmap.mbox` (local commit 5980d1b4b5 on `lane/drawrec1010-tlbmap`, not pushed to this
branch) gives a batch one scan: `tlb_reset_dirty_bitmap(cpu, start, length, bmp, bit0)`
is the same locked walk with a `test_bit()` of the entry's page in the OWED bitmap,
and `physical_memory_dirty_bitmap_cleared(base, bmp, first, last)` runs it once per
vCPU over `[first, last)` of OWED. `tlb_reset_dirty()` becomes the walk with a NULL
bitmap, which the always-inlined body folds away, so the existing callers are unchanged.
`HAKUX_DRAWREC_MAP=0` restores the per-run walk; it is inside `HAKUX_DRAWREC=1`.

Expected from 10.2's counters, not measured: 9.4 batches/flip, so ~10 scans for the
owed pages instead of ~52, plus the ~12/flip by which `[rdc]` walks (64) exceed the
batch's runs (52.1), not identified; ~20 walks/flip and ~0.3 ms/flip against 64 and 0.96 (run 951926), ~-0.65
ms/flip. That is also what R predicted (<= 20).

It edits `accel/tcg/cputlb.c`, `system/physmem.c`, `include/exec/cputlb.h` and
`include/system/physmem.h`, none on this lane's row. The board request is in
`$DISPATCH_DIR/board-requests/drawrec1010.md` (2026-10-10 ~15:25 PDT), unanswered when
attempt 3 moved on to Addendum 1. Host gcc and NDK clang build it clean. The next lane
with those four files can `git am docs/lanes/drawrec1010/tlbmap.mbox` and run it as
an env A/B (`HAKUX_DRAWREC=1` with `HAKUX_DRAWREC_MAP=0` vs unset) on the NFS route.

## 12. Do not repeat

- Do not `cd` out of the worktree in a Bash call: the session's working directory follows.
- `phaseread.py` takes `--window=-2,13` (with the equals sign); `-2,13` as a separate
  argument is read as an option.
- The vertex-sync counters `Vsyn` are on the overlay only, not in logcat; the `[rdc]`
  line is the logcat source for the walk cost.
- A `--runs 2` request measures the band inside one request only. `ab_compare.py`
  called GeometrySuperscreen_0.5626 "ATTRIBUTABLE" because each recheck request agreed
  with itself. Across requests the capture took three different images, and one of
  them appeared in both arms (section 15). Hash the capture across every run of both
  arms before reading a named-noise move as the switch.
- A pace floor under 33.3 ms cannot be measured at the NFS race start. The title
  presents at v2, so `hakuX-pace` stops at the vblank period. Do not predict a pace
  floor below it (section 16, `P_floor`). If the vCPU's own floor is the question, read
  the vCPU's busy ms/frame.

## 13. Addendum 1: what a recorder thread would buy (probes, default off, measurement only)

lane.local's Addendum 1 (2026-10-10 15:12 PDT) asks three things before anyone builds a
recorder thread that takes pipeline, descriptor, uniform and recording work off PFIFO:
the floor PFIFO reaches without that work, what the handoff costs, and how often PFIFO
waits on the GPU mid-frame. Every switch stays default off and is never proposed for
default.

**The switches (draw.c, ff6c3adc47 and 0a4976ece0):**

- `HAKUX_PROBE_NULLREC=1`, the floor. `flush_draw_one_pass` keeps what a recorder
  design leaves on PFIFO: attribute bind, vertex-RAM sync, remap, primitive rewrite,
  texture upload (`poll_bound_textures` and a `bind_textures` when the generations
  moved), and the inline vertex/index uploads into the staging buffers. It skips
  `begin_pre_draw` (pipeline, uniforms, descriptors), `begin_draw`, the `vkCmd*` and
  `end_draw` with a `goto` to each branch's `*_done` label. The surface update is in
  `pgraph_vk_draw_begin` and clears still take the full path, so surface/finish ordering
  and the skew bound are unchanged. `pgraph_vk_ensure_command_buffer` is still called, so
  that `pgraph_vk_finish` submits and rotates and the staging buffers reset as before.
  Pixels are wrong: the frames show only clears.
- `HAKUX_PROBE_SNAPQ=1`, the upper bound on the handoff. The real path runs unchanged.
  In addition, `pgraph_vk_draw_end` copies a full `RenderCommandSnapshot` (~40 KB:
  32 KB of `regs_`, the program, the vertex constants, the attributes) plus the draw's
  payload (the inline array/buffer/elements) into an 8 MB ring. It then enqueues an
  `RCMD_DRAW` to the render thread, which frees it (`default: break`).
  `try_snapshot_draw_arrays` / `try_snapshot_inline_elements` were not used as the
  addendum named them, because they run `begin_pre_draw` and store its OUTPUTS (pipeline,
  descriptor set, uniforms). That is the split a recorder moving pipeline and descriptor
  work cannot use, and calling them on PFIFO would charge the moved work twice.
- `HAKUX_PROBE_SNAPQ=2`, the lower bound. As 1, but the record is
  `sizeof(ReorderWindowEntry)` (~0.7 KB) of `regs_`. That is what a recorder fed by
  dirty deltas would copy.
- `HAKUX_PROBE_WAITS=1` (on in every arm; NULLREC and SNAPQ imply it) times every
  GPU wait on the PFIFO thread in `pgraph_vk_finish`:
  - the non-deferred `qemu_event_wait(finish_event)`;
  - the rotation's `vkWaitForFences(frame_fences[next])`.
  A non-deferred finish is always a point; a rotation wait is a point if >= 100 us.
  FLIP_STALL/PRESENTING finishes count as the flip; every other reason is mid-frame.
  It prints `[probe1010]` on hakuX-stall every 60 flips, with mid/frame, ms each, a
  0/1/2/3/4+ histogram, non-deferred finishes by reason, rotation waits, draws, and the
  snapshot's KB/copy us/enqueue us (1 in 8 draws timed).

**Arms** (`drawrec1010-probe.json`, refs `bf43e8c4ef` on `lane/drawrec1010-probe`:
the probes merged with reportasync1010 @ 0f6326deac, whose `HAKUX_REPORT_ASYNC=1`
the addendum asks for). Plain build, 500 s, two runs each of base / NULLREC / SNAPQ=1 /
SNAPQ=2, interleaved (section 4). Every arm carries F1-F3, `HAKUX_DRAWREC=1`,
`HAKUX_REPORT_ASYNC=1`, `HAKUX_TEXSCAN=1`, `HAKUX_FRAMETRACE=1`,
`HAKUX_PROBE_WAITS=1`, and pulls `frametrace_*.csv`. 8 x (500 s + 90 s) ~79 min,
inside the addendum's 1.5 h.

**Judge:** `proberead.py` over the warm countdown (go2..go12, [mark-2, mark+1.5]) gives,
per arm:
- pace ms/frame;
- vCPU busy/idle per frame (rr425w windows inside [mark-4, mark+1.5]);
- the `[probe1010]` lines;
- ftwin's per-frame table.

Verdict as registered:
- BUILD = floor <= 28 and SNAPQ=1 - base <= 2 and base mid <= 1/frame;
- DO NOT BUILD = floor > 33, or SNAPQ=2 - base > half of (base - floor).

The lower bound decides DO NOT BUILD, so that a 40 KB copy no design would ship cannot
by itself kill the design.

Baseline before any probe ran, plain off 3707918 (b10dcdb737, F1-F3 only, no
REPORT_ASYNC/TEXSCAN): warm 39.2 ms/frame. vCPU busy 24.1 and idle 15.7 ms/frame (61%
busy; vcpuread over [mark-4, mark+1.5]).

Attempt 3 ended here, waiting on 12 runs. All 12 are read in sections 14-16.

## 14. Plain A/B, two runs per state (attempt 4)

Runs on b10dcdb737, plain build, F1-F3 in both states, queued in the order off, ON,
ON, off:
- off: `1-1791670433-drawrec1010-3707918`, `1-1791670442-drawrec1010-3709079`;
- ON: `1-1791670434-drawrec1010-3708043`, `1-1791670441-drawrec1010-3708870`.

All four have 12 marks, no fatal signal, and the switch line matching the env. Every
one of the 48 `s*-g11.png` frames shows a moving car: sparks, traffic, and the
speedometer at 42-94 mph.

`drawread.py --expect drawrec1010-nfs.json` over these four runs and the perflog pilot
pair (951926/952014):

| | off | ON | ON - off |
|---|---|---|---|
| warm countdown pace, ms/frame (pooled; per run) | 38.8 (39.2, 38.5) | 37.3 (37.4, 37.2) | -1.5 |
| warm v2 share | 66.1% | 75.3% | +9.2 points |
| cold countdown pace (one line per run) | 49.1 (43.3, 54.9) | 49.0 (47.7, 50.3) | not read |
| `[rdc]` vtx walks/flip, warm | 165.8 (2.62 ms) | 66.5 (0.99 ms) | -60% |
| us/draw, perflog pilot | 7.77 | 6.16 | -20.8% |

`[drawrec]` per flip, ON (3 runs): 136-142 dirty ranges, 286-289 REDO-only copies,
0.8-1.0 flip walks plus 8.4-8.6 budget walks, 52-55 runs. These are the same in every
run.

Legs:
- V PASS;
- **R FAIL**: 68.1 walks/flip, against <= 20 predicted;
- U PASS: -20.8%, Syn 1.91;
- P PASS: -1.5 in [-7, -1];
- H PASS: +9.2 >= 5.

**VERDICT: REFUTED**, on R alone. Every speed leg passed. The mechanism's size was wrong:
deferring the walk removes 60% of the walks, not 88%. Section 10.2 gives the reason (one
full-TLB scan per merged run in each budget batch), and `tlbmap.mbox` (section 11) is
the fix. It is still parked: the board request has no answer.

The brief's T targets (reported, not judged):
- warm ON 37.3 <= 38: met;
- cold ON 49.0 <= 52 (n=2): met;
- v2 +9.2 >= 10: not met.

## 15. Pixel recheck: three runs per arm (attempt 4)

The recheck is A `1-1791670443-drawrec1010-3709316` and B
`1-1791670444-drawrec1010-3709731`, runs 2 each. With the pilot pair that is three runs
per arm. The switch line is `drawrec=0 vtx=0 shc=0` in both A logcats and
`drawrec=1 vtx=1 shc=1` in both B logcats.

`ab_compare.py --a 3709316 --b 3709731 --expect drawrec1010-pixels.json`:
- 1,059 of 1,060 captures are byte-identical between the arms;
- GeometrySuperscreen_0.5626 reads 285 px in both A runs and 570 in both B runs;
- the tool calls that move "ATTRIBUTABLE" and gives **VERDICT: FAIL** on it.

The capture's sha256, every run:

| run | arm | GeometrySuperscreen_0.5626 | px | Stencil_ZERO_ST |
|---|---|---|---|---|
| 951834 (pilot) | A off | 0cf84e6cea8f | 570 | d3b4d0470b61 (0 px, the rare one) |
| 3709316 run 1 | A off | 42eb3edd3567 | 285 | 246921161bac |
| 3709316 run 2 | A off | 42eb3edd3567 | 285 | 246921161bac |
| 950252 (pilot) | B ON | 9c6f4705adce | 0 | 246921161bac |
| 3709731 run 1 | B ON | 0cf84e6cea8f | 570 | 246921161bac |
| 3709731 run 2 | B ON | 0cf84e6cea8f | 570 | 246921161bac |

How to read it:
- **GeometrySuperscreen_0.5626 is the prediction's named noise.** Each arm produced two
  different images over its three runs. One image (0cf84e6c, 570 px) appears in both
  arms. The two runs of one request agree with each other, but different requests do
  not, so the tool's within-request band is too narrow to call this the switch.
- **Stencil_ZERO_ST**, the pilot's one unnamed move, is byte-identical in five of six
  runs, in both arms. The pilot's A run had the rare image (section 10.1).

Under the registered rule, "a move there gets a runs=3 determinism check of both arms
before it is read as the switch", **the pixel leg passes: no capture moves with the
switch.** The tool's one-pair FAIL is recorded here and in PR.md, not overridden.

## 16. Addendum 1 results: the recorder-thread probes

Eight runs on bf43e8c4ef, plain build, apk 0a0ff13f1271, two per arm, interleaved
(section 4). Every arm carries F1-F3, `HAKUX_DRAWREC=1`, `HAKUX_REPORT_ASYNC=1`,
`HAKUX_TEXSCAN=1`, `HAKUX_FRAMETRACE=1` and `HAKUX_PROBE_WAITS=1`. All eight have 12
marks, no fatal signal, the probe line matching the env, `drawrec=1`, and a frametrace
CSV.

The g11 frames of the base, SNAPQ=1 and SNAPQ=2 runs (72 frames) all show a moving car.
NULLREC's frames show only clears, as designed, so they cannot show the car. Its route
reached all 12 marks with 39 warm pace lines.

Read with `proberead.py --expect drawrec1010-probe.json`.

**Warm countdown** (go2..go12, [mark-2, mark+1.5]):

| arm | pace ms/frame (per run) | v2 | ftwin P mean / p50 / p95 | late | frame class | vCPU busy / idle ms/frame | PFIFO run / idle | gpu |
|---|---|---|---|---|---|---|---|---|
| base | 34.2 (34.3, 34.1) | 63.5% | 34.4 / 33.3 / 47.6 | 68% | run 50%, vsync 32% | 24.6 / 9.6 (72% busy) | 16.8 / 16.0 | 9.7 |
| NULLREC | **33.5** (33.6, 33.5) | 96.0% | 33.5 / 33.4 / 35.6 | 9% | vsync 91% | 19.1 / 14.4 (57% busy) | 11.3 / 24.7 | 0.2 |
| SNAPQ=1 | 38.5 (39.4, 37.8) | 61.7% | 40.9 / 40.0 / 56.5 | 95% | run 74% | 28.4 / 10.4 (73%) | 23.0 / 13.9 | 11.4 |
| SNAPQ=2 | 37.6 (36.7, 38.6) | 66.3% | 39.4 / 38.9 / 51.9 | 86% | run 56% | 27.8 / 9.7 (74%) | 21.2 / 14.2 | 11.5 |

ftwin read 946 SNAPQ=1 frames, against 1,957-2,300 for the other arms. The pace column
uses its 30 pace lines.

**Cold start** (`gameplay`; one pace line per run, two for NULLREC; thin):

| arm | pace ms/frame (per run) | ftwin P mean / p50 / p95 (frames) |
|---|---|---|
| base | 38.7 (39.4, 37.9) | 41.0 / 39.5 / 57.8 (171) |
| NULLREC | 34.0 (34.1, 33.8) | 33.8 / 33.5 / 37.3 (207) |
| SNAPQ=1 | 47.4 (47.3, 47.5) | 52.0 / 50.4 / 70.1 (68) |
| SNAPQ=2 | 48.7 (47.0, 50.4) | 51.2 / 49.9 / 72.4 (136) |

**Mid-frame GPU waits on the PFIFO thread**, base arm, `[probe1010]`:

| | waits/frame | ms each | ms/frame | frames with 0 / 1 / 2 / 3 / 4+ waits |
|---|---|---|---|---|
| warm (2,280 frames) | 0.49 | 3.68 | 1.82 | 1793 / 191 / 128 / 75 / 93 |
| cold (120 frames) | 1.32 | 2.70 | 3.56 | 66 / 17 / 14 / 6 / 17 |

Almost all of them are rotation fence waits: `vkWaitForFences` on the command-buffer
ring's next fence for >= 100 us, 0.49/frame and 1.80 ms/frame warm. Non-deferred
finishes are 0.00-0.02/frame. So these are not reads of a result the GPU produced this
frame. PFIFO has filled the ring and waits for the GPU to retire a buffer. A recorder
thread feeding the same ring would block at the same points. reportasync1010's
frametrace pair was not on master when this was read, so these numbers are from this
lane's base arm only.

**The handoff** (1 draw in 8 timed):

| arm | record | copy us/draw | enqueue us/draw | ms/frame |
|---|---|---|---|---|
| SNAPQ=1 | 41.2 KB | 1.99 | 3.93 | 7.76 |
| SNAPQ=2 | 1.2 KB | 0.38 | 3.49 | 5.36 |

The enqueue costs about 90% of the handoff, and the copy about 10%. The pace deltas are
+4.3 (SNAPQ=1) and +3.4 (SNAPQ=2) ms/frame. Per run the two bounds overlap: 37.8-39.4
against 36.7-38.6.

**Verdict, as registered: DO NOT BUILD.** Both clauses hold:
- floor 33.5 > 33;
- SNAPQ=2 +3.4 > 0.5 x (34.2 - 33.5) = 0.35.

- **What holds the floor: vblank.** The 33.5 ms floor is the title's v2 present period:
  96% of NULLREC's warm frames are at v2, and 91% are classed vsync. The vCPU does not
  hold it: it is busy 19.1 ms/frame, under the ~25-27 ms the addendum anticipated. The
  waits do not hold it either: 0.06 ms/frame in NULLREC. So the first clause fires
  because the floor *is* 33.3 ms, not because it is above it. A perfect recorder would
  reach 30 fps.
- **Warm, the base is already there:** 34.2 ms/frame, p50 33.3. The most a recorder could
  win is 0.7 ms/frame, against a handoff of 3.4-4.3 ms/frame through the existing queue.
  Even a copy-only handoff costs 0.5 ms/frame (0.38 us x 1,382 draws).
- **Cold, the gap is real but mostly GPU:** base - floor = 4.7 ms/frame (pace, n=2) to
  7.2 (ftwin mean). Of that, 3.56 ms/frame is the ring's GPU waits, which a recorder
  still pays. NULLREC removes them only because its command buffers carry no draws. The copy alone is
  0.65 ms/frame at 2,016 draws. That leaves about 0.5-3 ms/frame at the cold start for a
  design priced at 15-25 lane-days.

BUILD fails on two counts: the floor is not <= 28, and SNAPQ=1 +4.3 is not <= 2. The
mid-wait count, 0.49/frame warm, passes BUILD's at-most-one bar. At cold it is
1.32/frame, which does not.

The registration's point ranges:
- `P_base` 34.2 in [33, 40];
- `P_floor` 33.54 **out** of [25, 33]: the prediction did not allow for the v2 cap;
- `P_snapq_d` 4.3 in [1.5, 7];
- `P_snapq2_d` 3.38 **out** of [0.2, 3.0]: the enqueue, not the copy, costs;
- `P_mid` 0.49 in [0, 2].

**Context, not an A/B.** With every switch on (F1-F3, DRAWREC, REPORT_ASYNC, TEXSCAN),
the probe base arm runs the warm countdown at 34.2 ms/frame and the cold start at 38.7.
Section 14's ON arm, without REPORT_ASYNC and TEXSCAN, ran 37.3 warm on b10dcdb737. The
refs differ (bf43e8c4ef merges reportasync1010), so the -3.1 ms is not attributed here.

## 17. Recommendations (attempt 4)

- **`HAKUX_DRAWREC=1`: default-on after one title screen, not now.** It does what the
  speed legs predicted:
  - -1.5 ms/frame warm and +9 points of v2 (2 plain runs per state);
  - -21% us/draw (perflog pilot);
  - no capture moves on the 27-suite disc in 3 runs per arm.

  The registered verdict is still REFUTED on R. And VTX changes when vertex pages are
  re-armed, on a correctness argument read from the code (section 8). Only NFS's race
  start and the disc have exercised it. The check before a flip: a Nova screen of the
  Playable titles with the switch on against off, with frames region-compared and no new
  fatal signal. A missed vertex copy shows as broken geometry in a title that writes
  vertex buffers with the CPU mid-frame, and neither workload here isolates that.
- **perdrawon1010's three (`HAKUX_UNI_BULK/UBERCACHE/FOGCACHE`): yes, default-on,** as
  perdrawon1010 recommends. This lane ran them in both arms of every run: 15 NFS runs
  with no fatal signal, and 6 pixel-disc runs. That is stability evidence only; it adds
  no measurement of their effect.
- **Probe switches: never default**, as the addendum says. Their verdict is DO NOT
  BUILD the recorder thread (section 16).
- **For the next lane at the cold start:** the cold frame is GPU ring back-pressure
  (3.56 ms/frame of fence waits), PFIFO lock waits (lockw 9.0 ms/frame in the base
  arm's cold frames), and the vertex walks `tlbmap.mbox` would cut (~0.65 ms/flip
  expected, unmeasured). Warm, the race start is at vblank. A per-draw CPU change there
  shows up as v2 share, not as pace.
