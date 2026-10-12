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
  WAITING: grant for hw/xbox/nv2a/pgraph/vk/surface.c (draft patch, not committed).
- 2026-10-12 granted (lane.local, origin/board 9dbc5b2242); `HAKUX_ZETA_D24` (off by default) committed at
  ede7c891c5, index regenerated c29c31ea5e. Runs on disk widen the class: NBA Live 06/07, Buffy, LOTR, Fantastic 4
  read two-tile; MechAssault 2 and ToeJam mostly (NOTES.md 5a). Depth-exactness cost written (NOTES.md section 7)
  before any screen. Pilots (DOA3, NGB, MC3) queued at sweep tier, ref 00fde8afb3; 0 runs so far.
- 2026-10-12 pilot read (3 runs; NOTES.md section 8). NG Black at master is still the two-tile class (in/out 0.52-0.54,
  29-19 ms of GPU per command buffer at 270-480 s) and reads fps_ok 0.913 on the survey route. That is near the bar,
  but the survey never marks gameplay, so it is no lane.local candidate yet. Midnight Club 3 went from 0.006 to
  **0.815** (window median 29.4). It is not the GMEM class: it does 14 synchronous `range` surface downloads per
  flip, 11.9 ms/frame of render-thread wait, the caller SURFGPU/TEXSCAN did not reach (shared with Forza, MC II, CS).
  The DOA3 run was void before input (com.android.settings held the display), not a title failure.
- 2026-10-12 prediction registered: `docs/testing/predictions/fpsbelow1012-zetad24.json` (sha256 ec352c20..., one
  binary be0239bac8 both arms, B `HAKUX_ZETA_D24=1`). The window is A's two-tile buckets, fixed before B is read. NG
  Black B+A, DOA3 A and Buffy A are queued at sweep tier (ToeJam's route was refused: no `# state:` line, not this
  lane's file). Runs: 3 done, 4 queued, cap 30.
- 2026-10-12 A/B first title judged (NOTES.md 9a): **NG Black passes every leg of `fpsbelow1012-zetad24.json`**.
  With `HAKUX_ZETA_D24=1` the scene pass is one tile (census in/out 0.53 -> 0.99), the GPU's outer span per command
  buffer drops 21.5 -> 12.3 ms (x0.57), gfps 40 -> 59, and G 25.6 -> 16.9 ms over the 270-s class window. Whole-run
  fps_ok is 0.847 -> 0.960 on the survey route: a lane.local candidate *with the switch*, which needs a gameplay
  route to confirm. DOA3 A and Buffy A are queued; their B arms follow if they read in the class. Separately,
  MC3's `range` cost (12.3 ms/frame) is not the texture scan (NOTES.md section 10). It is the vertex-RAM sync or a
  blit, and Forza with SURFGPU shares it. The `[sdrange]` instrument runs on both are queued (`-2104673`,
  `-2906178`). Runs: 5 done, 4 queued, cap 30.
- 2026-10-12 A/B judged (NOTES.md 9d): **`fpsbelow1012-zetad24.json` is a LOSS by its own rule.** One of three
  titles (NG Black) passes every leg; DOA3 and Buffy fail W, a median of G against a frame cap (60 Hz, and Buffy's
  own 30), as 9b/9c wrote before their B arms ran. V, M and P pass on all three: the scene pass is one tile with the
  switch (in/out 0.49-0.53 -> 0.97-1.00), GPU outer span x0.57-0.64. Hand-read, not judged: NG Black fps_ok 0.847 ->
  0.960 and Buffy 0.793 -> 1.000 (like for like); DOA3 0.698 -> 0.961, but the arms fought different opponents on
  different stages. Candidates *with* `HAKUX_ZETA_D24=1`, survey route only (no gameplay mark), so each needs a
  gameplay-route confirmation, and the switch's depth pair is read first: Buffy, NG Black, DOA3.
- 2026-10-12 11 runs done, 2 queued, cap 30 (NOTES.md section 4). Forza at master (section 11): fps_ok 0.506, not
  H1 (the vertex sync downloads nothing). Its `range` wait (16.6 ms/frame, 785 downloads in 114 finishes per 60
  frames) is range lookups completing the batch of eviction downloads forza414 defers. The rule that does it,
  `found_overlap && num_deferred > 0`, predates forza414. NFS MW's `range` is TEXSCAN's (4 per finish), not this.
- 2026-10-12 ranking (NOTES.md section 12), expected impact = titles x gain x P: **L1 `HAKUX_ZETA_D24`** (3 titles
  measured, ~9 more two-tile on disk; P 0.7); **L4a `HAKUX_VTX_EXACT`** (MC3, H1 measured to the byte; P 0.85 the
  downloads go, 0.55 MC3 crosses); **L4c precise range completion** (Forza, at most half its range wait; ~0.15);
  then L2, L4b, L5; L3 dropped (L1 supersedes it). Queued: the depth-pixels pair `-286227` (B) and `-286943` (A),
  sweep tier. WAITING: grants for draw.c, vertex.c, renderer.h (L4a) and an extension on surface.c (L4c's split
  counter).
