# Tron 2.0 - Killer App (USA, Europe) -- run retro-tron (held run, verdict in run root)

Title as listed: `Tron 2.0 - Killer App (USA, Europe)` (verdict title).

## Verdict numbers (verdict.json)

- reached_gameplay true, gameplay_s 612.5, play_share 0.9994, fps_ok_share 0.9777 (bar 30), median fps 37.2, window min 25.07
- hitches 0, audio_starve 0.0, crash false, hang false, pass true, failures none

## SCENE SHOULD CONTAIN (derived; no OUTBOX scene line exists for this run)

- Player: the Tron avatar (first-person view here; HUD shows the disc/energy bars).
- Enemies: guard programs or training programs the player fights or passes during the window.
- HUD: energy/health bars (green and red bars with 50/50 readouts, present every frame), "Jet" and disc counter (0/0).
- Scenery: the Archive Bin area; it should change as the player moves through it.
- Progress: location or the Archive Bin room sequence changes across the window.

## Per-frame (16 hold frames, 084-128)

| frame | scene | live play? |
|---|---|---|
| 084 | Archive Bin room, doors on both sides, figures behind glass panes, camera facing the room | live (HUD) |
| 087 | same room, figures behind glass on both sides, doors | live |
| 090 | caption "ID: Archive Bin Training Room"; a figure standing inside a far room behind glass | live |
| 093 | same caption; same far-room figure | live |
| 096 | same caption; same far-room figure, camera still | live |
| 099 | open door, corridor with light strips; no enemy | live |
| 102 | view through a door into a room with a seated figure (behind glass) | live |
| 105 | view through a door, figure at the back of the room | live |
| 107 | view through a door, figure in the room | live |
| 110 | view through a door, figure in the room | live |
| 113 | view through a door, figure in the room | live |
| 116 | view through a door, figure in the room | live |
| 119 | view through a door, room mostly empty | live |
| 122 | view through a door, figure in the room | live |
| 125 | open corridor with a curved floor and a wall glyph; no figure | live |
| 128 | open corridor, same wall glyph, curved floor; no figure | live |

Every frame is live play with the HUD up (energy bars and 50/50 readout). No menu, pause, cutscene, or loading card.
The camera sits in one area of doors and corridors the whole window; there is no combat or action in any frame.

## Checks

(a) SCENE items present: player HUD in all 16 frames; the player avatar is not visible (first-person). Enemies: NONE in any
frame. The only figures are standing or seated behind glass in side rooms, and none is shown fighting, chasing, or
attacking. This is a missing class of object for a Tron combat-action scene: FAIL.
Scenery: Archive Bin doors, glass and corridor appear in every frame. Present.

(b) Progress: the view moves through doors and along a corridor between 084-096 (the same room, the same caption) and
099-128 (doors, corridor). The caption "ID: Archive Bin Training Room" is in 090-096 only. Position changes in the view, but
no score, kill count or objective is visible to show progress. Caveat: the hero's location is not readable from the frames
beyond "same area". Not a standing-still hold (the view moves), but no progress is visible.

(c) Visual defects: none seen. Textures and glass render; the light streaks on the glass are the scene's look. Blinking or
duplicated objects: none seen between adjacent frames. No flicker judged here (owner checks flicker).

## VERDICT: REJECT: the 612-s hold walks a training bin of doors and corridors with no enemies in any of 16 frames. The
verdict passes on play share and fps; the frames show no combat or progression, and a missing enemy class is a FAIL under
the review rules. Not a Playable as held. A hold that reaches combat (or a hold with an enemy in frame) would be the next
step. lane.local may overrule with a fuller look at the route if they judge the training bin the expected scene.
