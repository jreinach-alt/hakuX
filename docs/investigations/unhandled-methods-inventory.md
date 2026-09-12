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
are sent during this suite's setup with small parameters (1, 4, 0). What they
are is not established here and is not worth guessing: the point is that the
inventory exists and can be looked up deliberately.

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
