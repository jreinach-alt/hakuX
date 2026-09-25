# lane.gamecheck: #265 re-check of Retro Tech Dad's hakuX 0.3.1 glitch list

Pinned ref for the whole pass: `e48514f98034dfdf1daca82e2142fbc005732faa`
(origin/master, 2026-09-25). The dispatcher built it as apk `851650a27937`,
and every soak and the whole phase-2 hold ran that apk. Device: the Nova
(`ee317437`) only. Frames, contact sheets, WAVs, phase-2 screencaps, logs and
the helper scripts (`sheet.py`, `pcm_look.py`, `pcm_bands.py`, `gc.sh`,
`hold_when_claimed.py`) are on the host under `/home/justin/hakux-work/gamecheck/`.
Every soak frame is in `dispatch/results/<request id>/frames/`. Verdicts, one
per game, are comments on #265.

## Verdicts

| game (ISO on the Nova) | reported on 0.3.1 | verdict at `e48514f980` | evidence |
|---|---|---|---|
| Spikeout: Battle Street (Europe) | cutscenes badly broken | **reproduced**: boot/attract FMV covered in green block corruption, subtitles clean | soak `1790364700-gamecheck-355013`; `spikeout-soak/f00028.png` |
| Galleon (USA) | stipple / hatching (#77) | **reproduced** (existing #77), hands-off in the lava-cave attract demo | soak `1790365217-gamecheck-415198`; `galleon-soak/f00070.png`, `f00073.png`, `f00066.png` |
| Crimson Skies (USA) | crash skipping first cutscene | **not reproduced**: boot FMV skip and mission-cutscene skip both clean (`fe418afedf` holds) | hold 20:22-20:52; `phase2/cs1_after_skip_t65.png`, `cs2_sp3.png` |
| RalliSport Challenge 2 (Japan, Europe) | car renders wrong on Vulkan | **not reproduced visibly** (weak: the race runs at 1-2 fps) | soak `1790364698-gamecheck-354879` (FMV only); hold: `phase2/rs_race7.png`, `rs_race_b.log` |
| Tork (USA) | ambient audio wrong | **not reproduced as a measurable fault**; needs a listener or reference | soak `1790365218-gamecheck-415427`; `tork-soak/tork_level_190-260s.wav` |
| Grabbed by the Ghoulies (USA) | texture glitches | **not reached** (story intro at 3-11 fps did not end in ~7 min) | soaks `1790365974-gamecheck-732876`, control `1790366421-gamecheck-890892`; `phase2/gh_*.png` |
| Conker Live & Reloaded | minor graphical glitches | **not reached** (load stalled; dispatcher soaks never launched it) | soaks `1790365976-gamecheck-734705`, `1790366865-gamecheck-998763`; `phase2/ck_*.png`, `ck_load.log` |

New problems found on the way (marked on #265 for the board):

- **In-engine frame rate collapses to 1-7 gfps** (G 250-1000 ms, Vpf 7-15)
  in Ghoulies (title and attract; filed as **#311**), in a RalliSport 2
  race, and in Conker's bar menu. Menus and FMV on the same apk run at
  59 gfps. Crimson Skies flies at 24-29 and Galleon's demos run at 18-22.
  Thermal status was 0. A soak without frame capture shows the same collapse,
  so it is not capture overhead. The review ran all three at 2x native on
  0.3.1, so this may be a regression since then. Not bisected; that is the
  next lane's job.
- **Conker's single-player load stalls**: no completed frame for 2.5+ min
  while the guest CPU runs.
- **Harness:** `request.sh --title "Conker Live & Reloaded.iso"` never
  launches the app (0 logcat lines, twice). A hand `am start` of the same path
  works. It is the only file name on the device with `&`.

## Reach method per game

| game | hands-off (soak) reaches | needs input for | input path that worked |
|---|---|---|---|
| Spikeout | boot FMV at ~22 s, replayed in attract after ~40 s on the title | nothing: the symptom is in the attract loop | none |
| Galleon | three attract demos; the lava cave is the 2nd, ~100-150 s after boot | nothing for #77's artifact | none |
| Crimson Skies | boot newsreel FMV (~35 s), then the main menu | the skip itself | A at ~35 s, START; then A (Single Player), A (profile "Nathan"), A: straight into flight |
| RalliSport 2 | ~100 s of FMV, title, FMV loop; no attract race | any race | START, A, A (Create profile), A on "0" key, hat D/R to **Done**, A; hat L to SINGLE RACE, A x5 (defaults), A on START RACE |
| Tork | title, in-engine intro, then drops into the first level by itself at ~170 s | nothing for the ambience | none (`--audio-capture 64 --pull 'apu_monitor.s16le48k2ch.pcm*'`) |
| Ghoulies | book title and comic-panel control reel, looping | gameplay | START, A (slot 1 holds a save), A ("Play: Chapter 1, Scene 1"), then A per story panel; not finished in 7 min at 3-11 fps |
| Conker | nothing (dispatcher never launches it) | everything | by hand: `am start`, wait ~25 s, START, A at the bar menu, then the load stalls |

## What made scenes hard to reach (feeds the scripted-input harness item)

- **`pad.sh`'s d-pad codes do nothing on this pad.** The Retroid Pocket
  Controller (`/dev/input/event7`) navigates menus with `ABS_HAT0X` (16) and
  `ABS_HAT0Y` (17) at -1/0/1. `BTN_DPAD_*` (544-547) exist but RalliSport 2's
  menus ignored them. Its sticks are +-32767, not 128-centred as `pad.sh`
  assumes, and the triggers are `ABS_GAS` (9) and `ABS_BRAKE` (10).
- **Every adb call can drop.** The WSL `UtilAcceptVsock ... accept4 failed 110`
  error hit roughly one call in five this session. A dropped `sendevent` pair
  loses a button, or leaves it half-pressed and lands late (a keyboard typed
  "00" for one press). A harness must verify each step with a screencap, or
  run the whole input script in ONE `adb shell` invocation.
- **The same flake fakes guest exits in soaks.** Spikeout's soak says "guest
  exited after 185s" and the Ghoulies control says 35 s. Both logcats run on
  normally and have no crash line. `soak_title.sh`'s `alive()` treats a
  failed `ps` as a dead guest.
- **The Stop hook kills a hand-driven run.** Any agent session's turn end runs
  `stop-emulator.sh`, which force-stops the emulator and sleeps the panel
  unless the device's lease is fresh. While the dispatcher is held, nothing
  renews `/tmp/hakux-device-lease.nova`, so my Crimson Skies run died at
  13:27:48 mid-menu. It looked like a crash until the log showed
  `forceStopPackage ... from pid 15139` plus the sleep button. Renew the
  per-device lease (every 30 s) for the length of a hold, and let it lapse
  when you lift.
- **At 1-7 fps a menu takes minutes**, and presses during load screens or
  transitions are eaten. Ghoulies' story intro and Conker's load were not
  finishable in the hold. Until the frame-rate problem is fixed, gameplay in
  those two titles is out of reach for a 60-minute hold.
- **Profiles and saves persist on the device.** Crimson Skies ("Nathan"),
  Ghoulies (slot 1) and now RalliSport 2 ("00") have saves. Resuming them
  skips a lot of menu, but it also means "the first cutscene" of a resumed
  save is not the new-game cutscene.

## Things that cost time

- **ISO names are not guessable.** My first two soaks failed TITLE NOT FOUND
  on Redump-style `(USA).xiso.iso` names. RalliSport 2 and Spikeout on the
  Nova are the **PAL** images; Conker and Tork are plain `.iso`. Nothing on
  the host lists the device's `Games/XBox/`, so I took a 2-minute hold
  (19:29-19:31 UTC) to `ls` it. The listing is on #265.
- A soak's audio can be longer than `--seconds`: adb round-trips stretched a
  240 s hold to 263 s of app lifetime. Check the capture length against the
  logcat span before calling it stale. It was not stale.
- Holding with MY apk installed: other lanes' requests switch the apk
  between runs. `hold_when_claimed.py` places the hold the moment my own soak
  is claimed, so the device is left on my build when that soak ends.

## Do not repeat

- Do not score Galleon's 2 s-sampled soak frames against #77's per-100 rate.
  The baselines are from denser captures.
- Do not call Tork's level ambience "noise" from the spectrogram. The display
  scaling makes it look broadband; the spectral flatness is <= 0.002.
- Do not read a `hakuX-watchdog STALL` line as a hang by itself. It fires
  every few seconds during healthy 59-gfps FMV. The hang signal is the
  absence of `gfps` lines.
