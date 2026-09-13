# Accuracy scoreboard

Each cell is **exact/captures · structural px** — structural being differing pixels that are not one step out, which is the part that is a rule rather than a rounding floor.

| run | binaries | built | hw commits behind tip | discs | captures | rescored |
|---|---|---|---:|---:|---:|---:|
| `pre-fixes-fb4dfafc` | fb4dfafc6d38 | 2026-09-12 | 22 ⚠️ | 60 | 1748 | — |

| category | goldens | `pre-fixes-fb4dfafc` |
|---|---:|---|
| Texture formats ⚠️15% | 119 | 10/18 · 1,936 |
| Render to texture ⚠️16% | 67 | 8/11 · 399,197 |
| Lighting | 195 | 27/195 · 476,228 |
| Bump mapping | 82 | 0/82 · 818,008 |
| Fog | 280 | 23/280 · 1,574,992 |
| Blend ⚠️9% | 1722 | 5/154 · 5,907,527 |
| Depth / stencil ⚠️18% | 1688 | 80/298 · 504,164 |
| Rasterisation ⚠️96% | 514 | 43/496 · 2,009,138 |
| Clipping / viewport ⚠️17% | 183 | 25/32 · 532,200 |
| Vertex pipeline ⚠️61% | 226 | 19/137 · 371,258 |
| 2D / blit ⚠️98% | 46 | 18/45 · 198,029 |

† that run did not record the one-step column, so its figure is *all* differing pixels and is not comparable with a structural count. The 2026-09-08 baseline predates it.


**hw commits behind tip** is how many commits touching `hw/` separate the binary that produced a column from the branch tip when it was collected. `apk_sha` says which binary; this says whether it is the current one. A column collected on 2026-09-12 sat 87 commits and 2,111 `hw/` insertions behind, with every correctness fix of that day missing, and its sha was perfectly consistent throughout -- consistency is not currency. A dash means the column predates this record.


⚠️ on a category means the leftmost run scored fewer captures than that category has goldens: the cell is a floor, not a score. ⚠️ on a run means its rows disagree about which binary produced them.

