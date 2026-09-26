# Audit pass 2: PR #389 (claude/docs-tooling-agentic-coding-u152m1), #274 SFP guard

Head verified: `07a47ebd6b`. Pass 1 audited `a6a47f4e70` (see the `-pass1.md`
file beside this one, second section).
Auditor: job.cloud, 2026-09-26.

**Result: clean. Pass 1 raised no HIGH or MEDIUM, and no scenario it recorded
can mislead a reader of the code at this head. Next state: `fold-ready`.**

## What changed since pass 1

`git diff a6a47f4e70 07a47ebd6b`, excluding the pass-1 file itself:

- `hw/xbox/nv2a/pgraph/vk/draw.c`: a comment-only change of 5 lines inside the
  guard's block comment in `begin_pre_draw_inner()`. The `else if` condition,
  its `OPT_STAT_INC(sfp_miss_uniforms)` and `sfp_ok = false` are byte-identical.
- `docs/testing/nv2a_index.json`: regenerated for the shifted lines (tool output).
- `docs/lanes/remote/NOTES.md`: lane notes only.

No behaviour moved, so every "What was checked" item of pass 1 still holds as
written.

## The pass-1 findings

**LOW 1 (`sfp_miss_uniforms` counts two causes).** Not changed, and pass 1 did
not ask for a change. Observability only; it stays open as a LOW.

**LOW 2 (the comment's "a miss clears the flags" fails under async compile).**
Fixed. The comment now reads that the flags stay set while the bound shader is
still compiling under `OPT_ASYNC_COMPILE`, because the refresh returns early
and the draw is skipped. Checked against the code at this head:

- `shaders.c:1317-1322`: `pgraph_vk_update_shader_uniforms()` returns when
  `binding->ready` is false, before the flag clear at `shaders.c:1370-1373`.
- `draw.c:4192`: the full path counts the draw as `draws_skipped_pending` and
  skips it.

The comment matches both. The scenario (a reader trusts the comment and
misreasons about SFP hit rates on an async-pending shader) no longer occurs.

**LOW 3 (no scored capture detects a revert of the guard).** A coverage gap,
not a defect in the diff, and the PR discloses it under "Not covered". It
remains true at this head; nothing in pass 2 can or should close it.

## CI and merge state

CI at `07a47ebd6b`: build ×2 and check, all SUCCESS. GitHub reports the PR
`MERGEABLE`.
