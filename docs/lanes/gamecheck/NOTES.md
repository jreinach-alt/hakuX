# lane.gamecheck -- #265 re-check of Retro Tech Dad's hakuX 0.3.1 glitch list

Pinned ref for the whole pass: `e48514f98034dfdf1daca82e2142fbc005732faa`
(origin/master, 2026-09-25), which the dispatcher built as apk `851650a27937`.
Device: the Nova (`ee317437`) only. Frames, sheets, WAVs and helper scripts are
on the host under `/home/justin/hakux-work/gamecheck/<game>-soak/`; every
frame of every soak is in `dispatch/results/<request id>/frames/`.

(in progress: table below is filled per game as verdicts land on #265)

| game (ISO on the Nova) | reported on 0.3.1 | verdict | evidence |
|---|---|---|---|
| Spikeout: Battle Street (Europe) | cutscenes badly broken | **reproduced** | soak `1790364700-gamecheck-355013`, `spikeout-soak/f00028.png` |
| RalliSport Challenge 2 (Japan, Europe) | car renders wrong on Vulkan | not reached by soak | soak `1790364698-gamecheck-354879` |
| Galleon (USA) | stipple / hatching (#77) | **reproduced** (existing #77) | soak `1790365217-gamecheck-415198`, `galleon-soak/f00070.png` |
| Tork (USA) | ambient audio wrong | not reproduced as a measurable fault | soak `1790365218-gamecheck-415427`, `tork-soak/*.wav` |
| Grabbed by the Ghoulies (USA) | texture glitches | pending | soak `1790365974-gamecheck-732876` |
| Conker Live & Reloaded | minor graphical glitches | pending | soak `1790365976-gamecheck-734705` |
| Crimson Skies (USA) | crash skipping first cutscene | pending (phase 2) | |

## Things that cost time

- **The ISO names are not guessable.** My first two soaks failed with TITLE
  NOT FOUND on Redump-style `(USA).xiso.iso` names. RalliSport 2 and Spikeout
  on the Nova are the **PAL** images, and Conker and Tork are plain `.iso`
  files. Nothing on the host lists the device's `Games/XBox/`. I took a two-minute
  hold (19:29-19:31 UTC) to `ls` it. The listing is on #265.
- **"guest exited after N s" can be an adb flake.** Spikeout's soak says the
  guest exited at 185 s. Its logcat has no crash line, the guest was logging
  at 59 gfps up to its last line, and `run.log` shows the WSL
  `UtilAcceptVsock` error. The last frame is a truncated PNG.
- A soak's audio can be longer than `--seconds`: the hold loop's adb
  round-trips stretch 240 s to ~263 s of app lifetime. Check it against the
  logcat span before calling a capture stale.
