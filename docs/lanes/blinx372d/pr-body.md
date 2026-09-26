Lane: blinx372d            Issue: #372
Base: master @ a5b5b628f2
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/blinx372d/NOTES.md, docs/lanes/blinx372d/pr-body.md, docs/lanes/blinx372d/cc_surface.py, docs/lanes/blinx372d/abread.py, docs/testing/predictions/blinx372d-demo-ab.json, docs/testing/predictions/blinx372d-mnm.json
Prediction: docs/testing/predictions/blinx372d-demo-ab.json @ 427f96bff6083462 (soak A/B, queued by this lane); docs/testing/predictions/blinx372d-mnm.json @ 4d97b2fbcd03e5b3 (must-not-move, arms job)
Needs device: yes    Needs NDK: no

This PR removes the two synchronous `pgraph_vk_finish(SURFACE_DOWN)` calls per frame in Blinx's attract demo. Both come from the incompatible-binding eviction in `update_surface_part`.

**Hunk (0f9735049c).** Some incompatible evictions have a shelved partner with the same width, height, pitch, swizzle and bytes per pixel, differing only in host format or colour/zeta role. For those, the download-to-VRAM-then-re-upload round trip is now recorded on the GPU as image -> buffer (packed by the download's compute pass for a depth-stencil source) -> buffer (unpacked by the upload's pass for a depth-stencil destination) -> image. There is no host finish. The byte stream is the same one the VRAM round trip carried.

The partner is now the active binding and owes the download. It is marked dirty through `pgraph_vk_surface_watch_mark_dirty`, so its CPU-access watch is live. The evicted binding is shelved clean and stale.

Every other case falls back to the unchanged download: pitch or size mismatch, another binding over the range, a CPU request or write, no TCG, or a surface scale other than 1.

**Interaction with #387's watch.** `surface_access_callback` downloads only *active* bindings on a CPU access. For a shelved one it only cancels the writeback on a write. So leaving the owed download on the shelved binding (the brief's proposal) would let a guest read see stale VRAM. The obligation goes to the active partner instead. Details are in NOTES sec 3.

**Counter (9540a21f79).** `[evict372]` prints which compatibility fields differ, and the most-repeated held -> target pairs. The counter soak and both A/B arms are queued on the Thor.

| arm | request | ref |
|---|---|---|
| counter | 1790432905-blinx372d-2396550 | 9540a21f79 |
| A | 1790433606-blinx372d-2480701 | 9540a21f79 |
| B | 1790433607-blinx372d-2481219 | 0f9735049c |

Price (bound): median Tot 66-71 ms, Sub 33.5-35.2 ms, GPU 44-46 ms. That gives a GPU-bound ceiling of 22-23 fps by Tot, about 18-19 by gfps, against 12.4-12.6 now.

Build check: `vk/surface.c` passes a `-Werror` syntax check with the desktop build's flags (`cc_surface.py`), and `check_android_guards.py` passes. This lane did no local Android build; the dispatcher builds each arm's ref.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
