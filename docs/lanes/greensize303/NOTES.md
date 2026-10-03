# greensize303 -- sizing the green-block video defect (#303)

Offline, read-only lane. No device, no code change. Question from the brief: how many titles show
green blocks in gameplay or block reaching play? The gate is 3 or more; #303 takes the next Opus slot only if it is met.

**Result: the gate is not met.** Two titles show green blocks, both on pre-game screens (FMV, logos, title,
loading). Neither title's gameplay is green, and both reached gameplay in their pathfind runs. Zero titles are
blocked from reaching or holding play by the green. #303 waits; this file is the count.

## Method

- Frames read from disk: 24,241 frames in `wt/pathfind/scratch/runs/*/frames/*`,
  `docs/lanes/pathfind/runs/*/*.jpg`, `dispatch/results/*/frames/*` and `dispatch/results/*/route-frames/*`.
  (Not every title has frames on disk; titles without frames are not covered.)
- Detector: `tools/greenscan.py`. A pixel is green when G>=110, R<=40, B<=40, G-R>=100, G-B>=100. A 8x8 aligned
  block is green when >=90% of its pixels are. A frame is flagged when >=0.3% of its blocks are green.
  Output: `hits.tsv` (177 flagged frames).
- Calibration: the first pass used G>=230 and found only Spikeout's loading screen. Sampling the green in
  sw3's title screen and cutscene showed the defect colour is around G 115-225, R and B near 0. The second pass
  found the sw3 FMV and title hits.
- Every title's hits were confirmed by eye (contact sheets `sheet_*.png`).
- A low threshold is intentional. The detector also flags natural green (see below), so the threshold only
  nominates candidates. The by-eye check is what counts.

## Table: titles with green-block frames

| Title | Where the green appears | Blocks reaching or holding play? | One frame each |
|---|---|---|---|
| Star Wars Episode III Revenge of the Sith (4C410017) | Publisher logo (002, 28% of blocks), intro video (003, 26%), title screen with PRESS START (004, 17%), opening FMV/cutscenes (005-015, up to 10%). Clean from the in-game opening cutscene onward. **Gameplay: clean** (share 0.00 in every gameplay frame). | No. pathfind reached gameplay in 3.5 min. The titleroutes2-2688279 route reached gameplay (share 0.00). | `/home/justin/hakux-work/wt/pathfind/scratch/runs/sw3/frames/003-intro_video.jpg`; `/home/justin/hakux-work/dispatch/results/1790921690-titleroutes-1082096/route-frames/004142-booted.png` (38%); clean gameplay `/home/justin/hakux-work/dispatch/results/1790944635-titleroutes2-2688279/route-frames/061927-gameplay.png` |
| Spikeout: Battle Street (53450029) | Sega presents (f00004), NewEntertainment logo (gamecheck f00016), title card (f00021), story FMV with subtitles (f00026, f00032, f00052), loading screen (pathfind 017, 22%). Title screen with PRESS START is clean (gamecheck f00062, f00066); a story FMV frame is clean (f00074). **Gameplay: clean** (pathfind 020, share 0.00). | No. pathfind reached gameplay in 4.3 min. | `/home/justin/hakux-work/wt/pathfind/scratch/runs/spikeout/frames/017-loading.jpg`; `/home/justin/hakux-work/dispatch/results/1790364700-gamecheck-355013/frames/f00026.png` (28%) |

Counts behind the table (177 flagged frames in total): Star Wars has 89 (75 from the titleroutes dispatch runs, 14
from pathfind; 72 of the dispatch frames are at 2% or more). Spikeout has 73 (70 from the dispatch runs
1790364700-gamecheck-355013 and 0-0-y-1790395182-rtdbench-5, plus 3 from pathfind). The other 15 flagged frames are the natural-green false
positives below.
Green share timeline in gamecheck: 0 for frames 1-11, green over 12-53 (the FMV and logo sequence), 0 for 54-66 (black
and clean title screen), green again at 67-80 (FMV). The titleroutes route: green on boot and menu-labelled
frames until frame 26, then 0.00 from frame 27 onward (the in-game opening cutscene, then gameplay).

