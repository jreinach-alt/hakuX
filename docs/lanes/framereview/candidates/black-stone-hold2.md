# Black Stone: Magic & Steel (58490004) -- run black-stone-hold2 (Nova, held, 10-03 11:55 PDT)

Title as listed: `Black Stone Magic Steel` (ISO name not in the run's verdict; the verdict's title is the one pathfind wrote).

## Verdict numbers (verdict.json)

- reached_gameplay true (route), play_share 0.9996, fps_ok_share 1.0 (bar 30), median fps 59.94, window min 36.32
- hitches 1 (worst 673.7 ms, shader class, at +4.5 s), audio_starve 0.0, crash false, hang false
- Title verdict: PASS. Pathfind's own review (OUTBOX 10-03 11:55 PDT) already said "not confirmed on the frames".

## SCENE SHOULD CONTAIN (derived; no OUTBOX scene line exists for this run)

- Player character: the red-armoured fighter, moving through the arena.
- Enemies: the dungeon's enemies should appear and be fought over a 10-minute window.
- HUD: health bar, KILL / Gold / KEY counters (present in every frame).
- Scenery: the octagonal arena and its wider rooms, which should change as the fighter travels.
- Progress: position or kill count or gold must change across the window.

## Per-frame (hold frames 024-069, 16 kept; probes 015a-c and 016-023 and 014 are before the hold)

Every frame: live play HUD up (health bar, KILL/Gold/KEY). Camera fixed on the same octagon in all frames. Fighter
on the same spot of the same floor in all frames.

| frame | scene | live play? |
|---|---|---|
| 024 | fighter in the octagon centre, sword raised | live (HUD) |
| 027 | fighter, sword swinging down, swing arcs | live |
| 030 | fighter at centre, sword low, swing arcs | live |
| 033 | fighter at centre, sword swing | live |
| 036 | fighter at centre, same stance | live |
| 039 | fighter at centre, swing arcs | live |
| 042 | fighter at centre, same stance as 036 | live |
| 045 | fighter at centre, swing | live |
| 048 | fighter at centre, swing | live |
| 051 | fighter at centre, sword angle changed | live |
| 054 | fighter at centre, swing | live |
| 057 | fighter at centre, swing | live |
| 060 | fighter at centre, same stance | live |
| 063 | fighter at centre, swing arcs, sparks | live |
| 066 | fighter at centre, arcs at the rim | live |
| 069 | fighter at centre, arcs at the rim | live |

No menu, pause, cutscene or loading card in any hold frame. Live play, but static: one spot, one camera.

## Checks

(a) SCENE items present: fighter present in all 16 frames. Enemies: NONE in any frame (not one enemy across 600 s). HUD present
in all frames. Scenery: the same single octagon in all frames; no other room. FAIL on enemies and on scenery change.

(b) Progress: none. Position is fixed in all 16 frames; HUD readout (the "410" beside the health bar, and the KILL / Gold / KEY
panel) reads the same in frames 024 through 069. The hero stands on the same spot for the whole ~600 s. Far beyond the 60-s caveat
line. FAIL.

(c) Visual defects: none seen (textures and geometry intact). The arcs of the sword swing between frames, which is normal
for the attack, not a duplicated object. No flicker judged here (owner checks flicker).

## VERDICT: REJECT: the fighter stands on one spot of one octagon for the whole 600-s window, with no enemies, no progress,
and no scene change. The verdict's PASS comes from the play-share and fps rules, which do not check position. The same
design fault pathfind found on 10-03 (black-stone-hold2 and -hold3). Not a Playable.
