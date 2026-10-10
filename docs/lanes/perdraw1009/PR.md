# perdraw1009: cut the renderer's per-draw CPU cost (NFS Most Wanted, ~11 us per draw) (#433, 0.5)

State: draft

Lane: perdraw1009          Issue: none (#433 umbrella)
Base: master @ 3f6762f180
Files: hw/xbox/nv2a/pgraph/vk/shaders.c, hw/xbox/nv2a/pgraph/vk/renderer.h, docs/testing/titles/routes/nfs-mw.route, docs/testing/predictions/perdraw1009-nfs-soak.json, docs/testing/predictions/perdraw1009-nfs-toggle.json, docs/testing/predictions/perdraw1009-bf2-gen.json, docs/lanes/perdraw1009/NOTES.md, docs/lanes/perdraw1009/OUTBOX.md, docs/lanes/perdraw1009/PR.md, docs/lanes/perdraw1009/WAITING, docs/lanes/perdraw1009/armread.py, docs/lanes/perdraw1009/genread.py, docs/lanes/perdraw1009/togread.py, docs/lanes/perdraw1009/bulkcheck.sh, docs/lanes/perdraw1009/prof_tree.py
Prediction: docs/testing/predictions/perdraw1009-nfs-toggle.json @ 482fc384aa29445f981bacd6cd7171c9684b6ff4cd8b8e61c4e8e76b206fe840 (supersedes perdraw1009-nfs-soak.json @ b1ee6d91fc5d6477ba737905abe2057af741d806fe49894ad1ad193f96f46641 -- see table below); docs/testing/predictions/perdraw1009-bf2-gen.json @ 32999ceee794cf74e15dd11313a95c7f09f33d95bb4484781e3253ee6d095e09 (generalisation arm, job item 7, pending)
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

A/B, round 1 (separate runs, flags on (B) vs off (A)), judged by armread.py
against perdraw1009-nfs-soak.json:

| arm | request | result |
|---|---|---|
| B1 | 1-1791614071-perdraw1009-2017514 | matched with A1: STATIC Draw us/draw -2.29, (Pipe+Mfp)/draw -1.88, both within band |
| A1 | 1-1791614079-perdraw1009-2018606 | matched with B1 (65% plain wall, 439/438 draws/frame) |
| B2 | 1-1791614081-perdraw1009-2018875 | matched with A2: STATIC Draw us/draw -1.49, (Pipe+Mfp)/draw -1.59, both within band |
| A2 | 1-1791614116-perdraw1009-2019230 | matched with B2 (66% billboard wall, 801/855 draws/frame) |

Each pair passed P1-P3/P6 independently, but the two pairs stopped against two
different walls, so the combined four-run table failed P4 (cross-pair scene
mismatch, not a regression) and X (region diffs from camera parallax between
any two live runs of the same held input run as large as between arms --
confirmed by diffing A1 against A2, same flags, max region diff 208). X as
registered cannot separate a flag effect from per-run camera drift on this
route with one run per arm. Full tables and frame evidence: NOTES.md section 9.

A/B, round 2 (one run, HAKUX_UNI_TOGGLE=10, both states read against the same
scene): judged by togread.py against perdraw1009-nfs-toggle.json, which
supersedes perdraw1009-nfs-soak.json's X leg for the reason above.

| run | result |
|---|---|
| 1-1791618767-perdraw1009-3415447 | all six legs PASS: STATIC Draw us/draw on-off -1.70 (-15.2%), (Pipe+Mfp)/draw -1.66, gfps +0.00 at the 30 fps cap, pixels unchanged (XT excess -2 of a +8 budget) |

NOTES.md section 10 has the full toggle read. **Job items 1-6 are closed by
this result.**

Job item 7 (generalisation, since NFS won and pixels held): one A/B on
Battlefield 2 MC, registered as perdraw1009-bf2-gen.json, grounded on
bf2stall433/bf2push656's own findings that BF2's heavy view is GPU-bound and
this CPU-side fix should show in genread.py's CPU "med us/draw" without
moving heavy-row fps (NOTES.md section 12).

| arm | request | result |
|---|---|---|
| A | 1-1791620320-perdraw1009-3885164 | pending |
| B | 1-1791620323-perdraw1009-3885931 | pending |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