### Not green-block titles (detector false positives, confirmed by eye)

Sheet: `sheet_other.png`. Natural saturated green, not the block defect:

| Title | Hit | Why it is not the defect |
|---|---|---|
| Sonic Heroes | team-select menu (0.03), play frames (0.003-0.007) | Sonic's green and grass; smooth shading, no block grid |
| Blinx The Time Sweeper | play frames (0.016) | the green creature |
| Arctic Thunder | menu, play frame (0.009) | green "GO!" text over a clean scene |
| Crash Bandicoot | boot (0.004) | the green LOADING logo on black |
| (fuzion titleplay) | gameplay-labelled frame (0.004) | green UI text, no block grid |

Titles with frames on disk and no flagged frame at the 0.3% threshold: not listed one by one; the scan's `hits.tsv` is the full list of flagged frames.

## Likely subsystem (hypothesis, not measured)

The defect has a consistent shape across both titles:

- Luma survives. In sw3's intro, the blue lightsaber and the figures are visible through the green blocks; in
  Spikeout's loading screen the "Loading" text and the scene structure show through. The green replaces the
  colour, not the picture.
- The blocks are saturated green (around 0, 136-203, 0) with coloured fringes (red, blue, magenta) at column
  edges, in 8-px-wide vertical stripes. That is a colour-plane problem with the picture kept.
- Video clips decode on the game's side and reach the emulator as an upload. Zeroed or misaligned chroma in a
  packed YUV texture gives exactly this: Y kept, U/V wrong, green cast.

The emulator has a packed-YUV path that fits this:

- `hw/xbox/nv2a/pgraph/texture.c:517-527`: YUY2/UYVY texture conversion. It picks the pair bytes by
  `yuy2 = color_format == ...`. A wrong format read or chroma byte offset here would give this symptom.
- `hw/xbox/nv2a/pgraph/vk/display.c:149`: `convert_yuy2_to_rgb` on the display path (the scanout copy).

The chain is candidate, not proven. What would separate it from a format mismatch elsewhere is a probe that logs
the texture color_format and the chroma bytes on the FMV draws. That is a device run and out of this lane's scope.

## Next, with P and win (not a fix)

The gate is not met, so no fix is recommended now. If the count rises (3 or more titles in gameplay or blocking reach),
rank these:

| Candidate | P | Win if it works | Cost |
|---|---|---|---|
| A. Probe: log color_format and the chroma bytes on the FMV draws of sw3 and Spikeout | 0.8 that it decides between the YUV-chroma path and another format | Decides the subsystem. No titles unblocked by itself | 1 device run each title, about 5 min |
| B. Fix the YUY2/UYVY chroma handling in texture.c / display.c, after A confirms it | 0.3-0.4. Mechanism fits, but nothing is measured yet | Clears green on 2 titles' pre-game FMV and loading screens. 0 titles unblocked now, so the win is cosmetic | 1 patch, 2 device runs |
| C. Fix the game-side decoder | low. Not in the emulator | — | out of scope |

Ranking by P x win: at the current gate, the win is small (cosmetic, 0 titles unblocked), so nothing gets device time now.
A is the cheap step that decides between candidates, so it goes first if the gate is met. B is worth doing only after A.

## Caveats

- The detector sees only frames on disk. A title with green only in an unrecorded phase is not counted.
- The count is 2 titles with green on pre-game screens and 0 with green in gameplay or blocking play. A title
  whose gameplay is green but not sampled in the 240 s route would not be seen.
- The by-eye check covered one representative frame per phase group and every natural-green title group. It did
  not view all 177 rows of `hits.tsv` one by one. The Spikeout dispatch rows were checked as a sheet of 12 spread
  across the 70 and the zero-share gaps of gamecheck; the Star Wars rows by their route-label groups.
