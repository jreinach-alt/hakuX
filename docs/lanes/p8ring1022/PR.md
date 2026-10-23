# p8ring1022: the submit ring length is a runtime value, 2..8 from HAKUX_RING; arrays sized to a capacity of 8 (#433)

State: draft

Lane: p8ring1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p8ring1022/PR.md, hw/xbox/nv2a/pgraph/vk/buffer.c, hw/xbox/nv2a/pgraph/vk/command.c,
hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h,
hw/xbox/nv2a/pgraph/vk/reports.c, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c,
hw/xbox/nv2a/pgraph/vk/vertex.c
Prediction: at HAKUX_RING=6 against HAKUX_RING=3 (same build, same scene, perflog), `rotfen` ms/flip in
  `[dipwin]` falls by 1-3 ms in windows where GPU ms/flip < `[rdc] tcpu`, and is unchanged (within run-to-run
  spread) in a GPU-bound window (GPU ms/flip >= tcpu). Falsifier: `rotfen`/flip unchanged at ring 6 in windows
  where GPU ms/flip < tcpu.
Needs device: yes, for the A/B only (Nova, PurpleVK; see "Device A/B")
Needs NDK: yes, a perflog Android build for the A/B; the default path needs no device run to be the same code
Selftest: 65-status-objective 71-cloud-territory 86-nightly-notes 87-nightly-trunk 99-dipwin-counters -- every
  fragment that names a changed source file by path or basename (offline_fold.py mentioning_fragments: 65, 71,
  86, 99) plus 87-nightly-trunk, 86's SHARD_CHAINS partner. Only 99-dipwin-counters reads vk/draw.c (the
  `[dipwin]` counters and their one emitter, which the A/B reads); the others use vk paths as fixture strings.
  No fragment reads the submit ring. The diff changes no harness file. The fragments that match only this PR.md's
  basename (87-ops-tick 96-fleet-registry 98-foldjam1018 98-lane-shape) were run as well; see Checks.

fps30 plan P8 (handoffs/fps30-1022/PLAN.md). The default is unchanged: without `HAKUX_RING` the renderer
allocates 3 slots and takes its length from the submit_frames pref (1..3), exactly as on master.

## Step 0

### Already tried

| commit | lane | change | result |
|---|---|---|---|
| e3a83e6780 | -- | runtime 1/2/3 selector (`submit_frames` pref) | introduced the length switch in `pgraph_vk_finish` |
| 5a047fd645 | -- | default 2, message "Triple buffering tanks performance" | no measurement recorded |
| f534b0bb51 | -- | depth 3 for fence back-pressure | no measurement recorded |
| 786f82d4bb, a7fc868303 | coldstart1010 | `HAKUX_SUBMIT_FRAMES` 3 against 2 | -1.51 / -1.49 ms on the NFS cold start, PASS |
| 3f1eace130 | nfsdefault1011 | native default 3 | shipped |
| 6f6af20088 | gpunonrender | `HAKUX_STALLFIN=reports` | refuted, -4.5 fps |
| -- | pfifowait1009 | PFIFO wait attribution | refuted |
| -- | gta3instr1018 | GTA III wait split | `rotw` = 0; `rotfen` is a real GPU fence wait |

No depth above 3 has been built or measured: `NUM_SUBMIT_FRAMES` was a compile-time 3, and the pref and
`HAKUX_SUBMIT_FRAMES` were clamped to it. No commit message, lane note or code comment gives a reason that the
ring must stay at 3; 5a047fd645's "tanks performance" is about 3 against 2 and has no number.

### Premise date check

The plan's measurements come from master perflog 72af9cb92c (2026-10-18). `git log 72af9cb92c..b944110629`
over renderer.h, draw.c and command.c: one commit, e1a99c506d (an `image_scale` field), which does not touch the
rotation, the ring arrays or `num_active_frames`. `git log -S` over hw/ in the same range for
`NUM_SUBMIT_FRAMES`, `num_active_frames`, `frame_fences` and `submit_count`: no commit. The plan's premise (3 slots, compile-time) **holds** at the base. Line references below are this
branch's unless marked "base".

## Mechanism

