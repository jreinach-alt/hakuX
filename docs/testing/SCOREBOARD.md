# Accuracy scoreboard

Each cell is **exact/captures · structural px** — structural being differing pixels that are not one step out, which is the part that is a rule rather than a rounding floor.

| run | binaries | built | hw commits behind tip | discs | captures | rescored |
|---|---|---|---:|---:|---:|---:|
| `0026f00534` | 88452c539d64 | 2026-09-13 | 31 ⚠️ | 100 | 3379 | — |
| `after` | 553cfffc73d3 | 2026-09-12 | 28 ⚠️ | 100 | 3379 | — |
| `pre-fixes-fb4dfafc` | fb4dfafc6d38 | 2026-09-12 | 57 ⚠️ | 99 | 3375 | — |

| category | goldens | `0026f00534` | `after` | `pre-fixes-fb4dfafc` |
|---|---:|---|---|---|
| Texture addressing ⚠️99% | 198 | 65/197 · 811,873 | 65/197 · 811,873 | 65/197 · 789,528 |
| Texture formats | 119 | 69/119 · 584,148 | 69/119 · 584,148 | 61/119 · 1,182,369 |
| Render to texture ⚠️99% | 67 | 23/66 · 613,452 | 23/66 · 613,452 | 16/66 · 638,222 |
| Shadow / projective | 288 | 256/288 · 11,732 | 256/288 · 11,732 | 176/288 · 17,388 |
| Lighting | 195 | 27/195 · 358,686 | 27/195 · 358,686 | 27/195 · 476,228 |
| Bump mapping | 82 | 0/82 · 747,933 | 0/82 · 814,408 | 0/82 · 818,008 |
| Fog | 280 | 37/280 · 154,377 | 31/280 · 1,240,473 | 23/280 · 1,574,992 |
| Blend ⚠️9% | 1722 | 13/154 · 5,141,245 | 13/154 · 5,141,245 | 5/154 · 5,907,527 |
| Depth / stencil ⚠️62% | 1688 | 257/1042 · 6,007,774 | 260/1042 · 5,907,122 | 246/1042 · 6,006,689 |
| Rasterisation ⚠️98% | 514 | 44/502 · 2,036,188 | 44/502 · 2,036,188 | 43/502 · 2,054,474 |
| Clipping / viewport | 183 | 174/183 · 517,228 | 174/183 · 517,228 | 167/183 · 533,596 |
| Vertex pipeline | 226 | 101/226 · 403,652 | 101/226 · 403,652 | 101/222 · 405,100 |
| 2D / blit ⚠️98% | 46 | 19/45 · 94,999 | 19/45 · 94,999 | 18/45 · 198,029 |

† that run did not record the one-step column, so its figure is *all* differing pixels and is not comparable with a structural count. The 2026-09-08 baseline predates it.


**hw commits behind tip** is how many commits touching `hw/` separate the binary that produced a column from the branch tip when it was collected. `apk_sha` says which binary; this says whether it is the current one. A column collected on 2026-09-12 sat 87 commits and 2,111 `hw/` insertions behind, with every correctness fix of that day missing, and its sha was perfectly consistent throughout -- consistency is not currency. A dash means the column predates this record.


⚠️ on a category means the leftmost run scored fewer captures than that category has goldens: the cell is a floor, not a score. ⚠️ on a run means its rows disagree about which binary produced them.

