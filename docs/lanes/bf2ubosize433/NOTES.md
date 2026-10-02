# lane.bf2ubosize433 notes

#433 (0.5: sustained fps). Brief: size Battlefield 2's per-draw UBO-rebind
cost before anyone builds the push-constant fix that bf2stall433 named
(docs/lanes/bf2stall433/NOTES.md sections 7-8). This lane measures; it does not
build the fix.

Base: master 66bce0c222.

## 1. What the counter has to see (reading, no device)

- **The per-register dirty bits cannot be used.** `pg->vsh_constants_dirty[]`
  is set by every constant write in pgraph.c and never cleared on the Vulkan
  path (only `vsh_constants_any_dirty` and the `ltc*_any_dirty` flags are, in
  `pgraph_vk_update_shader_uniforms`). Read per draw, it would say "every row
  ever written". So the counter keeps its own shadow and compares content.
- **Content, not writes.** The fix pushes what *changed*. A game rewriting a
  matrix with the same value costs nothing under the fix, so the counter
  compares bytes.
- **Per upload, not per call.** `pgraph_vk_update_shader_uniforms` runs more
  than once for some draws (`pgraph_vk_bind_shaders` calls it, and so do three
  draw.c paths). The block is written to a new offset at exactly two sites:
  `pgraph_vk_update_descriptor_sets` (shaders.c, when `uniforms_changed`) and
  `upload_draw_uniforms` (draw.c, the draw queue). The counter hooks those.
- **The uploaded layouts, as well as the guest registers.** The VS layout
  holds `c[192]` plus `inlineValue`, lighting, fog, `clipRange` and so on, and
  the PS layout has its own. The push fix has to carry every changed byte of
  both, so the main histogram is over 16-byte chunks of both layouts, compared
  with the previous upload of the *same* shader binding. A binding switch
  changes the layout and is counted separately (`sw`). The guest-side count
  (`c`, rows of `pg->vsh_constants`) does not depend on the binding, so it
  covers switches too.
- **Binds happen every draw regardless.** `bind_descriptor_sets` re-binds the
  UBO set on every draw, whether or not the offsets moved. The counter counts
  binds and the binds that repeat the previous one.

## 2. The counter (d9729d6250, perflog builds only)

`ubosz[n d q sw lay <hist> sum c <hist> sum span <hist> pk8 pk16 bind/same]`
and `ubosz-top[c <row:count x8> | u <stage.uniform:chunks x6>]`, on
hakuX-stall (the dispatcher's logcat allow-list carries it), from
`opt_stats_log_and_reset`, every 60 flip finishes. Histogram bins: 0, 1, 2,
3-4, 5-8, 9-16, 17-32, 33-64, 65-128, 129+.

- `pk8`/`pk16` replay the fix's policy on the same uploads: push every chunk
  changed since the policy last uploaded, while there are at most 8 (16), else
  upload and rebind. The count is the uploads it still rebinds. Add `sw` for
  the switches, which it rebinds as well.
- Hooks: the two upload sites; the three UBO bind sites
  (`bind_descriptor_sets`, `rebind_ubo_dynamic_offsets`, the reorder replay).
- Prototypes are repeated in draw.c and shaders.c because `vk/renderer.h` is
  outside this lane's files. The natural home is renderer.h.
- Cost: per upload, a 3 KB compare of the constants plus one compare of both
  layouts (about 7 KB), and copies of each. At ~2,150 uploads a frame that is
  a few ms of draw-thread CPU, so **this build's fps is not a measurement**.
  Release builds compile none of it.

## 3. Local verification (no device)

- `ubosz_selftest.py` (this dir) cuts the counter block out of shaders.c as it
  is in the tree and compiles it on the host against stub types, with ASan and
  UBSan. It drives three sequences with known answers: 4 rows a draw on one
  binding; one new row a draw, so the policy rebinds every 9th (17th) upload;
  and alternating bindings, a PS-only change, a single uniform, the partial last
  chunk, an identical upload and repeat binds. It also checks that a reset
  leaves an empty window. **PASS, 31 checks.**
- `ubosz_read.py` on bf2stall433's A1 soak (no counter in that build): VOID,
  as it should be. On a synthetic logcat built from A1's rows (a ubosz line
  injected at each xemu-work row): 17 heavy windows (armread.py found 17 in
  the same run), and F16 0.80 and R16 0.287, as constructed.
- In the real logcat, the opt-stats lines land ~0.1 s (one frame) before their
  hakuX-pace row, so the nearest-row join within 2 s pairs the right windows.
