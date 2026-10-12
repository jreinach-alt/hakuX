# lane.fpsbelow1012 OUTBOX (one line per milestone)

- 2026-10-12 table written (NOTES.md section 2, 43 titles). Only 4 have a gameplay route the profile gate admits
  (Amped 2, MC3, Burnout Revenge, Forza) and 9 more the survey route; 8 titles are blocked only by R1 (a first-run
  route over an existing golden: DOA3, Arctic Thunder, Galleon, Ghoulies, Nightfire, BF2MC, DnD Heroes, NGB), which a
  profileconv1011-style re-head to `any` would unlock. Predicted at the bar from folded switches alone, unmeasurable
  here (no route): NBA Live 05/06/07 (SURFGPU removed their `reuse` wait), Nightfire and BF2MC (fastpaths), Hulk.
- 2026-10-12 ranking (draft, NOTES.md sections 5-6): L1 `HAKUX_ZETA_D24`, P 0.6, every 32-bit 640/720x480 GMEM title
  where the GPU is the wait (DOA3, NG Black, Otogi, Black; LOTR/NHL 2K3/Spider-Man 2 where GMEM). Cause found offline:
  Z24S8 as D32_SFLOAT_S8_UINT (since #16, 09-10) puts a separate 1-byte stencil plane in GMEM, which doubles the
  tile alignment, so the pass needs 2 tiles; 2 tiles get no HW binning, so each replays every draw. D24S8 fits 1 tile.
  WAITING: grant for hw/xbox/nv2a/pgraph/vk/surface.c (patch ready: docs/lanes/fpsbelow1012/zetad24.patch).
