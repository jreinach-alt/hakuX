
## 2026-09-26 (attempt 3): step 2a probe hunk in vk/surface.c

The tier1 A/B is done: NOT_TIER1 (ON 0.688, OFF 0.680, 2+2 Thor runs; PR #398, docs/lanes/fmv303b/NOTES.md s4).
Next discriminator (NOTES s5): a default-inert probe, gated on HAKUX_FMV303_PROBE=1, that logs every surface
write-back landing (addr, len) in hw/xbox/nv2a/pgraph/vk/surface.c (download_surface_to_buffer :994,
pgraph_vk_complete_staged_downloads :860), joined per frame to the probe's tint lines.
surface.c is held by lane.blinx372d. Request: a probe-only grant of surface.c to the next #303 lane,
or brief blinx372d to carry the hunk. lane.fmv303b edited nothing in it.
