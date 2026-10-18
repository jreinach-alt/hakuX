# haloring1017: Halo CE main-menu ring: the static inside surface is the stock driver; the missing layer is not shown by any measurement (#939)

State: ready

Lane: haloring1017            Issue: #939
Base: master @ 9abd80e90c (master eb46eb2548 merged in)
Files: docs/lanes/haloring1017/NOTES.md, docs/lanes/haloring1017/PR.md, docs/lanes/haloring1017/tools/bandfit.py, docs/lanes/haloring1017/tools/bandsum.py, docs/lanes/haloring1017/tools/c13series.py, docs/lanes/haloring1017/tools/chromafit.py, docs/lanes/haloring1017/tools/clockfit.py, docs/lanes/haloring1017/tools/combwords.py, docs/lanes/haloring1017/tools/constmove.py, docs/lanes/haloring1017/tools/deskrun.py, docs/lanes/haloring1017/tools/detailfit.py, docs/lanes/haloring1017/tools/edgecmp.py, docs/lanes/haloring1017/tools/excessmap.py, docs/lanes/haloring1017/tools/excessreg.py, docs/lanes/haloring1017/tools/faceedge.py, docs/lanes/haloring1017/tools/facefit.py, docs/lanes/haloring1017/tools/facemap.py, docs/lanes/haloring1017/tools/floorfit.py, docs/lanes/haloring1017/tools/framepick.py, docs/lanes/haloring1017/tools/gainfield.py, docs/lanes/haloring1017/tools/glarefit.py, docs/lanes/haloring1017/tools/hullsw.py, docs/lanes/haloring1017/tools/levelcmp.py, docs/lanes/haloring1017/tools/maskfit.py, docs/lanes/haloring1017/tools/normcheck.py, docs/lanes/haloring1017/tools/otwrites.py, docs/lanes/haloring1017/tools/photocal.py, docs/lanes/haloring1017/tools/photojudge.py, docs/lanes/haloring1017/tools/photoreg.py, docs/lanes/haloring1017/tools/posefit.py, docs/lanes/haloring1017/tools/reflfit.py, docs/lanes/haloring1017/tools/regvalid.py, docs/lanes/haloring1017/tools/ringuv.py, docs/lanes/haloring1017/tools/run13anchors.sh, docs/lanes/haloring1017/tools/run13map.sh, docs/lanes/haloring1017/tools/spatial.py, docs/lanes/haloring1017/tools/swapfit.py, docs/lanes/haloring1017/tools/swcheck.py, docs/lanes/haloring1017/tools/t1scale.py, docs/lanes/haloring1017/tools/termfit.py, docs/lanes/haloring1017/tools/termpanel.py, docs/lanes/haloring1017/tools/texfit.py, docs/lanes/haloring1017/tools/texregs.py, docs/lanes/haloring1017/tools/transfer.py, docs/lanes/haloring1017/tools/unlitjudge.py, docs/lanes/haloring1017/tools/vidmap.py, docs/lanes/haloring1017/tools/vidpose.py, docs/lanes/haloring1017/tools/vidratio.py
Prediction: none: analysis-only (no emulator code changed, so no arm)
Selftest: none -- docs/lanes/haloring1017 only; no harness script, job or test file changed
Needs device: no    Needs NDK: no

Release note (none): analysis only; no emulator code changed.

Analysis and tools only. Everything is in `docs/lanes/haloring1017/NOTES.md`: the Already-tried table, the symptom
accounts, the hypothesis table with each P and the evidence that moved it, M1-M11, "Root cause and remedies", and
questions for the owner.

**(c), the static inside surface, is the stock Qualcomm driver (R4, 0.9).** The band turns at the hull's angular rate
in the guest's own state (M1). On screen it follows its scroll at slope 0.88 on the desktop (lavapipe, M2) and 1.020
on Turnip (run 13, PurpleVK from its log, M2b), where static is 0 and the hull control is 1.0. Nothing to fix in
hakuX.

**(b), the bursts:** fixed by FIST_ROUND, not reopened.

**(a), the missing bright grey layer: no root cause, because no measurement shows the console drawing more than
hakuX.**
- (a) is made inside the hull draw `n5`, if anywhere (M3).
- A software render of `n4`+`n5` reproduces hakuX to r 0.977 (M4). It is the judge for the console photos.
- Photo 5, the one console image with a dump at its pose, has hakuX's texture scale and phase, cube mask and cube
  face layout (M5, M9, M10).
- Its extra brightness, per cube face, is inside what the photo's own dark-level lift at that screen place predicts.
  The lift is fitted on the space background, where both machines draw the same pixels (M11, `gainfield.py`).
- Photos 1-4 hold no hull at their poses on the new Nova dump (M10).
- Every factor in `n5`'s state that could scale a term was read and matches (M3, M7, M10).

| account of (a) | P |
|---|---|
| photo 5's excess is the photo: camera, and the TV seen off-axis (R11) | 0.5 |
| the owner's by-eye difference is the display hakuX was watched on (R13) | 0.3 |
| a real gap in `n5` below photo 5's precision (R10, R12, R5) | 0.2 |

Ranked remedies (P x win): 1, a capture card on the console, judged against hakuX's framebuffer with this lane's
tools (0.9); 2, the owner viewing both machines on one TV (0.5); code remedies 0.07 and below. Remedies 1 and 2 are
owner-side and are asked of lane.xbox: board request 10-18 06:35 PDT and its follow-up. **No fix is measured,
because none is justified yet.**

Missing from the brief's definition of done, and why:
- the root cause of (a), and a measured fix: blocked on remedy 1 or 2;
- the top two remedies are chased only as far as the board request, because both need the owner's console.

Desktop runs are paused: C: had 32 GB free at the end of attempt 4, under the 40 GB floor.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
