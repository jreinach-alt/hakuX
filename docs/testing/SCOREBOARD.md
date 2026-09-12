# Accuracy scoreboard

Each cell is **exact/captures · structural px** — structural being differing pixels that are not one step out, which is the part that is a rule rather than a rounding floor.

| run | binaries | discs | captures | rescored |
|---|---|---|---:|---:|
| `today-partial` | fb4dfafc6d38 | 50 | 1448 | — |

| category | goldens | `today-partial` |
|---|---:|---|
| Texture formats ⚠️15% | 119 | 10/18 · 1,936 |
| Render to texture ⚠️16% | 67 | 8/11 · 399,197 |
| Lighting ⚠️80% | 195 | 27/156 · 195,442 |
| Bump mapping | 82 | 0/82 · 818,008 |
| Fog | 280 | 23/280 · 1,574,992 |
| Blend ⚠️9% | 1722 | 5/154 · 5,907,527 |
| Depth / stencil ⚠️16% | 1688 | 50/266 · 454,164 |
| Rasterisation ⚠️53% | 514 | 16/274 · 1,392,840 |
| Clipping / viewport ⚠️17% | 183 | 25/32 · 532,200 |
| Vertex pipeline ⚠️58% | 226 | 12/130 · 371,258 |
| 2D / blit ⚠️98% | 46 | 18/45 · 198,029 |

† that run did not record the one-step column, so its figure is *all* differing pixels and is not comparable with a structural count. The 2026-09-08 baseline predates it.


⚠️ on a category means the leftmost run scored fewer captures than that category has goldens: the cell is a floor, not a score. ⚠️ on a run means its rows disagree about which binary produced them.

