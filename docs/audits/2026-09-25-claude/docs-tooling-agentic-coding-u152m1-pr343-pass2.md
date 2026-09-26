# Audit pass 2 -- PR #343 (claude/docs-tooling-agentic-coding-u152m1, #274)

- Head audited: `ed6591d6e8` (`dad040909e`, the pass 1 head, plus the pass 1 audit file only)
- Master: `origin/master` as fetched 2026-09-25

**Result: clean. Next state: `fold-ready`.** Pass 1 found no HIGH and no
MEDIUM, so there is no scenario that pass 2 has to show can no longer happen.
This pass checks that pass 1's reading still holds on current master and that
nothing blocks the fold.

## The change against current master

- `git diff dcea2d7840 origin/master -- hw/xbox/nv2a/pgraph/vk/` touches only
  `display.c` (+244, the #303 FMV probe). `texture.c`, `surface.c`,
  `shaders.c` and `draw.c` are unchanged since the merge base. The readers that
  pass 1 listed are therefore the same text. The added `display.c` code does
  not mention `push_tex_infos`, `texture_state_gen`, `pipeline_state_dirty`,
  `pgraph_vk_texture_surface_view_retired` or `destroy_surface_image`.
- So the patch-id binding from pass 1 still holds (the registered b_ref is the
  head's `texture.c`), and so do the four hand-reported `must_not_move` guard
  PASSes.

## The conflict (pass 1 process note)

`git merge-tree --write-tree origin/master HEAD` reports exactly one
conflicting path, `docs/testing/nv2a_index.json`. All three sides name the
same `provenance.tests_commit`:

| side | tests_commit |
|---|---|
| origin/master | `6743b6ab16` |
| lane head | `6743b6ab16` |
| merge base `dcea2d7840` | `6743b6ab16` |

When the index is the only conflict and the provenance agrees, `fold.sh`
resolves it mechanically: it takes master's index and rebuilds it over the
merged tree. The lane does not need to merge master first. Because of the
conflict, GitHub has no check rollup on `ed6591d6e8`. CI was green on
`dad040909e`, and the only difference between the two is the audit markdown.

## LOW-1 to LOW-3

These stand as pass 1 described them, since the code is unchanged:

- LOW-1: one redundant push-info rebuild after each retirement of a direct slot. The output is correct.
- LOW-2: file-scope `static bool` instead of a `PGRAPHVkState` field. It costs nothing, because the
  first bind after init rebuilds everything anyway.
- LOW-3: the replay window restores the flags. The master `display.c` addition
  opens no path from the deferred-queue replay body to `destroy_surface_image()` or
  `migrate_surface_image()`, so the scenario is still unreachable.

None of them blocks the fold. They are good candidates for a follow-up that
moves the flag into `PGRAPHVkState` and clears it at the three rebuild sites.
