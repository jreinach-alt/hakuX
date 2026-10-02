# titleroutes2: per-title routes and surveys on the Nova, successor to lane.titleroutes (#397)

State: draft

Lane: titleroutes2         Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 333711ac66 (origin/master merged at edcb5afd06)
Files: docs/lanes/titleroutes2/NOTES.md, docs/lanes/titleroutes2/OUTBOX.md, docs/lanes/titleroutes2/PR.md, docs/testing/titles/routes/bloody-roar-extreme.route, docs/testing/titles/routes/gunvalkyrie.route, docs/testing/titles/routes/halo-2.route, docs/testing/titles/routes/halo-ce.route, docs/testing/titles/routes/ninja-gaiden-black.route, docs/testing/titles/routes/star-wars-ep3.route, docs/testing/titles/targets.toml
Prediction: none: route data (inputs) and notes, no emulator code; route checks are --no-expect dispatch runs
Needs device: yes (Nova, queued requests; short held sessions only if needed)    Needs NDK: no

Per-title routes written from survey frames and confirmed by frame-reviewed Nova replays (numbers are screening reads
from `title_verdict.py --targets`; details in `NOTES.md`):

| title | route | state | Nova reading |
|---|---|---|---|
| Gunvalkyrie (49470017) | `gunvalkyrie` | confirmed, nominated (#433) | 59.94 median, 100% at 30+, no hang |
| Star Wars Ep. III (4C410017) | `star-wars-ep3` | confirmed, nominated (#433) | 29.97 median, 96.3% at 30+ |
| Ninja Gaiden Black (5443000D) | `ninja-gaiden-black` | confirmed | 39.4 median (target 60), shader hitches |
| Bloody Roar: Extreme (48550001) | `bloody-roar-extreme` | confirmed | 9.84 median, texture-class hitches |
| Halo: Combat Evolved (4D530004) | `halo-ce` | draft | reaches the cryo bay; the aimed light test needs drive.py |
| Halo 2 (4D530064) | `halo-2` | draft, replay 1 queued | survey reached the Armory's look test |

Release note (none): route data and notes only, no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