GTA III splits a flip into 3-5 command buffers. At every finish that rotates, `pgraph_vk_finish` moves to
`next = (current + 1) % num_active_frames` (draw.c:6103) and, before reusing that slot, waits for its fence
(`wait_frame_submitted`, `rotw`, draw.c:6113; `vkWaitForFences`, `rotfen`, draw.c:6125). With three slots and
more than three CBs per flip, the fence waited for belongs to a CB submitted within the same flip, so the CPU waits
for GPU work that is less than one flip old. When the GPU is the limit that wait is the GPU's cost and the depth
does not matter; when GPU ms/flip is below the CPU's (`tcpu`), a longer ring lets the CPU record the next CBs
while the GPU still runs the earlier ones, and the part of `rotfen` that waits on same-flip work shrinks.

## The change

Three numbers, defined at renderer.h:1293-1314:

- `SUBMIT_RING_CAP` (8) is the compile-time capacity. It bounds every per-slot array; nothing is allocated from
  it.
- `r->ring_alloc` is the number of slots that own GPU resources (command buffers, fences, staging, query ranges,
  release lists). It is fixed at init: `HAKUX_RING` when set, else `SUBMIT_FRAMES_PREF_MAX` (3), so the pref can
  still change the length at runtime as before.
- `r->num_active_frames` is the ring length: the rotation modulus, the retirement distance and every wait-all
  loop. It is 1..`ring_alloc`.

