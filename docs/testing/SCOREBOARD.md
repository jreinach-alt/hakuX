# Accuracy scoreboard

Each cell is **exact/captures · structural px** — structural being differing pixels that are not one step out, which is the part that is a rule rather than a rounding floor.

| run | binaries | discs | captures | rescored |
|---|---|---|---:|---:|
| `baseline` | unknown | 1 | 1871 | — |
| `today` | unknown | 1 | 2372 | 87 |

| category | goldens | `baseline` | `today` |
|---|---:|---|---|
| Texture addressing ⚠️49% | 198 | 3/97 · 5,369,877 diff† | 6/80 · 445,305 |
| Texture formats ⚠️31% | 119 | 0/37 · 2,996,406 diff† | 17/34 · 786,136 |
| Render to texture ⚠️72% | 67 | 4/48 · 920,256 diff† | 3/51 · 3,399,792 |
| Shadow / projective ⚠️21% | 288 | 0/60 · 2,063,120 diff† | 176/288 · 17,388 |
| Lighting ⚠️66% | 195 | 0/129 · 7,174,271 diff† | 1/137 · 493,516 |
| Bump mapping ⚠️35% | 82 | 0/29 · 2,773,965 diff† | 0/40 · 435,201 |
| Fog ⚠️59% | 280 | 0/166 · 11,669,501 diff† | 23/210 · 1,366,604 |
| Blend ⚠️7% | 1722 | 0/123 · 7,648,445 diff† | 4/32 · 1,747,626 |
| Depth / stencil ⚠️39% | 1688 | 91/654 · 29,719,086 diff† | 188/840 · 5,831,583 |
| Rasterisation ⚠️66% | 514 | 3/337 · 37,794,055 diff† | 21/419 · 1,711,816 |
| Clipping / viewport ⚠️22% | 183 | 0/40 · 1,642,760 diff† | 102/104 · 1,396 |
| Vertex pipeline ⚠️58% | 226 | 13/131 · 4,705,862 diff† | 0/96 · 245,242 |
| 2D / blit ⚠️43% | 46 | 1/20 · 3,356,097 diff† | 9/41 · 373,755 |

† that run did not record the one-step column, so its figure is *all* differing pixels and is not comparable with a structural count. The 2026-09-08 baseline predates it.


⚠️ on a category means the leftmost run scored fewer captures than that category has goldens: the cell is a floor, not a score. ⚠️ on a run means its rows disagree about which binary produced them.

