# p2qry1022: occlusion queries recorded inside the render pass, behind HAKUX_QRY_INPASS (#433)

State: draft

Lane: p2qry1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p2qry1022/PR.md, docs/lanes/p2qry1022/zrep_ab.py,
hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/reports.c
Prediction: Fable: The Lost Chapters on the Nova, one build, HAKUX_QRY_INPASS=1 against =0, play windows only:
  [dipwin] bqry < 10 per flip (=0: 310-402), rp per flip down >= 60 %, hakuX-phase GPU down >= 8 ms per frame;
  qry_overflow = 0; HAKUX_ZREP report values equal between arms within the A/A spread, identity exact in both
Needs device: yes (Nova): the A/B below. Nothing here has run on a device
Needs NDK: yes (renderer C change; the A/B needs an apk built from this commit, with --perflog)

With `HAKUX_QRY_INPASS=1` (read once at init) an occlusion query begins after the draw's render pass is begun
and ends inside the same pass, so a query transition no longer ends the pass. The query's pool index is reset
in the aux command buffer, which runs ahead of the main one in the same submission, instead of by a
`vkCmdResetQueryPool` just before each `vkCmdBeginQuery` (illegal inside a pass). Unset, or any value but `1`,
every query command is recorded where and when it is today.

## Premise: the cost is on master

- `git log 72af9cb92c..b944110629 -- hw/xbox/nv2a/pgraph/vk/`: 12 commits (renderer.h 1, surface.c 4,
  texture.c 10), none in draw.c or reports.c. The query block in `begin_draw` (master draw.c 7599-7625) still
  ends the pass on every query begin and end.
- Fable, Nova, perflog build, captures/fpsnext1019/runs/fable-h2/logcat.txt, play 12:29:05-12:30:41, 27
  `[dipwin]` windows: bqry 310.7-402.2 per flip against rp 403.2-518.5 per flip (query breaks ~76 % of all
  pass ends); hakuX-phase GPU 26.5-34.2 ms (X 19.4-31.1). The phase line's `RP:` under-reads here
  (GPU_TS_MAX_RENDER_PASSES = 48), so `[dipwin] rp=` is the pass count used.

## Already tried

