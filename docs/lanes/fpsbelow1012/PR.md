# fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

State: ready

Lane: fpsbelow1012          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 78cd417e9d (the fold of this lane's first piece; 0 behind on 10-12 07:2x PDT)
Files: docs/lanes/fpsbelow1012/NOTES.md, docs/lanes/fpsbelow1012/OUTBOX.md, docs/lanes/fpsbelow1012/PR.md, docs/lanes/fpsbelow1012/tools/forza-sdrfin.out, docs/lanes/fpsbelow1012/tools/l1-gate.out, docs/lanes/fpsbelow1012/tools/l4-verdicts.out, docs/lanes/fpsbelow1012/tools/mi-gate.out, docs/lanes/fpsbelow1012/tools/mi-vcpu.out, docs/lanes/fpsbelow1012/tools/vtxexact-pair.out
Prediction: docs/testing/predictions/fpsbelow1012-vtxexact.json @ eb30dbad227e76d2ec45886f26af3eafdb5e0d1c2de3d78fdfdd29b274062bf4 (L4a on MC3, judged here: WIN, every leg). Folded earlier and judged: fpsbelow1012-zetad24.json @ ec352c20a21e07b144e4b1cc6bfaa895d0792fd745c215135a0a3a739c6dce7e (title A/B, LOSS); fpsbelow1012-zetad24-pixels.json @ c543e6ac7e76b4bc73d102c1140b9f59b7816cce469b47086a950e0ad1e9caee (depth cost, PASS)
Needs device: no (every run this piece reads has landed)    Needs NDK: no

This piece is analysis only: it reads the three runs that landed after the first fold and records the lane's final
ranking. No source file changes. The switches and instruments it reads folded at 78cd417e9d:
- `HAKUX_ZETA_D24=1` (L1, vk/surface.c) stores Z24S8 as D24_UNORM_S8_UINT, so a 640/720x480 32-bit pass fits one
  GMEM tile on the A740 and keeps HW binning (NOTES.md section 5).
- `HAKUX_VTX_EXACT=1` (L4a, vk/draw.c, vertex.c, renderer.h) makes the vertex-RAM sync stale-test and download only
  the bytes a draw reads, not the page-rounded range (section 10a).
- `HAKUX_RANGELOG=1` and `[sdrfin]` (perf builds): instruments.

Both switches are off by default.

**The L4a pair on Midnight Club 3** (`fpsbelow1012-vtxexact.json`; B `z-1791810680-fpsbelow1012-567845`, A
`z-1791810682-fpsbelow1012-567963`; ref 67e3fcf745, sweep tier; NOTES.md section 15):

| leg | registered | read | |
|---|---|---|---|
| V | A =0, B =1, each >= 40 periods | 149 and 185 periods | pass |
| C | A's median `range` downloads >= 300 per 60 frames | 431 | pass |
| M | B/A median `range` downloads <= 0.05 | 0.000 | pass |
| P | B/A median `range` wait <= 0.25 | 0.000 (539 -> 0 ms per 60 frames) | pass |

**Registered verdict: WIN.**

Hand-read, not judged:
- ph_Fin falls 9.6 -> 4.0 ms/frame over the window, and 17.6 -> 4.2 over the ~34 s both arms moved.
- fps is not credited. The route is blind throttle, the arms spawned on different streets, and B parked ~34 s after
  the mark. So B's fps_ok 0.935 is a parked car's; A read 0.40.
- B's moving stretch read a median of 26.1 fps. P that L4a alone takes MC3 over the bar falls from 0.55 to 0.3.
- MC3 needs a steered route before an fps reading of this switch means anything (lane.local's).

**Forza's `[sdrfin]` split** (`z-1791810687-fpsbelow1012-568864`; section 16). `range` costs 13.6 ms/frame, split:

| class | share |
|---|---|
| `own` | 70%: one completion per frame, 9.5 ms each |
| `tscan` | 30% |
| `clean` | 0 |
| `dest` | 0 |

By the rule written before the run (section 13), **L4c (`HAKUX_RANGE_EXACT`) is dropped**: the only class it removes
is 0. What is left is one finish per frame for an invalidated surface, which a texture lookup or a blit reads. Its fix
would be a GPU-side reader (L4d): one title, P 0.15, not started.

**Mission: Impossible** (4947001F, Addendum 3; section 17), read from lane.pathfind's held run:
- 6.94 fps in play, with the vCPU 72% busy and the render thread at 28% CPU;
- about half of wall is guest work after its NOP software callback;
- 7 pipeline misses: not shader compiles.

The frame is the guest's. No renderer lever of this lane's covers it; it is L5's (vcpuplan). The gate refuses every MI
route (no golden), so no run was queued.

**L1's gameplay-route confirmations** (Buffy, NG Black, DOA3; section 18). Each title's gameplay route is first-run,
and R1 refuses it over the kept profile. The survey route is what the A/B already ran, and `--remake-profile` is ruled
out. Each needs a returning route on its kept profile: lane.local's.

**Ranking (section 12), titles x gain x P:**
1. L1 `HAKUX_ZETA_D24`: 3 titles measured, ~9 more two-tile on disk; P 0.7.
   - A/B: LOSS on its W leg, a median against a frame cap. V, M and P pass 3 of 3.
   - Depth pair: PASS. Its cost is a +1 LSB read-back of F24 depth, with drawn colour unchanged.
   - Next: lane.local's cross-title screen and the confirmations.
2. L4a `HAKUX_VTX_EXACT`: MC3. The mechanism is measured (WIN). P 0.3 that MC3 crosses. Next: a steered route.
3. L2 profiled autotune (lane.local's decision), then L4b (TEXSCAN's caller), L4d (Forza), L5 (guest vCPU,
   including MI).
4. Dropped: L4c (zero by its own rule) and L3 (L1 supersedes it).

**Device runs:** 16 of the 30 cap: 16 done, 0 queued, all sweep tier, none a retest. None is queued in this piece.

**Checks on this head:** `docs/testing/preflight.sh --allow-tracker`, run before this push. No source changed, so
there is no NDK or desktop build.

Release note (none): analysis only; HAKUX_ZETA_D24 and HAKUX_VTX_EXACT stay opt-in and off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
