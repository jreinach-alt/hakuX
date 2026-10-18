# haloring1017: Halo CE main-menu ring: the missing surface layer and the static inside surface (#939)

State: draft

Lane: haloring1017            Issue: #939
Base: master @ 9abd80e90c
Files: docs/lanes/haloring1017/PR.md, docs/lanes/haloring1017/NOTES.md, docs/lanes/haloring1017/tools/constmove.py, docs/lanes/haloring1017/tools/otwrites.py, docs/lanes/haloring1017/tools/ringuv.py, docs/lanes/haloring1017/tools/deskrun.py, docs/lanes/haloring1017/tools/bandfit.py, docs/lanes/haloring1017/tools/bandsum.py, docs/lanes/haloring1017/tools/vidmap.py, docs/lanes/haloring1017/tools/clockfit.py, docs/lanes/haloring1017/tools/c13series.py, docs/lanes/haloring1017/tools/hullsw.py, docs/lanes/haloring1017/tools/swcheck.py, docs/lanes/haloring1017/tools/combwords.py, docs/lanes/haloring1017/tools/run13anchors.sh, docs/lanes/haloring1017/tools/run13map.sh
Prediction: none: analysis-only (so far)
Needs device: no    Needs NDK: no

Step 0 is committed: the Already-tried table and the hypothesis table are in `docs/lanes/haloring1017/NOTES.md`.

(c), the static inside surface, does not reproduce off the stock Qualcomm driver:
- in the guest's own state (M1), the band turns at the hull's angular rate;
- on screen on the desktop (lavapipe, M2), the band's texture follows its scroll at slope 0.88 +- 0.02 (static is 0;
  the hull control gives 1.01);
- on Turnip (run 13's video, PurpleVK from its log, M2b), it follows at slope 1.020 +- 0.001 (the hull: 1.003).

So (c) is the stock driver (R4), which the owner's rule of 10-17 puts out of scope. The lane is now on (a), the
missing bright grey layer: a numeric judge that registers the console photos to the framebuffer and asks which
combiner term the console's layer is made of.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
