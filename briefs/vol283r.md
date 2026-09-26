# #283 residual -- the +-1 low-byte error on Volume texture Y16 / R16B16 (desktop-side analysis)

Issue: #283. Base: origin/master tip when you start (last cited: 6550967a5e). Needs device: no. Needs NDK: no.
Files: docs/lanes/vol283r/** only (analysis + a named hunk; you edit no hw/ file).
psh.c is held by lane.fog278 (lent to lane.y16bump10); vk/texture.c is lane.remote's. Name hunks, do not edit them.
(First written for the cloud outlet as briefs/283.md; unclaimed, so a local lane takes it.)

## State -- settled, cite it, do not re-derive
PR #289 (fold 036e6c191f, arm PASS on 186 checks) took Y16 65,819 -> 2,605 px and R16B16
48,412 -> 1,638 px. docs/lanes/texvol283/NOTES.md has the byte-order mechanism and the arm table
("Do not repeat" section included). What is left: on Y16 R and G are exact on every pixel and all
2,605 differences are in B, the LOW byte: +1 on 2,070 px, -1 on 534, one 255 at (343,122) on the
quad edge. R16B16's B carries the same +-1/+-2 (1,110 px RGB) with four edge outliers up to 242.

## Goal
Say which of three readings the residual is, from the captures on disk (arm result dirs
1790367468-arms-texvol283-{base-1190693,fix-1190715}; golden = console set K where it covers Y16):
1. the float recovery `round(t*65535)` in the fix's byte split (UNORM16 fetch precision, ours),
2. silicon's own low-byte rounding or a filter tie (a rule, therefore ours to copy),
3. a precision floor (Adreno UNORM16 fetch) that no shader change removes.
Test (1) offline: model `round(t*65535) & 255` against the exact 16-bit texel the test uploads
(rebuild it as texsim.py did -- scratch, not committed) and count how many of the 2,604 +1 pixels
it explains. The +1/-1 split (2,070 / 534) is itself evidence: a rounding rule is one-signed.

## Falsifier
Reading (1) is refuted if the recovered low byte equals the uploaded byte on the mispredicted
pixels. Reading (2) is refuted if a candidate rule moves any pixel that is exact today, checked
against the 184 other captures in the six suites (Volume texture, Texture format, Bump map, Bump
env lum, Texture render target, Texture BRDF). Do not treat the geometry-free G-vs-(G,B) identity as
a count of pixels -- the geometry model is approximate.

## Done when
docs/lanes/vol283r/NOTES.md names the reading with the pixel counts behind it; if it is (1) or
(2), it carries the exact hunk (psh.c split, or the byte-typed R8G8B8A8/R8G8 view for vk/texture.c)
with its predicted must_move / must_not_move legs, ready to append to briefs/pshqueue.md; if it is
(3), it says so and the board records #283 as precision-floor. The PR is ready and says what it did
not chase.
