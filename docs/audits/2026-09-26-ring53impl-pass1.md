# Audit pass 1: PR #395, lane/ring53impl

#53: six-entry ring of stale FF lighting inputs under a lit vertex program.
Diff read at head `7c765d19ec` against `origin/master`. Code under review:
`hw/xbox/nv2a/pgraph/{pgraph.c,pgraph.h}`, `glsl/{vsh.c,vsh.h,vsh-ff.c}`.

**Verdict: one HIGH, three LOW. Remediation needed.**

## Checked and sound

- Uniform sizes: `ringInput` is 36 vec4 = 576 bytes = `sizeof(ff_lit_ring)`
  (6x6x4 floats); the build-time assert pins it.
- Which vertex index the shader sees. Vulkan draws inline buffers and inline
  arrays with `vkCmdDraw(n, 1, 0, 0)`, or `vkCmdDrawIndexed(..., 0, 0, 0)`
  over a 0-based rewrite index list (`vk/draw.c` inline buffer/array
  branches). GL uses `glDrawArrays(mode, 0, n)` or a 0-based
  `glDrawElements`. So `gl_VertexIndex`/`gl_VertexID` is the vertex's
  position in the draw on both, including quads rewritten to triangles. The
  replay path with a non-zero `first_vertex` (`RW_DRAW_DIRECT`) and the draw
  merge are reached only by array and inline-element draws, which get
  `ringPhase = -1`.
- Order at END: `pgraph_glsl_ring_fill` runs before `draw_end` (which clears
  `inline_buffer_populated` in the Vulkan inline-buffer branch), the
  uniforms read `ring_pos` inside `draw_end`, and `ring_pos` advances after.
- `pgraph_ring_weigh` runs only for Kelvin: the slow path calls it in the
  `NV_KELVIN_PRIMITIVE` branch only, and both fast paths require
  `cached_graphics_class == NV_KELVIN_PRIMITIVE`. The BEGIN/DRAW_ARRAYS/END
  squash consumes four words without weighing them, and all four weigh 0.
- Every word is weighed once on the paths that complete: fast-path words are
  weighed after a successful apply, the first-word failure jumps to the slow
  path before weighing.

## HIGH-1: Vulkan's super-fast pre-draw path keeps the previous draw's `ringPhase`

`vk/draw.c` `begin_pre_draw_inner`: when no generation moved and no uniform
dirty flag is set, the draw returns with `pre_draw_skipped = true`, never calls
`pgraph_vk_update_shader_uniforms`, and `begin_draw` does not rebind the
descriptor sets. The draw reuses the previous draw's uniform block. The #274
comment in that function describes this failure for FF setters, which is why
they raise `*_any_dirty` flags.

The ring changes `ring_pos` (every vertex, and every weighted method) and
`ff_lit_ring` without raising any flag or generation. `pgraph_reg_w` bumps
`any_reg_gen` only when a value changes, so a same-value rewrite does not
bump it either. Examples are `COMBINER_COLOR_ICW` and `SPECULAR_ENABLE`,
which the PR measures at +1 each.

Failure scenario: a title draws lit fixed-function quads (which fill the
ring), switches to a lit vertex program, and draws two inline-buffer quads
back to back. Between them there is either nothing, or only re-emitted state
with unchanged values. Quad 1 takes the full path: `ringPhase = p`, and
`ring_pos` becomes p+4. Quad 2 has the same shader, pipeline, textures and
`any_reg_gen`, so it passes every `sfp_ok` test, is drawn with
`ringPhase = p`, and lights its corners from slots p..p+3 where silicon uses
p+4..p+7. The corner colours are wrong. This is not "the ring is
approximate": the PR computes the right phase and then the renderer drops it.

The arm passing does not cover this. It is reachable only when two
lit-program inline draws have no register change between them. Single-quad
test draws separated by constant uploads or test-boundary state changes miss
`sfp` through `vsh_constants_any_dirty` or `any_reg_gen`. GL is not affected
(`gl/shaders.c` `update_shader_uniforms` recomputes on every bind: "FIXME:
Dirty tracking").

Remedy options: make `begin_pre_draw_inner` miss `sfp` when the bound vertex
state reads the ring (`!is_fixed_function && lighting`) and `ring_pos` or the
ring contents changed since the last upload (for example, record the
`ring_pos` and a ring generation the block was built with). Alternatively,
raise `r->uniforms_changed` / a pgraph dirty flag from `SET_BEGIN_END` and
`pgraph_ring_weigh` when the phase moves. The second option costs a refresh
per draw for every shader, so gating on the bound state is cheaper. Either
way, a test should draw two lit-program inline quads with no method between
them and assert that the second one's phase differs.

## LOW-1: the mid-header rollback in cross-command coalescing double-weighs

`pgraph.c`, both coalescing loops (`pgraph_method_try_fast` and the
`pgraph_method` fast table). When `fast_entry_apply` fails at word i > 0 of a
lookahead header, `consumed -= (i + 1)` hands the header and its i applied
words back to the puller, which dispatches them again. Those i words were
already weighed, so `ring_pos` moves i extra slots (mod 6). The register
writes are idempotent; the ring weigh is not. It is reachable only when
`fast_xlat` returns `UINT32_MAX`, which means an enum value outside the
tables (blend factor/equation, depth func, stencil op, shade/polygon mode,
cull/front face). Those tables look complete for valid values, so this needs
malformed guest state. The fix is to weigh after the header's words have all
applied, or to un-weigh on rollback.

## LOW-2: a constant split across headers weighs 0

The transform-program/constant rule puts the +1 on the word whose method
address has `(method >> 2) & 3 == 3`. The hardware's 128-bit write is keyed
on the transform unit's write pointer, not on the method address. If one vec4
is sent as two 2-word headers at `0x0B80`, it weighs 0, and a header that
starts mid-vec4 moves the +1 to a different word. nxdk and D3D always write
whole vec4s from an aligned address, so this is unmeasured and has no known
trigger. It is noted only because the table in the comment presents the rule
as measured.

## LOW-3: ring state is not in the savestate

`ff_lit_ring` and `ring_pos` are not in any vmstate description. After a
load, the ring is zeros at phase 0 until six FF lit vertices refill it, so
the first lit-program draws after a load light from zero inputs. This is
transient and bounded.

## Not findings

- Lit FF array/element draws advance the ring without writing it, and FF
  skinning is excluded. Both are documented limits (#41's), not defects.
- Post-transform vertex-cache reuse for inline-element draws (a repeated
  index might not take a new slot on silicon) is unmeasured. It is an opinion
  without a failure scenario, so it is not ranked.