- NDK clang type-check of shaders.c and draw.c (`.scratch/cc_check.py`, the
  main tree's compile_commands pointed at this worktree), with
  `NV2A_PERF_LOG=1` and without: rc 0, and the only warnings are on lines that
  were already there. `check_android_guards.py`: ok.

## 4. Prediction and run

`docs/testing/predictions/bf2ubosize433-bf2-ubosz.json`, registered before any
run: one Nova soak of the counter build, route bf2mc, 420 s, frames every
20 s, perflog, default regimen. The verdict is read from heavy windows
(BE >= 1800):

- **PUSH**: F16 >= 0.50 (same-binding uploads changing <= 16 chunks) and
  R16 = (pk16 + sw)/n <= 0.50. Then a successor brief.
- **PUSH-SWITCH-BOUND**: F16 >= 0.50, R16 > 0.50. The brief then has to
  include one uniform layout shared across shaders.
- **LARGE**: F16 < 0.50 and median > 32 chunks. Then the lever is batching.
- **MIXED** otherwise. Note **Z** if >= 30% of uploads are identical.

Prior: PUSH ~50%, SWITCH-BOUND ~20%, LARGE ~15%, MIXED ~15%.

### The real push budget (reading, for whoever builds the fix)

- The pipeline layouts already push a geometry-stage vec4 at offset 0
  (`GEOM_PUSH_CONSTANT_SIZE`, 16 B). Inline attribute values go in push
  constants only when `maxPushConstantsSize >= 16 + 16 x 16 = 272`
  (`pgraph_vk_init_shaders`). Turnip's `maxPushConstantsSize` is
  `MAX_PUSH_CONSTANTS_SIZE`, which I believe is 256 upstream. **Not verified
  against the fleet's driver**: nothing in a Nova logcat prints it, and the
  Turnip copy bf2stall433 extracted does not carry the header. If it is 256,
  then on the Nova inline attributes do NOT go in push constants: `inlineValue`
  travels in the UBO and its changes count in `lay` (a `v.inlineValue` entry in
  `ubosz-top` would show it). The fix's lane should log the limit at init
  first.
- If so, the free push space on the Nova is 256 - 16 = **240 B, 15 vec4**, and the
  fix also has to tell the shader which register each pushed vec4 replaces (an
  index list, or a fixed per-title mapping). In practice that is ~12-14 vec4 of
  data. The prediction's 8 and 16 bracket it, and `pk8`/`pk16` read on each
  side.

## 5. Status: waiting on the device (2026-10-02 09:40 PDT)

Queued `1790958948-lane.bf2ubosize433-1976093` (ref d9729d6250, normal
priority, because #433's labels are unreadable while gh is down). The Nova is
under lane.pathfind's direct-drive hold since 16:24Z, so the dispatcher will
not claim it until that hold is released. Nothing else is queued. When the run
is DONE: `ubosz_read.py <result dir>`, judge, then the successor brief or the
batching lever (section 4).

The fold also needs a finished run built from the FINAL head (offline_fold.py
matches the head sha exactly), and this branch carries emulator code. Plan:
after the results commit, queue one more identical soak at the final head as a
replicate, and record its numbers outside the branch (the successor brief and
the session report) so that the head does not move again.

### Why attempt 1 ended here

The session that wrote this status ended correctly, not short: the run was
queued and genuinely blocked behind another lane's Nova hold, this lane has no
way to wait inside a session without a background task dying with it
([[lane-background-task-dies-with-session]]), and the brief itself caps device
work at the one soak queued. Per `roles/lane.md` ("Never end a session waiting
on your own background task"), the correct move with a result pending outside
the session was to post the `waiting:` line (OUTBOX, 09:40 PDT) and stop, which
is what happened. The plan in this section (one more replicate soak at the
final head before fold) was written before anyone had looked at the first
run's numbers, and turned out not to be needed: see section 6. `handback.sh`
resumed this lane (attempt 2) once the run was DONE, per its own contract.

## 6. Judged: PUSH (2026-10-02 15:01 PDT)

`ubosz_read.py` against `1790958948-lane.bf2ubosize433-1976093` (ref
d9729d6250): `ok ubosz windows=37 joined=37 max|dt|=1.94 s`, 18 heavy windows
(BE >= 1800), M0 **PASS**.

```
F8 = 0.873  F16 = 0.917  R16 = 0.413  switch share = 0.360
identical uploads Z = 0.072  median bin 3-4
VERDICT: PUSH: most heavy-view uploads change <= 16 vec4, and a 16-vec4 push
policy keeps the UBO bind off most of them -> successor brief
```

- **F16 = 0.917** >= the 0.50 PUSH threshold by a wide margin: 92% of
  same-binding uploads in BF2's heavy views change 16 or fewer 16-byte chunks
  (<= 16 vec4) of the VS+PS layout. Median bin is **3-4** chunks, well inside
  even the 8-vec4 budget (F8 = 0.873).
- **R16 = 0.413** <= 0.50: even after adding binding switches (switch share
  0.36, which a push-constant fix cannot remove on its own) to the uploads a
  16-vec4 policy would still have to rebind, under half of all uploads would
  still force a UBO rebind. So this is **PUSH**, not PUSH-SWITCH-BOUND, though
  the switch share is large enough that the successor brief should still cover
  it (see below) rather than treat it as free.
- **Z = 0.072**: only 7% of same-binding uploads are byte-identical to the
  previous one, so "skip the redundant rebind" alone is a small win next to
  "push what's small instead of rebinding."
- **What actually changes** (`ubosz-top`, pooled over heavy+light): by far the
  largest chunk counts are in `v.ltctxb`, `v.c` (the raw vertex-constant
  array), `v.ltctxa`, `v.ltc1`, then the infinite-light direction/half-vector
  and specular params. By register (`c<n>`), the hottest rows are **c112-c115**
  then **c96-c105** — BF2's fixed-function path rewrites a handful of
  lighting-context registers (not matrices) almost every draw. This matches
  the "small, frequent" shape the prior called for 3-4 vec4 typical, not the
  12-14 vec4 estimate in section 4's push-budget note, which was a ceiling,
  not the typical case.
- Prior stated before the run: PUSH ~50%. Observed: PUSH, decisively (F16
  0.92 against a 0.50 bar).
- This run used the ref from section 2 (d9729d6250); no commit since then
  touches `hw/` (`git diff --stat d9729d6250..HEAD -- hw/` is empty), so the
  run remains built from the code at HEAD for fold purposes.

Run budget used: 1 of however many were available (the one queued in section
5). No second run was needed: M0 is PASS, not BELOW RESOLUTION, and the
verdict is clean PUSH, not MIXED.

Successor brief posted to OUTBOX.md for lane.local to dispatch (forge #656).
Per this lane's brief, the fix itself (vk/shaders.c, glsl/vsh*.c, vk/draw.c)
is not built here.
