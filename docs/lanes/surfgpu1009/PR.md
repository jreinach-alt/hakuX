# surfgpu1009: a GPU-side route for the reuse/surfupd rebind, behind HAKUX_SURFGPU=1 (NBA Live 05/06/07) (#433, 0.5)

State: draft (NBA 05 pilot read; golden and NBA 06/07 pairs queued; see NOTES.md sections 7-8)

Lane: surfgpu1009          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ f2c6b9c5d6
Files: docs/lanes/surfgpu1009/NOTES.md, docs/lanes/surfgpu1009/PR.md, docs/lanes/surfgpu1009/sg_judge.py, hw/xbox/nv2a/pgraph/vk/surface.c, docs/testing/predictions/surfgpu1009-golden.json, docs/testing/predictions/surfgpu1009-nba2005-soak.json, docs/testing/predictions/surfgpu1009-nba06-soak.json, docs/testing/predictions/surfgpu1009-nba07-soak.json
Prediction: docs/testing/predictions/surfgpu1009-nba2005-soak.json @ a19ce605b0386b34, surfgpu1009-nba06-soak.json @ 16eef2f67c71b29d, surfgpu1009-nba07-soak.json @ c55ecd3b4f8c27ac, surfgpu1009-golden.json @ d491a6b3cd1d77e7 (sha256 prefixes; all a_ref = b_ref = 1e5b1af818, env-only A/B)
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
  caller (`reuse`, `surfupd`, `record`, ...). New `[surfgpu] frames= detach=
  nodisp=` line per `[sdcall]` window when the switch is on.

## Measurements

Pending. See NOTES.md section 7 for the queued request ids.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
