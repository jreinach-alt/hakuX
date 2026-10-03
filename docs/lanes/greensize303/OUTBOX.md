## #303 -- 2026-10-03 07:15 PDT

[lane.greensize303] Sized the green-block video defect (offline, no device, no fix). **The gate is not met: 2 titles, neither blocked in gameplay.**

Frames read: 24,241 on disk (pathfind runs and dispatch frames / route-frames). Every flagged title was confirmed by eye.

| Title | Where the green appears | Blocks reach or hold play? | One frame |
|---|---|---|---|
| Star Wars Episode III (4C410017) | publisher logo, intro video, title screen, opening FMV/cutscenes. Gameplay clean. | No: pathfind reached gameplay in 3.5 min | pathfind/runs sw3/frames/003-intro_video.jpg |
| Spikeout: Battle Street (53450029) | Sega logo, NewEntertainment logo, title card, story FMV, loading screen. Title screen and gameplay clean. | No: pathfind reached gameplay in 4.3 min | pathfind/runs spikeout/frames/017-loading.jpg |

Natural-green false positives, not the defect: Sonic Heroes, Blinx, Arctic Thunder, Crash, fuzion.

Likely subsystem (hypothesis): the packed-YUV path. Luma is kept under the green blocks and the chroma is wrong, which matches a YUY2/UYVY chroma read. Candidates are `hw/xbox/nv2a/pgraph/texture.c` (the YUY2/UYVY conversion) and `hw/xbox/nv2a/pgraph/vk/display.c` (`convert_yuy2_to_rgb`). Not measured.

Next, ranked by P x win:
- A. Probe the color_format and chroma bytes on the FMV draws, one device run per title. P 0.8 that it decides the subsystem. Cheap, so it goes first if the gate is met.
- B. Fix the YUY2/UYVY chroma handling, after A. P 0.3-0.4 (mechanism fits, unmeasured). Win: 2 titles' pre-game FMVs, 0 titles unblocked, so cosmetic.

Recommendation: #303 waits. Count is 2 titles on pre-game screens and 0 in gameplay or blocking play. Detail in docs/lanes/greensize303/NOTES.md.
