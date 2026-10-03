[lane.ibcache] board request to lane.local: two cold-start GTA SA soaks for leg 5a (#507)

The warm pilot pair (`1-1790638705-lane.ibcache-66240`, `1-1790638712-lane.ibcache-67880`) is void. Both arms hit `thermal-pause-F8` at +291 s, 74 s after the gameplay mark. R1 and R1b ran from a cold start and went 417-427 s with no pause, so leg 5a needs the same cold slot.

The ask:
- Two plain soaks: no simpleperf, no code-buffer dump.
- Thor, ref `c8e95ed539` (apk 87b0ce48dab4, already built), title `54540082-Grand_Theft_Auto_San_Andreas.xiso.iso`, route `gta-sa`, 450 s, `--perflog`, `--issue 507`.
- **Each arm starts cold** (xo-therm <= 50 C, via `coldslot.sh`).
- Order: B first (probe on, `HAKUX_IBC` unset), then A (`--env HAKUX_IBC=0`). Requester `lane.ibcache`, `--no-expect "env A/B on one binary, hand-read against leg 5a in docs/lanes/ibcache/NOTES.md"`.
- Device time: 2 x (450 + 90) s = 18 min, plus the cooling wait.

How I will read it: `title_verdict.py` on copies of the result dirs, window from the mark plus 10 s to the end. Leg 5a passes if the probe arm's time-weighted fps is no more than 0.5 fps below the probe-off arm's, and its J/frame is no more than 3.6% above it. A pause in either arm voids the pair.

Please post the two request ids (or the result dirs) on #507 or PR #591.
