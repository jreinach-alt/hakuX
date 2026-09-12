# Asking the emulator what it drops on the floor

Added 2026-09-12. `docs/investigations/issue-19-isolation-2026-09-12.md` put ten
features on the board by showing which tests render another test's image. This
answers the complementary question directly, in register numbers, without
inferring anything from pixels.

## Why it was invisible

`pgraph_method`'s fallthrough calls `trace_nv2a_pgraph_method_unhandled`. That
goes through QEMU's trace framework, which **does not reach logcat on Android**
— so a method we do not implement is dropped in complete silence. For an
accuracy question that is the worst available failure mode, because "we ignore
it" and "the guest never sends it" are indistinguishable from outside.

The fallthrough now also logs to `hakuX-unhandled`, one line per distinct
(class, method) pair so a suite hammering an unimplemented method logs once
instead of thousands of times.

## First run: `Image blit`, 41 captures

```
class 0x0019 method 0x0000 param 0x00014d40   (sub 5)
class 0x0019 method 0x0300 param 0x00000000   (sub 5)
class 0x0019 method 0x0304 param 0x01000100   (sub 5)
class 0x0039 method 0x0000 param 0x00014cf0   (sub 2)
class 0x0039 method 0x0180 param 0x00011190   (sub 2)
class 0x0072 method 0x0000 param 0x00014d60   (sub 7)
class 0x009f method 0x0184..0x0198 (six)      (sub 3)
class 0x0097 methods 0x09f8 0x16bc 0x1710 0x1d80 0x1d84  (sub 0)
```

**The clip rectangle is confirmed, with its values.** Class **0x19** is the NV
clip-rectangle object; `0x300` is its point and `0x304` its size. The guest
binds the object, sets the point to **(0, 0)** and the size to **0x01000100 —
256 × 256** — and we discard all three methods. That is exactly what #19's
isolation pass pointed at from the other direction: all six `ImgBlt_Clip_*`
tests render the *unclipped* blit, 6 for 6. Two independent methods, same
answer, and this one names the registers.

No clip-rectangle class is defined in `nv2a_regs.h` at all, so this is not a
handler with a gap — the object is simply absent.

**Five 3D methods are undefined too.** `NV097` `0x09f8`, `0x16bc`, `0x1710`,
`0x1d80`, `0x1d84` do not appear in our register header under any name. They
are sent during this suite's setup with small parameters (1, 4, 0).

### All five are now named

Two came from the test repository's own headers. The last three needed nxdk,
whose submodule was uninitialised, so its headers were not on disk at all:
`git submodule update --init --depth 1 third_party/nxdk` in
`nxdk_pgraph_tests`, checked out at `73c95900`.

| method | name | source | label |
|---|---|---|---|
| `0x09f8` | `NV097_SET_SWATH_WIDTH` | `swath_width_tests.h:10` | DOCUMENTED |
| `0x16bc` | `glEdgeFlag` | `edge_flag_tests.h:10` | DOCUMENTED |
| `0x1710` | **`NV097_BREAK_VERTEX_BUFFER_CACHE`** | nxdk `lib/pbkit/nv_regs.h:477` | DOCUMENTED |
| `0x1d80` | **`NV097_SET_COMPRESS_ZBUFFER_EN`** | nxdk `lib/pbkit/nv_regs.h:628` | DOCUMENTED |
| `0x1d84` | **`NV20_TCL_PRIMITIVE_3D_CULL_ENABLE`** | nxdk `lib/pbkit/nv_objects.h:1214` | DOCUMENTED, naming caveat |

`0x1710` sits in the vertex-data-array block, between `SET_TEXCOORD3_4S` and
`SET_VERTEX_DATA_ARRAY_OFFSET`. `0x1d80` sits between `SET_ZMIN_MAX_CONTROL`
and `SET_ZSTENCIL_CLEAR_VALUE`. Both are ordinary `NV097` names in nxdk's
register header; neither is in ours.

