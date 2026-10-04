# alwaystelemetry: perflog costs ~1.2 ms/frame of render thread (+30% CPU); design the always-on tier (#433)

State: ready

Lane: alwaystelemetry        Issue: #433
Base: master @ b9e33845bd (origin/master merged into the branch at 18:18 PDT)
Files: docs/lanes/alwaystelemetry/NOTES.md, docs/lanes/alwaystelemetry/PR.md, docs/lanes/alwaystelemetry/OUTBOX.md, docs/lanes/alwaystelemetry/WAITING, docs/lanes/alwaystelemetry/abread.py, docs/lanes/alwaystelemetry/ab_castlevania.md
Prediction: none: a rate measurement, not a pixel change. The rate prediction P1 was registered in NOTES.md before the run. Judged: not met as worded (fps), cost confirmed in headroom.
Needs device: yes (done: 1-1791070366-lanelocal-968308, 1-1791072308-lanelocal-1173788)
Needs NDK: no

Release note (none): measurement and design only, no emulator change.

Part 1 of the brief: measure the perflog overhead, inventory the telemetry, design the always-on tier. No emulator code changes.

**The measurement.** One Nova pair on the same ref a971c31220: Castlevania: Curse of Darkness, returning route, golden 20235e93867b, 960 s, plain against `--perflog`. The title is vsync-capped, so the cost is read in headroom from two lines both builds print. The window is the 150 s after the mark where both arms walk the same path.

| | plain | perflog | delta | plain-vs-plain noise |
|---|---|---|---|---|
| fps_ok | 1.0 | 0.9965 | -0.35 pt (one compile stall, a confound) | |
| gfps median | 59.94 | 59.94 | 0 | |
| render-thread CPU ms/s (`[rdc] tcpu`) | 248 | 322 | +74 (+30%) | 14 |
| renderer idle ms/flip (`Ri`) | 8.0 | 6.9 | -1.1 | 0.2 |
| J per frame | 0.1141 | 0.1167 | +2.3% | 0.107-0.115 |

- **The cost:** perflog costs about 1.2 ms of render-thread time per frame, so the thread's busy time per frame goes up 13-19%. That is invisible under the vsync cap and real on a render-bound title. The vCPU does not move.
- **The perflog arm's FAIL** is 15 first-time pipeline compiles of content the plain arm never reached: the route's wall-clock walk loop diverged. It is filed as a NEW ISSUE in OUTBOX.md.

**Decision:** do not make perflog the default. Build the two-tier change. The always-on tier is counters, per-frame phase timers, a 1-in-16 sampled draw timer, GPU timestamps and a per-hitch line; it carries its own self-time and must stay under 10 ms/s. The deep tier stays behind -Pperflog: per-method, per-draw, per-bind and per-upload instrumentation. The full design, with files and functions, is in OUTBOX.md (18:22 post). The derivation and the P x win ranking are in NOTES.md (attempt 4).

`abread.py` reproduces the table from the two result dirs. `ab_castlevania.md` is its output, plus the plain-vs-plain control (1-1791063303-lanelocal-3700348 against the plain arm).

**Local checks (no CI offline):**
- `python3 -m py_compile docs/lanes/alwaystelemetry/abread.py`: OK.
- `abread.py` run on both pairs: the output is committed.
- `git diff --stat origin/master...HEAD` touches only `docs/lanes/alwaystelemetry/`.
- No harness or emulator files changed, so `selftest.sh` and `preflight.sh`'s build gates do not apply.

**Next:** the two-tier change, in the Opus slot (P 0.8; win: no second run per performance miss). Then one Nova pair on this route, judged on `tcpu`, `Ri` and the tier's self-time.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
