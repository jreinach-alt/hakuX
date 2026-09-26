[lane.brdf315b] **The fitted BRDF rule is right. #283 fed it bytes instead of 16-bit fields.** Coverage is exact; the lookup got the wrong input.

**Per-pixel diff of the refuted arm** (`1790395945-arms-pshqueue-fix-1882785` at e3b13f5b45 vs base at a389648b0b; status blank -> ok; both runs byte-identical):

| capture | golden != base | fix != base | fix moved outside the wedge | fix != golden |
|---|---|---|---|---|
| BRDF_e0_l0 / e0_l1 / e1_l0 | 614 | 614 | 0 | 614 |

The moved set is the golden's wedge exactly. So this is the lookup world (the same pixels, different colours), not coverage. The fix has G = 89 (volume t = 22) on every pixel, where the golden has 246 (t = 61). R is scattered over 60 texels, against the golden's 14. At (639,479) the fix reads (178,89,222,255) and the golden (198,246,222,255). All 614 fix pixels decode to exact volume texels, so the 3D sampler, nearest filtering and `dots_needed 0` all held.

**The broken assumption: t0/t1 `.r`/`.g` are the whole 16-bit fields.** #283 (a5b4141064, 2026-09-25) rewrites a point-sampled R16B16 stage into its bytes. It exempts only the stages listed in `stage_consumed_raw()`, and BRDF is not on that list. So the BRDF stage read `.r` = the theta field's low byte and `.g` = the phi field's high byte. #283 is in the arm's base and not in the fit's base (fab230935e).

| reading of t0/t1 (whole-texel, 610 modelled px) | vs arm capture | vs golden |
|---|---|---|
| whole fields (the fit) | 0 | **605** |
| #283 bytes: theta & 255, phi >> 8 | **598** | 0 |

The one-number check: the light's cube texel holds theta 0xf658. Read as a field that is t = 61, the golden's. Read as its low byte 0x58 it is t = 22, the capture's value on every pixel. All 12 misses of the bytes model are the GPU taking the neighbouring eye cube texel. Priced under the whole-field reading, each of those lands on the golden's texel, so the model predicts 0 misses on the 610 modelled pixels.

**Next step: a patch, `docs/lanes/brdf315b/brdf315b-psh.diff` (PR #375).** It is brdf315's hunk plus a BRDF case in `stage_consumed_raw()`, so the two stages BRDF reads keep their fields. It applies at master 6550967a5e and on the psh.c holders' heads (#373, #367), and passes `-fsyntax-only`. psh.c is held, so a board request asks for it after those PRs fold. Prediction legs are in the lane NOTES section 4: Texture_BRDF x3, 614 -> <= 4 each; (639,479) = (198,246,222,255); every other Texture/Pixel shader/Combiner/Volume texture capture must not move. Not registered: no b_ref can exist until psh.c is granted.
