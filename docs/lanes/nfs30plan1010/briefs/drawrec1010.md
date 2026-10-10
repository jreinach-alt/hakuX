# lane.drawrec1010 -- cut the per-draw recording cost by a third: census of consecutive-draw state, then dirty-tracked reuse (#433, 0.5)

Opus (engineering, per the 10-10 model table; Sonnet when usage is Low). Issue: none (dispatched directly by lane.local,
#433 umbrella; step 3 of docs/lanes/nfs30plan1010/PLAN.md). Nova only.

## Why
- **NFS Most Wanted race start**: the PFIFO thread records 1,860-1,930 draws per frame at 11.9 us each on the perflog
  build (`Syn` 4.6, `Pipe` 6.4 of which `Sh` 4.1, `Desc` 2.7, `Setup` 1.4, `Mfp` 3.9 ms/frame; lane.nfs30plan1010
  runs `1-1791649387`/`1-1791649388`, NOTES 5.5), ~23 ms of a 75 ms instrumented frame, ~18 ms of the plain build's
  56-62 ms cold start (PLAN.md section 2's scaling). After steps 1-2 (texscan1010, reportasync1010) remove the GPU
  waits, this recording IS the frame: PFIFO on-CPU ~24-25 ms cold against a 33.3 ms budget, with the cold start's
  heavy frames over the line. -30% here is what brings the cold start to 30 fps at the median (PLAN.md section 5).
- **Where the per-draw time goes** (lane.perdraw1009's profile at the same scene, ms/frame at ~1,630 draws):
  pipeline lookup `create_pipeline` inclusive 7.51; `update_shader_uniforms` 4.43 (`uniform_copy` 2.84); descriptor
  sets 3.42 (ubosz hook 1.39, memcmp 0.79, memcpy 0.68); textures bind/create 2.33/2.12; vertex setup 1.59.
  perdrawon1010's three uniform switches took -1.76 us/draw (-17%) off the race start: real, small, and the baseline
  for this lane (both arms carry them on).
- **Nothing is reused between consecutive draws** except the pipeline handle and the dynamic-state diff:
  `begin_pre_draw_inner` (hw/xbox/nv2a/pgraph/vk/draw.c:5452) re-derives the shader/pipeline key from PGRAPH
  registers every draw (`create_pipeline` :2428, `pipe_bind_shd`), memcmps the vertex attributes (:5580-5592),
  re-binds textures, rebuilds the descriptor set (:5756) and re-uploads uniforms (:5755); `begin_draw` (:6045)
  rebinds set 1 with two dynamic offsets (:3398). Draw merging (`g_xemu_draw_merge`, :34) and the render-thread
  draw queue (RCMD_DRAW, :5940-5942) are off and, as draw.c:6837-6863 records, break the guest-read ordering
  guarantee (`pfifo_bound_skew`): every guest-memory read must stay inside method processing on the PFIFO thread.
- **The warning:** #474's uniform-hash skip was inert on Blinx (lane.energymap507). A title whose state churns on
  every draw gives this nothing. Whether NFS is that title is the census question, and it is answered before any
  rework is built.

## The job
1. **Census instrument, default off (`HAKUX_DRAWCENSUS=1`), no behaviour change.** On the plain build at the race
   start, for every consecutive pair of draws: which inputs changed since the previous draw: each PGRAPH register
   range that feeds the shader/pipeline key (combiner state, vertex-attribute formats, texture state, lighting,
   blend/depth), the bound textures, the uniform bytes `uniform_copy` would copy (hash them), dynamic state, the
   surface. Print one histogram per 60 frames to logcat, and a reader in your lane dir. Also run one
   `simpleperf record` of the PFIFO thread on the plain build over two race starts (nfs30plan1010 PLAN.md 4.5: the
   untimed 7-9 ms of PFIFO on-CPU has no function names yet). Put both tables in NOTES.md. **Decide from them**:
   - >= 50% of consecutive draws differ only in vertex data and transform/material uniforms -> step 2 (reuse);
   - low reuse but >= 40% of consecutive draws have identical pipeline + descriptors + uniforms -> batching (PLAN.md
     section 6, "batching guest draws"), inside the same switch;
   - neither -> stop, write the verdict, and recommend the recorder thread (PLAN.md 4.4 step 4 / section 6) as a
     separate brief. Do not build it in this lane.
2. **Dirty-tracked state reuse behind `HAKUX_DRAWREC=1`, default off.** Method dispatch (pgraph.c) sets a dirty
   mask per key-feeding register range; `begin_pre_draw_inner` skips key derivation, the vertex-attribute memcmp,
   texture re-bind and descriptor rebuild for ranges clean since the last draw; uniform upload copies only dirty
   ranges (the extension of perdraw1009's F1-F3). Push constants for the per-draw dynamic offsets if the census
   shows the two offsets are the only change on most draws (bf2stall433's suspect). Data: a dirty mask on
   `PGRAPHState`, last-bound pipeline/descriptor/uniform-range handles on `PGRAPHVkState`. Target: `Pipe` 6.4 -> ~2.5,
   `Desc` 2.7 -> ~1.2, `Mfp` 3.9 -> ~2.5 ms/frame on the perflog build; -30% of recording.
3. **Pixel check before any fps claim.** The 27-suite disc on vs off, byte-identical; a missed dirty bit is a wrong
   pipeline or a stale uniform on a draw, and the suites are the only thing that sees it. Then NFS race-start
   frames at the 12 marks on vs off, region-compared.
4. **Register the prediction first**, in docs/testing/predictions/drawrec1010-*.json: NFS race start, switch on vs
   off, plain build, perdrawon1010's switches on in both arms, 2 runs per arm, 12 starts, route
   `nfs-mw-quickrace`. Predict: us/draw (perflog confirmation run, one per arm, optional) -30%; countdown period
   (pace ms/60 pooled): off 41-42 warm / 56-62 cold, on <= 38 / <= 52 if steps 1-2 have not landed on your base,
   <= 34 / <= 40 if they have; v2 share up >= 10 points. Readers: `docs/lanes/nfs30plan1010/phaseread.py` (pace,
   draws/frame, `Draw per draw`), `startread.py` needs perdraw1009's state line and is not for this build. The
   route copy request.sh needs: `docs/lanes/nfs30plan1010/nfs-mw-quickrace.route` -> `docs/testing/titles/routes/`
   of your worktree; do not commit that copy.
5. **PR.md:** `State: ready`; the census tables and the decision they drove; measured numbers and the prediction
   verdict; `Needs device: yes (Nova, used)`; `Release note (performance): ...` or `none` if opt-in; whether this lane
   recommends default-on for its switch and for perdrawon1010's three.

## Rules
- Territory: hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/shaders.c, hw/xbox/nv2a/pgraph/pgraph.c (method
  dispatch dirty bits only), hw/xbox/nv2a/pgraph/vk/renderer.h (shared with reportasync1010: coordinate on the board
  before touching it), docs/lanes/drawrec1010/**, docs/testing/predictions/drawrec1010-*.json. Ask for any other
  file by name on the board.
- Do not turn on `g_xemu_draw_merge` or RCMD_DRAW as the fix: draw.c:6837-6863 says why, and three lanes lost fps
  moving work across threads (nfs30plan1010 NOTES 2.3).
- Titles run on the Nova only. Use pad.sh for input (RT is the gas), never `adb shell input keyevent`.
- No clock or performance-mode arms. A faster clock is not a fix (briefs/_next-step-rule.md).
- Perf claims come from this lane's runs only; cite the run id for every figure.
- A measured scene needs a moving player: confirm it from the `s*-g11.png` frames, not the HUD clock.
- No `gh`. Never `pkill -f` or `pgrep -f`.
- This is a headless session, and it ends when the turn ends. Never end a turn "waiting for a background task". With
  runs pending, commit and push `docs/lanes/drawrec1010/WAITING`, one `run <request-id>` line each; lanewaker
  resumes you when they are DONE.
