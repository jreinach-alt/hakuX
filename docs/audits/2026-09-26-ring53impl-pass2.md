# Audit pass 2: PR #395, lane/ring53impl

#53: six-entry ring of stale FF lighting inputs under a lit vertex program.
Read at head `8d72e2d4af`. The remediation is `2bafeccd3e` (code) and
`8d72e2d4af` (notes). CI (`build` x2, `check`) is green at this head.

**Verdict: clean. HIGH-1 can no longer occur, and the fix introduces no new
defect. LOW-1, LOW-2 and LOW-3 are still open, as pass 1 allowed.**

## HIGH-1: Vulkan's super-fast pre-draw path kept the previous draw's `ringPhase`

Pass-1 scenario: two lit-program inline-buffer quads back to back, with
nothing between them (or only same-value rewrites). Quad 2 passed every
`sfp_ok` test and drew with quad 1's `ringPhase`.

I traced the path quad 2 now takes:

1. `pgraph_glsl_set_vsh_uniform_values` (`glsl/vsh.c`) builds quad 1's block.
   Because quad 1 reads the ring, it records `ring_upload_phase = p` and
   `ring_upload_gen = ring_gen`.
2. At quad 1's END, `ring_pos` advances by 4 (`pgraph.c`, after
   `draw_end`).
3. Quad 2 reaches `begin_pre_draw_inner` (`vk/draw.c`). Every earlier test
   passes, as in the pass-1 scenario. The new last test,
   `pgraph_glsl_ring_uniforms_stale(pg, &r->shader_binding->state.vsh)`, then
   sees `ring_phase() = (p+4)%6 != p` and sets `sfp_ok = false`. The
   function never reaches `pre_draw_skipped = true; return;`.
4. The medium-fast path (or, if its conditions fail, the full path through
   `pgraph_vk_bind_shaders`) calls `pgraph_vk_update_shader_uniforms`. That
   rewrites `ringPhase` into the layout. With no constant dirty flag set, the
   layout hash is compared with `last_vsh_uniform_hash`. The phase float
   differs, so `uniforms_changed = true`.
5. `pgraph_vk_update_descriptor_sets` (`vk/shaders.c`) sees
   `uniforms_changed` and appends a fresh UBO. `pre_draw_skipped` is false,
   so `begin_draw` binds the new offsets. Quad 2 draws with `ringPhase = p+4`.

The same chain covers a ring refill without a phase move: `ring_gen` is
bumped on every `pgraph_glsl_ring_fill`, which makes `ringInput` differ.
If `ring_gen` moves but the refill writes byte-identical values, the hash
finds no change and the old UBO is reused. The old UBO holds the same values,
so this is correct.

Edge cases checked:

- **Async compile.** If the bound shader is still compiling,
  `update_shader_uniforms` returns before the setter records anything. The
  check keeps missing and the draw is skipped, the same as the #274 flags.
  Once the shader is ready, one refresh settles it.
- **Array and element draws under a lit program.** They get `ringPhase = -1`.
  The first one after an inline draw misses (`-1 != p`), refreshes, and
  records `-1`. Later ones hit `sfp` again unless the ring refills.
- **Programs that do not read the ring** (FF, or a program with lighting off).
  `vsh_reads_ring` is false, so the check is constant-false and the setter
  records nothing. Those paths behave as they did before.
- **Initial state.** `ring_upload_phase` starts at 0.0. The first draw under
  any lit program misses `sfp` anyway, through `shader_bindings_changed`.
- **GL.** It shares the setter, so it records the fields too, but it
  refreshes on every bind and never reads them. This is harmless.

Cost: under a lit vertex program, every inline draw that moves the ring now
takes the medium-fast path instead of the super-fast one. That is the cost of
being correct: the uniform block really differs. It is confined to draws that
read the ring.

The notes say that no device test pins this scenario, because no suite draws
two lit-program inline quads with no method between them. The scenario was
found by reading the code, and it is closed in the code, so that gap is
recorded rather than ranked.

## LOW-1, LOW-2, LOW-3

These are unchanged by the remediation and remain open as LOWs: the
mid-header rollback double-weigh, a constant split across headers weighing 0,
and the ring missing from the savestate. None of them blocks the fold.

## Result

Clean. `needs-audit-2` → `fold-ready`.
