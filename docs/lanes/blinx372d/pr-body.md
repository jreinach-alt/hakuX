Lane: blinx372d            Issue: #372
Base: master @ 9f5a3dfc98 (merged in as 790dc14730; branched from a5b5b628f2)
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/blinx372d/NOTES.md, docs/lanes/blinx372d/pr-body.md, docs/lanes/blinx372d/cc_surface.py, docs/lanes/blinx372d/abread.py, docs/testing/predictions/blinx372d-demo-ab.json, docs/testing/predictions/blinx372d-mnm.json, docs/testing/predictions/blinx372d-mnm2.json
Prediction: docs/testing/predictions/blinx372d-mnm2.json @ b002f5ac0b2b5dc2 (must-not-move on the merged refs, arms job); earlier: blinx372d-mnm.json @ 4d97b2fbcd03e5b3 (PASS), blinx372d-demo-ab.json @ 427f96bff6083462 (VOID: inert on the demo)
Needs device: yes    Needs NDK: no

This PR adds an `[evict372]` counter and a GPU handoff for incompatible evictions. The counter shows that the demo's two waits are a case the handoff does not cover, so the demo does not get faster. That case is written up for the next change.

**Counter (9540a21f79).** `[evict372]` prints which compatibility fields differ on an incompatible eviction, and the most-repeated held -> target pairs. On the Thor, in the demo:

    m08:993/0 m40:993/0     (plus m10:14/0, boot-movie swizzle pairs)
    Z f130 ln p2560 640x480 b4 -> Z f130 ln p2560 320x240 b4   n=993
    Z f130 ln p2560 320x240 b4 -> Z f130 ln p2560 640x480 b4   n=993

Both waits come from one D24S8 zeta surface at one address and pitch that switches between 640x480 and 320x240. The role, format, pitch and swizzle are all unchanged.

**Hunk (0f9735049c).** An incompatible eviction whose shelved partner has the same width, height, pitch, swizzle and bytes per pixel, differing only in host format or colour/zeta role, is now recorded on the GPU with no host finish:

- image -> buffer, packed by the download's compute pass when the source is depth-stencil;
- buffer -> buffer, unpacked by the upload's pass when the destination is depth-stencil;
- buffer -> image.

The partner becomes the active binding and owes the download. It is marked dirty through `pgraph_vk_surface_watch_mark_dirty`, so its CPU-access watch is live. The evicted binding is shelved clean and stale. Every other case takes the unchanged download, including any size or pitch change, so the demo's flip is declined.

**Interaction with #387's watch.** `surface_access_callback` downloads only *active* bindings on a CPU access, so an owed download cannot be left on a shelved binding. The obligation moves to the active partner instead (NOTES sec 3).

**Results.**

| arm | result | reading |
|---|---|---|
| must-not-move, 5 suites (`blinx372d-mnm.json`) | 102/102 rows byte-identical; B `handoffs=2` | PASS, exercised |
| demo A/B, Thor (`blinx372d-demo-ab.json`) | A 12.98 fps, B 12.25 fps; B `handoffs=0` | VOID: inert on the demo |

In the must-not-move arm, the two `Depth_buffer_fixed_function/z16_*_FZy_M00ffff` rows are `white-content` (unreadable) in both arms, with identical values. `blinx372d-mnm2.json` repeats the must-not-move arm on the merge of master.

**The demo's case** (NOTES sec 5). The 320x240 binding is exactly the top-left quadrant of the 640x480 one in VRAM, so a quadrant `vkCmdCopyImage` is exact for the pixels it covers. Big -> small still owes the other three quadrants to VRAM from a shelved binding, which the watch does not guard. Small -> big relies on the big binding's image matching VRAM outside the quadrant, and a guest CPU write to a clean shelved binding is not seen (the same exposure as master's same-format rebind). So small -> big alone is the candidate next change, after that gap is measured or closed. It would remove one of the two waits.

Build check: `vk/surface.c` passes a `-Werror` syntax check with the desktop build's flags (`cc_surface.py`), and `check_android_guards.py` passes. No local Android build was done; the dispatcher builds each arm's ref.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
