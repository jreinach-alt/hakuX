# #265: re-check Retro Tech Dad's hakuX 0.3.1 glitch list on today's build, on the Nova

Lane: gamecheck            Issue: #265
Base: origin/master (the build under test is master; pin one ref for the whole pass and record it)
Files: docs/lanes/gamecheck/** only. No code: this lane measures and reports. Frames and logs
stay on the host under `/home/justin/hakux-work/gamecheck/` and the dispatcher's result dirs,
never in the repo.
Needs device: yes, **the Nova (`ee317437`) only**. Needs NDK: no.

## Why

The owner is shifting part of the campaign from synthetic test-suite pixels to glitches in real
games. Retro Tech Dad's review of hakuX **0.3.1** (2026-08-08) is the source: the transcript is at
`/home/justin/hakux-work/gamecheck/retrodad-transcript.txt`, and the list is in #265. The owner
loaded the Nova's games from it; they are under `/storage/E6C6-D7AA/Games/XBox/`. Much has changed
since 0.3.1, and one item is already known fixed (the Crimson Skies intro-skip crash, `fe418afedf`,
v0.4.0-j1). So the first question for every item is: **does it still happen?**

## The job, in two phases

### Phase 1: hands-off soaks through the dispatcher (no hold)

For each game in #265's table, queue one soak on the Nova at your pinned ref. Record whether the
reported glitch shows in the intro, attract mode, demo or menus.

`bash docs/testing/request.sh --who gamecheck --purpose "<game>: <glitch>" --title "<exact ISO name>" --seconds 240 --frames-every 2 --device nova --ref <sha> --no-expect "game re-check, #265"`

- Use `bash docs/testing/request.sh`. A direct `docs/testing/...` call is refused by the lane
  allowlist.
- The idle-priority full-corpus sweep (`z-*`) yields to you between suites, so your soaks run
  promptly. Do not queue more than two at once: arms for other lanes also need the Nova.
- **Look at the frames yourself** (you can read PNGs). Look for the reported symptom: the RalliSport
  2 car, Spikeout's cutscenes, Galleon's stipple and hatching. Also note anything else broken that
  you see.
- Tork is audio: add `--audio-capture` (see `request.sh`'s header for the pull glob) and describe what
  the ambient track does.

### Phase 2: the scenes a soak cannot reach (a bounded hold)

Gameplay glitches (Ghoulies' textures, Conker, a RalliSport 2 race, Crimson Skies' intro skip) need a
controller. `request.sh` has no input scripting yet; that is a harness item, not this lane's. For
these:

1. **Place a hold** (read AGENTS.md "Working with a device" first). Touch
   `/home/justin/hakux-work/dispatch/hold/nova` and write `nova.why` with your lane name, the reason,
   and "lane.gamecheck lifts it by <time>". **At most 60 minutes per hold.** Only hold when
   `dispatch/running/` shows nothing on the Nova, and never hold while a request of another lane is
   running there.
2. Drive input at the **evdev layer** with `sendevent`, per the AGENTS.md table. **Never use
   `input keyevent 96` or a non-gamepad key: it exits the app.** Wake the screen first with
   `input keyevent KEYCODE_WAKEUP`, or the run is void.
3. Grab frames with `adb -s ee317437 exec-out screencap -p > <file>.png` at the moment the symptom
   should show.
4. **Lift the hold** (move `nova` and `nova.why` into `dispatch/hold/lifted/` with a timestamp suffix)
   and say so on #265.

## Report

- **On #265, one comment per game:** reproduced / not reproduced / not reached. Give the ref, the
  request id or hold window, and the frame file names under `/home/justin/hakux-work/gamecheck/`.
  Describe in one or two sentences what is visibly wrong, and where in the frame.
- For every **reproduced** glitch, add a comment line starting `` `[lane.gamecheck]` new defect: ``
  naming the game, the scene and how to reach it, so the board can file it with your frames. **Do not
  diagnose or fix.** That comes later, per issue.
- NOTES carry the table, the reach method per game, and anything that made a scene hard to reach. The
  latter feeds the scripted-input harness item.

## Do not

- **Touch the Thor.** It carries the sweep and other lanes' arms.
- **Hold the Nova for more than 60 minutes at a time,** or while another lane's request runs on it.
- **Change emulator settings globally.** If a per-game setting matters (for example
  skip-occlusion-queries), say which and leave it off by default.
- **Trigger CI as a self-check.**

## Done when

- Every Nova game in #265 has a verdict comment with its evidence.
- Reproduced glitches are marked for filing.
- The hold is lifted and NOTES are written.
- A PR with the lane template carries only `docs/lanes/gamecheck/**`, and is marked ready.
