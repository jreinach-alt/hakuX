# surfgpu1009: a GPU-side route for the reuse/surfupd rebind, behind HAKUX_SURFGPU=1 (NBA Live 05/06/07) (#433, 0.5)

State: draft (NBA 05/06/07 pilots and golden2 all read clean; g_sg_held built for NBA07's record residual, re-arm queued on 1b1fec978d; see NOTES.md sections 7-9)

Lane: surfgpu1009          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 1b1fec978d
Files: docs/lanes/surfgpu1009/NOTES.md, docs/lanes/surfgpu1009/PR.md, docs/lanes/surfgpu1009/sg_judge.py, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/draw.c, docs/testing/predictions/surfgpu1009-golden.json, docs/testing/predictions/surfgpu1009-golden2.json, docs/testing/predictions/surfgpu1009-golden3.json, docs/testing/predictions/surfgpu1009-nba2005-soak.json, docs/testing/predictions/surfgpu1009-nba06-soak.json, docs/testing/predictions/surfgpu1009-nba07-soak.json, docs/testing/predictions/surfgpu1009-nba07-held.json, docs/testing/titles/routes/nbalive07.route (outside stated territory, recovered a lost artifact needed to queue -- see NOTES.md 9.2)
Prediction: surfgpu1009-nba2005-soak.json @ a19ce605b0386b34, surfgpu1009-nba06-soak.json @ 16eef2f67c71b29d, surfgpu1009-nba07-soak.json @ c55ecd3b4f8c27ac, surfgpu1009-golden.json @ d491a6b3cd1d77e7, surfgpu1009-golden2.json @ 68f0c202e1abcb1b, surfgpu1009-nba07-held.json (new, registered on 1b1fec978d), surfgpu1009-golden3.json (new, registered on 1b1fec978d) (sha256 prefixes where known; nba2005/06/07-soak and golden a_ref=b_ref=1e5b1af818, golden2 a_ref=b_ref=c663a91697, nba07-held/golden3 a_ref=b_ref=1b1fec978d -- all env-only A/B)
Needs device: yes (Nova only)    Needs NDK: no

Release note (none): opt-in switch HAKUX_SURFGPU, off by default.

## What changed

`hw/xbox/nv2a/pgraph/vk/surface.c`, all behind `HAKUX_SURFGPU=1` (read once,
default off; with it unset every path is the shipped one):

- **(a) reuse rebind.** When a surface that a pending download batch still
  names is rebound (`update_surface_part`, the `reuse` caller), the switch
  detaches it from the batch (`deferred_downloads_clear_surface`) instead of
  completing the whole batch on the CPU. The batch's entries keep their
  destination and staging offset, so its bytes still reach guest RAM when the
  batch completes at frame rotation. The upload that rebinds the surface is
  covered by the existing splice (`HAKUX_SURFSPLICE`'s machinery, armed by
  either switch): it takes the pending bytes from staging on the GPU, and
  falls back to completing on the CPU at `SDC_SURF_UPDATE` where it cannot
  cover. A handoff source keeps the shipped completion.
- **(b) flip batch with no display surface.** When the flip's display
  pre-download is not recorded (no surface, not dirty, or the record failed)
  and a batch is pending, the batch is marked as the flip's pre-download with
  no display surface. The flip's finish submits it either way. The mark only
  lets the next surface update leave it pending, as #474 does for the display
  pre-download, instead of waiting on its fence (NBA Live 07's `surfupd`). A
  rebinding upload that reads the batch's bytes still waits.
- Telemetry unchanged: `[sdcall]` still attributes every completion to its
  caller (`reuse`, `surfupd`, `record`, ...). `[surfgpu] frames= detach=
  nodisp= dedup= hold= hwait= hrot= wrap=` line per `[sdcall]` window when the
  switch is on.
- **(c) hold the submitted batch aside (`g_sg_held`, `hw/xbox/nv2a/pgraph/vk/surface.c`
  + `vk/draw.c`).** NBA Live 07's arm with (a)/(b) alone passed every leg but
  one: the wait moved to `record` (12.68 ms/flip) because the flip's
  piggybacked display download makes the next frame's first record hit an
  already-submitted batch, one fence per batch. `g_sg_held` holds that
  submitted batch aside with its own fence instead of waiting it at record
  time, so the next download starts a new batch immediately; the held batch
  completes wherever the current batch would (every guest-visible completion
  path: overlap checks, the splice, `surface_access_callback`'s
  wait-for-downloads, reference/clear, handoff) or, failing that, at the
  frame-slot rotation that owns its fence (`pgraph_vk_surfgpu_slot_retired`,
  called from `vk/draw.c`'s `pgraph_vk_finish`). One held batch at a time;
  holding a second force-completes the first. Re-arm queued on this ref (see
  Measurements) to confirm `record` clears the P2 bar with the mechanism
  engaged (`hold= > 0`), and a fresh golden pass (`golden3.json`) since this
  is the same completion-ordering bug class `golden2` already caught once.

## Measurements

- NBA Live 2005 pilot (500 s, ref 1e5b1af818): every leg PASS. `reuse` 11.84
  -> 0.00 ms/flip, all `[sdcall]` waits 11.85 -> 0.22 ms/flip, `ph_Fin` 12.8
  -> 2.8 ms, gfps 25.25 -> 43.00. Pixels: only the pulsing PRESS START text
  differs from the noise floor.
- NBA Live 06 (460 s, ref 1e5b1af818): clean PASS, all legs incl. P2.
- NBA Live 07 (480 s, ref 1e5b1af818): PASS on P0/P1/P3/P4 (`reuse`/`surfupd`
  both to 0.00 ms/flip) but **FAIL on P2** (sum-wait ratio 0.66 > 0.5): the
  wait moved to `record`. Root cause and fix: part (c) above.
- Golden disc re-check after an unrelated record-dedupe fix found in the same
  pass (`c663a91697`, not part of this PR's diff -- fixed before this PR's
  branch picked it up): PASS, worse=0, 266/266 captures match, the one
  previously-broken capture (`Image_blit/Overlap_TR_Outside`) back to 1 px
  exactly matching flag-off.
- NBA Live 07 held-batch re-arm (480 s x2, golden3 disc x2, both ref
  `1b1fec978d`): **queued, not yet read** --
  `1-1791601841-surfgpu1009-2092062` (B), `-2092716` (A),
  `-2093286` (golden3 B), `-2098499` (golden3 A). See NOTES.md 9.2.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
