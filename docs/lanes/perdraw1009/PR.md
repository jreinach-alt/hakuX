# perdraw1009: cut the renderer's per-draw CPU cost (NFS Most Wanted, ~11 us per draw) (#433, 0.5)

State: draft

Lane: perdraw1009          Issue: none (#433 umbrella)
Base: master @ 39379dafdd
Files: docs/lanes/perdraw1009/PR.md, docs/lanes/perdraw1009/NOTES.md, docs/lanes/perdraw1009/OUTBOX.md, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: not yet registered -- no device run yet
Needs device: yes (Nova only)    Needs NDK: yes

Work in progress, attempt 2 (attempt 1 only opened this draft claim; see
NOTES.md section 0 for why -- a stale lane.sh copy, not a code problem).

Done so far: NOTES.md section 1 reads `flush_draw_one_pass` and its callees
against lane.local's 10-09 NFS profile and ranks candidates (most of the
named buckets are already dirty-tracked via a 3-tier fast-path; the
remaining headroom in shaders.c is a byte-identical-upload skip, unverified
for NFS). Job item 2 (take the perflog ubosz counter out of the default
path) is implemented: `HAKUX_UBOSZ_LOG` env flag, default off, gates
`pgraph_vk_ubosz_note_upload`/`_note_bind`/`_log_and_reset` in shaders.c with
no draw.c edit needed. Not yet done: the NFS route (blocked on confirming the
LT/RT gas-axis swap on device, addenda in NOTES.md section 3), any A/B,
pixel check, generalisation arm. vk/draw.c, vk/surface.c, vk/texture.c are
still surfgpu1009's (not folded yet); see OUTBOX for what's blocked on that.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
