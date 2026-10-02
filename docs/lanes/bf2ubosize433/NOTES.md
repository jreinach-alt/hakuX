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

(Results: section 5, after the run.)
