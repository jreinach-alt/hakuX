# #74 has no oracle on the scorable corpus, because the code never executes

#74 is `floatx80_to_int32`/`int64` defined as plain C casts in the
`#if defined(XBOX) && defined(__aarch64__)` block of
`target/i386/tcg/fpu_helper.c`, discarding the `float_status` that carries the
guest's rounding-control field where `FIST`/`FISTP` round per the control
word. Verified from primary source, lines 248-251:

```c
#define floatx80_to_int32(a, s)               ((void)(s), (int32_t)(a))
#define floatx80_to_int64(a, s)               ((void)(s), (int64_t)(a))
#define floatx80_to_int32_round_to_zero(a, s) ((void)(s), (int32_t)(a))
#define floatx80_to_int64_round_to_zero(a, s) ((void)(s), (int64_t)(a))
```

All four truncate. For the second pair that is **correct** — it is `FISTTP`.
Only the first pair is the defect.

The routing note asked for an oracle before a fix: *find a golden that moves,
or establish that none does; the second is a result, not a failure.* It is
the second, and the reason is stronger than "no golden happens to move".

## The four guest-visible sites are never reached

`floatx80_to_int32/int64` has six call sites. Four are guest-visible
instructions — `helper_fist_ST0` (FIST m16), `helper_fistl_ST0` (FIST m32),
`helper_fistll_ST0` (FISTP m64) and `helper_fbst_ST0` (FBSTP). The other two
(lines 1785 and 2160) are internal integer extractions inside transcendental
helpers, where the guest RC is not the governing rule.

Instrumented all four, plus `helper_fistt_ST0` (FISTTP) and — as the control
— `helper_frndint`, counting calls by rounding mode. Five discs:

| disc | captures | FRNDINT (control) | FIST m16 / m32 / FISTP m64 / FBSTP / FISTTP |
|---|---:|---|---|
| `iso_surf1` | 236 | 245 down, 8 up | **0 / 0 / 0 / 0 / 0** |
| `iso_clip` | 120 | 98 down | **0 / 0 / 0 / 0 / 0** |
| `iso_cube` | 78 | 2 down | **0 / 0 / 0 / 0 / 0** |
| `iso_dbff` | 80 | 4 down | **0 / 0 / 0 / 0 / 0** |
| `iso_blendall` | 105 | 422 down | **0 / 0 / 0 / 0 / 0** |

**619 captures. 771 FRNDINT calls under a non-default rounding mode. Zero
calls to any x87 float-to-integer store.**

## The control is the point

A probe that prints nothing is indistinguishable from a probe that was never
compiled in, which is why the run carries `helper_frndint` alongside. It
fires 771 times, and it fires with **RC=down 769 times and RC=up 8 times** —
which is #67's mechanism, nxdk's `floorf` and `ceilf` and their
save-CW / set-RC / FRNDINT / restore sequence, observed live. The instrument
works, the `atexit` dump works, and stderr reaches the log. The zeros are
measurements, not silence.

`iso_blendall` is worth singling out: it is the `Blend tests` suite, the disc
where #67's fix moved 1,711,362 px to zero. It makes **422** FRNDINT calls
and **no** FIST call at all. The two defects live in adjacent macros and only
one of them is reachable.

## Why, mechanically

The Xbox CPU is a Pentium III and nxdk targets it with SSE. A C cast
`(int)f` **must** truncate, so the compiler emits `cvttss2si` — an SSE
instruction that never touches the x87 stack. `FIST` appears only when a
value is already on the x87 stack and is stored as an integer, which a
compiler with SSE available has no reason to do.

`FRNDINT` is reachable for the opposite reason, and it is not an accident:
nxdk's `floorf` deliberately saves the control word, sets RC, executes
`FRNDINT` and restores. That is a hand-written sequence in a header every
test links. **No equivalent hand-written sequence ending in `FIST` has been
found**, in the tests, in `pbkitplusplus`, or as a library call — there is no
`lrint`, `lrintf`, `lround`, `llrint` or `nearbyint` call anywhere in either
tree, checked with word boundaries after a first pass matched `snprintf` on
the substring `rintf`.

## What this does and does not establish

**Establishes**: no capture on any of these five discs can move under a fix to
#74, because the macros are never evaluated on a guest-visible path. A fix
would be unmeasurable here in either direction, and an arm demanding a pixel
change would fail on a correct change.

**Does not establish**: that no title reaches it. A game is not a test disc,
and `FBSTP` in particular is the kind of instruction a hand-written or
old-toolchain routine reaches. The honest scope is *the scorable corpus*, not
*the emulator*.

**Does not establish** anything about the two internal sites, 1785 and 2160.
They are inside transcendental helpers and were not separated here.

## So what #74 should be

Not a fix waiting on an arm. Either

* a **correctness-only change**, landed on the reading of the x86 manual
  rather than on pixels, reported as such and with an explicit statement that
  no golden judges it — the shape #61 was closed in; or
* left open with this measurement attached, so the next lane does not spend a
  device run looking for a capture that cannot exist.

Choosing between those is an orchestration call. What this lane can say is
that the search for an oracle is finished and it came back empty, with a
control proving the instrument.

Instrumentation removed; the tree carries none of it.
