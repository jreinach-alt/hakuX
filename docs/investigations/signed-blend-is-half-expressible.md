# #43: the factor half is a blend-state change, the sign half cannot be one

Scope: issue #43's implementation, not its derivation. The rule itself is
settled elsewhere and is not re-litigated here --
[`signed-blend-equations.md`](signed-blend-equations.md) derives it and
[`blend-signed-full-oracle.md`](blend-signed-full-oracle.md) confirms it on
176,160,768 of 176,160,768 channels across 448 captures:

    signed(S) = S - 256 if S >= 128 else S

    FUNC_ADD_SIGNED               = clamp(signed(S) + D, 0, 255)
    FUNC_REVERSE_SUBTRACT_SIGNED  = clamp(D - signed(S), 0, 255)

with both blend factors ignored and the destination left unsigned.

Those two documents both say Vulkan "cannot express" the rule as a blend op and
leave it there. This one says why, exactly, and shows that the statement splits
the rule into a half that *is* a blend-state change and a half that is not.

## PROVED: no arrangement of blend state can produce the sign fold

Fix a destination `D` and read silicon's output as a function of the source
byte `S`. At `S = 127` it is `clamp(127 + D)`; at `S = 128` it is
`clamp(D - 128)`. For any mid-range `D` those are far apart -- at `D = 127`,
254 against 0 -- and they are adjacent source values. The function is
**discontinuous at the sign bit.**

Everything fixed-function blending offers is a *continuous* map of the source
colour. The fifteen factors are each either a constant, or a linear function of
the source, the destination or the blend constant; `ADD`, `SUBTRACT` and
`REVERSE_SUBTRACT` are sums of those products; `MIN` and `MAX` are continuous;
and the saturate is continuous. A composition of continuous maps is continuous,
so this holds however many passes are chained, whatever the blend state, and
whatever the write mask -- as long as each pass is handed the same fragment
output. The sign test therefore cannot live in blend state at all. It is not a
missing `pgraph_blend_equation_vk_map` entry and no cleverer entry exists.

(Slopes are bounded too, so the quantised version of the argument holds: the
factors give slope at most 2 per pass, and reaching a 128/255 step across one
1/255 source step by repeated sharpening would need seven passes *and* somewhere
to keep `D` while doing it, which a single colour attachment does not have.)

## VERIFIED: the factor half is expressible, and is exact on half the source range

"Both factors are ignored" is a statement about the factor fields, so forcing
`ONE`/`ONE` says all of it. That makes us compute `clamp(S + D)` and
`clamp(D - S)`, which equals the rule exactly for every channel whose source
byte is below 128, and is wrong above it.

Measured, not argued, on `Texture signed component tests` --
[`signed_blend_source_halves.py`](../testing/signed_blend_source_halves.py),
goldens only, no device:

| | channels | wrong today | wrong after ONE/ONE |
|---|---:|---:|---:|
| `txt_A8R8G8B8_SADD`, source < 128 | 856,098 | 594,738 | **0** |
| `txt_A8R8G8B8_SADD`, source >= 128 | 365,491 | 365,491 | 365,491 |
| `txt_A8R8G8B8_SREVSUB`, source < 128 | 856,098 | 592,409 | **0** |
| `txt_A8R8G8B8_SREVSUB`, source >= 128 | 365,491 | 341,803 | 365,491 |

The suite's own plain-`ADD` case is the control and it is **bit-exact against
silicon, 0 differing channels over 640x480** -- so in these captures the
layout, the texture decode, the checkerboard phase and the unsigned blend
arithmetic are all already right, and the signed equation is the only defect
left. That is what makes the split above trustworthy: the two halves are the
same capture, so a whole-capture pixel count mixes them, but nothing *else*
is mixed in.

Note the last row. Under `SREVSUB`, 23,688 channels in the upper half are
accidentally right today -- `D - S*As/255` happens to land on
`clamp(D - signed(S))` for them -- and `ONE`/`ONE` loses them. It is a real
regression inside a change that is net strongly positive, and it is the shape
to expect from a half fix: the half it cannot reach gets no better and can get
slightly worse.

On the retired `BlendTests::TestDetailed` oracle the same change scores
stack A (`DrawColorStack`, the region that is bit-exact under all five unsigned
equations) at 18,350,080 of 29,360,128 channels against 14,426,608 today, on
448 captures. Exactly half of the blended colour channels, because that scene
draws only three distinct source bytes -- 0, 221 and 255 -- so only the zero
falls in the reachable half. The oracle is a poor discriminator here for that
reason, and `Texture signed component`'s full 0..255 gradient is the one to
score against.

### One rival rejected, because it fits better and is not a mechanism

Forcing `ONE`/`ONE` *and swapping the operation* -- `REVERSE_SUBTRACT` for
`FUNC_ADD_SIGNED` -- scores stack A at 21,102,592 channels, better than the
honest change. It is overfitting and was discarded: it amounts to assuming
every source is negative, and it wins only because three of that scene's four
swatch colours have components at or above 128. On `Texture signed component`'s
uniform gradient it would be wrong on the half the honest change gets exactly
right.

## Where the sign half has to go, and what it costs

Unchanged from `signed-blend-equations.md`, restated with the impossibility
above in hand. All three need a file outside the blend state:

- **A float intermediate colour target.** A fixed-point attachment clamps the
  source to [0,1] *before* blending, which is what destroys the negative half;
  a float one does not, so the shader can emit `signed(S)/255` and an ordinary
  `ONE`/`ONE` `ADD` is correct. Changes the format, bandwidth and download path
  of any surface a game blends this way.
- **Shader-side blending** behind framebuffer fetch -- an input attachment with
  a subpass self-dependency, or `VK_EXT_rasterization_order_attachment_access`.
  Exact, generalises, structural, and the extension is not universal.
- **One pass per (channel, sign)**, `colorWriteMask` set to the one channel and
  a `discard` on the other sign. Needs no extension; costs six passes for RGB,
  eight with alpha.

The measurement that should come before choosing is still unmade: a count of
how often titles actually program `FUNC_*_SIGNED`. It is cheaper than any of
the three.

## What is inferred here, and what is measured

Measured: the fit table above, the stack A scores, the `ADD` control's
bit-exactness, the recovered destination set `{127, 255}`, and the 23,688-channel
upper-half regression. Inferred: nothing about silicon -- the rule is taken as
given from the two prior documents. The impossibility is a proof about Vulkan's
blend model, not a measurement, and it is falsifiable in one line: exhibit a
blend state, or a sequence of them over one fragment output, whose result is
discontinuous in the source colour.
