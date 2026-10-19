# fpsnext1019: GTA III driving, Blinx 2 and Fable toward 30 fps (#433)

State: draft

Lane: fpsnext1019            Issue: #433
Base: master @ 2e6d29d4f8 (fpsdata1018's fold landed on master; merged in)
Files: docs/lanes/fpsnext1019/NOTES.md, docs/lanes/fpsnext1019/PR.md, docs/lanes/fpsnext1019/FINDINGS.md, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: none: measurement first. A falsifiable prediction for the one code change so far (s2t_widen_view()
  reject-reason counters) is written in NOTES.md but not yet run through the dispatcher -- no pixel/fps claim is
  made yet, so no ab_compare.py registration applies
Needs device: yes    Needs NDK: yes

Measures where the frame goes in GTA III's in-car driving scene and in Blinx 2's gameplay. GTA III: recovered and
analyzed attempt 1's SYSMEM/GMEM render-mode hold batches (contested, not a clean win either direction -- see
FINDINGS.md), then found every captured arm's surface-to-texture copies are 100% caused by a texture component-map
mismatch with the two fast paths built for exactly that case never engaging; added reject-reason counters to
`s2t_widen_view()` (instrumentation only, no behavior change) to find out which of its guards is rejecting every
call. Blinx 2: root-caused (not fixed) why the generic drive route never reaches gameplay -- the dispatcher's
`EXPLORE_LADDER` excludes `START` without a built profile, and Blinx 2 has none; deferred in favor of GTA III.
Detail in `docs/lanes/fpsnext1019/NOTES.md`; per-title table in `FINDINGS.md`.

Release note (none): instrumentation/measurement only so far, no behavior change for players.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
