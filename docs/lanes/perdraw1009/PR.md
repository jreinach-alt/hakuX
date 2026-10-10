# perdraw1009: cut the renderer's per-draw CPU cost (NFS Most Wanted, ~11 us per draw) (#433, 0.5)

State: draft

Lane: perdraw1009          Issue: none (#433 umbrella)
Base: master @ 39379dafdd
Files: hw/xbox/nv2a/pgraph/vk/shaders.c, hw/xbox/nv2a/pgraph/vk/renderer.h, docs/testing/titles/routes/nfs-mw.route, docs/testing/predictions/perdraw1009-nfs-soak.json, docs/lanes/perdraw1009/NOTES.md, docs/lanes/perdraw1009/OUTBOX.md, docs/lanes/perdraw1009/PR.md, docs/lanes/perdraw1009/WAITING, docs/lanes/perdraw1009/armread.py, docs/lanes/perdraw1009/bulkcheck.sh, docs/lanes/perdraw1009/prof_tree.py
Prediction: docs/testing/predictions/perdraw1009-nfs-soak.json @ b1ee6d91fc5d6477ba737905abe2057af741d806fe49894ad1ad193f96f46641
Needs device: yes (Nova only)    Needs NDK: yes

Release note (none): three opt-in per-draw uniform switches (HAKUX_UNI_BULK, HAKUX_UNI_UBERCACHE, HAKUX_UNI_FOGCACHE), off by default; the perflog ubosz counter now needs HAKUX_UBOSZ_LOG=1

Three default-off switches in shaders.c cut the per-draw uniform work in
`pgraph_vk_update_shader_uniforms`, measured at 4.43 ms/frame (2.7 us/draw) at NFS
MW's 3-racer start:

- HAKUX_UNI_BULK copies each std140 array uniform with one memcpy instead of
  element by element. Byte identity is checked on the host by bulkcheck.sh (OK 2013).
- HAKUX_UNI_UBERCACHE caches the per-binding uber constant values. Without it they
  are built with snprintf every draw.
- HAKUX_UNI_FOGCACHE caches the fog-write string.

The perflog ubosz counter is gated off by default (HAKUX_UBOSZ_LOG).
pfifo_thread's 6 ms of self time turns out to be the perflog's own clock reads
(87.5%), not renderer work. NOTES.md section 1 has the splits and OUTBOX.md names
the pfifo.c lines.

nfs-mw.route holds RT, which is the gas (step-0 run 1529147). It reaches the race
with ~25 s of motion, then a fixed scene against a wall at 12.3 +- 0.2 us/draw. That
scene runs at the 30 fps cap with ~14 ms of renderer idle, so the A/B judges us/draw
and states gfps as unchanged.

A/B: one build (9bdfd6d4f0), flags on (B) vs off (A), two runs each, judged by
armread.py against the registered prediction (point -1.5 us/draw in the fixed scene).

| arm | request | result |
|---|---|---|
| B1 | 1-1791614071-perdraw1009-2017514 | pending |
| A1 | 1-1791614079-perdraw1009-2018606 | pending |
| B2 | 1-1791614081-perdraw1009-2018875 | pending |
| A2 | 1-1791614116-perdraw1009-2019230 | pending |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
