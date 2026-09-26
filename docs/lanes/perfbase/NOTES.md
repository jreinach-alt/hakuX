# lane.perfbase NOTES

Brief: a fresh guest-thread performance baseline at master on the Nova, and a
`hakuX-pace` line with exact late-frame counts (#68 context). PR #310.

## The `hakuX-pace` line (format proposed to lane.titlerun on #307)

`hw/xbox/nv2a/pgraph/profile.c`, logcat tag `hakuX-pace`, INFO, one line per
60 flips, printed right after the unchanged `hakuX-perf` line:

```
f=<frame_count> v0=<n> v1=<n> v2=<n> v3=<n> v4=<n> vb=<n> max=<ms .1f> ms=<ms .1f>
```

| field | meaning |
|---|---|
| `f` | `g_nv2a_stats.frame_count` at the end of the window (a multiple of 60) |
| `vK` | flips in the window that consumed exactly K VBLANKs; `v4` is 4 or more |
| `vb` | total VBLANKs in the window (mean VBLANKs per flip = vb/60) |
| `max` | longest flip-to-flip interval in the window, ms |
| `ms` | the window's wall time, ms; window fps = 60 / (ms / 1000) |

- `v0` is included (a flip with no VBLANK since the previous flip) so that
  v0+...+v4 == 60 always holds.
- Late flips for a title with nominal N VBLANKs per flip (1 at 60 fps, 2 at
  30 fps) = sum of vK for K > N.
- Parse by key, not position. New fields go on the end.
- The first line of each process is not a steady-state window: the first
  VBLANK delta is taken from zero and the first flip has no predecessor.
  `pace_check.py` drops it.
- The counts are exact per flip; `Vpf` and `G` on the `hakuX-perf` line are
  EMAs of the same quantities.

A soak queued through `request.sh --title` does **not** collect this tag
today: `soak_title.sh`'s and `dispatcher.sh`'s `LOGCAT_SPEC` list
`hakuX-perf` and `hakuX-pages` but not `hakuX-pace`. Both files are
lane.titlerun's (#307), which reads the line, so the ask is on #307.
`perf/run_perf.sh` (hand runs) collects it.

## Prediction

`docs/testing/predictions/perfbase-pace.json`, sha256
`b3f01aa17d887fcd80164866a4c686c9dd101e477fd93ef25e914e3a7430c5b8`, a_ref
724a0dd868 (master), b_ref 5c50884181. Judge:
`python3 docs/testing/perf/pace_check.py <log> --nominal 2 --judge`
(`--selftest` checks that each leg fails on its own broken fixture; P3 has no
mutant fixture).

The brief's third leg compared the late-frame share with `Vpf`. Those are
different quantities (a fraction of flips against a mean VBLANK count), so
the leg was registered on the commensurable one, vb/60 against Vpf, and it
is not independent: Vpf is an EMA of the same per-flip count. P4 is the leg
with two independent sources (VBLANK timer count against the flip clock).

## Tooling changes

- `run_perf.sh`: `OUT=` output dir; collects `hakuX-pace`, `hakuX-pages`
  with threadtime, and `hakuX-build` to `$OUT/<tag>-build.txt` before the
  pre-measure clear (the 2026-09-26 logs predate this and carry no build
  line); refuses to run if `validation_layers` is on;
  saves the prefs before/as-run to `$OUT/<tag>-prefs-{before,run}.xml` and
  restores the before file on exit, checked by read-back; a failed read-back
  exits 3.
- `profile_guest.sh`: `GAME`, `MASH`, `BOOT_S`, `SETTLE_S`, `TAG`, `OUT`;
  records the prefs it ran under and refuses validation layers.
- `bench_ff.sh`: calls the `run_perf.sh` beside it, not the copy in
  `~/hakux-work/perf`.

## Attempt 1 ended waiting, not failed (2026-09-25)

Attempt 1 landed the line, the tooling and the prediction (head `fbc9c48c6d`,
CI green), then stopped: the Nova was held by lane.gamecheck until 21:22 UTC,
so no baseline run could start, and there was nothing else on the brief that
did not need the device. It left the PR in draft without a `waiting:` comment,
which is why handback had to find it. Attempt 2 (resumed 22:52 UTC) merged
master (59 commits, clean) and picks up the device work.

## Device log (attempt 2)

The raw logs, PNGs, prefs and `perf.data` files are under
`/home/justin/hakux-work/perf/2026-09-26/`, driven by
`~/hakux-work/perf/perfbase_campaign.sh`. The write-up is
`docs/investigations/perf-baseline-2026-09.md`.

- **Hold.** `dispatch/hold/nova` was placed ~22:55 UTC, with the reason in
  `nova.why`. The lane waited for texvol283's running arm to leave (23:04)
  and touched the device 23:04-23:49. The hold was lifted at 23:49:26 (moved
  to `hold/lifted/nova.20260925T234926Z`). The `hold_device.sh` lease was
  released.
- **Binary.** `20a1a20eec`, built into `dispatch/builds/` under the
  dispatcher's own `.build.lock` (the same steps as `build_ref`), and
  installed with `adb install -r`.
- **Shader caches.** Cleared once at the start. The dispatcher's
  `.shader_cache_apk.nova` marker (`acad684607ae`) was deleted afterwards,
  so its next Nova run clears this build's caches rather than inheriting
  them.
- **Prefs, as found (`prefs-start.xml`).** `skip_game_picker=false`,
  `setup_complete=true`, `debug_tools=true`, and `dvdUri`, `flashPath`,
  `mcpxPath`, `gamesFolderUri`, `eeprom`, `hddPath`. There was **no
  `validation_layers` key**, no `surface_scale`, and no `env_vars`.
- **Prefs, as run.**
  - `run_perf.sh` runs used the prefs as found plus `surface_scale=1`
    (`<tag>-prefs-run.xml`). Each restored its before file, and the
    read-back was identical in all 6 runs.
  - `profile_guest.sh` writes no prefs, so the profiles ran with the prefs
    as found (no `surface_scale`, i.e. the app default).
- **Prefs, as left.** They match the start except for `dvdUri`, which the
  app rewrites itself to the last disc launched (Crimson Skies). The
  dispatcher had already claimed the Nova (bisect311) when this was
  noticed, so it was not touched again. Every launch rewrites that key.
- **Battery.** 74% at the start.

| tag | what | result |
|---|---|---|
| crimson-r1, r2 | `run_perf.sh 1 <tag> 120` | 72 / 75 pace lines; pace legs P1-P5 PASS on both |
| crimson-p1 | `profile_guest.sh 30` | **VOID**: `Event type 'cpu-clock' is not supported`, then the old script pulled a stale 20 s `perf.data` of another pid |
| crimson-p1b, p2 | `profile_guest.sh 30` | 63,938 / 63,932 samples |
| ff-r1, r2 | `bench_ff.sh 1 <tag> 60` | r1 measured menus (98% of windows at 60); r2 played a round |
| ff-p1, p2 | `profile_guest.sh 30`, startmash 5 | probably menus (3 s settle, as r1) |
| galleon-r1, r2 | `run_perf.sh 1 <tag> 60`, no input, BOOT 150 s | attract demo; r1 hit loading gaps (5 windows) |
| galleon-p1, p2 | `profile_guest.sh 30` | different demo scenes (guest 12% vs 31% of samples) |

## The prediction

**The run.** `perfbase-pace-2.json` (sha256 `ef55b58a...`) re-registers
`perfbase-pace.json` on the refs this attempt actually ran. `a_ref` is
`90a8dc1c1a` and `b_ref` is `20a1a20eec`. `profile.c` is byte-identical to
the old b_ref `5c50884181`, and the legs are unchanged.

`pace_check.py --nominal 2 --judge` on crimson-r1 and crimson-r2 gave
**PASS** on every leg:

| leg | r1 | r2 |
|---|---|---|
| P1 | 71 steps, 0 bad | 74 steps, 0 bad |
| P2 | 0 windows off | 0 windows off |
| P3 | 2.354 vs 2.358 (0.2%) | 2.298 vs 2.283 (0.6%) |
| P4 | 0 windows exceed | 0 windows exceed |
| P5 | 26.16 vs 25.39 (3.0%) | 26.73 vs 26.07 (2.5%) |

**Outside the registration** (other titles, not legs), P3 fails:

- ff-r2: 1.506 vs 1.364 (10.4%);
- galleon-r1: 14.6 vs 3.5.

**The line is right and Vpf is what drifts.** In all six runs, the pace
line's VBLANK total times 16.683 ms equals its summed window wall time to
0.9977-1.0000 (`~/hakux-work/perf/perfbase_vbwall.py`, a scratch
script, not in the repo). At the judge's P4 period, 1000/60 = 16.667 ms, the
whole-run ratios are 0.9967-0.9990 (galleon-r2 lowest) and single windows
0.945-1.009. Vpf is an EMA sampled at the window
end, and it under-reads a window that contains a multi-second stall
(3.3-11.4 s in those runs). P3 is a check that holds on steady content
only; do not reuse it as a correctness check on titles with long stalls.

## Do not repeat

- **Do not trust a `perf.data` without the record's own "Recorded for" line.**
  `profile_guest.sh` now deletes the output first, retries once, and refuses
  to pull. Before this fix it silently pulled whatever was left in
  `/data/local/tmp`.
- **Fuzion Frenzy's `bench_ff.sh` (startmash 5, 3 s settle) does not reliably
  reach a minigame.** Look at `<tag>-end.png` before calling it a minigame
  baseline. A four-player minigame needs a pad sequence, which is
  lane.titlerun's `pad.sh`.
- **Galleon's attract demo has multi-second loading gaps.** A 60 s window
  can hold 5 pace windows. Use 180 s or more if the demo is the workload.
- **Do not re-derive the jump-cache caller from simpleperf.** The unwinder
  loses the stack inside `tcg_flush_jmp_cache`. The source path
  (`CF_PCREL` → `tb_jmp_cache_inval_tb` on every discard) and the `di`
  counter carry the argument.

- lane.tcgchurn (#309) owns `accel/tcg/cputlb.c` and `target/i386/tcg/**`
  and is adding the full-TLB-flush trigger counters; this lane answers "from
  which path" with simpleperf call graphs, not with a second counter.

## Audit decisions (pass 1 and 2, 2026-09-25)

Each of the seven LOWs in `docs/audits/2026-09-25-perfbase-pass1.md`:

1. `hakuX-build` cleared before collection: fixed. `run_perf.sh` dumps it to
   `<tag>-build.txt` before the pre-measure `logcat -c`. The six 09-26 logs
   still carry no build line; their build identity is the lane's record.
2. P3 unfixtured: fixed. The selftest has an `ema` mutant (Vpf 2.30 against
   vb/60 2.05) that must give `FAIL P3` alone.
3. `pace_check.py` boundaries and empty paths: fixed. A frame count that does
   not go up starts a new process, so a one-line process followed by `f=60`
   is excluded, not a step of 0. No window left, or no window with `ms > 0`,
   prints a FAIL and exits 1 instead of a traceback.
4. `profile_report.py` bare StopIteration: fixed. It says which lookup
   failed: no `qemu_main` thread, or a `--tid` not in the split.
5. "within 0.2%": corrected in the PR body to 0.9967-0.9990 at 16.667 ms
   (whole run), and above.
6. "up from the 35-40% read on 09-11": dropped. The 09-11 group total has no
   source in the repo, and the grouping is new. The investigation now states
   the lookup sub-share (11.6-11.8 points) and the 28.6-29.3% left without it.
7. Prefs restore and the superseded prediction: fixed. A failed read-back
   exits 3 from the EXIT trap. `perfbase-pace.json` carries `superseded_by`
   naming `perfbase-pace-2.json`; its legs and refs are unchanged.
