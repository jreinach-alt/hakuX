# lane.clrwin88: #88, colour wins the same-offset surface on Vulkan

Brief: put #88's colour-wins decline back on Vulkan now that #91 is fixed
(#237). Port the policy only. Do not port the gate.

## What changed

Commit `78a9609125` changes `hw/xbox/nv2a/pgraph/vk/surface.c` in
`update_surface_part()`, at the `surface == other` site. Zeta now declines a
surface colour holds: it clears `buffer_dirty` and returns. Colour still
evicts zeta. These are the same four lines #237 used as its a_ref scaffolding
(`9c5f7416d8`) and #148 carried at `67dc7724ee`. The "withdrawn" comment is
rewritten to describe the shipped state.

The gate is not ported. Vulkan's gate is already
`!current_binding || (upload && ...)` (`9161e3e14a`), and that gate is what
brings zeta back once colour moves away. #237's fix (`9de95de849`, the depth
`bufferOffset` on the compute unpack path) is untouched and is below this
commit on master.

## The counter

A counter already exists at the site: `surf91_overlap_probe()`. It logs
`[surf91] frame=F declines=N f_declines=M overlap=ADDR` unconditionally on
Android, on the first decline in each frame plus every 512th. It stays, so I
added no new probe; one comment line ties it to #88.

What it read on #237's two arms, which carried this exact decline:

| run | [surf91] lines | final declines |
|---|---|---|
| `1790328745-arms-clrwb91-base` | frames 34, 36 | 3 |
| `1790328746-arms-clrwb91-fix` | frames 35, 37 | 3 |

Neither `run1.log` contains PARTIAL COVERAGE or UtilAcceptVsock, and all 11
captures in both arms have status `ok`.

## The arm

The file is `docs/testing/predictions/issue88-vk-same-offset-colour-wins.json`,
re-pointed and not re-derived: a_ref `0a4e284536` (master) -> b_ref
`78a9609125`. It uses the three-suite disc ("Color Zeta Disable",
"Color zeta overlap", "Null surface"), so the two out-of-suite controls are
scored.

| leg | A (predicted) | B (predicted) |
|---|---|---|
| ColorIntoZeta_ZB | 131,495 | **10,766** |
| ZetaIntoColor | 102,255 | **71,663** |
| Swap (must_not_move) | 165,447 | 165,447 |
| Swap_ZB (expect) | 0 | **0** |
| 8 other controls (must_not_move) | unchanged | unchanged |
| `[surf91] declines` | >=1 (site reached, master then unbinds colour) | 3, in 2 frames |

The B column has already been measured once. #237's fix arm (apk
3c0863f5c029) is master plus this decline, and it scored 10,766 / 71,663 /
165,447 / 0 with 0 unreadable captures. This arm confirms that on current
master, with the decline as the only variable.

### Swap_ZB, predicted

The prediction is 0 in both arms, and it is registered as an absolute. The
evidence:

- It scored 0 with status `ok` in both #237 arms (the decline and master's
  policy alike).
- It scored 0 on six earlier handheld runs.
- The tracker's 141,125 comes from the desktop/lavapipe iso_surf1 run. It
  equals the golden's own count of black pixels, which is the signature of
  nothing rendered in that region.

So on the device this change neither causes Swap_ZB nor fixes it. **Read the
status column before believing a 0.** An unreadable capture scores 0.

## Open reading, not measured

The early return skips the download tail, which is the only place
`pg->surface_zeta.draw_dirty` is cleared. A zeta-writing draw made while zeta
is absent keeps `draw_dirty` set. `pgraph_vk_surface_update()`'s download
branch then re-enters `update_surface_part(d, false, false)`. While colour
still holds the address, the decline fires again and nothing happens. Once
colour has moved, a fresh zeta surface is created and downloaded over VRAM.

Every arm that has carried this return (the old one at `67dc7724ee` and both
of #237's) shows no capture on this disc moved by it. Beyond this disc it is
unmeasured. If a wider sweep ever shows a depth-heavy suite moving under this
commit, clear `draw_dirty` on the decline as well, and measure it.

## For the next lane

- Do not port the gate half of #66. Vulkan already has a more permissive gate.
- Swap's 165,447 is the quad's E91A24 vs E91624 depth-precision gap, which
  exists under both policies. It is not a surface-policy defect.
- The arm verdict arrives as a `[job.arms]` comment on this PR. Check both
  arms' `scores1.tsv` status column and `run1.log` before accepting it.

## State at end of session 1 (2026-09-25)

Waiting. The arms job needs to run the re-pointed prediction and post a
`[job.arms]` verdict on PR #253, and CI needs to run on the head. Preflight
passes on this head. When the verdict lands, check both arms' `scores1.tsv`
status column, their `run1.log` (PARTIAL COVERAGE, UtilAcceptVsock), and
`[surf91]` in B's logcat. Then mark the PR ready.