`0x1d84` carries a caveat. nxdk names it only in the `NV20_TCL` namespace, as
`CULL_ENABLE` with `bit0:OcclusionCullEnable bit1:StencilCullEnable`, and there
is **no `NV097` name for it in `nv_regs.h` at all**. nxdk is also internally
inconsistent: `nv_objects.h:1001` lists `0x00001d84` in a block of *unnamed*
offsets while line 1214 names it. So the identification is good enough to stop
guessing and not good enough to put in a header without a second source.

### The adjacency guess is moot, and it was pointing at the wrong neighbour

`0x1d80` had been noted as sitting one slot above `0x1D7C`, on the reasoning
that adjacency hints at a related function. It now has a real identification,
so the guess is retired — but for the record the neighbour was misnamed. Our
header calls `0x1D7C` `NV097_SET_ANTI_ALIASING_CONTROL` (`nv2a_regs.h:1305`)
and nxdk calls it `NV20_TCL_PRIMITIVE_3D_MULTISAMPLE`, with
`bit0:MultiSampleAntiAliasing`. Those agree with each other; neither is a
smoothing control.

### `SET_COMPRESS_ZBUFFER_EN` is the one with immediate consequences

**Three suites push it and we handle it nowhere** — `depth_format_fixed_function_tests.cpp:263`,
`wbuf_tests.cpp:448`, `depth_clamp_tests.cpp:81`. `grep COMPRESS_ZBUFFER
hw/xbox/nv2a/` returns nothing.

Two of those three set it **false**, which is effectively what we do by
ignoring it, so they cost nothing. The third varies it, and #52 measured what
that variation is worth: the `Cn`/`Cy` depth dumps are bit-identical **on
silicon as well as here**, 196 pairs of 196, and the colour frames differ only
in the 36 pixels of the label glyph that spells `n` instead of `y`.

So dropping this method is provably free on the one suite that exercises it,
which is a pleasing closure rather than a new defect: we discard a register,
and the goldens show the register does nothing to the depth buffer. It is
still a real method we silently discard, and if any other consumer turns up
that enables it, that suite is where the cost would appear.

**Class 0x39 is `NV_MEMORY_TO_MEMORY_FORMAT`**, which the header defines but
`pgraph_method` has no case for — so its object binding and `0x180` are
dropped. Class **0x72** is not in the header. And six consecutive `NV_IMAGE_BLIT`
methods, `0x184` through `0x198`, are dropped, all carrying the same parameter
`0x14d30`, which is the shape of a run of context-object bindings.

## Why this is worth keeping

One log line per pair, one run per suite, and the output is a list of things
the guest asked for and did not get — with no sampling, no statistics and
nothing to misread. Tonight three of my own mechanisms died to better
measurements; this is the opposite kind of evidence, and it should be run over
every suite in the corpus before anyone infers another mechanism from pixel
differences.

The obvious next step is exactly that: one pass per suite, collecting the
union. `Image blit` alone named fifteen dropped methods.

## Second run: `Blend tests`, and a clean negative

Ran the 2025 oracle disc with the log armed — roughly 450 of its 1,568 tests
before the timeout, across every unsigned and signed equation.

**Nothing new appeared.** The log holds exactly the startup set from the
`Image blit` run — class 0x39's two methods and the five undefined `NV097`
methods — and not one additional pair in ~450 blend tests.

So **every method the blend tests use is one we handle**, and the fifth-quad
defect is *not* a dropped method. That eliminates the whole class of
"unimplemented register" explanations for it and narrows the search to our
handling of methods we do accept: state tracking, draw batching, or the
surface and blend pipeline. Given that three mechanisms for this region have
already died, a negative that removes an entire class is worth more than
another candidate.

## A constraint on the 2025 disc worth knowing

`skip_tests_by_default` with per-test `{"skipped": false}` entries **does not
work on the 2025 XBE** — the config is newer than the binary. Naming four tests
ran all 1,568. Suite-level selection (`--suite "Blend tests"`) is honoured;
per-test selection is not. So on that disc the unit of work is a whole suite,
which also means `make_isolation_discs.py`'s single-test discs cannot target
it.
