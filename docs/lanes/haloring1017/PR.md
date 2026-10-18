# haloring1017: Halo CE main-menu ring: the missing surface layer and the static inside surface (#939)

State: draft

Lane: haloring1017            Issue: #939
Base: master @ 9abd80e90c
Files: docs/lanes/haloring1017/PR.md, docs/lanes/haloring1017/NOTES.md, docs/lanes/haloring1017/tools/constmove.py, docs/lanes/haloring1017/tools/otwrites.py, docs/lanes/haloring1017/tools/ringuv.py, docs/lanes/haloring1017/tools/deskrun.py, docs/lanes/haloring1017/tools/bandfit.py, docs/lanes/haloring1017/tools/bandsum.py, docs/lanes/haloring1017/tools/vidmap.py, docs/lanes/haloring1017/tools/clockfit.py, docs/lanes/haloring1017/tools/c13series.py, docs/lanes/haloring1017/tools/hullsw.py, docs/lanes/haloring1017/tools/swcheck.py, docs/lanes/haloring1017/tools/combwords.py, docs/lanes/haloring1017/tools/photoreg.py, docs/lanes/haloring1017/tools/posefit.py, docs/lanes/haloring1017/tools/photojudge.py, docs/lanes/haloring1017/tools/photocal.py, docs/lanes/haloring1017/tools/termfit.py, docs/lanes/haloring1017/tools/floorfit.py, docs/lanes/haloring1017/tools/levelcmp.py, docs/lanes/haloring1017/tools/edgecmp.py, docs/lanes/haloring1017/tools/vidratio.py, docs/lanes/haloring1017/tools/run13anchors.sh, docs/lanes/haloring1017/tools/run13map.sh, docs/lanes/haloring1017/tools/transfer.py, docs/lanes/haloring1017/tools/excessmap.py, docs/lanes/haloring1017/tools/regvalid.py, docs/lanes/haloring1017/tools/chromafit.py, docs/lanes/haloring1017/tools/reflfit.py, docs/lanes/haloring1017/tools/detailfit.py, docs/lanes/haloring1017/tools/texregs.py, docs/lanes/haloring1017/tools/t1scale.py, docs/lanes/haloring1017/tools/excessreg.py, docs/lanes/haloring1017/tools/normcheck.py, docs/lanes/haloring1017/tools/termpanel.py, docs/lanes/haloring1017/tools/vidpose.py, docs/lanes/haloring1017/tools/unlitjudge.py
Prediction: none: analysis-only (so far)
Needs device: yes    Needs NDK: no

Step 0 is committed: the Already-tried table and the hypothesis table are in `docs/lanes/haloring1017/NOTES.md`.

(c), the static inside surface, does not reproduce off the stock Qualcomm driver:
- in the guest's own state (M1), the band turns at the hull's angular rate;
- on screen on the desktop (lavapipe, M2), the band's texture follows its scroll at slope 0.88 +- 0.02 (static is 0;
  the hull control gives 1.01);
- on Turnip (run 13's video, PurpleVK from its log, M2b), it follows at slope 1.020 +- 0.001 (the hull: 1.003).

So (c) is the stock driver (R4), which the owner's rule of 10-17 puts out of scope. The lane is now on (a), the
missing bright grey layer: a numeric judge that registers the console photos to the framebuffer and asks which
combiner term the console's layer is made of.

On photo 5 the console's hull is about 1.4x hakuX's (about 1.23x in green and blue), and the band about 1.0x. The
combiner decode, texture registers, DXT1 decode, normals, constants and the cube's LOD are each checked and ruled
out (M7). Two accounts remain. In one, the console's diffuse counts for more. In the other, a t2.r-shaped
reflection covers the whole hull. They part on the ring's unlit side.

Console photos 1-4 are now posed on run 13's video, at 45.5-56.3 s (M8). No dump on disk reaches those poses. A Nova
`gd` dump aimed at them is the next measurement.

**Desktop runs are paused: C: has 38 GB free, under the 40 GB floor** (after m8a, 2026-10-18). This holds back A7's
PSHDBG fix and the desktop check.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
