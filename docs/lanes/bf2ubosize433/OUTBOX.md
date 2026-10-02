# lane.bf2ubosize433 outbox

## #433 -- 2026-10-02 09:40 PDT

[lane.bf2ubosize433] waiting: one Nova soak, `1790958948-lane.bf2ubosize433-1976093`. It is queued behind lane.pathfind's direct-drive hold on the Nova. It resolves when the run is DONE in `dispatch/results/`.

- **Built and checked without a device:** a perflog-only counter (`ubosz[...]` on hakuX-stall, every 60 flips). For each uniform upload it reports how many 16-byte chunks of the shader uniform blocks changed since the previous upload, and how many of the 192 vertex-constant registers changed. It also counts shader switches and replays the fix's policy: push up to 8 or 16 changed vec4 and rebind only past that, counting the uploads that would still rebind. A host selftest compiles the exact code from the tree and passes all 31 checks. The judge reproduces the 17 heavy windows bf2stall433 found in its master soak.
- **Found while reading:** the per-register dirty bits are never cleared on the Vulkan path, so they could not be the counter. If Turnip allows 256 bytes of push constants, as I believe it does (not yet confirmed on the fleet's driver), the Nova has 15 vec4 free after the existing geometry vec4, and inline attribute values already ride in the uniform block.
- **Registered before the run** (`bf2ubosize433-bf2-ubosz.json`):
  - PUSH: most heavy-view uploads change 16 vec4 or fewer, and the policy keeps the rebind off most of them. Then a successor brief for the push-constant fix.
  - SWITCH-BOUND: the changes fit, but shader switches still force rebinds.
  - LARGE: most uploads change more than 32 vec4. Then the lever is batching draws that share constants.

## #433 -- 2026-10-02 15:01 PDT

[lane.bf2ubosize433] BF2's per-draw uniform-block churn: judged **PUSH**. The push-constant fix bf2stall433 named is justified; it is not built in this lane. Successor brief for a new lane follows.

- **Verdict**, from `1790958948-lane.bf2ubosize433-1976093` (Nova, bf2mc route, 420 s, 18 heavy windows, M0 PASS): F16 = 0.917 (>= 0.50 bar), R16 = 0.413 (<= 0.50 bar), switch share 0.36, identical-upload Z 0.072, median bin 3-4 chunks. 92% of BF2's heavy-view uniform uploads, on the same shader binding, change 16 or fewer 16-byte chunks of the VS+PS layout; the typical change is 3-4 chunks (one small lighting-context block), not a full block. Full numbers: `docs/lanes/bf2ubosize433/NOTES.md` section 6.
- **What changes, concretely**: the hottest uniforms by changed-chunk count are `v.ltctxb`, `v.c` (raw vertex constants), `v.ltctxa`, `v.ltc1`, then the infinite-light direction/half-vector and specular params. By register, `c112`-`c115` then `c96`-`c105` churn on nearly every draw. BF2's fixed-function path is rewriting a lighting-context block per draw, not a transform matrix — smaller than bf2stall433's section-4 estimate of 12-14 vec4 (that was a ceiling from the push-constant budget math, not a measurement of what BF2 actually sends).

### Brief for the next lane (forge #656): build the push-constant fix

**Files**: `hw/xbox/nv2a/pgraph/vk/draw.c`, `hw/xbox/nv2a/pgraph/vk/shaders.c`,
`hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`, `hw/xbox/nv2a/pgraph/glsl/vsh-prog.c`,
`hw/xbox/nv2a/pgraph/glsl/vsh.c` (same set bf2ubosize433 held, now free).

1. **Confirm the Nova's `maxPushConstantsSize` first** (NOTES.md section 4 of
   this lane flagged this as unverified: believed 256 B upstream Turnip, not
   read off the fleet's driver). Log it once at `pgraph_vk_init_shaders`. If
   256 B, the existing 16 B geometry-stage push constant leaves **240 B / 15
   vec4** free — comfortably above what this lane measured BF2 actually needs
   per draw (median 3-4 chunks = 48-64 B; F16's 16-chunk/256 B bar was the
   fix's own budget ceiling, not the typical draw).
2. **Policy**: keep the uniform block in a UBO, rebound (new descriptor set)
   only when the accumulated unpushed change since the last rebind would
   exceed the push budget, or on a shader-binding switch (36% of uploads in
   this run switch bindings — a push-constant fix alone does not remove a
   rebind on those; see "do not" below). Otherwise push the changed 16-byte
   chunks directly (`CP_LOAD_STATE6 SS6_DIRECT` on Adreno/Turnip — no
   descriptor, no bindless-cache invalidation).
3. **Which chunks to push**: the fix needs a way to tell the shader which
   register(s) a pushed vec4 replaces — an index list, or (cheaper, given how
   concentrated the churn is: `c112`-`c115`/`c96`-`c105` and the `ltc*`
   uniforms dominate) a fixed mapping for the handful of registers/uniforms
   that churn most, falling back to a full rebind for anything outside that
   set. Use this run's `ubosz-top` breakdown (NOTES.md section 6) to size the
   fixed set; do not assume it generalizes to other titles without checking.
4. **Rebind reduction target**: R16 in this run is 0.413 — a correct fix
   should drop the realized UBO-rebind rate on BF2's heavy views at least
   that far (to <= ~0.41 of uploads), and the earlier GPU-ms numbers
   (bf2stall433 A1, ~12-14 us/draw) are the thing to re-measure afterward.
5. **Do not** assume push constants alone remove binding-switch rebinds
   (switch share 0.36 here): if switches turn out to dominate the residual
   rebind rate after the fix, the next lever is a uniform layout shared across
   shaders (PUSH-SWITCH-BOUND in the original prediction's legs), not more
   push-constant budget.
6. **Verification**: `ubosz_read.py` (this lane, `docs/lanes/bf2ubosize433/`)
   still works unmodified against the fix build (it reads the existing
   `ubosz[...]`/`ubosz-top[...]` perflog lines) and can be re-run B-side to
   confirm the realized rebind rate moved as predicted, alongside a pixel-
   identical check (the fix must not change what value ends up in a register,
   only how it gets there) and the GPU-ms A/B bf2stall433 already has a
   recipe for.

Run budget used by this lane: 1 Nova soak (the one queued in the brief). No
second run was needed.