| What | Where | Outcome | Difference here |
|---|---|---|---|
| Queries inside the pass, upstream "initial GPU optimizations" | 876942ca09 (2026-02-21) | Reverted by 307ab9e42f "fix draw" (2026-02-26) | That version recorded `begin_query` before `begin_render_pass` (a query could begin outside a pass and end inside one: different subpass scope); `end_render_pass` did not end a running query (a query active across `vkCmdEndRenderPass`); it reset the whole pool `[0, max)` in the main command buffer, ending the pass to do it; and it dropped the clear path's pass end. Each is a rule in the table below; here each has a code path. Its `queries_reset_in_cb` field is still in renderer.h, written at draw.c 6306 and never read |
| `skip_occlusion_queries` | draw.c 7645-7651, `g_xemu_skip_occlusion_queries` | Removes the breaks by never counting: the guest reads the last count or 0 | Not a fix (stale visibility). Left as is: with it set, no query command is recorded in either mode |
| #804: wait for submitted frames before reading results | 510ebb25f2 | Kept (reports.c 1229-1249) | The reset now sits in the aux command buffer of the same submission, so the same fence wait covers it |
| HAKUX_REPORT_ASYNC reader thread, per-frame slots of 1024 | 2e9f535300, 477893cdbf | Kept | The reset range is the slot's `[cur_base, num)` when the reader runs |
| HAKUX_REPORT_EARLY | 08fd920b5c | Kept | Reads values, not query placement |
| HAKUX_ZREP per-query / per-report log | 084e5e266b (#1039) | Used as the count check below | |
| `[dipwin]` pass-end causes | 25915ae59e (#1049) | Source of bqry; two counters added | |
| Turnip GMEM against sysmem ZPass counts | rendermode474 (#527) | ZPass counts differ between the two modes (40960 against 65536) | Larger passes can change the autotuner's choice; see Risks |

No Turnip in-pass occlusion defect is recorded in this tree or in docs/testing/nv2a_issues.toml. The local
Turnip fork's history for tu_query_pool.cc has occlusion fixes already in it (8f5d4338402 counting after an FS
that kills, 930f7f4a1b5 depth state recalculated at query begin/end, d88c1837853), and no open one.

## Turnip (local fork mesa-turnipfork 4c18636110f, src/freedreno/vulkan)

- In-pass occlusion is supported: `emit_begin_occlusion_query` / `emit_end_occlusion_query`
  (tu_query_pool.cc 1091, 1491) write into `draw_cs` when `cmdbuf->state.pass`, which is replayed per bin and
  accumulates `end - begin` into the result. Availability goes into `draw_epilogue_cs` (1520, 1600), run once
  after the pass.
- A740 has `has_event_write_sample_count`: the in-pass end is one `CP_EVENT_WRITE7 ZPASS_DONE` with
  `write_accum_sample_count_diff`, then `emit_counter_barrier` = WFI (606, 1588). Out of a pass it is two
  events and the same WFI. In GMEM mode the in-pass WFI runs once per bin.
- Each in-pass begin/end dirties `TU_CMD_DIRTY_DISABLE_FS | TU_CMD_DIRTY_LRZ` (1604) and toggles
  `occlusion_query_may_be_running`, which moves `EARLY_Z` to `EARLY_Z_LATE_Z` for FS-kill draws while a query
  runs (tu_cmd_buffer.cc 8286-8300).
- With an in-pass query, autotune's sample-count metric emits a pairing `ZPASS_DONE`
  (`has_zpass_done_sample_count_write_in_rp`, tu_autotune.cc 598-606). This path is not reached today.

## The change

| File:line | What |
|---|---|
| reports.c 488-492 | `HAKUX_QRY_INPASS` read once into `r->qry_inpass` (`1` only); log `[qry433] occlusion queries inside|outside the render pass (HAKUX_QRY_INPASS=n)` on `hakuX-lane` |
| reports.c 770-802 | `pgraph_vk_reset_cb_queries`: one `vkCmdResetQueryPool(cmd, base, num - base)`, base = `ra.cur_base` with the reader thread, else 0 |
| renderer.h 1623-1628, 2058 | `bool qry_inpass`; the declaration |
| draw.c 4230-4248 | `begin_query`: asserts `in_render_pass` when on, `!in_render_pass` when off; the per-index reset only when off |
| draw.c 4261-4269 | `end_query`: the same conditional assert |
| draw.c 4502-4514 | `end_render_pass`: when on and a query runs, `end_query` before `vkCmdEndRenderPass`; counted as `qsplit` |
| draw.c 5864-5868 | `pgraph_vk_finish`: when on, `pgraph_vk_reset_cb_queries` into the aux command buffer after the aux/main barrier, before `vkEndCommandBuffer(aux)` (5870); the main buffer ended at 5811 with no query running (5799-5802) |
| draw.c 7659-7670, 7713-7715 | `begin_draw`: when on, the query block only ends queries (new query needed, ZPASS off, or clearing) and sets `qry_begin`; `begin_query` is recorded after the pass is begun. The off block (7671-7697) is unchanged |
| draw.c 9930-9948 | `pgraph_vk_draw_end`: when on, finish (`NEED_BUFFER_SPACE`) once `num + 8 > max`, before the draw records anything; counted as `qry_overflow` |
| draw.c 1206-1221, 1252, 1262, 1389 | `[dipwin]` doc, `DW_QRY`: `qsplit=` and `qry_overflow=` after `bsmd=`, under `NV2A_PERF_LOG` |

GET_REPORT and CLEAR_REPORT_VALUE are unchanged (reports.c 719-765): both set `new_query_needed`, and the next
ZPASS draw ends the running query, now inside the pass. A finish ends it via `end_render_pass`.

**Same indices, same sums.** Off, every pass end that can find a query running is followed by `end_query`:
`pgraph_vk_finish` (5799/5801), `pgraph_vk_ensure_not_in_render_pass` (6385-6388, behind every non-draw pass
end), `begin_draw` (7678, 7686, 7694); the clear ends (7704, 8011) find none, the query block having ended it.
On, `end_render_pass` does the same ending, so queries begin and end at the same draws and the index count per
command buffer is the same. Both readers (sync reports.c 1280-1329, async 880-909) sum results up to each
report's `query_count`, so a report's value does not depend on how the draws are split across indices.
Invariant when on: `query_in_flight` implies `in_render_pass`.

**Off is today's path.** Every changed statement is under `r->qry_inpass` except: the two asserts, now the
same assert inside an `else`; `bool qry_begin = false`, never set when off; the init log line; and the two new
`[dipwin]` fields (0 when off).

## Validity

| Vulkan rule | Guaranteed by |
|---|---|
| `vkCmdResetQueryPool` outside a render pass (VUID-vkCmdResetQueryPool-renderpass) | The only reset when on is reports.c 800, into the aux command buffer, which never begins a render pass; draw.c 4245 skips the in-CB reset |
| Begin and end in the same subpass (VUID-vkCmdEndQuery-None-07007) | Begin is recorded only after `begin_render_pass` (draw.c 7709-7715, assert 4233-4234). The end is in `begin_draw`'s query block (7662-7670, same pass: nothing between the pass begin and the block ends it) or in `end_render_pass` before `vkCmdEndRenderPass` (4502-4514). Render passes have one subpass |
| No query active at `vkCmdEndRenderPass` (VUID-vkCmdEndRenderPass-None-07004) | `end_render_pass` is the only `vkCmdEndRenderPass` call site and ends a running query first (4502) |
| No query active at `vkEndCommandBuffer` (VUID-vkEndCommandBuffer-commandBuffer-00061) | `pgraph_vk_finish` 5799-5802 before 5811 |
| Reset not of an active query (VUID-vkCmdResetQueryPool-None-02841) | The range is this command buffer's own indices, all ended before 5811 (assert reports.c 797); indices of earlier buffers were ended in those buffers |
| Begin on an unavailable (reset) index (VUID-vkCmdBeginQuery-None-00807) | `{aux, main}` are one `VkSubmitInfo` (submit_worker.c 50-57, render_thread.c 136), query commands execute in submission order, and the reset covers `[base, num)`, every index the main buffer began (`num` only increments while a buffer is open) |
| No index reused before its reset and read | `num` returns to `base` only after submit: sync, reports.c 1336 at the end of `process_pending_reports_internal` (after the #804 fence wait and a WAIT_BIT read); async, ra_internal reports.c 1086-1089 after `ra.pending[slot] == 0`. Neither runs with a command buffer open (reports.c 1195). `begin_query` asserts `num < max` (4242); draw_end keeps 8 free |
| No two active occlusion queries (VUID-vkCmdBeginQuery-queryPool-01922) | `assert(!r->query_in_flight)` in `begin_query`, unchanged |

## Index bound

`max - base` = 1024 on both paths (reports.c 500; `RA_SLOT_QUERIES` 63). Between two `pgraph_vk_draw_end`
checks at most 4 queries begin: 1 for a merged draw-queue flush, 2 for the signed-blend fold's two passes, 1
for a draw-queue flush from outside `pgraph_vk_draw_end`; the reorder window's replay begins none
(`reorder_reject_zpass`). A `qsplit` is one of these, as it is when off. Headroom 8. `pgraph_vk_finish` flushes
the reorder window and draw queue first (5733-5744), and their draws fit in the headroom. Off, the same
overflow is the `assert` at 4242 (no handling, as today). The check fires at 1017 queries in one command
buffer; Fable's 310-402 query breaks per flip stay under that unless one buffer spans three or more flips, so
`qry_overflow` should read 0 there.

## Prediction and falsifier

Prediction (Fable, Nova, play windows, =1 against =0): bqry < 10 per flip; rp per flip down >= 60 %;
hakuX-phase `GPU:` down >= 8 ms per frame; `qry_overflow=0`; ZREP identity exact in both arms.

Falsified, pass breaks not the cost: bqry < 10 per flip and rp down >= 60 %, but GPU down < 8 ms.
Off (do not default it): any `VK_ERROR_DEVICE_LOST`, an `assert` abort, a report-value difference beyond
the A/A spread, or any validation message from these paths on the desktop run below.

## Device A/B (exact)

One apk: this commit, `--perflog`. Both arms and the A/A pair on the same ref and device; only the env differs.
Fable has no route or save in this tree; a `--title` request with no `--route` gets `routes/auto.route` (gate
clause `auto-route`). Only windows inside a `hakuX-route: state=play` stretch count; a run that never reaches
play is void, not a result.

**1. Time (no ZREP: its writes would cost time).** Four requests, arms `0`, `1`, `0`, `1` (two A/A-able pairs):

```
docs/testing/request.sh --who p2qry1022 --device nova --ref <this commit> --perflog \
  --title "4D5300D1-Fable_The_Lost_Chapters.xiso.iso" --seconds 300 \
  --env HAKUX_QRY_INPASS=0 --priority arm --issue 433 \
  --no-expect "A/B read from [dipwin] and hakuX-phase" --purpose "#433 queries in pass: arm 0"
```

Read from each logcat:

- `hakuX-lane` `[qry433] occlusion queries outside|inside the render pass (HAKUX_QRY_INPASS=0|1)`. A missing
  or wrong line voids the arm.
- `hakuX-rpbrk` `[dipwin]`: `bqry/fl`, `rp/fl`, `qsplit`, `qry_overflow` (expect 0), `bfin=` (buf should not
  rise), `brk`.
- `hakuX-phase`: `GPU:` and its `X:`, per window.
- `vulkan`, `VALIDATION`, `ValidationLayer` lines; any `DEVICE_LOST`; process death.

**2. Counts.** The same pair with ZREP armed by a records-only frame dump in play (`after<S>` = seconds from
start to the play stretch seen in step 1):

```
  --env HAKUX_QRY_INPASS=0|1 \
  --env HAKUX_ZREP=/sdcard/Android/data/com.jreinach.hakux.debug/files/zrep.txt \
  --env XEMU_FRAME_DUMP=30,noimages,after<S> --pull 'zrep.txt'
```

Check `[zrep1039] on -> ...zrep.txt` in each logcat, then:

```
python3 -I docs/lanes/p2qry1022/zrep_ab.py <arm0>/zrep.txt <arm1>/zrep.txt --divisor <surface_scale^2>
```

- identity, per file: every report after the first clear equals the sum of its queries' samples / divisor;
  `mismatch=0` and `checked>0` in both, else exit 1. This checks each arm's bookkeeping.
- queries per report: arm 1 may show more indices per report (`qsplit`); values must not move with it.
- A/B: reports aligned by offset sequence; `equal` / `differ` and the largest difference. Live play does not
  repeat frame for frame, so the arm-1 `differ` fraction is held against an A/A pair (arm 0 twice) run the same
  way. `--require-equal` applies to a deterministic scene only.

**3. Validation (desktop).** The fleet driver loads through `volkInitializeCustom`, which skips the Vulkan
loader and every layer (docs/testing/vk_validation_android.md, block 2), so device logcat cannot show VUIDs.
The validation check is a desktop lavapipe run with `vulkan-validationlayers`, `[display.vulkan]
validation_layers = true` (docs/testing/desktop-runs.md, "Running with the validation layer") and
`HAKUX_QRY_INPASS=1` in the environment, on the `ZPass_pixel_count` suite, then
`grep -o 'VUID-[A-Za-z0-9_-]*' run.log | sort | uniq -c`; the VUIDs in the table above must not appear. The
same suite on the Nova (`--suites ZPass_pixel_count --env HAKUX_QRY_INPASS=0|1`) must score the same in both arms.

## Checks run

- `tools-p/cc_wt.py` on draw.c and reports.c, `-DNV2A_PERF_LOG=1` and `=0`: exit 0, all four. reports.c: no
  warnings. draw.c: 16 warnings, none on a changed line (missing prototypes 1447-1541, `cmd` shadow 5982,
  unused `r` 8069), all present before this change.
- `SELFTEST_ONLY` over the 16 fragments that mention these paths or read a lane PR.md (62-status-freshness,
  65-status-objective, 86-nightly-notes, 87-fold-stale-ci, 87-ops-tick, 90-fold-index, 96-fleet-registry,
  98-audit-outlet, 98-coverage-rest, 98-foldjam1018, 98-lane-shape, 99-dipwin-counters, 99-handback,
  99-handback-draft, 99-handback-parked, 99-handback-resolved): 656 passed, 0 failed.
- `nv2a_index.py check`: exit 1 on 9 sites, all in texture.c, none in a file this change touches; the same on
  the base.
- zrep_ab.py on generated fixtures: a split query with equal sums passes (6/6 equal); a wrong value, a file
  with no clear line and three files all fail.

## Risks not closed

- Bigger passes can move Turnip's autotune between GMEM and sysmem, and ZPass counts differ between the two
  (rendermode474). The ZREP A/B is what shows it; identity holding with values moving would be this.
- One WFI per in-pass query end per GMEM bin on A7xx. At ~200 queries per flip this may eat part of the gain;
  the GPU-ms clause of the falsifier is where it shows.
- The 4-per-check bound is read from the code, not measured; `qry_overflow` and the assert at 4242 are the
  measures.
- No device or desktop run yet; the validation run needs the desktop layer installed.