Every slot index the renderer records (`current_frame`, `invalidation_frame`, `deferred_downloads_frame`, a held
download's frame, an XFR pending frame, `last_use_frame`) is < `num_active_frames` when recorded, so it is <
`ring_alloc`.

| file:line | change |
|---|---|
| renderer.h:1293-1314 | `NUM_SUBMIT_FRAMES 3` replaced by `SUBMIT_RING_CAP 8`, `SUBMIT_FRAMES_PREF_MAX 3`, new field `ring_alloc`, and a comment block on the three numbers |
| renderer.h:1317-1324, 1363-1366, 1434, 1638 | per-slot arrays bound by `SUBMIT_RING_CAP` |
| renderer.h:2083-2084 | prototypes `xemu_submit_ring_env`, `xemu_get_submit_frames` (replaces two nested `extern`s) |
| draw.c:1512-1526 | `xemu_submit_ring_env()`: `HAKUX_RING`, read once, accepted 2..8, else 0 |
| draw.c:1530-1534, 1545 | `xemu_set_submit_frames`: under `HAKUX_RING` the pref is ignored; otherwise clamp to `SUBMIT_FRAMES_PREF_MAX` as before |
| draw.c:1551-1552 | `xemu_get_submit_frames` returns the ring when set |
| draw.c:1495, 1507 | `HAKUX_SUBMIT_FRAMES` clamp: `SUBMIT_FRAMES_PREF_MAX` (same value, 3) |
| draw.c:5747-5748 | runtime length switch: `MIN(xemu_get_submit_frames(), r->ring_alloc)` |
| draw.c:2010, 2042 | fence create / destroy over `ring_alloc` |
| draw.c:4635-4663, 5316 | XFR and gpu_ts per-slot static arrays bound by `SUBMIT_RING_CAP` |
| draw.c:5028 | XFR query pool `XFR_QUERIES_PER_CB * ring_alloc` |
| draw.c:5438 | `pgraph_vk_flush_all_frames` waits every allocated slot |
| command.c:49-62 | ring sized before every per-slot resource; one init line `[submitring] ring=%d src=%s slots=%d cap=%d` (tag `hakuX-vk`) |
| command.c:67, 85-86 | `ring_alloc * 2` command buffers allocated and freed |
| command.c:75 | slot flag reset over `SUBMIT_RING_CAP` |
| buffer.c:159-160 | texture-cache floor `NV2A_MAX_TEXTURES * (ring_alloc + 1)` |
| buffer.c:442, 539, 573 | per-slot staging alloc / fail / finalize over `ring_alloc` |
| buffer.c:526-530 | staging log line ends `, %d slots)`; the `(%d frames, idx=` prefix coldread.py reads is unchanged |
| vertex.c:232 | stale marks over `ring_alloc` |
| reports.c:95 | `pending[SUBMIT_RING_CAP]` |
| reports.c:476-477 | `[reportasync] on: %d slots of %d queries (ring %d)`; the `[reportasync] on` prefix raread.py and ppread.py match is unchanged |
| reports.c:513 | RA query pool `ring_alloc * RA_SLOT_QUERIES` |
| reports.c:940-941 | comment: the reader gate holds at any ring length |
| renderer.c:496 | gpu_ts query pool `GPU_TS_QUERIES_PER_CB * ring_alloc` |
| texture.c:5661, 5689; surface.c:6865, 6889 | deferred release lists created / freed over `ring_alloc` |

`HAKUX_RING` replaces the submit_frames pref and `HAKUX_SUBMIT_FRAMES` for the whole run. Out-of-range values
(unset, 0, 1, 9, text) leave the master path. `HAKUX_RING=2` gives the ring-2 path with 2 slots allocated.

### The 41 uses of NUM_SUBMIT_FRAMES at the base

Capacity = an array bound (`SUBMIT_RING_CAP`). Allocated slots = a loop that reaches a slot's resources
(`ring_alloc`). Length = the rotation, retirement or a wait (`num_active_frames`). Pref limit = the clamp on the
pref and `HAKUX_SUBMIT_FRAMES` (`SUBMIT_FRAMES_PREF_MAX`).

| # | base file:line | use | now | class |
|---|---|---|---|---|
| 1 | renderer.h:1293 | the define | `SUBMIT_RING_CAP 8` + `SUBMIT_FRAMES_PREF_MAX 3` | split |
| 2-5 | renderer.h:1297-1300 | `command_buffers`, `frame_fences`, `frame_submitted`, `frame_enqueued` | `SUBMIT_RING_CAP` | capacity |
| 6 | renderer.h:1304 | `frame_cb_serial` | `SUBMIT_RING_CAP` | capacity |
| 7-10 | renderer.h:1343-1346 | `deferred_framebuffers`, `_count`, texture and surface release lists | `SUBMIT_RING_CAP` | capacity |
| 11 | renderer.h:1414 | `frame_staging` | `SUBMIT_RING_CAP` | capacity |
| 12 | renderer.h:1618 | `gpu_ts_rp_counts` | `SUBMIT_RING_CAP` | capacity |
| 13 | command.c:63 | slot flag reset | `SUBMIT_RING_CAP` | capacity |
| 14 | buffer.c:444 | staging alloc | `ring_alloc` | allocated slots |
| 15 | buffer.c:540 | staging fail path | `ring_alloc` | allocated slots |
| 16 | buffer.c:574 | staging finalize | `ring_alloc` | allocated slots |
| 17 | vertex.c:232 | stale marks on other slots | `ring_alloc` | allocated slots |
| 18 | reports.c:95 | `pending[]` | `SUBMIT_RING_CAP` | capacity |
| 19 | reports.c:476 | `[reportasync] on` log | `ring_alloc`, plus the length | log |
| 20 | reports.c:513 | RA query pool | `ring_alloc` | allocated slots |
| 21 | renderer.c:496 | gpu_ts query pool | `ring_alloc` | allocated slots |
| 22-23 | texture.c:5661, 5689 | texture release lists init / finalize | `ring_alloc` | allocated slots |
| 24-25 | surface.c:6865, 6889 | surface release lists init / finalize | `ring_alloc` | allocated slots |
| 26 | draw.c:1495 | comment | `SUBMIT_FRAMES_PREF_MAX` | pref limit |
| 27 | draw.c:1507 | `HAKUX_SUBMIT_FRAMES` clamp | `SUBMIT_FRAMES_PREF_MAX` | pref limit |
| 28 | draw.c:1524 | pref clamp | `SUBMIT_FRAMES_PREF_MAX` | pref limit |
| 29 | draw.c:1630 | comment on CBs in flight | `num_active_frames - 1` | length |
| 30 | draw.c:1988 | fence create | `ring_alloc` | allocated slots |
| 31 | draw.c:2020 | fence destroy | `ring_alloc` | allocated slots |
| 32-38 | draw.c:4613-4615, 4618, 4638, 4639, 4641 | XFR per-slot static arrays | `SUBMIT_RING_CAP` | capacity |
| 39 | draw.c:5006 | XFR query pool | `ring_alloc` | allocated slots |
| 40 | draw.c:5294 | `gpu_ts_read[]` | `SUBMIT_RING_CAP` | capacity |
| 41 | draw.c:5416 | `pgraph_vk_flush_all_frames` | `ring_alloc` | allocated slots |

The length was already a runtime value at every use that is not in this table, and those are unchanged:
the rotation modulus (draw.c:6103), the any-in-flight descriptor reset (draw.c:6191), `staging_reclaim_any`
(buffer.c:662), the reports loops and `cur_nframes` (reports.c:468, 816, 966, 1047, 1180, 1203), the
texture retirement tests (texture.c:2467, 4515, 4578, 5531, 5543) and the renderer JSON (renderer.c:2395).

`ring_alloc`, not the length, bounds the allocation loops because the length can change at runtime without
`HAKUX_RING` (pref 1..3 inside 3 allocated slots); a loop over the length would leak or skip slots that a
shorter length no longer visits.

## Retirement and derived assumptions, at lengths 2..8

- **Texture retirement** (`submit_time + num_active_frames > submit_count`, texture.c:2467, 4515, 4578, 5531,
  5543). Non-rotating submits are synchronous, and a rotating submit reuses a slot only after waiting for its
  fence, which covers every earlier submit in queue order. So after `num_active_frames` submits past
  `submit_time` the GPU has finished with the texture, for any length. Unchanged code.
- **`invalidation_frame`, `deferred_downloads_frame`, held downloads, XFR pending, `last_use_frame`.** These are
  slot indices recorded as `current_frame` (< length). Their work completes when the rotation next reaches that
  slot and waits its fence; that is independent of the length. Unchanged code.
- **Deferred destroy lists** (framebuffers, texture and surface releases). Appended at `current_frame` and drained
  when the slot is reused after its fence wait. The lists exist for `ring_alloc` slots; the appends index
  `current_frame` (texture.c:3311, 3316, 5484; surface.c:4420).
- **Length change at runtime** (draw.c:5747-5755). `pgraph_vk_flush_all_frames` now waits and drains every
  allocated slot (draw.c:5438) before the length shrinks, so nothing is left in a slot the new length no longer
  visits. The new length is clamped to `ring_alloc`, so a pref above the allocation cannot index past it.
- **Reports** (`ra`). The pool has `ring_alloc * RA_SLOT_QUERIES` queries; the reader works by slot index <
  length; a length change sets `wait_all` (reports.c:966) as before. The reader gate's comment (reports.c:940)
  said "with three slots"; the argument (the rotation has already waited the slot's fence) holds at any length.
- **Texture-cache floor** (buffer.c:159-160). **Changed:** it was keyed to `xemu_get_submit_frames()` at init,
  which is not the longest length the run can reach (the pref can rise to 3 later); it is now
  `ring_alloc + 1`. On the default path with the default pref (3) the value is the same (4 x 4 = 16 entries;
  28 at ring 6). It only applies when a cache size override is set below it, and the settings offer
  0/512/1024/2048.
- **Per-slot staging sizes** (buffer.c:365-440) still come from `xemu_get_submit_frames()`'s tier (1, 2, >= 3).
  At `HAKUX_RING` >= 3 every slot gets the ring-3 sizes; `HAKUX_RING=2` gets the ring-2 sizes, as the pref did.
- **#426 pipeline census.** Per-slot cb serial (`frame_cb_serial[SUBMIT_RING_CAP]`); depth-generic.
- **First use of a slot** copies the whole 64 MiB vertex RAM into it (draw.c:6231-6237,
  `vertex_ram_initialized`), as slots 1 and 2 do today; slots 3..L-1 add one copy each, once per run.

## Memory

Measured per-slot sizes on the Nova (PurpleVK Adreno 740, renderer budget 1536 MB tier, heap 8448 MB),
captures/fpsnext1019/runs/g1-B2/logcat.txt, `buffer_init: create FRAME0_*` lines: INDEX_STAGING 32,212,254 +
VTXINLINE_STAGING 134,217,728 + UNIFORM_STAGING 96,636,764 + STAGING_SRC 134,217,728 + VERTEX_RAM 67,108,864 =
464,393,338 B = 442.9 MiB per slot, all `memprops=0xf` (device-local, host-visible, coherent, cached), plus a
2 KiB uploaded bitmap.

| ring | slots | per-slot staging | delta against master |
|---|---|---|---|
| 2 | 2 | 885.8 MiB | -442.9 MiB |
| 3 (default) | 3 | 1328.6 MiB | 0 |
| 6 | 6 | 2657.3 MiB | **+1328.6 MiB** |
| 8 | 8 | 3543.1 MiB | +2214.4 MiB |

Query pools at ring 6: gpu_ts +3 x 98 timestamp queries, XFR (when on) +3 x 384 timestamp queries, reportasync
(when on) +3 x 1024 occlusion queries. Command buffers +6, fences +3. Host-side struct and static arrays grow by about 31 KB, fixed, whatever
the env. The per-slot caps are fractions of the renderer budget per slot (buffer.c, `perframe_*_cap`), not divided
by the slot count, so the 1536 MB tier does not bound the total at ring 6. A failed allocation fails
`pgraph_vk_init_buffers` at start, visibly.

## Checks

- `cc_wt.py` (the desktop build's own flags, `-fsyntax-only`) on each touched C file, `-DNV2A_PERF_LOG=1` and
  `=0`: buffer, command, draw, renderer, reports, surface, texture, vertex: 16 runs, all exit 0, 0 errors.
  Warnings against the base (same tool on master b944110629): no new warning; five removed (the nested
  `extern int xemu_get_submit_frames` in command.c and buffer.c x2, buffer.c's redundant redeclaration, and
  draw.c's missing-prototype for `xemu_get_submit_frames`). Remaining: buffer 3, draw 15, renderer 7, surface 3,
  texture 2, all present on master.
- `SELFTEST_ONLY="65-status-objective 71-cloud-territory 86-nightly-notes 87-nightly-trunk 99-dipwin-counters"
  docs/testing/jobs/selftest.sh`: `selftest: 196 passed, 0 failed, PARTIAL: 5 of 160 fragments`, exit 0.
- `SELFTEST_ONLY="87-ops-tick 96-fleet-registry 98-foldjam1018 98-lane-shape"`: `selftest: 190 passed, 0 failed,
  PARTIAL: 4 of 160 fragments`, exit 0.
- Log parsers: coldread.py matches `per-frame staging created \(3 frames` (prefix kept); raread.py and ppread.py
  match `\[reportasync\] on` (prefix kept).
- No device run.

## Device A/B

Arms: `HAKUX_RING=3` against `HAKUX_RING=6`, through the env_vars pref, on a perflog build, on the Nova, same title
and scene. Both arms ignore the submit_frames pref. Verify at start:
`[submitring] ring=6 src=HAKUX_RING slots=6 cap=8` and `buffer_init: per-frame staging created (6 frames, ...
6 slots)` (and the `ring=3`/`3 slots` forms in arm A). Counters: `[dipwin]` `rotfen`, `rotw`, `defw`, `ndw`;
phase `Fen` and `Idle`; GPU ms/flip against `[rdc] tcpu` to split the windows into GPU-bound and not. Guards:
`buf_ds_full`, `ubo_ring_grow`, `fall`/FAF, `stale`/`staleK`.

## Risks

- **Input-to-photon latency** can grow by up to the extra slots' queued GPU work when the GPU is the wait. Not
  measured here; the A/B's GPU-bound windows show whether the queue is deeper there.
- **Present pacing** (`defer_cap`, nv2a.c:1128) is untouched; it does not know the ring is longer.
- **Full drains.** texture.c:4515 and 4578 call `pgraph_vk_flush_all_frames` when an in-flight texture's content
  changes. A longer ring keeps a texture "in flight" for more submits, so the drain can fire more often and waits
  up to L-1 CBs. Guard: `fall`/FAF.
- **Texture-cache pinned set** grows with L: in-flight textures cannot be evicted for L submits instead of 3
  (the Nova tier has 1024 entries).
- **Stale vertex RAM copy** at rotation grows by about (L-1)x the uploaded bytes (vertex.c:232 marks every
  other slot). Guards: `stale`, `staleK`. P6 (lane/p6vtxstale1022) reduces this cost.
- **Descriptor and UBO reset** (draw.c:6191) needs no other slot in flight, which is rarer at a longer ring.
  Guards: `buf_ds_full`, `ubo_ring_grow`.
- **Invalid surfaces** stay unprunable for longer (the #414 class), and deferred releases and downloads complete
  later.
- **+1.3 GiB** of host-visible staging at ring 6.

## Merge note

vertex.c:232 conflicts textually with lane/p6vtxstale1022, which adds a `QEMU_BUILD_BUG_ON` above the same loop and
replaces its body with `vtxstale_mark`. Resolve by keeping p6's lines with this lane's `r->ring_alloc` bound. The
bound is required with p6: its per-slot `vertex_ram_stale` bitmap exists only for allocated slots. p6's buffer.c
hunks sit inside the alloc, fail and finalize loops whose bounds this lane changes, and compose. Renaming the
define (rather than keeping `NUM_SUBMIT_FRAMES` as the capacity) makes any new use in another branch fail to
compile instead of silently taking the capacity as the length; no open p-lane branch adds one.
