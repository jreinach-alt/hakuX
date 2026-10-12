# snapshot1011 OUTBOX (#433)

## #433 -- 2026-10-11 14:10 PDT

The save-state engine is ported to Android with its test sequence (`HAKUX_SNAPSHOT_TEST`). `ui/xemu-snapshots.c`
is built in place of the stub; states carry a version 2 header (schema, build, title, disc, controller layout)
that is checked before the machine resets; save and load start a paused machine first; the vertex-attribute,
lighting-ring, fog and other unsaved pgraph state is saved; the APU FIFO is emptied on load. Every changed C file
passes the NDK compiler with the Android build's flags. The first Nova run of the sequence is next.

## #433 -- 2026-10-11 17:48 PDT

First Nova run of the test sequence (1-1791753422-snapshot1011-2350466, 187: Ride or Die): every step passed.
Save 263 ms, load 116 ms, state 59.0 MB; 20 save/load cycles 40/40 (save median 307 ms, load median 107 ms);
60 s of play after the load with six distinct region hashes; a save and a load while paused leave the machine
paused; a state naming a different controller layout is refused after a 5 ms header check, before any reset,
and the game keeps running. Both slots were deleted, and the disk harvest matches the title's previous run.
The race in this run never moved off its start line, so the frames cannot show a scene change for the first
criterion; a second run saves on the mission briefing and loads it back from the race.

## #433 -- 2026-10-11 18:29 PDT

All five phase-0 criteria hold on the Nova. Second run (1-1791764800-snapshot1011-813455, master merged): the
state saved during the pre-race cutscene and loaded from the race brings the cutscene back on the first frame
after the load, then the countdown and race play again. Save 338 ms, load 123 ms, 58.4 MB; 20 cycles 40/40 (save
median 291 ms, load median 98 ms); the paused save and load and the controller-layout refusal pass again. No
black screen and no renderer change needed. Left for phase 1: a state loads only into the APK that made it, the
title disk is rebuilt every run, and the route does not rewind with a load.
