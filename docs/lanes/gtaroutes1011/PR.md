# gtaroutes1011: routes into play for GTA III, Vice City, and a San Andreas driving route (#433, 0.5)

State: ready

Lane: gtaroutes1011        Issue: none (#433 umbrella)
Base: master @ 13e0590809
Files: docs/lanes/gtaroutes1011/NOTES.md, docs/lanes/gtaroutes1011/PR.md,
docs/testing/titles/routes/gta-3.route, docs/testing/titles/routes/gta-vc.route,
docs/testing/titles/routes/gta-sa-drive.route, docs/testing/titles/targets.toml,
docs/testing/titles/pathknow/paths/5454000E.json, docs/testing/titles/pathknow/paths/5454000F.json,
docs/testing/titles/pathknow/hints/learned-pub-5454.md, docs/testing/titles/pathknow/hints/learned-series-grand-theft-auto.md
Prediction: none: route data (inputs) and notes, no emulator code; route proofs are --no-expect dispatch runs
Needs device: yes (Nova only, via request.sh and pathfind.py)    Needs NDK: no
Release note (none): frame-rate routes for GTA III and Vice City (test data only, no emulator change).

The two `pathknow/hints/learned-*.md` files are `pathfind.py`'s own side-effect writes. They are outside the brief's
territory list. Pathfind-running lanes commit them the same way.

## Results

Every proof is a 600 s soak on the Nova, `--frames-every 30`, on the title's golden (`hdd.json`:
`"loaded": "golden"`). The bar is the brief's: mark reached, `gameplay_s` >= 300, and the player in a different
place in >= 3 post-mark frames. `fps_ok_share` and the median are from `title_verdict.py`'s 30 fps windows.

| Title | Route | Golden | Proof result id | gameplay_s | fps_ok_share | median fps (min) | Frames showing movement | Result |
|---|---|---|---|---|---|---|---|---|
| GTA III (5454000E) | gta-3 | 9153c63300da | `1-1791747431-gtaroutes1011-1129784` | 453.6 | 0.9804 | 29.97 (24.88) | 4: f00009, f00010, f00015, f00021 (Callahan Bridge, minimap moves each time) | pass |
| Vice City (5454000F) | gta-vc | 77a5f0908dce | `1-1791761282-gtaroutes1011-282177` | 492.1 | 0.9908 | 29.97 (24.74) | 10: f00005-f00014 (Ocean Beach streets, sidewalk, neon, beachfront); f00015-f00020 wedged at one fence | pass |
| San Andreas drive (54540082) | gta-sa-drive | 7da19befd45b | `1-1791761288-gtaroutes1011-284417` | 402.1 | 0.9895 | 29.97 (28.13) | 0: on the BMX, in one spot by the alley wall | fail |
| San Andreas drive, rerun | gta-sa-drive (pedal fix) | 7da19befd45b | `1-1791768457-gtaroutes1011-1576234` | 380.0 | 0.9831 | 29.96 (27.97) | 0: on the BMX, in the same spot by the alley wall, radar unchanged | fail: stopped |

`title_verdict.py --require confirmation` says FAIL on every row. That is the confirmation tier's 600 s bar.
These are route proofs, judged against the brief's 300 s bar.

**GTA III.** On the golden, `START` at the title opens a New Game / Load Game menu. The first-run disk never showed
it. The route's cutscene-skip A train clears it by t=270 s, and play runs uninterrupted after that.

**Vice City.** Tommy covers ten places from the mark to 18:04:24. After that he runs in place against a fence
corner for the last ~2.5 min. That still meets the bar. A periodic heading change in the loop would keep all of
it moving.

**San Andreas drive.** The first proof mounted the BMX ("BMX" captioned) but pedalled with `LY min`. The game's
help text says that stick only shifts CJ's weight, so he sat still. The one fix keeps the boot and mount. The
loop now holds A to pedal, taps it once a cycle, steers on the pedal, and brakes and turns briefly so a wall
cannot pin him. The rerun was on the same build (`def393be25`), so the route was the only change. It failed the
same way: twelve post-mark frames, one place.

The brief allows one fix and one rerun, so SA-drive stops here. The blocker is that the input that pedals the
BMX on this Xbox port is unknown.
- Tried: LY, A held, A tapped, X, LX.
- A reaches the game: the same run's A presses skip every cutscene.
- A car needs the same accelerate input, so it is blocked on the same unknown.

To unblock it, a held pathfind session on the golden probes RT, LT and B one at a time from the mount.
Alternatively, read the in-game Controller Setup screen. Then change only the route's loop and run one 600 s
proof. `gta-sa-drive.route`'s header says NOT PROVEN, and it is not in `targets.toml`. `gta-sa.route` is untouched.

`targets.toml`: rows for 5454000E and 5454000F with `iso.nova` and the route. Neither has a sourced `target_fps`:
there is no documented cap, and no #482-style read of the game's limiter was done. Both rows say so and use
the 30 default.

Full account in `docs/lanes/gtaroutes1011/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
