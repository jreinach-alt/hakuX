# Golden overrides

Reference images that replace an upstream golden
(`abaire/nxdk_pgraph_tests_golden_results`) for one test, because that golden
is known to be wrong for the suite build we run. Each is a byte copy of a
console capture and is used only where console and upstream golden disagree
and our output agrees with the console.

**Inert for now.** Nothing reads this tree yet. It takes effect when the
scorer gets its ordered golden-root lookup (lane.toolsmith defect 17: a
`--golden-overrides` root that `score_sweep.py` checks before the upstream
goldens, passed by `dispatcher.sh` as a tree path, not a `$SNAP` sibling).
Until then every scored run still compares against the upstream golden.

**Keyed on suite/test, not test name.** The path is
`<suite>/<test>.png`, with the suite directory named as in the upstream
goldens. Test names repeat across suites: `Texture_render_target` has its own
`TexFmt_R6G5B5`, a different image with a correct golden. A lookup on the
test name alone would score that row against the `Texture_format` frame.

A row scored against an override is still a live regression guard: it is
compared pixel for pixel with real hardware running our disc.

| suite / test | source capture | override sha256 | upstream golden sha256 | why | issue |
|---|---|---|---|---|---|
| `Texture_format` / `TexFmt_R6G5B5` | console set K, `hardware/runs/2026-09-19-calib/full/out/run1/Texture_format::TexFmt_R6G5B5.png` | `07dedad9ac60aa7c36f2791bf877311f66779359912f239bb7815a704ea385f8` | `50af66a644f6a2ba3b7026fcb9a2e1fb5034a2ecca3950d830b5612f1cf24d4e` | Golden is from a suite build printing `C: 0` (`require_conversion` off, RGB565-packed texels); our disc prints `C: 1`. Console (three runs, 09-19 to 09-25) and ours are byte-identical; the golden differs from both by 134,902 px. | #287 |

Evidence and the offline re-score: `docs/lanes/goldencorr287/NOTES.md`,
`docs/lanes/goldovr287/NOTES.md`.
