# SZ_R6G5B5 in Texture_format: the golden's data is R5G6B5-packed (#21)

`TexFmt_R6G5B5` differs from the golden in green ("two ramps where ours has
one") and, less visibly, in red. The decode is not the cause. The golden was
captured with texture data packed differently from what today's test packs.

## Method

`Texture_format` draws one quad of a synthetic gradient:
`R = ⌊ty·255/256⌋, G = ⌊tx·255/256⌋, B = 255 − R` (256×256 texels). The
screen→texel mapping was fitted from the `R5G6B5` golden's staircases
(`x_normal = 0.69217·x − 94.148`, `y_normal = 0.69218·y − 38.781`, residual
0.33), which gives the exact source RGB of every screen pixel and therefore
the exact 16-bit word under any packing. Pixels whose 5×5 neighbourhood maps
to one word are compared to the golden (27.5 k pixels, 2048 distinct words).
The `R5G6B5` golden reproduces under its own packing to a worst error of 0.7,
so the method is sound.

## Result

| data packing | decode | golden pixels within ±1 |
|---|---|---|
| today's `texture_stage.cpp` (`R[7:2]→[15:10], G[7:3]→[9:5], B[7:3]→[4:0]`) | R6[15:10] G5[9:5] B5[4:0] unsigned | 384 / 27 483 (1.4 %) |
| **RGB565** (`R[7:3]→[15:11], G[7:2]→[10:5], B[7:3]→[4:0]`) | same decode | **27 522 / 27 570 (99.8 %)** |

Seen through the current packing, the golden looks like "red's LSB is bit 9,
bit 10 is ignored, green is a 4-bit ramp" — which is exactly `R6[15:10]`
reading `R[7:3],G[7]`, and `G5[9:5]` reading `G[6:2]`, of a 565 word.

Our own output is the current packing through the same decode
(27 459 / 27 485 within ±1). So:

- the emulator's decode — unsigned `R6[15:10] G5[9:5] B5[4:0]`, bit-replicated
  expansion — is what the hardware does;
- the golden and our ISO contain different texture bytes for this test.
  `TexFmt_R6G5B5` (and `BumpMap_R6G5B5`, which feeds its surface through the
  same `SetTexture` conversion) cannot be scored against these goldens until
  either side is regenerated with the other's packing.

The local pbkitplusplus clone is shallow (one commit), so the revision that
changed the packer is not pinned here; the golden repository's last update is
2026-08-11 (results for nxdk_pgraph_tests#307).

The two earlier "decode fits" for this test ([8:5] and [8:4]) were fitting the
565 layout by accident, which is why they broke `BumpMap_R6G5B5`.
