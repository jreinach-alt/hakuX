# Audit pass 2 — PR #234, `lane/vshconst`: emulate vertex-program writes to constant registers (#233)

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #234, branch `lane/vshconst`, remediation tip **`0e5f4167a3`**
("nv2a/vsh: fix the two MEDIUMs from vshconst pass 1").
**Pass 1** `2026-09-25-vshconst-pass1.md`, audited at `a73eb00a7f`.
**Date** 2026-09-25.

**Both pass-1 MEDIUMs can no longer occur. The head is not clean: the
remediation commit left `nv2a_index.json` stale, so CI `check` is red.**
Verdict: `needs-remediation`. The fix is mechanical: regenerate the index.

## M1 (paired ILU reads its MAC partner's constant write): closed

For the pass-1 program `mad c[5], v0, c[5], c[5]` + `rcp r1.x, c[5].x`
(output mux = MAC, `FLD_CONST` = `FLD_OUT_ADDRESS` = 5), I traced
`decode_token` → `decode_opcode` at `0e5f4167a3`:

* On the MAC call, `use_temp_var` is set because the ILU is not NOP. The
  suffix is now allocated at the top of the branch, before the output write,
  so the constant arm can append to it. In the constant arm, `use_temp_var`
  sends the write to `_c_rw_tmp` with the o-mask. It also appends
  `c_rw[5].<m> = _c_rw_tmp.<m>;` to the suffix. Here `<m>` is
  `&mask_str[O_MASK][1]`, and `O_MASK != 0` is guaranteed by the enclosing
  condition, so `<m>` is never empty.
* `decode_token` appends the ILU statement to `ret` and only after that the
  `mac_suffix`. So `RCP(R1,x, c_rw[5].x)` reads the old `c_rw[5]`, and the copy
  lands afterwards. Both units read before either writes, as the emulator's
  `prepare_inputs` does.
* The out-of-range arm is checked first and still goes to `_c_rw_oob`
  whether or not the MAC is paired. That is correct, because nothing reads it.
* `_c_rw_tmp` is declared beside `c_rw` and `_c_rw_oob`, inside the block
  emitted only when the program writes a constant. So a program that writes no
  constant produces the same GLSL as before.
* The converse pairing (ILU muxed to a constant, MAC present) was already safe.
  The MAC statement is emitted first and has read all its inputs before the
  ILU writes.
* Moving `*suffix = mstring_new()` earlier changes nothing else. The same
  condition guards it, it still runs once per MAC call, and the ARL and R-temp
  arms append to it just as before.

The scenario cannot occur.

## M2 (third merged Vulkan draw misses the writeback): closed

* `pgraph_vsh_writeback_constants` now sets `changed` in the same
  `bits != pg->vsh_constants[r][c]` branch that marks a constant dirty. After
  the loop it bumps `pg->any_reg_gen` if `changed` is set.
* The call order is `SET_BEGIN_END(END)`: `draw_end` (which enqueues draw N and
  records `q->any_reg_gen`), then the writeback (which bumps
  `pg->any_reg_gen`). On draw N+1, `try_enqueue_draw_arrays`
  (`vk/draw.c:5004`) and the indexed variant (`:5119`) see
  `pg->any_reg_gen != q->any_reg_gen`, so they call `upload_draw_uniforms`
  instead of reusing the previous entry's offsets.
* Other readers of `any_reg_gen`, checked for regressions: the fast path at
  `draw.c:3965` only drops to the slow path, and the flush replay at
  `:5283/:5301/:5537` saves and restores it. Neither is made wrong by an extra
  bump. The bump fires only when a constant actually changed, so programs
  that write no constant are untouched.

The scenario cannot occur.

## New in the remediation: stale `nv2a_index.json` (blocks fold)

The remediation adds 10 lines to `hw/xbox/nv2a/pgraph/pgraph.c` and does not
regenerate the index. CI `check` on `0e5f4167a3`
(run 36127240122) fails with:

```
STALE INDEX - regenerate with: nv2a_index.py build --tests DIR
  sites differ (committed 765, tree 765; 138 MOVED)
    moved: NV097_ARRAY_ELEMENT16:  hw/xbox/nv2a/pgraph/pgraph.c:4605 -> ...:4615
```

The site count is unchanged (765 and 765). Each of the six moves the log
prints shifts by +10, which is the number of lines this commit added to
`pgraph.c` above them. So this looks like line numbers only. I have not seen
the other 132 moves. The fold
job gates on CI green before it would ever rebuild an index, so the PR cannot
fold as it stands.

**Remediation.** Regenerate with `nv2a_index.py build` against a tests tree
of the same `provenance.tests_commit`, commit, and push. Nothing else is owed
for pass 2. Once `check` is green on the new head, this record's verdict for
M1 and M2 stands, and the PR can go straight to `fold-ready` with no third
audit, provided that commit touches only `nv2a_index.json`.

## LOWs

L1 to L3 were left as recorded, and `NOTES.md` says so. They do not block.

## Still owed (not audit findings)

The remediation has not been re-armed. Neither fix can move the arm 2
captures (no `.vsh` on the pgraph disc writes a constant), so this is
acceptable. The handheld ILU RCP Tests run through `--program vsh` is still
owed, as `NOTES.md` records.
