# Accuracy scoreboard

Each cell is **exact/captures · structural px** — structural being differing pixels that are not one step out, which is the part that is a rule rather than a rounding floor.

| run | binaries | built | hw commits behind tip | discs | captures | rescored |
|---|---|---|---:|---:|---:|---:|
| `0026f00534` | 88452c539d64 | 2026-09-13 | 31 ⚠️ | 100 | 3379 | — |
| `6762a54c82` | 03ca859f9457 | 2026-09-13 | 6 ⚠️ | 100 | 3379 | — |
| `after` | 553cfffc73d3 | 2026-09-12 | 28 ⚠️ | 100 | 3379 | — |
| `c866527e03` | 6bf6a11955f3 | 2026-09-13 | 22 ⚠️ | 100 | 3379 | — |
| `pre-fixes-fb4dfafc` | fb4dfafc6d38 | 2026-09-12 | 57 ⚠️ | 99 | 3375 | — |
| `repeat-c866527e03` | 6bf6a11955f3 | 2026-09-13 | 26 ⚠️ | 100 | 3379 | — |

| category | goldens | `0026f00534` | `6762a54c82` | `after` | `c866527e03` | `pre-fixes-fb4dfafc` | `repeat-c866527e03` |
|---|---:|---|---|---|---|---|---|
| Texture addressing ⚠️99% | 198 | 65/197 · 811,873 | 65/197 · 811,873 | 65/197 · 811,873 | 65/197 · 811,873 | 65/197 · 789,528 | 65/197 · 811,873 |
| Texture formats | 119 | 69/119 · 584,148 | 74/119 · 396,435 | 69/119 · 584,148 | 76/119 · 272,054 | 61/119 · 1,182,369 | 76/119 · 272,054 |
| Render to texture ⚠️99% | 67 | 23/66 · 613,452 | 24/66 · 610,690 | 23/66 · 613,452 | 24/66 · 610,690 | 16/66 · 638,222 | 24/66 · 610,690 |
| Shadow / projective | 288 | 256/288 · 11,732 | 256/288 · 11,732 | 256/288 · 11,732 | 256/288 · 11,732 | 176/288 · 17,388 | 256/288 · 11,732 |
| Lighting | 195 | 27/195 · 358,686 | 27/195 · 358,686 | 27/195 · 358,686 | 27/195 · 358,686 | 27/195 · 476,228 | 27/195 · 358,686 |
| Bump mapping | 82 | 0/82 · 747,933 | 0/82 · 747,933 | 0/82 · 814,408 | 0/82 · 747,933 | 0/82 · 818,008 | 0/82 · 747,933 |
| Fog | 280 | 37/280 · 154,377 | 37/280 · 154,377 | 31/280 · 1,240,473 | 37/280 · 154,377 | 23/280 · 1,574,992 | 37/280 · 154,377 |
| Blend ⚠️9% | 1722 | 13/154 · 5,141,245 | 13/154 · 4,991,440 | 13/154 · 5,141,245 | 126/154 · 310,742 | 5/154 · 5,907,527 | 126/154 · 310,742 |
| Depth / stencil ⚠️62% | 1688 | 257/1042 · 6,007,774 | 257/1042 · 5,940,646 | 260/1042 · 5,907,122 | 258/1042 · 5,918,676 | 246/1042 · 6,006,689 | 257/1042 · 5,912,888 |
| Rasterisation ⚠️98% | 514 | 44/502 · 2,036,188 | 44/502 · 1,935,788 | 44/502 · 2,036,188 | 48/502 · 1,936,437 | 43/502 · 2,054,474 | 48/502 · 1,933,621 |
| Clipping / viewport | 183 | 174/183 · 517,228 | 174/183 · 517,228 | 174/183 · 517,228 | 174/183 · 517,228 | 167/183 · 533,596 | 174/183 · 517,228 |
| Vertex pipeline | 226 | 101/226 · 403,652 | 101/226 · 403,645 | 101/226 · 403,652 | 102/226 · 403,069 | 101/222 · 405,100 | 102/226 · 403,069 |
| 2D / blit ⚠️98% | 46 | 19/45 · 94,999 | 19/45 · 94,999 | 19/45 · 94,999 | 19/45 · 94,999 | 18/45 · 198,029 | 19/45 · 94,999 |

† that run did not record the one-step column, so its figure is *all* differing pixels and is not comparable with a structural count. The 2026-09-08 baseline predates it.


**hw commits behind tip** is how many commits touching `hw/` separate the binary that produced a column from the branch tip when it was collected. `apk_sha` says which binary; this says whether it is the current one. A column collected on 2026-09-12 sat 87 commits and 2,111 `hw/` insertions behind, with every correctness fix of that day missing, and its sha was perfectly consistent throughout -- consistency is not currency. A dash means the column predates this record.


⚠️ on a category means the leftmost run scored fewer captures than that category has goldens: the cell is a floor, not a score. ⚠️ on a run means its rows disagree about which binary produced them.


A ⚠️ FLOOR IS NOT ALWAYS A LIMITATION OF THE EMULATOR, AND BLEND'S IS NOT. Blend shows the worst coverage on this board because 1,568 of its 1,722 goldens come from `TestDetailed`, which upstream marked interactive-only when `#spot_` replaced it -- so the stock disc does not run them and the sweep cannot score them. That was recorded for a day as "behind the test-suite fork", and it was false: on 2026-09-13 a run on a one-byte-patched disc scored **1,673 of 1,673** with `partial: false`. The 1,568 captures had also been on disk since 2026-09-12.

So this row is liftable, not stuck. `docs/testing/request.sh --base-iso /home/justin/nxdk_pgraph_tests_xiso_interactive.iso` reaches them; that disc's `disc_id` tags as `iso:85b525/...` so its figures can never be silently compared with a stock column, which is also why those 1,673 captures are NOT folded into the columns above. Anyone reading this row as a permanent ceiling should read `docs/investigations/xbe-interactive-patch.md` first.

