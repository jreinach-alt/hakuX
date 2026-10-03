# lane.memfast: remove the XBOX load fast path, with the [mf0] VA==PA census (#507)
State: ready

Lane: memfast            Issue: #507 (PR #590 before the suspension)
Base: master @ 9d1155f919 (phase 1 folded as ddbc5f0173; this head adds its Nova scores, docs only)
Files: accel/tcg/cputlb.c, system/physmem.c, tcg/aarch64/tcg-target.c.inc, docs/lanes/memfast/NOTES.md, docs/lanes/memfast/PR.md, docs/lanes/memfast/OUTBOX.md, docs/lanes/memfast/arm_noise.py, docs/lanes/memfast/f0a_rates.py, docs/lanes/memfast/legs_read.py, docs/lanes/memfast/mf0_read.py, docs/lanes/memfast/unstable_caps.py, docs/lanes/memfast/out/arm-noise.out, docs/lanes/memfast/out/f0a-rates.out, docs/lanes/memfast/out/jitmix-bref.out, docs/lanes/memfast/out/jitmix-r1.out, docs/lanes/memfast/out/legs-bref.out, docs/lanes/memfast/out/legs-r1.out, docs/lanes/memfast/out/mf0-auf-a1.out, docs/lanes/memfast/out/mf0-nightfire-a1.out, docs/lanes/memfast/out/mf0-nightfire-a2.out, docs/lanes/memfast/out/sym-bref.out, docs/lanes/memfast/out/sym-r1.out, docs/lanes/memfast/out/unstable-caps.out, docs/lanes/memfast/out/unstable-caps2.out, docs/testing/predictions/memfast-drop-pixels.json, docs/testing/predictions/memfast-drop-pixels-stable.json, docs/testing/predictions/memfast-drop-pixels-stable2.json, docs/testing/predictions/memfast-drop-soak.json, docs/testing/predictions/memfast-drop-soak-nova.json
Prediction: docs/testing/predictions/memfast-drop-pixels-stable2.json @ abc1ce1b80d98c18e48cc38f0cd263dcc1820c600ea64ebc9a6ca604542d5c07 ; docs/testing/predictions/memfast-drop-soak.json @ 08c3f0519d9dd61a715aba243efd850d4785a8b0d7bedf52e1b0c7918c6a83b7 ; docs/testing/predictions/memfast-drop-soak-nova.json @ 583315ad893a281b56b820d3e7ab291f68bbc763bf5f8ff78c2ed0135ced00dd
Needs device: yes    Needs NDK: yes

Release note (performance): the emulated CPU does about 5% less work per frame in GTA San Andreas. A memory-read shortcut that never engaged in gameplay no longer costs a check on every block and every read. Fps and battery draw did not measurably change on the 30 fps titles measured.

## What it changes

- **`31515f9751` (a_ref): the `[mf0]` census, instrumentation only.** It
  classes every TLB install in the fast path's two windows by whether
  `host_base + VA` is the TLB's own translation. One line every 2 s.
- **`82e0ef1fa9` (b_ref): the fast path is removed.** That is the per-TB
  preamble and the per-load `cbz x26` + window test. X26 and X27 go back
  to the allocator. Loads keep the softmmu compare they already took in
  gameplay.
- **Why removed, not fixed.** On GTA, Nightfire and AUF the path is
  disarmed by NV2A surface watches from boot onward (`cb >= 2` on every
  line after window 0). Wherever it was armed, 98.7-99.4% of low-window
  installs had VA != PA, so it read the wrong page. A correct version needs
  a per-page lookup, which is the TLB. Fastmem (phase 2) is the correct form.

## Legs

| leg | result |
|---|---|
| S: preamble and per-load test gone (GTA, Thor, cold profile) | **PASS.** 0 of 3,429 TBs hold either sequence (R1: 3,829 and 3,292). Host instructions per TB -21%. About 6% of the vCPU thread left: 3.1% on the sequences, 2.9% from the load compares |
| vCPU time per frame (an observation) | -4.3% and -6.2% on two GTA pairs |
| Pixels, `memfast-drop-pixels.json` (Thor) | FAIL, 6 of 3,379. All six are known run-to-run noise |
| Pixels, `memfast-drop-pixels-stable.json` (Nova) | FAIL, 36 of 3,167. All in ZPass_pixel_count: the same fix APK gave base-exact values in arm 1, and the suite takes 1750 on builds without this change. The rule's reader skipped `white-content` rows (NOTES) |
| Pixels, `memfast-drop-pixels-stable2.json` (Nova, read 2026-10-03) | **PASS**, all 3,064 registered checks |
| J/frame: mean B/A over pairs per title (Nova, read 2026-10-03; registered pass <= 0.98) | **NOT SHOWN.** GTA 1.011 (1.028, 0.995), Nightfire 0.993 (0.904, 1.082), Crimson 0.975 (one pair). Not refuted (that needs >= 1.00 on both). Same-arm spread (Nightfire B: 15%) exceeds the 2-7% predicted, and every title runs at its 30 fps cap. GTA pilot 0.830 (Thor, not pooled) |
| F: fps | VOID: every A run is at its 30 fps cap |
| G: B reaches gameplay with no crash or hang | **PASS**: GTA (Thor; Nova x2), Nightfire (Nova x2), Crimson (Nova) |
| Census | GTA, Nightfire, AUF, Crimson: dead in play, non-identity wherever armed. BAR1 all identity |

## Local checks (no CI while GitHub is suspended)

- `-fsyntax-only` with the NDK compile database's flags on `cputlb.c`,
  `physmem.c` and `tcg.c` (which includes the backend): rc 0, no errors, no
  warnings beyond master's own `TARGET_PAGE_MASK` shifts.
- The Desktop fix from 09-28 (a constant 12-bit page shift for the census
  bitmaps) is unchanged. It was CI-green on 6badcd9404.
- No harness files changed, so `selftest.sh` does not apply.

## Next

Recorded in `docs/lanes/memfast/NOTES.md`, "Next", with P x win. First W1
(the per-page watch flush, P 0.7, Conker's 287 full flushes/s) alongside
F0a's device half. Those decide F1 (fastmem loads: P 0.4, about 11% of GTA's
vCPU).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

_Set ready by lane.local 2026-10-03 under the PM's operational authority (plan 10-03 action 6). On the Thor, the
ZPass_pixel_count A/A run (FIX 82e0ef1fa9 against itself, 1791004647-lanelocal-thor-2044245) and the A/B run (FIX
against BASE 31515f9751, 1791004648-lanelocal-thor-2044305) both have 0 differing captures, all 72 byte-identical.
The stable arm's 36/3,167 ZPass FAIL does not reproduce with the test run alone, so it is not a memfast defect as
measured._
