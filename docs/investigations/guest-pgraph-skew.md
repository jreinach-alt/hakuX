# The guest↔pgraph skew

Opened 2026-09-13 on `ea19eeb827`, out of #44. Instrument at `90c5b88033`,
bound at `008298446d`. Reader in `docs/testing/fifo_skew_report.py`.

#44 is resolved to a mechanism, texel-exact, and its own conclusion is that
the fix is not in the texture path:

> The texture upload for draw N reads guest memory **after** the guest has
> begun writing iteration N+1's surface to the same address. The draw renders
> with its **successor's** texture.

12,596 of 12,596 wrong pixels explained across a ten-run noise floor, a
row-major prefix of the successor's write on 9 of 9 measurable frontiers, and
ten wrong pixels that are a byte-level mixture inside **one texel** — which no
stale-allocation or missed-re-upload story reaches, and only a read while a
write is in flight does. Real silicon races identically and wins on speed.

This document is the other half: **what bounds that window today, what should
bound it, and what bounding it costs.** None of #44's evidence is re-derived
here.

## VERIFIED FROM SOURCE: nothing in this device bounds it

The submission path, end to end, with the thread each step runs on:

| step | where | thread |
|---|---|---|
| guest writes the texture into VRAM | plain stores, no device involvement | guest CPU |
| guest writes pushbuffer words | plain stores into a guest DMA object | guest CPU |
| guest publishes by storing DMA_PUT | `user.c:97`, then `pfifo_kick()`, **returns immediately** | guest CPU |
| pusher walks DMA_GET → DMA_PUT | `pfifo_run_pusher`, `pfifo.c` | PFIFO |
| puller runs the method | `pfifo_run_puller` → `pgraph_method` | PFIFO |
| **the draw reads guest memory** | `get_texture_layout`, `vk/texture.c:253`, `(char *)d->vram_ptr + texture_vram_offset` | PFIFO |

The last row is the race, and the thing that makes it a *pacing* question
rather than a synchronisation one is that **it is synchronous**. When the
PFIFO thread returns from `NV097_SET_BEGIN_END(END)`, guest VRAM has already
been copied into the host staging buffer and `vkCmdCopyBufferToImage` recorded
(`vk/texture.c:742`, `:788`). There is no queue in between: the reorder window
(`g_xemu_draw_reorder`) and the draw-merge queue (`g_xemu_draw_merge`) are
both **off by default on Android** (`xemu_android.cpp:949`, `:954`),
`RCMD_DRAW` is defined and never produced, and the merge queue is drained on
the same thread anyway. The s3tc fan-out spawns workers and joins before
returning.

So the read happens at a definite moment, on a definite thread, and the guest
is running freely in between.

**Vertex data is the same shape, which is why the class is shared with #39.**
`pgraph_vk_bind_vertex_attributes` resolves the guest address and
`sync_vertex_ram_buffer` copies it with `memcpy(vram->mapped + offset, data,
size)` (`vk/vertex.c:60`), on the PFIFO thread, synchronously with the method.
Index data is *not* in this class: indices arrive as pushbuffer method
parameters (`ARRAY_ELEMENT16/32`) or are synthesised, never re-read from guest
RAM.

### The only backpressure is the guest's own ring

`user_write` stores DMA_PUT, calls `pfifo_kick()` and returns. Nothing waits.
The guest's next instruction runs, and the next thing that instruction stream
does is generate iteration N+1's surface into the same address.

The one thing that can stop it is the guest's own pushbuffer ring filling, at
which point nxdk spins on DMA_GET until the pusher makes room. That is a bound
in **ring bytes**, not in draws, and it is set by the guest: `nv_dma_load`
reads the DMA object's word 1 as the limit (`nv2a.c:75`) and `nv_dma_map`
returns it verbatim as `dma_len` (`nv2a.c:96`), with the size assertion
commented out.

**Nothing in this tree or in any captured run has ever printed that limit.** A
search of `docs/investigations/**`, the repo-root logs and every
`dispatch/results/*/logcat.txt` finds zero occurrences of `dma_put`,
`dma_get`, `dma_len` or `pushbuffer`. The only instrumented pusher figure is
words consumed (`pfifo.c:616`), behind `NV2A_PERF_LOG`, in a line no shipping
soak emits.

So "the bound today is the ring" was, until this pass, a claim with no number
attached to either side of it. The `fifoskew` line exists to change that.

## The instrument

A `fifoskew` line joins `vbl`/`vblphase` under `hakuX-perf`, every two
seconds, emitted from the PFIFO thread. Two fields are the measurement and the
rest are its context:

| field | what it is |
|---|---|
| `drain(n= mean= p50= p90= p99= max=)` | publish-to-consumed, **per submission**, as a 50 µs histogram. **This is the skew**, in nanoseconds: the width of the window in which a guest store can beat PGRAPH's read of the same address |
| `ring=` | the guest's DMA object limit — the bound that exists without the hold |
| `backlog(mean= max=)` | un-consumed pushbuffer bytes at the instant of publication |
| `behind=` / `kicks=` | submissions made while PGRAPH was not yet current: the share of the guest's own submissions that are exposed at all |
| `held(...)`, `spun=`, `slept=`, `gave=` | non-zero only with the bound on: what the guest paid, and how |

Three decisions in it are worth recording because the alternatives are traps
this project has already paid for.

**Timed per submission, never per pushbuffer word.** `AGENTS.md` records a
`syscall(SYS_gettid)` added to the pusher's inner loop — 144,712 calls in a
few seconds — throttling the emulator until it presented as a renderer
deadlock. Two clock reads per submission is three orders of magnitude cheaper,
and `kicks=` reports how many submissions that is rather than leaving the cost
assumed.

**Retirement is batched at DMA_GET == DMA_PUT.** Testing each published
address against DMA_GET individually would be wrong: the pushbuffer is a ring
walked with JMP, so DMA_GET *passing* an address does not order against it.
The caught-up moment is the only one at which every outstanding segment is
provably consumed. The same JMP is why `backlog` excludes the non-linear case
and counts it as `wrap` instead — a wrapped difference would read as a 4 GB
backlog and swamp the mean.

**The parser carries its own subject.** `fifo_skew_report.py --selftest`
checks its regex against the format string `pfifo.c` actually prints. A tool
that silently matches nothing reports a soak full of numbers as a soak that
emitted none, which reads exactly like a failed run; that cost two falsifiers
on 2026-09-12.

## The bound, and why zero is the only sufficient value

`pfifo_bound_skew` holds the guest at its own DMA_PUT store until PGRAPH has
consumed what that store published. While the guest executes, the FIFO then
holds no unprocessed method, so **PGRAPH performs no read of guest memory
concurrently with guest execution.**

The argument that this is a fix rather than a timing change — the distinction
#44 insists on, because "make it rarer" and "fix it" are indistinguishable at
n=10:

- The guest's loop is *write surface N, publish draw N, write surface N+1*.
  Its **only observable act** between the two writes is the DMA_PUT store, so
  that store is the only place the emulator can interpose without the guest's
  cooperation.
- At the moment the guest resumes, **draw N is already inside the segment just
  published.** So *any* un-consumed pushbuffer leaves draw N's texture read
  still to come while surface N+1 is being written. There is no intermediate
  skew allowance that is sufficient; zero is not a tuned value, it is the only
  one with a proof.
- The measurement agrees from the other direction. #44 established the guest
  is **at most one iteration ahead** — the immediate successor explains 100%
  of wrong pixels, successor+2 explains 32/146, 400/992 and 234/591 — so the
  skew to remove is exactly one submission's worth, and nothing less than all
  of it will do.

### The one hole, counted rather than argued

If the pusher parks **without** catching up, the guest is released with work
outstanding. That happens when the pusher is stalled on a flip, on a NOP
acknowledgement or on a context switch — none of which can clear until the
guest runs again, so the alternative to releasing it is a deadlock.

`gave=` counts it. #44's eighteen draws sit inside one frame with no
FLIP_STALL between them, so the hole should not be on its path; a title that
flips every frame was expected to exercise it constantly, which is why the cost
arm is registered to report `gave` as a **rate** rather than judge it. That
rate is the honest scope of the change and was unknown before this pass.

The expectation in that sentence turned out to be wrong, and it is left here
because it is the reason the counter was split: on Galleon the flip accounts
for four or five releases out of ~2,500, and the NOP handshake for 99.7%.
Reasoning about which of four causes dominates is exactly what a single
summed counter licenses and cannot support.

### Two mechanics that are easy to get wrong

**The BQL is released around the sleep, and reacquired outer-first.** Every
nv2a MMIO handler runs with the BQL held — `prepare_mmio_access`
(`system/physmem.c:3343`) takes it when the region has no `lockless_io`, and
none of `blocktable`'s entries sets one; the TCG store path additionally holds
`BQL_LOCK_GUARD()` (`cputlb.c:2597`). Sleeping with it held would stop the
PGRAPH method path (which takes the BQL to raise an interrupt) **and** the
main-loop VBLANK timer that a FLIP_STALL in the waited-on segment needs, so
the wait would be satisfiable only by its own timeout. Reacquiring it while
still holding `pfifo.lock` would invert against `nv2a_lock_fifo()`, which
holds the BQL and *then* waits for `pfifo.lock`, so `pfifo.lock` is dropped
first — the order `pgraph.c`'s own IRQ paths use
(`nv2a_set_surface_scale_factor`, and the NOP-error path at `pgraph.c:2262`).

**Which caller may be held is decided on DMA_PUT having advanced.** That is
what keeps the whole change inside `pfifo.c`, with no edit to `user.c`: the
guest CPU is the only writer of that register, so the test is exact. It also
excludes the dangerous caller by construction — `pgraph_write` reaches
`pfifo_kick()` holding `pgraph.lock` as well as `pfifo.lock`, and waiting
there for a thread that needs `pgraph.lock` to process a method is a deadlock.
DMA_PUT cannot have advanced on that path.

**The invariant the `current_cpu` gate rests on, and what breaks if it ever
stops holding.** The gate excludes every non-guest caller, but one guest-side
caller is excluded only by an ordering fact: `pgraph_write` reaches
`pfifo_kick()` holding **`pgraph.lock` as well as `pfifo.lock`**, and waiting
there for a thread that needs `pgraph.lock` to process a method cannot
succeed. It never enters the wait today because **every write to DMA_PUT is
immediately followed by a kick on the same thread** — `user_write` always
kicks, and `pfifo_write` on the `CACHE1_DMA_PUT` register does too — so by the
time any later MMIO write reaches `pfifo_kick()`, DMA_PUT has already been
consumed by the submission test. If a path is ever added that advances DMA_PUT
*without* an immediate kick, that stops being true, and the symptom is a
repeated 250 ms stall on PGRAPH register writes rather than a hard hang: the
pusher parks stalled, the unconditional broadcast releases the waiter, and
`gave=` counts it. Worth knowing which number to look at.

**A separate condition variable, not `fifo_idle_cond`.** The idle signal means
"the PFIFO thread has stopped", which is what `nv2a_lock_fifo()` needs, and it
only becomes true after `FIFO_SPIN_ACTIVE_NS` = 100 µs of spinning. The bound
needs "PGRAPH has caught up", a much earlier event; waiting for the idle
signal would add 100 µs to every submission the guest makes and price the
bound out of existence before it was measured. The new signal is broadcast
unconditionally after `pfifo_run_pusher` returns rather than at the caught-up
break inside it, because the pusher has five other exits and a waiter that
only hears about the happy one waits out its whole 250 ms timeout instead.

## MEASURED

Arms queued 2026-09-13, both `Texture border` ×10 on the **nova**, matching
the `disc_id` and run count of the published noise floor
(`1789255594-exp54-stst-correct-3660183`, `disc_id = Texture border`, 10
runs). Arm A `90c5b88033` (instrument, bound off), arm B `008298446d` (bound
on). Prediction registered and committed at `968403a80c`, before either arm
was queued, in `docs/testing/predictions/issue44-fifo-skew-bound.json`; the
cost pair is Galleon 240 s ×2 on the nova against
`issue44-fifo-skew-bound-cost.json`.

### ARM A, and the skew is measured for the first time

`d97d506514` / apk `b9f196e7ced9`, dispatch `1789303576-skew-bound-1885045`,
**nova** (read out of `result.json`, not assumed), `disc_id = Texture border`,
10 runs, `progress_log_proof` on every one, 18 captures each. 45 two-second
windows over 145.5 s.

| | |
|---|---|
| pushbuffer ring (the guest's DMA object limit) | **67,088,383 bytes** — 63.98 MiB |
| submissions | 148,667 (1,022/s pooled; 2,000–3,300/s in steady windows) |
| **submissions made while PGRAPH was not yet current** | **148,667 — 100.0%** |
| backlog at publish | mean 10,065 bytes, max 65,204,224 |
| **SKEW, publish → consumed** | **mean 16,885,845 ns**, p50 8,650,000, p90 34,900,000, p99 ≥51,250,000, **max 527,868,229** |

**`behind` is 100.0% of 148,667 submissions.** That is S0, the leg registered
to be able to refute the whole model on arm A alone, and it does not merely
hold — the guest is ahead of PGRAPH at *every single submission it makes*. The
skew model is not a story about an occasional overtake.

**And the window is milliseconds to half a second.** The CPU work between two
of this test's draws is one `GenerateBordered2DSurface` into scratch plus a
`swizzle_rect` of a 64×64 surface — microseconds. Against a p50 of 8.65 ms
the guest does not need to be lucky to get a whole iteration ahead; it needs
to be unlucky not to. A ~46% per-run loss rate needs no further explanation.

Two limits on those numbers, both reported by the instrument rather than
inferred:

- `lost = 2,084` of 148,667 (1.4%): the 256-entry pending ring overflowed in
  the boot windows, so the **skew mean is a floor**. The max is exact.
- p90 and p99 are **floors** too. The histogram covers 0–51.2 ms and p99
  lands in the overflow bin, so more than 1% of submissions exceed 51.2 ms.
  The mean and max are computed outside the histogram and are exact. A future
  revision wants a wider span; the range was chosen to match the VBLANK
  histogram, which was the wrong reference for a quantity this large.

### Arm A's `stale_px`, and the gate

```
stale_px     5160, 0, 481, 64, 192, 0, 0, 0, 64, 0     5 of 10 non-zero
races_lost      4, 0,   1,  1,   1, 0, 0, 0,  1, 0
unexplained_px  0 on all ten runs
```

**S8, the validity gate, holds**: the flake reproduces on 5 of 10 runs against
a registered bar of at least 3. The magnitudes are smaller than the published
floor's (5,961 px total against 12,596) and the failing shapes differ — 16x1,
8x2, 2x2 and 8x8 here against 8x2, 32x32 and 4x8 there. Both are what a
combinatorial flake looks like: each swatch has a fixed cost if it loses and a
run's total is the sum over whichever subset lost, which is exactly why this
is judged on `stale_px` and the classes rather than on differing pixels.

| class | swatches | px | share |
|---|---|---|---|
| torn | 4 | 776 | 13.0% |
| complete | 3 | 3,137 | 52.6% |
| partial-successor | 1 | 2,048 | 34.4% |

The `partial-successor` row is new against the floor and is the documented
non-uniqueness rather than a new phenomenon: captures1's pass-1 16x1 has
`wrong = 2,048` with `successor = 1,024` and `best = 1x1` at 2,048, i.e. the
grey padding checkerboard is identical across iterations so several candidates
tie. Its pass-2 16x1 row is the more interesting one — `cut = 88`,
`prefix_ok = True`, successor 158 of 456 but `4x8` (successor **+2**) at 456 —
which is the same successor+2 tail #44 already records at 32/146, 400/992 and
234/591.

**One cross-lane datum, and it is not one this lane went looking for.** Three
of arm A's failures are **pass-2 8x8** (64, 192, 64 px on captures4, 5 and 9),
and all three are `torn` — `cut = 172, 236, 172`, `prefix_ok = True`. Pass-2
8x8 is one of the two shapes the texture lane's `blind` counter fired on. A
missed re-upload cannot produce a frontier at an arbitrary offset, so on these
three runs that shape is a mid-write read. That does not refute their
mechanism — two causes can share a shape — but it does mean theirs is not the
only cause even on the shapes their counter names.

### ARM B: the bar is met, and one leg failed

`ec7f50e859` / apk `24a5f905a794`, dispatch `1789303576-skew-bound-1885066`,
**nova**, `disc_id = Texture border`, 10 runs, progress-log proof on every
one. One line from arm A.

```
stale_px     0, 0, 0, 0, 0, 0, 0, 0, 0, 0        10 of 10
races_lost   0, 0, 0, 0, 0, 0, 0, 0, 0, 0
```

All ten runs are **bit-identical**: 15 of 18 exact, 4,600 px, every run. Arm A
gave 14–15 exact and 4,600–9,760 px.

| class | A px | B px | |
|---|---|---|---|
| torn | 776 | **0** | closed |
| complete | 3,137 | **0** | closed |
| partial-successor | 2,048 | **0** | closed |

`ab_compare` on the same pair, both arms 10 runs, same `disc_id`, same
`classifier_rev`: **0 better, 0 worse, 17 same, 1 noise**, nothing outside its
measured band, exact 14 → 15. Verdict **PRE-REGISTERED: PASS, all 20
registered checks hold** — the prediction was queued at 12:46:16Z naming the
file and its content still hashes to the sha recorded then.

### The instrument says the bound executed, which is a separate question

| | arm A | arm B |
|---|---|---|
| `held(n)` / `kicks` | 0 | **1.0000** (148,704 of 148,704) |
| skew p50 | 8,650,000 ns | **100,000** |
| skew p90 | 34,900,000 | **150,000** — a 99.6% fall |
| skew p99 | 51,250,000 | **1,100,000** |
| skew mean | 16,885,845 | **1,052,811** |
| skew max | 527,868,229 | 607,705,521 |
| guest held, mean | — | 497,095 ns |
| guest held, max | — | 252,009,323 ns |
| spun / slept | — | 37,103 / 111,601 |
| `gave` | 0 | **1,002** |
| `lost` (untimed) | 2,084 | **0** |

`held(n)` equal to `kicks` to four decimal places is what makes S1 a
measurement rather than a coincidence: **every submission the guest made was
held.** A flat count cannot distinguish a change that never ran from one that
ran and returned a different wrong answer, which is why this was registered as
its own leg.

Two figures in that table are not improvements and should not be read as
regressions either. The skew **max** rose, 528 → 608 ms: that is the host
stall tail, which no bound reaches, and it is the same population as the
725 ms non-deferred VBLANK lateness the `clamp=` counter sees. And `lost` went
to zero because with the bound in force at most one submission is ever
outstanding, so the pending ring cannot overflow — arm A's skew mean was a
floor and arm B's is exact.

### S4 FAILED, and it is the most useful line here

**`gave = 1,002` of 148,704 submissions — 0.674%.** The registered bar was
zero. `gave` counts releases of the guest with pushbuffer still outstanding,
which happen when the pusher parks stalled on a flip, a NOP acknowledgement or
a context switch — none of which can clear until the guest runs again, so the
alternative to releasing it is a deadlock.

So the honest statement of what this change achieves is narrower than "the
race is impossible", and the leg is what forces it to be said:

> The race is **impossible on the 99.326% of submissions the bound covers**,
> and merely **unlikely on the remaining 0.674%**.

S1 passing on 10 of 10 does not by itself close that gap, exactly as the
prediction said it would not. What it does say is that the hole did not cost a
race in ten runs, which is unsurprising rather than lucky: the submissions
that matter are the eighteen per run that publish a draw whose texture the
guest then overwrites, out of 148,704 that include boot, the dashboard and
every other test on the disc.

**What is not known is where the 1,002 come from**, and the instrument cannot
say: `gave` is one counter over four stall reasons. 1,002 is far more than the
~180 flips the ten runs contain, so most of them are not FLIP_STALL. Splitting
`gave` by `pfifo_pusher_should_stall`'s four conditions is a one-counter change
and is the named next step — it decides whether the residual is reachable at
all or is inherent to the flip handshake.

### T1 and T3

**T1 holds**: torn and complete both zero. **T3 holds** as registered — no
`complete` swatch is strictly better matched by a predecessor than by its
successor; on 2 of 3 the successor is the unique best match and on 1 of 3 it
ties with a lower-indexed candidate, which is the padding-checkerboard
degeneracy #44 already records.

**T2b is VOID**, not passed: the `unmodelled-successor` class does not appear
in arm A at all, so this pair could not test it. The 680-px case is in the
published floor, not here.

**One row deliberately left uninterpreted.** Arm A's `partial-successor`
swatch (captures1, pass-1 16x1, 2,048 px) has `successor = 1,024` while a
lower-indexed candidate accounts for 2,048. That reads like predecessor
content — the texture lane's mechanism — and **it is not safe to read it that
way from this tool.** `read_through` builds a per-candidate table keyed on
texel position, and a candidate scores zero on a texel it simply has no entry
for, so two candidates' counts are not a like-for-like comparison across
different surface dimensions. Deciding what that row is needs the counting
normalised, which this lane has not done. It is 2,048 px on 1 of 10 runs and
it went to zero in arm B along with everything else; nothing in the verdict
rests on it. Recorded rather than guessed at, because guessing at this tool's
fields already cost one retraction today.

### What arm A's own numbers predict about the cost, stated before the cost arm runs

A p50 skew of 8.65 ms does **not** mean the bound makes every submission wait
8.65 ms. That figure is a queue-depth effect: it is how long a backlog takes
to clear, and with the bound in force the backlog is never allowed to form.
The quantity that survives is the **service time of one submission**, and the
arithmetic goes the other way:

- 3,000 submissions/s × 8.65 ms would be 26 seconds of waiting per second of
  wall clock. The bound is not merely expensive at that rate, it is
  impossible — so the p50 cannot be the per-submission cost, and reading it as
  one would have been the "a bound is not a value" mistake.
- What it should cost instead is the PFIFO thread's own busy time per
  submission, plus a thread round trip. `frame-pacing-and-parallelism.md`
  measures `nv2a.pfifo_thread` at **48%** busy in steady state; at 3,000
  submissions/s that is **~160 µs of service per submission**.
- Serialised, the guest then spends roughly the PFIFO thread's busy fraction
  blocked where it previously spent approximately none. The same document has
  the guest CPU thread **83%** busy with the renderer idle 21.2 ms of a 50.2 ms
  frame waiting on it, so the two halves overlap substantially and it is that
  overlap the bound removes.

**So the honest expectation is that C1 fails.** A cost of order the PFIFO
thread's busy fraction is well past "the `gfps` ceiling falls by at most 2",
and `orchestration.md` says what to do with that rather than leaving it to
judgement: measure the accuracy, then the cost, then hand the trade over with
both numbers. It also says which way the default should lean while that
happens — *if a change improves accuracy, keep it, and recover the throughput
through the performance work stream* — which is why the bound is committed on
by default with `HAKUX_FIFO_SKEW_BOUND=0` as the escape, rather than committed
off pending a decision nobody asked for.

Two things would make it cheaper without weakening the guarantee, and both are
measurements this arm produces rather than guesses: if `slept` dominates
`spun`, the cost is scheduler round trips and the 60 µs spin window is the
thing to widen; if `spun` dominates and the cost is still there, the cost is
the serialisation itself and no spin tuning reaches it. That is registered as
C3.

Noise floor to beat, ten runs of one unchanged APK:

```
stale_px    146, 0, 2352, 0, 0, 2430, 0, 1847, 5640, 181
races_lost    1, 0,    2, 0, 0,    3, 0,    2,    3,   1
```

**Bar: `stale_px == 0` on 10 of 10 runs.**

### The judging path is validated before the arms land

`border_swatch_origin.py` was run against the noise floor's own result
directory (`1789255594-exp54-stst-correct-3660183`, ten `captures<N>/`
directories) on this tree, and reproduces the published figures exactly —
`stale_px` 181, 0, 2352, 0, 0, 2430, 0, 1847, 5640 with `races_lost` 1, 0, 2,
0, 0, 3, 0, 2, 3, every `prefix_ok=True`, `unexplained_px=0` on every run, and
the cut points 116, 175, 229, 405, 432, 506 and two `complete`. Its
`--self-check` reproduces all 73,728 golden swatch pixels.

That is worth doing before rather than after, for the reason `AGENTS.md`
records twice: a tool that reads captures and silently finds none answers
anyway, and on 2026-09-12 one reported all three of its captures MISSING on an
arm that contained them — which reads exactly like a failed render.

### The twelve failing swatches are not one population, and two lanes are on it

Computed offline from the same ten-run floor, with `border_swatch_classes.py`
over `border_swatch_origin.py --json`, and **registered before either arm was
claimed** (`docs/testing/predictions/issue44-skew-class-split.json`). The
field that separates them is `cut`:

| class | swatches | px | share | what it is |
|---|---|---|---|---|
| **torn** | 8 | 3,852 | 30.6% | a finite `cut` with `prefix_ok` — the stale set is a row-major prefix of the successor's write, cut at 116/175/207/229/405/432/506, a different offset every run |
| **complete** | 3 | 8,064 | 64.0% | no `cut`, successor explains every wrong pixel — the successor's write had *finished* when the read happened |
| **unmodelled-successor** | 1 | 680 | 5.4% | `successor == 0` with pixels still wrong — the one swatch whose successor the tool does not model |

```
captures1   146   torn=146
captures3  2352   torn=304  complete=2048
captures6  2430   torn=382  complete=2048
captures8  1847   torn=1847
captures9  5640   torn=992  complete=3968  unmodelled-successor=680
captures10  181   torn=181
```

Three things follow, and the first is the one that matters for judging.

**`stale_px == 0` on 10 of 10 is a sum over classes that fail for different
reasons, and #44 is now being worked by two lanes with two mechanisms.** The
texture lane has a decoded-length hash gate that declines to re-upload at all
— `blind=2` measured directly, on pass-2 4x4 and pass-2 8x8 — while this lane
has the skew. `AGENTS.md`'s rule is exactly on point: a class count is a count
of pixels a mechanism *touches*, not of pixels it is solely responsible for,
and subtracting one from a differing total assumes an additivity these classes
do not have. So the mechanism leg is registered separately: **all three
classes must go to zero in arm B**, with the first two carrying the mechanism
argument and the third resting on a cross-test successor.

**The `complete` class is what separates the two mechanisms, directionally.**
A texture that was never re-uploaded holds content from an *earlier* upload,
so it cannot show the **successor's** surface — which is written after the
draw that is missing it. A missed re-upload therefore cannot reach this class;
a skew can, as a run-ahead of one whole iteration rather than a partial one.
That is registered as a leg that can fail: if any `complete` swatch is better
matched by a predecessor than by its successor, the argument is wrong and the
two mechanisms are not separable this way. (#44 already records that on 2 of
11 losses the successor is not *uniquely* identified — pass-1 8x2's +1/+2/+3
all match 2,048 of 2,048 — so the leg is about predecessor versus successor,
not about which successor.)

**RETRACTED, before any arm ran: this section first claimed #44's "the
immediate successor explains 100% of wrong pixels" was really 94.6%.** It is
not. `border_swatch_origin.py:255` sets `succ = None` for the **final** swatch
of the test, and its own comment says why — *"the last swatch's successor is a
write by the NEXT TEST, whose content this tool does not model"* — so
`successor == 0` on pass-2 4x8 is **definitional, not measured**. The headline
is a claim about the eleven swatches with a modelled successor and it stands.

The failure is the one `AGENTS.md` records as *an inference can be valid and
still wrong, because the model it is valid inside was never checked*: the
arithmetic was right, inside a reading of the `successor` field taken from its
name rather than from the code that produces it. And the companion rule says
what to report alongside a correction — **what changed about the
measurement**. Here: the surviving split keys on `cut`, whose semantics the
tool's docstring does state, which is exactly why torn-versus-complete
survives and the 94.6% figure does not.

It also made the prediction **weaker** than it should have been. The final
swatch's successor is the next test's first write; a cross-test successor is
still a skew; and the bound holds the guest at **every** submission, including
that one. So the registered leg is now that this class goes to zero in arm B
too — and if it survives while torn and complete go to zero, that points at a
submission the bound does not reach rather than at a class it cannot.

### The caveat that has to travel with any verdict

**Five of the eighteen swatches are structurally blind.** The coloured
checkerboard is position-indexed, so a larger image is a superset of a smaller
one in-window, and pass-1 1x1…16x16 render identically whether or not they
lost their race. `races_lost` is therefore a **floor**, and this change could
take `stale_px` to 0 on 10 of 10 runs while still losing races on those five —
**and this instrument would call that a pass.**

It is still the right instrument: it is the only one that separates the
mechanism from a differing-pixel count, and a count cannot be used to judge
this capture at all. But the bar it clears is narrower than "the race is
gone", and what has to carry the rest is the impossibility argument above plus
the two legs that read the bound directly — `held(n)` against `kicks` (did it
execute) and `gave == 0` (no exceptions on this path).

## MEASURED: the cost, and it is the reason this ships off by default

Galleon, 240 s per arm, **nova** both sides (`device_label` read out of each
`result.json`), `--who skew-bound-cost`, same two refs as the accuracy pair.
Arm A `1789303629-skew-bound-cost-1885758`, arm B
`1789303629-skew-bound-cost-1885779`.

| | arm A | arm B |
|---|---|---|
| pushbuffer ring | **134,197,247 bytes (128 MiB)** | same |
| submissions/s | 257 | 181 |
| **made while PGRAPH was behind** | **100.0%** | 100.0% |
| skew mean | 55,384,393 ns *(a floor: 4,251 untimed)* | **2,070,692** |
| skew p50 / p90 / p99 | 2,450,000 / 7,350,000 / 20,200,000 | — |
| skew max | **4,668,197,291** ns | 524,949,844 |
| `held(n)` / `kicks` | 0 | **1.0000** |
| guest held, mean | — | **2,245,410 ns** |
| **guest blocked at submissions** | ~0% | **40.7% of wall clock** |
| `spun` / `slept` | — | 4,237 (9.6%) / 40,060 (90.4%) |
| `gave` | 0 | **2,482 — 5.603%** |
| **`gfps` p90** | **29** | **13** |
| **`gfps` max** | **30** | **15** |
| `gfps` p50 *(printed, not judged)* | 16 | 10 |

**C1 FAILS: the frame-rate ceiling more than halves.** p90 29 → 13 against a
registered tolerance of 2, and max 30 → 15. That is not a tolerance missed by
a little; it is the pipeline's remaining CPU/GPU overlap being removed.

**And it is what the arithmetic predicted before the arm ran.** The prediction
committed with arm A's result said the cost would be of order the PFIFO
thread's busy fraction — 48% from `frame-pacing-and-parallelism.md` — and the
guest came back blocked for **40.7%** of wall clock. The prediction holding is
worth more here than the number: it means the cost is understood rather than
merely observed, and it is why "widen something" is not the repair.

**`behind = 100.0%` reproduces on a real title**, at twice the ring size and a
tenth the submission rate of the test disc. The skew model is not an artefact
of a pgraph disc.

**C5's RATE behaves exactly as registered; its ATTRIBUTION was wrong.** `gave`
is 5.603% on Galleon against 0.674% on the test disc, and the bound covers
94.4% of a flipping title's submissions. Both of those stand.

> **CORRECTED BY MEASUREMENT — the cause named here is not the cause.** This
> section read "*because Galleon flips every frame and the guarantee genuinely
> does not hold across a flip stall*". Splitting the counter gives
> `gaveby(flip=4 nop=2534 ctxsw=1 noaccess=0 other=1)` on one run and
> `flip=5 nop=1973` on a second: **99.8% and 99.6% of the releases are the NOP
> acknowledgement handshake, and four or five of ~2,500 are the flip.** The
> rate was right and the reason was wrong, which is precisely what one counter
> summed over four reasons cannot tell you. It also redirects the residual — a
> flip stall clears only on a VBLANK and is arguably unclosable, whereas the
> NOP handshake is a different mechanism whose reachability is an askable
> question. See "99.8% of the releases are `waiting_for_nop`".

### C3's registered interpretation was wrong, and the hold mean says why

C3 was recorded as a diagnosis rather than a leg, and its reading was: if
`slept` dominates, the cost is scheduler round trips and the 60 µs spin window
is the thing to widen; if `spun` dominates and the cost is still there, the
cost is the serialisation itself.

It came back **90.4% slept**, which by that reading points at the spin window.
**That reading is backwards**, and the figure that settles it is one the same
line already carries: the mean hold is **2,245,410 ns — 37× the 60 µs spin**.
A wait that long is real service time on the PFIFO thread, not wakeup
latency. Nothing can be spun for 2.25 ms, so no spin tuning reaches it.

The discriminator should have been **hold mean against the spin window**, not
the `spun`/`slept` split alone. A split that is 90% sleeps tells you the spin
did not catch them; it does not tell you *why*, and those are opposite
repairs. Recorded because the wrong version was registered.

### Which points at the cheaper version, now motivated rather than guessed

The guarantee that closes #44 is **"no unprocessed draw sits in the FIFO while
the guest runs"**. Holding at *every* submission is a far stronger condition
than that, and the gap is enormous: a submission carrying no draw adds no
draw, so holding only at **draw-publishing** submissions preserves the
invariant exactly — and this disc makes **148,704 submissions for 180 draws**.

It needs a pre-scan of the published segment for `NV097_SET_BEGIN_END` before
deciding whether to hold, and it needs its own arm. It is the concrete target
`orchestration.md` asks for when it says to recover the throughput through the
performance stream rather than dropping the fix.

### The trade, handed over rather than resolved

The constant is defaulted **off** (`HAKUX_FIFO_SKEW_BOUND=1` turns it on), and
that is a statement about *this* version's scope, not about the mechanism:

- **Accuracy bought**: #44 closed on every measurable class, `stale_px` 0 on
  10 of 10, PRE-REGISTERED PASS on 20 of 20 checks, with the bound proven in
  force at `held(n)/kicks = 1.0000`.
- **Cost**: over half the frame-rate ceiling of a real title, and 5.6% of that
  title's submissions not covered anyway.
- **What is not being claimed**: that this is the final shape. A selective
  bound plausibly buys the same accuracy at a fraction of the cost, and that
  is the next arm rather than a hope.

## THE SELECTIVE BOUND: hold only where a draw is outstanding

Written 2026-09-13 on `5cfc236d9b`, arms queued, results to be filled in.
None of the mechanism above is re-derived; this is the sizing and the four
places the obvious implementation is wrong.

`HAKUX_FIFO_SKEW_BOUND` gains a third value: 0 off, 1 the every-submission
bound measured above, 2 hold only where a draw is outstanding. Mainline stays
at 0 and arm B is the side branch `arm/issue44-draw-only-on`, one hunk apart.

### Why it can be this much cheaper, and it is arithmetic rather than hope

The guarantee is *"no unprocessed draw sits in the FIFO while the guest
runs"*. A submission carrying no draw adds no draw.

> **CORRECTED BY MEASUREMENT — the sizing below was wrong by 30×.** This
> section originally read "148,704 submissions for 180 draws, so mode 1 pays
> **826** holds for every one the invariant needs". Arm B measured **5,286
> draw-publishing submissions**, not 180: the 180 is the draw count of the
> *measured test*, while the run also boots, runs the dashboard and executes
> seventeen other tests, and every draw in all of that is a draw the bound
> must cover. The figure is left visible rather than quietly replaced because
> it was used to size the change. See "The 826:1 sizing was wrong, and by 30×".

So mode 1 pays **27** holds for every one the invariant needs — and the price
of those 27 is `gfps` p90 29 → 13 with the guest blocked 40.7% of wall clock,
which is unchanged, because that was measured directly and never derived from
the ratio.

### The scan is a WORD FILTER, not a parse, and the asymmetry is the reason

A **false positive costs one unnecessary hold. A false negative breaks the
invariant silently**, which is the failure this lane exists to remove. So the
test is deliberately loose in the safe direction: every word is treated as a
possible method header, with no attempt to tell headers from parameters.

- Both header forms — increasing `(w & 0xe0030003) == 0` and non-increasing
  `== 0x40000000` — have bits 31, 29, 17, 16, 1 and 0 clear, so the filter
  `(w & 0xa0030003) == 0` is a **superset** and rejects no real header.
- JMP, old-JMP, CALL and RETURN each set one of those bits, so they are
  rejected — and none of them can carry a method number anyway.
- **An increasing run can reach `NV097_SET_BEGIN_END` with no header naming
  it**, so the test is the run's whole span `[m, m + 4·count)` and not `m`.
  Applying the increasing rule to a non-increasing header over-approximates
  again, which is once more the safe direction.

One load, one mask and two compares per word, against the pusher's own
per-word method dispatch. `scan(ns=)` is what says whether that is true
rather than this paragraph.

### The scan's subject is `[DMA_GET, DMA_PUT)`, not the bytes just published

That is the invariant restated verbatim, and it is what makes the argument
local instead of an induction over previous segments. **With a selective
bound DMA_GET genuinely lags**, because draw-free submissions are no longer
drained, so "what I just published" and "what nobody has read" are different
sets and only the second answers the question.

### Which is why the word budget does two jobs, and the second is the load-bearing one

`FIFO_SKEW_SCAN_MAX_WORDS` bounds the scan, obviously. It also bounds the
**region** the scan must cover: a span that grows because nothing drains it,
rescanned at every submission, is **quadratic**. Holding when the span
exceeds the budget forces a drain, so the span is capped and the scan is
O(budget) rather than O(run length).

16,384 words = 64 KiB, against a measured steady-state un-consumed backlog of
**3,396–13,352 bytes mean and 32,264 bytes max** on Galleon under mode 1
(`1789303629-skew-bound-cost-1885779`) — 2× the largest backlog that run ever
showed. **Budget exhaustion is a counted row (`big=`), separate from "no draw
found" (`nodraw=`)**, because otherwise a hold rate rising under a heavy
scene reads as the mechanism working when it is the budget running out.

### A header can sit at a segment's end with its parameters in the next

This is the hole a scan-the-new-bytes design cannot see, and it is not
hypothetical arithmetic — it is what the pusher does when it runs out of
data. It consumes up to DMA_PUT, parks with `METHOD_COUNT` still set and
`DMA_GET == DMA_PUT`, **which satisfies a hold**, while the method has not
executed. The next segment carries only parameter words, so a scan of it
alone says "no draw" and releases the guest into exactly the race this
closes.

`fifo_skew_pending_method_is_draw()` reads the pusher's own DMA state, so
this needs no carry flag and no guess about how many submissions a run
spans.

### Narrower than mode 1, and the narrowing has to travel with it

The 2D class reads guest memory **outside a draw** — `pgraph_image_blit` and
the surface-download paths. **Mode 1 covers those; mode 2 does not.** Scoped
deliberately to the mechanism #44 measured texel-exact, and the method test
is where a blit would be added if one is ever shown to race. A `stale_px`
pass does not certify the blit path.

### The precondition the whole bound rests on, verified rather than asserted

"DMA_GET reached DMA_PUT" is a proxy for "every guest-memory read those
methods perform has happened", and that proxy holds **only while the reads
are synchronous on the PFIFO thread**. #54's lane checked the three ways it
could be false: `RCMD_DRAW` appears only in the enum and is never enqueued;
`g_xemu_draw_merge` and `g_xemu_draw_reorder` are both static `false` with
the Android prefs defaulting both false; and the reorder path does not defer
the read anyway, because `try_snapshot_*` calls `begin_pre_draw` at *enqueue*
time on the PFIFO thread and `emit_reorder_entry` reads no guest memory at
flush.

**If `g_xemu_draw_merge` is ever enabled that stops holding**, and the
failure mode is the bad kind. `flush_draw_queue_internal` defers the draw's
guest read to flush and `RCMD_FLUSH`/`RCMD_PROCESS_PENDING` run it on the
**render thread** — so the submission is consumed, DMA_GET reaches DMA_PUT,
the guest is released, and the read has not happened. `held(n)/kicks` would
still read 1.0000 and `gave` would still read low: **the instrument would
report a guarantee that is intact while it is void.** Nothing in `pfifo.c`
can detect it, which is why it is a comment in `pfifo_bound_skew` and not
only a line here.

### `gave` is split, because one counter over four reasons decides nothing

S4 failed at 1,002 releases on the disc (0.674%) and 2,482 on Galleon
(5.603%). `gaveby(flip= nop= ctxsw= noaccess= other=)` is
`pfifo_puller_should_stall`'s four conditions plus a residual, read directly
rather than through that predicate because `pfifo_stall_for_flip` **clears
`pgraph.waiting_for_flip` as a side effect** and an instrument that mutates
its subject is not an instrument.

`flip`, `nop` and `ctxsw` **cannot be closed** — the alternative to releasing
the guest there is a deadlock — so a hole made of those is inherent. `other`
is the row that decides whether a read-side mitigation is ever needed: the
pusher was merely behind and the 250 ms backstop expired, which is a
performance problem rather than a protocol one. It is an **upper** bound on
the timeout case, because the flags are read after both locks are reacquired
and a pusher that unstalled in between lands there.

### `Texture border` cannot exercise the hole AT ALL, and that changes the arm

This is the sharpest thing #54's lane found and it is a structural blindness,
not a power problem. **The disc's eighteen draws sit in one frame with no
FLIP_STALL between them**, so the pusher never parks while stalled and the
`gave` hole is unreachable by construction. `stale_px == 0` on that disc
therefore **cannot distinguish "the hole is closed" from "the hole was never
opened"** — which is this project's own recurring error, a negative result
read from an instrument that could not see the mechanism.

So `gave` is judged on the two flipping titles instead, and Crimson Skies
gets a better falsifier than `stale_px`: **`Tr` from the #54 probe**, which
counts `begin_pre_draw` windows where a bound texture's dirty bit was
consumed by an upload and then set again before the window closed — #44's
mechanism read from the other side. Baseline **0.5661 and 0.5672** across two
runs of one binary, reproducible to better than 0.2%, with DOA3 (0/2455) and
JSRF (0/5733) as negative controls and `Xd` an impossible row at 0 over
5,630,702 windows.

**The bar is `Tr == 0`, not `Tr` smaller.** "Tr fell" is satisfiable by any
perturbation of timing; "Tr == 0" only by making the race impossible.

### Arms

| | ref | what |
|---|---|---|
| accuracy A | `2e4e8403d9` | mode 0, `Texture border` ×10, nova |
| accuracy B | `78f3f5eec8` | mode 2, one hunk apart |
| cost A / Crimson A | `5cfc236d9b` | mode 0, + the `gave` split |
| cost B / Crimson B | `d879e6e03b` | mode 2, one hunk apart |

Predictions committed before anything was queued:
`issue44-draw-only-bound.json`, `issue44-draw-only-bound-cost.json`,
`issue44-draw-only-crimson.json`. The accuracy pair keeps the older refs
deliberately — it does not read the `gave` split, and moving it would have
made its arms differ by two things.

### RETRACTED AT n=6, BY THE SAME ERROR I HAD JUST USED TO REFUTE ANOTHER ONE

At 5 of 10 runs I wrote this section up as *"the control has stopped
flaking, so the accuracy pair is VOID"*, with a bisection window and a named
suspect. **Run 6 read `stale_px = 286`, `races_lost = 1`, `successor_px =
286`, `unexplained_px = 0` — a genuine race loss, successor-explained, with
nothing unaccounted for.** The mechanism is intact and the claim was wrong.

It is worth recording *how* it was wrong, because it is the identical mistake
this lane had spent the afternoon correcting in #65. There, the value 12 was
justified as "1.35× the observed maximum" and the refutation was that the
maximum came from ~32 windows and the tail is three times larger — **a
small-sample extreme read as the distribution.** Here I read a small-sample
**absence** as the distribution: five zeros in a row, against a floor rate of
6 in 10, is about a 1% event and therefore *evidence*, but it is not a
finding, and I wrote it as a finding with a mechanism attached.

The asymmetry that should have stopped me: refuting a maximum needs more
samples than the maximum had, and I had **fewer** samples than the floor I
was contradicting. A rate measured on 5 runs cannot overturn a rate measured
on 10.

### What the arm actually shows so far, stated as a rate with its n

| | `2D_BorderTex_SZ` differing, per run | non-zero |
|---|---|---|
| published floor `7b63484c69` | 146, 0, 2352, 0, 0, 2430, 0, 1847, 5640, 181 | 6 of 10 |
| mode-1 arm A `d97d506514` | (`stale_px` 5160, 0, 481, 64, 192, 0, 0, 0, 64, 0) | 5 of 10 |
| **this arm A `2e4e8403d9`** | **0, 0, 0, 0, 0, 286, …** | **1 of 6** |

1 of 6 against 6 of 10 and 5 of 10 is a **possible** reduction and is not
established; the binomial spread at these n overlaps. **V0 needs at least 3
of 10 non-zero and is still live** — it needs two more in the remaining four
runs. If it fails, the pair is VOID and no `stale_px` result from arm B means
anything, which is the whole reason the gate was registered rather than
assumed.

What survives from the retracted section, because it does not depend on the
rate:

- **The instrument is sound, and there is a control inside the capture.**
  `Texture_border::2D` reads **59 differing pixels in both the published
  floor and this arm** — same `disc_id`, same 18 captures, same goldens —
  and `--self-check` reproduces all 73,728 golden swatch pixels on this tree.
  So a change in the flaky swatch is a change in the flake, not in the
  comparison.
- **The floor is 128 commits old** (`7b63484c69` against `2e4e8403d9`), and
  15 of those touch `pgraph/`. A stale floor reads like a fix, which is this
  project's recorded rule about captures and goldens applied to a *floor* —
  and in the more dangerous direction, because a floor that overstates the
  defect makes any arm look like a win. **Whatever V0 decides, the floor
  should be re-taken at the tip rather than cited from `7b63484c69`.**
- **If the rate really has fallen**, the window is clean: the last ref that
  demonstrably flaked at 5 of 10 is `d97d506514`, which lacks five
  texture-path commits this arm has, and of the 128 commits between them the
  only behavioural texture change is **`cdd8dc4c89`, #56's stale-binding
  fix** — the texture lane's mechanism, the other half of #44. That is a
  hypothesis with a named suspect and no measurement behind it, and it is
  recorded as such.
- **None of this bears on the skew itself**, which is measured directly and
  not through this capture: 100.0% of 148,667 submissions made with PGRAPH
  behind, p90 ≥34.9 ms, max 528 ms, reproduced on Galleon at twice the ring
  and a tenth the rate.

### And a defect in my own prediction, recorded rather than repaired

**The Crimson Skies pair has no arm-A gate.** X1 names only arm B's bar
(`Tr == 0`); nothing in that prediction says arm A must be non-zero for the
leg to discriminate, which is precisely the gate V0 provides for the disc.
The exposure is real: `Tr` = 0.5661 / 0.5672 was measured at `e353735028`,
which is **not** an ancestor of these arms and does **not** contain
`cdd8dc4c89`.

`vram_race_report.py`'s own **L5** leg supplies it — "runs with Tr>0 = 0 of
N → FAIL" — so the judge carries the gate the prediction should have. The
prediction is registered and sha-bound, so it is not being edited; the gap is
written down here instead.

### V0 FAILED at 2 of 10. THE ACCURACY PAIR IS VOID, by its own registered gate

Arm A complete: `2e4e8403d9` / apk `bfb13fa5f097`, **nova**,
`disc_id = Texture border`, 10 runs, `progress_log_proof` on every one, 18
captures each.

```
stale_px      0, 0, 0, 0, 0, 286, 0, 481, 0, 0      2 of 10 non-zero
races_lost    0, 0, 0, 0, 0,   1, 0,   1, 0, 0
successor_px  0, 0, 0, 0, 0, 286, 0, 481, 0, 0      successor explains 100%
unexplained_px  0 on all ten runs
```

**The registered bar was at least 3 of 10. It is 2.** So V0 fails and no
`stale_px` figure from arm B can be cited — which is precisely what the gate
was registered to do, and it did it before an arm B result was read as a
pass.

**And the sharpest way to say why is the bar's own false-pass rate.** V1 asks
for `stale_px == 0` on 10 of 10 in arm B. At the floor's rate of 6 in 10 a
binary with no fix passes that by luck with probability 0.4¹⁰ ≈ **0.01%**. At
this arm's 2 in 10 it passes with probability 0.8¹⁰ ≈ **10.7%**. The bar did
not change; the disc did, and a one-in-nine coin flip is not a falsifier.

### The rate DID NOT fall by any standard I am entitled to apply

This is the second correction to this section and it goes the other way from
the first. Having retracted "the control stopped flaking" at n=6, the
temptation at n=10 is to claim the weaker "the rate fell". **It is not
established either:**

| | non-zero runs | vs this arm, Fisher two-sided |
|---|---|---|
| published floor `7b63484c69` | 6 of 10 | **p = 0.160** |
| mode-1 arm A `d97d506514` | 5 of 10 | **p = 0.350** |
| **this arm A `2e4e8403d9`** | **2 of 10** | — |

Ten runs per arm cannot separate 0.2 from 0.6. Calling that difference at
p < 0.05 needs **about 20 runs per arm**, and 15 is still only p = 0.057. The
summed magnitudes moved in the same direction — 767 px here against 12,596 in
the floor and 5,961 in the mode-1 control — but a sum over a combinatorial
flake is a sum over whichever subset lost and is not a second, independent
statistic.

So the honest position: **V0 fails on a registered count, which is a verdict.
"The defect is receding" is a hypothesis at p = 0.16, which is not.** The
named suspect from the n=6 write-up (`cdd8dc4c89`, #56's stale-binding fix,
the texture lane's half of #44) remains a suspect with no measurement behind
it.

### What arm B is still worth, and it is most of what this change needed

Only **V1** depends on the flake. Arm B alone still delivers the legs that
are actually about the selective bound, and they are the ones mode 1 could
not distinguish:

- **V2** — `held(n)/kicks ≤ 0.05` against mode 1's 1.0000. Did it select at
  all?
- **V3** — `scan(ns=)` under 2% of the window span. **Did the pre-scan move
  the cost instead of removing it?**
- **V5** — `(wrap + big)/held(n) < 0.20`. Are the conservative fallbacks
  doing the work?
- **V6** — the two counter identities, exactly.

None of those needs a flaky capture; they read the bound directly. So the arm
stays queued rather than being cancelled, and its verdict is reported as
**V1 VOID, V2/V3/V5/V6 judged.**

### Two things this costs the lane, stated as work rather than as regret

1. **The floor must be re-taken at the tip.** `7b63484c69` is 128 commits
   behind, and a stale floor overstates the defect, which flatters every
   later arm. Any future `stale_px` verdict on this disc needs a
   contemporaneous control.
2. **At 2 in 10 this disc needs ~20-30 runs per arm to be an instrument**, or
   a different instrument. Crimson Skies' `Tr` is the better one on both
   counts: it is a *rate over draws* rather than a per-run coin flip
   (0.5661 and 0.5672 across two runs, reproducible to 0.2%), so it does not
   need replicates to have power, and its bar is `Tr == 0` rather than a
   count of clean runs.

### ARM B MEASURED: the pre-scan costs 0.03% where the hold cost 40.7%

`78f3f5eec8` / apk `ba4d5d52987e`, **nova**, `disc_id = Texture border`, 10
runs, `progress_log_proof` on every one, `bound=2` on every `fifoskew` line.
Pooled over 47 windows and 149.8 s of wall clock: **148,706 submissions.**

| leg | measured | bar | |
|---|---|---|---|
| **V2** `held(n)/kicks` | **0.0370** (5,506 of 148,706) | ≤ 0.05 | **HOLDS** |
| **V3** `scan(ns=)` / wall clock | **0.0303%** (45.4 ms over 149.8 s) | < 2% | **HOLDS** |
| **V5** `(wrap+big)/held(n)` | **0.0400** (220 of 5,506) | < 0.20 | **HOLDS** |
| **V6a** `draw+nodraw+wrap+big == scan_n` | 47 of 47 windows exact | exact | **HOLDS** |
| **V6b** `held(n) == draw+wrap+big` | 45 of 47 windows exact | exact | **FAILS** |
| **V4** `gave/held(n)` | **0.07374** | ≥ 0.00674 | **HOLDS** |
| **V1** `stale_px == 0` on 10 of 10 | 0 on 10 of 10 | — | **VOID** (V0) |

**The pre-scan does not cost what the hold cost, and the margin is not
marginal.** Mode 1's guest sat blocked for **40.7%** of wall clock at a mean
hold of 2,245,410 ns. Mode 2's scan costs **0.0303%** — a mean of **306 ns
over 252 words**, about **1,340× cheaper** than the thing it replaces. That
was the brief's first question and it is answered: the cost was removed, not
moved.

**The budget was nearly reached, and it is a good thing it is counted.** The
worst single scan walked **16,038 words against the 16,384 budget** — 98% of
it — in a boot window, and `big` fired 20 times over the arm. Had budget
exhaustion been a silent fall-through to holding, that window would have read
as the mechanism working. It is 4.0% of holds (V5), so the fallbacks are not
carrying the guarantee, but the headroom is thinner than the 2× the constant
was sized for and a busier title may sit on it.

### The 826:1 sizing was wrong, and by 30×

The brief sized this change at "148,704 submissions for 180 draws", an 826:1
reduction. **The measured reduction is 27.0×**, because **5,286 submissions
publish a draw, not 180.** The 180 figure is the draw count of the *measured
test*; the run also boots, runs the dashboard, and executes the other
seventeen tests, and every draw in all of that is a draw the bound must
cover.

This does not weaken the change — 27× at 0.03% scan cost is the whole result
— but it does mean **any per-draw arithmetic taken from "180 draws" is wrong
by about thirty times**, including the "826 holds for every one the invariant
needs" line elsewhere in this document, which should read **27**.

### V6b FAILED, and the failure is the instrument's granularity, exactly as predicted

Two of 47 windows violate `held(n) == draw + wrap + big`. They are
**adjacent windows of one run, off by −1 then +1**, and they cancel. Pooled
over the arm the identity is **exact: 5,506 == 5,286 + 200 + 20.**

The cause is structural and benign: `fsk_note_scan` is called *before*
`pfifo_bound_skew` runs, so a window dump firing between the two puts one
submission's scan in window N and its hold in window N+1. This is `AGENTS.md`
verbatim — *"an identity that holds exactly tells you the two sides are read
at the same instant; one that holds to ±1 tells you they are not, which is
information about the instrument rather than noise"* — and the ∓1 in adjacent
windows **proves** the split rather than suggesting it.

Registered as a per-window identity, so it **fails as registered** and is
reported as failed. The one-line repair is to note the scan after the hold
returns rather than before; it is **deliberately not applied**, because the
cost and Crimson arms are queued against refs that would be invalidated by
it, and a ∓1 window artefact that pools exactly does not justify disturbing
them.

### V4: the hole MOVED rather than shrinking, as registered

| | mode 1 | mode 2 |
|---|---|---|
| `gave` / all submissions | 1,002 / 148,704 = **0.674%** | 406 / 148,706 = **0.273%** |
| `gave` / **covered** submissions | 0.674% (all were covered) | 406 / 5,506 = **7.374%** |

**As a fraction of what the bound actually covers the hole is 10.9× larger**,
which is what V4 predicted and why it was registered on the new denominator:
a draw-publishing submission is precisely the one a flip follows, so
selectivity concentrates the hole instead of diluting it. The absolute rate
did fall 2.5×, and quoting only that would have been the misleading half.

So the honest scope of mode 2, stated against mode 1's:

> Mode 1: the race is impossible on **99.326%** of all submissions.
> Mode 2: the race is impossible on **92.6% of draw-publishing
> submissions**, and those are the only ones that can carry it.

Mode 1's headline is the larger number and is **not** the stronger
guarantee per draw, because its own `gave` events were presumably
concentrated on the same draw-carrying submissions — it simply never split
the counter to find out. That is what `gaveby(...)` is for, and it is in the
cost and Crimson refs rather than this one.

`spun`/`slept` came back **2,386 / 3,120** — 43% caught by the 60 µs spin,
against mode 1's 9.6%, because a mode-2 hold waits for a much shorter queue.

## MEASURED: selectivity buys NOTHING on a real title, and the premise is refuted

Galleon, 240 s, **nova**, `--who draw-only-cost`. Arm A `5cfc236d9b` / apk
`4509eeeb11c7` (mode 0) ×2; arm B `d879e6e03b` / apk mode 2, run 1 of 2.

| | arm A run 1 | arm A run 2 | **arm B run 1** | mode 1 (published) |
|---|---|---|---|---|
| `bound=` | 0 | 0 | **2** | 1 |
| `gfps` p90 | **29** | **29** | **13** | 13 |
| `gfps` max | **29** | **29** | **15** | 15 |
| `held(n)/kicks` | 0 | 0 | **0.9481** | 1.0000 |
| hold mean | — | — | **2,316,996 ns** | 2,245,410 |
| `behind` | 100.0% | 100.0% | 100.0% | 100.0% |

| leg | measured | bar | |
|---|---|---|---|
| **W1** `gfps` p90 / max fall | **16 and 14** | ≤ 2 | **FAILS** |
| **W2** `held(n)/kicks` | **0.9481** | ≤ 0.20 | **FAILS** |
| W3 `scan(ns=)` / wall clock | 0.0173% | < 2% | **HOLDS** |
| W4 `big/scan_n`; `wmax` | 0.00004; 16,038 | <0.05; <16,384 | **HOLDS** |
| **W5** `gave/held(n)` | **0.05910** | > 0.05603 | **HOLDS** |
| **W8** `gaveby(flip)/gave` | **0.0016** | ≥ 0.50 | **FAILS** |

**Mode 2 costs exactly what mode 1 cost.** p90 29 → 13 and max 29 → 15,
against mode 1's 29 → 13 and 30 → 15 on the same title, device and duration.
The hold mean is 2,316,996 ns against mode 1's 2,245,410. **Selectivity
recovered none of the throughput.**

### Why, and it is the brief's sizing being a property of the test disc

**94.8% of Galleon's submissions carry a draw** — `draw = 42,980` of 45,334.
The `Texture border` disc's figure is **3.6%**.

So the premise *"a submission carrying no draw adds no draw, and most
submissions carry no draw"* is **true of a pgraph test disc and false of a
real title.** A disc submits 27 times more often than it draws; Galleon
submits **1.05 times** per draw. It publishes roughly one draw per
submission, which is what a game doing ~187 draws a second at ~189
submissions a second looks like.

**And the scan is not the cost — that part of the design is vindicated.** It
costs **0.0173%** of wall clock at a mean of 923 ns over 3,226 words
(12.8× the disc's segment size, still trivial). W3 and W4 hold, the budget is
barely touched (`big = 2`), and the identities hold. The implementation does
what it was designed to do. **The thing it was designed to exploit is not
there on a real title.**

Which means the conclusion is about the guarantee and not about this patch:
**"no unprocessed draw sits in the FIFO while the guest runs" is intrinsically
as expensive as mode 1 on a draw-dense workload**, because there every
submission has a draw and no selection rule can skip one. The cost is a
property of the invariant, not of how cheaply you detect draws. No further
tuning of this mechanism reaches it.

### W8 FAILED and it INVERTS the published attribution of the hole

`gaveby(flip=4 nop=2534 ctxsw=1 noaccess=0 other=1)` — sum 2,540, matching
`gave` exactly.

**99.8% of the releases are `waiting_for_nop`. Four of 2,540 are the flip.**

This document's C5 registered, and its verdict section published, the opposite:
*"`gave` is 5.603% on Galleon against 0.674% on the test disc, **because
Galleon flips every frame** and the guarantee genuinely does not hold across a
flip stall."* The rate was right and **the attribution was wrong.** It is the
**NOP acknowledgement handshake**, essentially never FLIP_STALL.

That is exactly what one counter over four reasons cannot tell you, and why
the split was the named next step. It also redirects the residual: a flip
stall clears only when a VBLANK fires and is arguably unclosable, whereas the
NOP handshake is a different mechanism with its own timing, and **whether it
is reachable is now a question someone can ask.**

`W5` holds at 5.910% of covered submissions — and `gave/kicks` is **5.603%**,
matching mode 1's Galleon figure to five figures, because with 94.8% of
submissions held the two denominators are nearly the same population. So on
this title the hole neither moved nor shrank; it is the same hole, now
correctly attributed.

### The trade, handed over with both numbers

- **Mode 2 is correct and cheap to evaluate**: the scan costs 0.03% on a disc
  and 0.017% on a title, the identities hold, the budget holds, and mode 0
  pays nothing at all (`scan(ns=) = 0`, ceiling unchanged from the
  pre-change arm).
- **Mode 2 is not cheaper than mode 1 where it matters.** On a pgraph disc it
  holds 27× less often; on Galleon it holds 1.05× less often and costs the
  same half of the frame-rate ceiling.
- **So it does not ship on**, and the reason is now a measurement rather than
  a caution. `XEMU_OPT_FIFO_SKEW_BOUND` stays 0.
- **What survives are two candidates, and reading the source changed which
  one is first.** Both are read-side and neither scales with draw density,
  which is the property that defeats everything else here.

  **(a) Release the guest when the draw's READS are done, not when DMA_GET
  reaches DMA_PUT.** This is the cheaper idea and it keeps the guarantee
  intact, because the guarantee is about the *reads*, and `DMA_GET ==
  DMA_PUT` is a much stronger proxy than it needs to be: it waits for the
  whole segment to drain when all that matters is that
  `get_texture_layout` and `sync_vertex_ram_buffer` have run. The hold mean
  is **2,316,996 ns** against a PFIFO service time of ~160 µs per
  submission, so **most of that hold is queueing behind work the guarantee
  does not care about.** A signal raised once a draw's guest-memory reads
  have completed would release the guest far earlier for the same
  invariant. It is entirely inside this lane's files.

  **(b) Re-upload on detection, and the detection ALREADY EXISTS.** I had
  written this up as "trap the guest's store", which is wrong about what is
  needed: `memory_region_set_log(d->vram, true, DIRTY_MEMORY_NV2A)` and
  `_NV2A_TEX` are **already enabled** (`nv2a.c:1283-1284`), and
  `pgraph_vk_poll_bound_textures` already test-and-clears the TEX bits at
  the top of `begin_pre_draw`. **`Tr` is that bit being set again before the
  window closes — so the emulator already knows, 61.7% of the time, that it
  read a texture the guest was writing.** No page protection and no store
  trapping is required. What is missing is not detection, it is a
  **response**: re-consume the bit and re-upload before the draw proceeds.

  The honest caveat on (b), and it is the one #44's own standard imposes: a
  bounded retry **reduces** the window rather than eliminating it, and this
  document is explicit that *"make it rarer" and "fix it" are
  indistinguishable at n=10*. At a 61.7% per-window race rate a retry
  converges slowly unless the re-read window is much tighter than the
  original — which is plausible but unmeasured. So (b) is a mitigation until
  someone measures the per-retry rate, whereas (a) is a cost reduction on a
  guarantee that already holds. **(a) first.**

### CONFIRMED on two runs per arm, and the reproducibility is the point

| | A r1 | A r2 | **B r1** | **B r2** |
|---|---|---|---|---|
| `gfps` p90 / max | 29 / 29 | 29 / 29 | **13 / 15** | **14 / 24** |
| `held(n)/kicks` | 0 | 0 | **0.9481** | **0.9493** |
| draw density | — | — | **94.18%** | **94.30%** |
| `gave/held(n)` | — | — | 0.05910 | 0.06010 |
| `scan(ns=)` / wall | — | — | 0.0173% | 0.0169% |
| hold mean | — | — | 2,316,996 | 2,335,808 |

**Every quantity reproduces to better than 1% between the two arm B runs**,
which matters because three legs today failed on run-to-run spread. The draw
density — the number the whole change turns on — is 94.18% and 94.30%. This
is not a noisy measurement that happened to come out badly.

**Worst-case W1: p90 29 → 13 (fall 16) and max 29 → 15 (fall 14)**, against a
bar of 2. **W2: 0.9493** against 0.20. Pooled, **86,142 of 90,804 submissions
held (94.87%)** and **85,572 of 90,804 carried a draw (94.24%)**.

**W8 pooled: `flip=9, nop=5,121, ctxsw=2, noaccess=0, other=2` of 5,134.**
The NOP handshake is **99.75%** of the hole and the flip is **0.18%**. Run 1's
inversion was not a fluke.

And `other = 2 of 5,134` — **0.04%** — so the 250 ms backstop essentially
never expires. The residual is almost entirely a **protocol** stall rather
than a performance one, which is the distinction the split was built to make:
it cannot be tuned away, because the pusher is waiting for something only the
guest can supply.

### A stronger statement of "free when off" than I first made

Arm A's `scan_n = 0`, not merely `scan(ns=) = 0`. Mode 0 returns from
`pfifo_kick` **before** the scan is reached, so the machinery is not cheap —
it is **not executed**. With `gfps` p90 29 / max 29 matching the pre-change
arm on both runs, adding this code costs a defaulted-off build nothing that
any instrument here can see.

### One process note, because it nearly produced a wrong number

Both of my first two attempts to pool these figures used a **hand-rolled
regex in a scratch script**, and on one run it silently matched nothing —
surfacing as a `ZeroDivisionError`, which is luck, because the same failure
one column over would have printed a plausible figure. The committed reader
parses **121 of 121 lines on all four runs**. `orchestration.md` already says
this — *"do not hand-roll the comparison; use the tool, or check what the tool
checks"* — and it is the second time in one session that a reader was the
thing at fault rather than the data.

### CRIMSON ARM A: the race is LIVE at this tip, at 61.7%, and that settles the disc question

`5cfc236d9b` / apk `4509eeeb11c7`, **nova**, Crimson Skies, 240 s, mode 0 —
run 1 of 2.

```
Tr = 11,829 / 19,167 / 23,859      raced/uploads = 0.6172
Vr = 0 / 3,040                      the vertex site is clean
Xd = 0                              the impossible row
```

**61.7% of texture uploads raced** — a bound texture's dirty bit consumed by
an upload and set again before the `begin_pre_draw` window closed. That is
#44's mechanism read from the other side, and it is **higher** than the
published baseline of 0.5661 / 0.5672 (measured at `e353735028`, a ref that
does not contain `cdd8dc4c89`).

**L5 PASSES — `Tr > 0` — which is the arm-A gate my registered prediction
omitted.** So unlike the disc pair, **this pair can discriminate.** The judge
supplied the gate the prediction should have carried, and it reads the right
way round.

### Which retires the hypothesis the n=6 write-up floated

That write-up guessed the `Texture border` flake was receding because
`cdd8dc4c89` (#56's stale-binding fix) had closed the race. **It has not.**
The race is live at 61.7% on a real title at the *same ref* those disc runs
used. So:

- **The disc's 2-in-10 is a weak observable, not a fixed defect.** The two
  readings are consistent — a disc whose eighteen draws sit in one frame is
  simply a poor detector of a race that a flipping title exhibits on three
  fifths of its uploads.
- **The n=6 retraction was doubly right to retract.** Not only was five zeros
  too few to conclude from; the conclusion itself was false.
- **`Tr` is the instrument this issue should have been using.** It is a rate
  over 19,167 uploads in one 240 s run, reproducible to 0.2% across runs,
  against a per-run coin flip that needs 20–30 replicates to have power. It
  also carries its own impossible row and a clean negative control at the
  vertex site (`Vr = 0` over 3,040 copies, bounding that rate at ≤9.87e-4).

**The vertex site being clean is worth stating separately**, because it is the
falsifier this document already answered from #39's hashes and now has a
second, independent measurement for: `Vr = 0/3,040`. Vertex data is read from
guest RAM at the same point by the same thread, and it does not race here.

### Arm A on two runs: `Tr` reproduces to 0.26%, and #56's fix INCREASED the exposure

| | run 1 | run 2 | spread |
|---|---|---|---|
| `Tr` raced | 11,829 | 11,866 | 0.31% |
| `tex_uploads` | 19,167 | 19,176 | **0.05%** |
| **rate** | **0.6172** | **0.6188** | **0.26%** |
| `Xd` | 0 | 0 | — |

**That is the best-behaved device measurement in this investigation.** A rate
reproducible to 0.26% and a denominator to 0.05%, from two 240 s runs — against
a `stale_px` observable that needs 20–30 runs per arm to separate 0.2 from 0.6.
L5 passes 2 of 2.

And against the published baseline at `e353735028`:

| | `Tr` | `tex_uploads` | rate |
|---|---|---|---|
| `e353735028` (published) | 7,061 / 7,113 | 12,474 / 12,540 | 0.5661 / 0.5672 |
| **`5cfc236d9b` (here)** | **11,829 / 11,866** | **19,167 / 19,176** | **0.6172 / 0.6188** |

Both pairs are internally reproducible to ~0.3%, and the two refs differ by
**9% in the rate and 53% in the uploads** — far outside either pair's spread.
So this is a real difference between refs, not noise.

**The likely mechanism runs opposite to the guess my n=6 write-up made, and it
is a cross-lane finding rather than a curiosity.** `e353735028` lacks
`cdd8dc4c89`, #56's stale-binding fix. That fix stops `create_texture` from
stamping `tex_reg_cache[i]` with registers a *failed* bind never honoured
while clearing `texture_dirty[i]` — so textures that were previously left
wrongly marked clean **now get re-uploaded**. More uploads happen: **+53%**.
And an upload is precisely what is exposed to the skew, so races rise **+67%**
in absolute terms and the *rate* rises 9%.

Stated as strength: the direction and the magnitudes are consistent with that
mechanism and I have not isolated it — two refs 128 commits apart is not a
bisection. But it inverts the intuition worth carrying: **fixing the
missed-re-upload half of #44 does not hide the skew half, it exposes more of
it**, because the skew can only lose a race on an upload that actually
happens. The two mechanisms were never additive, and they are not
independent in this direction either.

### CRIMSON ARM B: `Tr` goes to EXACTLY ZERO, and the cost is not there

`d879e6e03b` / apk `b87d7d112dc7`, **nova**, mode 2, run 1 of 2.

```
arm A   Tr = 11,829 / 19,167    rate 0.6172
arm A   Tr = 11,866 / 19,176    rate 0.6188
arm B   Tr =      0 / 13,751    rate 0.0000        Xd = 0
```

**X1 HOLDS, and the bar was exactly zero rather than "smaller".** That
distinction is the whole reason the leg was written that way: `Tr` fell is
satisfiable by any perturbation of timing, and against a baseline reproducible
to **0.26%** a perturbation would have moved the rate, not annihilated it.
**Zero over 13,751 uploads is the race being made impossible on the covered
path, measured on a title that flips every frame.**

So the selective bound **does close #44 on a real title.** The disc pair could
not show that — V0 voided it — and this is the instrument that could.

### And the cost is title-dependent, which contradicts what I expected

| | arm A r1 | arm A r2 | **arm B r1** |
|---|---|---|---|
| `gfps` p90 / max | 34 / 37 | 31 / 37 | **31 / 34** |
| `held(n)/kicks` | 0 | 0 | **0.7026** |
| guest blocked | ~0% | ~0% | **~30.7% of wall clock** |
| hold mean | — | — | **4,031,642 ns** |

**p90 falls by 0 and max by 3** — against Galleon's falls of **16 and 14** in
the same mode. I predicted X5 would fail as W1 did; on this title it very
nearly holds. (The judge correctly refuses to render leg 6 with one run per
arm: *"noise floor not measured"*. Run 2 decides it.)

The guest is blocked **30.7%** of wall clock here at a hold mean **74% larger**
than Galleon's, and the ceiling barely moves. **So the cost of this bound is
not a property of the bound — it is a property of whether the guest CPU thread
is the title's critical path.** Galleon's is (83% busy, per
`frame-pacing-and-parallelism.md`); Crimson's evidently is not. That is a
materially different conclusion from "mode 2 costs what mode 1 costs", which
was drawn from one title.

### `gave` OVER-COUNTS THE HOLE, and `Tr` is what proves it

`gave/held(n) = 0.4144` on this arm — **41.4% of covered submissions were
released with pushbuffer still outstanding**, against Galleon's 5.9%.
`gaveby(flip=462 nop=7,100 ctxsw=1 noaccess=0 other=1)` — the NOP handshake
again, at 93.9%.

**And `Tr` is nevertheless zero.** Those two facts are only compatible one
way: **`gave` counts "released with PUSHBUFFER outstanding", not "released
with a DRAW outstanding".** The pusher parks on `waiting_for_nop` at a NOP
method, which in a normal command stream comes *after* the draw it follows —
so the draw has already been consumed, its texture already read, and the
guarantee already satisfied, at the moment `gave` fires.

So `gave` is a **conservative upper bound on the hole, and a loose one**: 41.4%
of holds were incomplete by its definition and 0% of uploads lost a race.
Every leg I built on it — V4, W5, X4 — is therefore measuring a proxy that
over-reads, and all three "held" in the direction of *more* hole than exists.

**That is the third time today a proxy leg has been contradicted by a direct
counter**, after #65's E1 (exceedance windows) against E2 (`clamp=`), and
`fifo_skew_report`'s frozen sample against the live line. The pattern is now
explicit enough to state as a rule: **when a direct counter for the mechanism
exists, register the leg on the counter and use the proxy only for
direction.** `Tr` is the counter here; `gave` is the proxy.

*Crimson arm B run 2 to follow; it decides X5 and gives leg 6 its noise
floor.*

## Does #39 share the class? The falsifier is already answered, in the negative

#44 handed #39's lane a falsifier nobody had run: **does a lost quad's region
match a *later* draw's data, rather than being merely absent?** The reasoning
was that vertex data is read from guest RAM at the same point, so the same
skew would hand a draw its successor's vertices, and degenerate vertices
present as a lost draw.

The premise is right — `sync_vertex_ram_buffer` reads guest RAM on the PFIFO
thread, synchronously with the method, exactly like the texture path. **But
the falsifier is already answered on #39's own thread, by a measurement taken
for a different purpose.** Its 2026-09-12 comment reports, per draw, between a
passing and a failing run:

> vertex data offsets *and* content hashes … All identical. The three quads
> each get their own page, each uploaded then bound in order, same hashes both
> runs. So the vertex path is exonerated along with everything else.

Those hashes are taken at the emission point — that is, at the moment of the
read. If a failing run had read the successor's vertices, the hash would have
differed. It did not, on any draw, in either run. **So the vertices `pgraph`
read for #39's lost draw were the right ones, and the skew mechanism is
refuted for that defect** without spending a device run.

What is *not* answered is the other half of the original question: whether the
lost quad's **region** holds a later draw's output. That is a statement about
the rasterised result rather than about the data fetched, it needs captures
this lane does not have, and it belongs to the lane that owns #39.
`hw/xbox/nv2a/pgraph/gl/*.c`, `target/**`, `ui/**` and the desktop build are
that lane's; nothing here touches them.

Two further notes for whoever picks it up, both from reading rather than
measuring:

- #39's own numbers already point away from a submission-order race: every
  intervention behaves like a timing knob (3/10 baseline, 2/22 with
  `LP_NUM_THREADS=1`, 1/12 single-threaded guest, **0/20** with an uncached
  read added to the mirror write path, **0/7** with the validation layer on)
  and none of them is the pushbuffer.
- The `NUM_SUBMIT_FRAMES` finding on that thread — a compile-time 3 that
  segfaults immediately at 2 — is a separate, deterministic defect and is
  recorded there, not here.

## MEASURED, #54 lane: lever (a)'s premise is REFUTED and its ceiling is 38-47%

The handover at `dce367ca62` put "release the guest when the draw's READS are
done" first, on this reasoning: *"Measured hold mean is 2,316,996 ns against a
PFIFO service time of ~160 µs per submission, so MOST OF THE HOLD IS QUEUEING
behind work the guarantee does not care about."*

**The ~160 µs is not Galleon's service time, and the error is this document's
own 826:1 mistake in a second place.** It was derived at line 424 as the PFIFO
thread's busy fraction divided by a submission rate:

    160 µs  =  48%  /  3,000 submissions/s

The **48% is Galleon's** PFIFO busy fraction (`frame-pacing-and-parallelism.md`,
the gameplay-load column). The **3,000/s is the `Texture border` test disc's**
steady-window submission rate — this document, line 236: *"148,667 (1,022/s
pooled; 2,000-3,300/s in steady windows)"*. **Galleon submits at 257/s (arm A)
and 181/s (arm B)**, which is the same table the hold mean was read from.

So the figure divides a title's numerator by a test disc's denominator. Redone
with both halves on Galleon:

| | service time per submission | hold mean / service |
|---|---|---|
| as briefed (48% / 3,000·s⁻¹, disc rate) | 160 µs | **14.5x** |
| **corrected, arm A rate (48% / 257·s⁻¹)** | **1,868 µs** | **1.24x** |
| **corrected, arm B rate (48% / 181·s⁻¹)** | **2,652 µs** | **0.87x** |

**The hold is approximately ONE submission's service time. There is no queueing
term for lever (a) to remove**, and two independent confirmations sit inside
this document already:

- **The blocked fraction equals the busy fraction.** This document's own
  pre-registered arithmetic (line 425) said the guest would spend "roughly the
  PFIFO thread's busy fraction" blocked, predicted ~48%, and measured **40.7%**
  — celebrated at line 587 as the cost being *understood rather than merely
  observed*. If the hold were 14.5 service times, the blocked fraction would
  have to exceed 100%. 40.7% against 48% is the signature of hold == service,
  queueing == 0.
- **The bound prevents the backlog it would queue behind.** Lines 412-413:
  *"with the bound in force the backlog is never allowed to form"*, and
  `held(n)/kicks = 1.0000`. A backlog that never forms cannot be queued behind.

This refutes the *reason* given for (a), not (a) itself. The correct premise is
different and narrower: the hold is one submission's service, and (a) recovers
whatever share of that service happens **after** the draw's guest-memory reads.
That share is measurable, and it had not been measured.

### The ceiling, from an instrument that already existed

No new device run was needed. `NV2A_PERF_LOG` builds already emit a
`hakuX-phase` line carrying every sub-phase of the PFIFO thread's frame, and
two **Crimson Skies** captures were already on disk at
`/home/justin/hakux-work/perf/instr{1,2}.log` — the same title `Tr = 61.7%` was
measured on. 46 samples over two runs, read by
`docs/testing/phase_read_split.py`.

The decomposition is taken from the source, not from the field names, and it
closes exactly:

    BUSY = Surf + Draw + Fin
    Draw = Vtx + Syn + Prw + Pipe + Desc + Setup + Cmd + unclassified
    Pipe = Tx + Sh + Lu + Shd

    READ (the guarantee applies)   Surf, Syn, Tx  [+ Vtx, Prw conservatively]
      Syn   sync_vertex_ram_buffer      reads guest vertex RAM
      Tx    pipe_bind_tex               fast_hash(vram) AND get_texture_layout(vram)
      Surf  surface_update              pgraph_vk_upload_surface_data reads guest mem
    POST-READ (no guest read)      Sh, Lu, Shd, Desc, Setup, Cmd, Fin

`READ + POST + unclassified == BUSY` holds with a worst residual of **0.20 ms**
and a mean of **0.089 ms**, which is the one-decimal print rounding over eight
terms. That identity is the check that the parse is right.

| Crimson Skies, pooled 46 samples | ms/frame | share of BUSY |
|---|---|---|
| BUSY (nv2a.pfifo_thread) | 19.62 | 100% |
| Idle (waiting for work) | 16.59 | — |
| **READ, conservative** | **10.40** | **53.0%** |
| READ, generous | 9.67 | 49.3% |
| **POST-READ — lever (a)'s ceiling** | **7.36** | **37.5%** |
| unclassified inside `draw_dispatch` | 1.78 | 9.1% |

**So lever (a)'s ceiling is 38-47% of the PFIFO thread's busy time**, the
bracket being whether the unclassified `draw_dispatch` remainder is read-side or
not. Per run: instr1 `[34.6%, 44.4%]`, instr2 `[40.3%, 48.7%]` — reproducible
to about ±3 points, which is smaller than the effect.

**The other half is irreducible.** 49-53% of the hold is the guest-memory reads
themselves, which is exactly what the guarantee is about; no release-point
change can reach it. "Most of the hold is queueing" is refuted and replaced by
"about half the hold is the reads".

### And the read side is the DECISION, not the upload

The single largest read-side term is `Tx` — `pipe_bind_tex`, which wraps
`pgraph_vk_bind_textures` — at **5.85 ms/frame, 29.8% of the whole PFIFO busy
time.** The actual texture upload, `Tex` (`texture_upload_ns`, set inside
`upload_texture_image`), is **0.01 ms/frame**, with `TexU` at 1-2 cache fills a
frame.

So the emulator spends order **500x longer deciding whether to upload a texture
than uploading one**, and that decision is on the #44 critical path because
`create_texture` hashes guest VRAM to make it (`vk/texture.c:1953`,
`fast_hash(texture_data, texture_length)`, gated on `possibly_dirty`).

**Stated as strength: `Tx = 5.85 ms` is MEASURED; the hash's share of `Tx` is
NOT.** `pipe_bind_tex` also covers `resolve_possibly_dirty_textures`, the
eight-register comparison fast path and the LRU lookup. Attributing it to the
hash is an inference inside a model nobody has measured, which is the failure
this file records under "An inference can be valid and still wrong". The
measurement that settles it is one timer pair around the two `fast_hash` calls
in `create_texture`, in this lane's own file, needing no other lane.

### Two defects in the phase instrument, found by running it against real data

Both were found by asserting the emitter's own identities rather than trusting
the field names, with `docs/testing/phase_read_split_check.py`:

- **`Tot` double-counts its nested phases.** `profile.c:97` sums
  `surface_update + texture_upload + shader_compile + draw_dispatch + finish +
  flip_idle + fifo_idle`, but `texture_upload` is inside
  `pipe_bind_tex ⊂ draw_pipeline ⊂ draw_dispatch`, and `shader_compile` is
  inside `draw_pipeline` too. The proof is exact rather than argued: on the one
  sample with `Shd:2.9`, `Pipe:7.3` against `Tx:3.2 + Sh:1.0 + Lu:0.2 = 4.4`
  leaves **2.90**, matching `Shd` to the printed digit. Immaterial in
  steady-state gameplay (`Tex` and `Shd` are ~0), and **not** immaterial on the
  load screen `performance-next-three.md` flags, where 50-200 fills a frame
  would inflate `Tot` by exactly the upload time. `BUSY` above is defined as
  `Surf + Draw + Fin` to avoid it.
- **`Syn` covers 4 of the 9 `sync_vertex_ram_buffer` call sites.** The
  `draw_vtx_sync` timer is opened at only two places (`vk/draw.c:6560` and
  `:6686`), bracketing the calls at 6567/6571 and 6693/6697; the five at 4604,
  4674, 4992, 5138 and 5142 are untimed. So the measured READ side is an
  **under**-estimate and `POST / BUSY` is an **upper bound** — which is the
  safe direction for the conclusion here, since the claim is that (a) can buy
  *at most* 38-47%. A Galleon measurement should either widen the timer or
  quote the ceiling as a bound, and say which.
- **Every field is an EWMA, not a frame.** `SMOOTH_MS` is
  `dst = 0.8·dst + 0.2·src`, so a printed line is a ~5-frame smoothed estimate,
  and the line is emitted once per 60 frames. Means and shares are unaffected
  (smoothing is linear), but **min/max understate the true per-frame spread**,
  and `Fin` vs `Sub + Fen` cannot be expected to close exactly because each is
  smoothed separately — which is why that identity residual sits at a steady
  0.2-0.3 ms and is not a parse fault.

### What this makes of (a), given Crimson arm B

Arm B lands while this was being written and it reorders the question rather
than answering it. The selective bound already costs **`gfps` p90 −0, max −3 on
Crimson Skies** while taking `Tr` to exactly zero. So on Crimson there is no
cost for (a) to recover, and **the ceiling measured above is measured on the
title where the lever has nothing to buy.**

The cost exists on **Galleon** (p90 29 → 13), whose guest CPU thread is the
critical path at 83% busy. **The post-read share on Galleon is unmeasured**, and
this document's newest rule — *one title cannot establish a cost* — applies to
my figure exactly as it applied to the one it corrects. Quoting 38-47% as
Galleon's would repeat the error at the top of this section.

So the cheapest measurement that decides (a) is: **one Galleon soak on a
`-Pperflog=true` APK, and read `hakuX-phase` with
`docs/testing/phase_read_split.py`.** No new instrument, no prediction to
register (it is a survey, `--no-expect`), one device slot. The leg worth
registering afterwards is an absolute, not a fall: *the post-read share of
`BUSY` on Galleon is at most X%*, because that share caps (a) whatever the
baseline does.

Two things stand in the way of it being free, and both are recorded rather than
worked around: `HAKUX_PERF_LOG` is reachable only as a Gradle property
(`android/app/build.gradle.kts:52`, `-Pperflog=true`), and `dispatcher.sh:164`
builds with a bare `./gradlew assembleDebug`, so **no request can ask for a
perf build today**. And the profiler *"puts a clock read around every method in
the puller and so changes the number it is measuring"* (`profile.c`'s own
comment), so it perturbs absolutes — a share of `BUSY` is the right form to
quote from it, and an absolute ms figure is not.

### Lever (a) is NOT inside this lane's files, and the brief says it is

Stated because the brief and the wave-19 territory note both assert *"entirely
inside this lane's files"*, and that is checkable in one grep:

| what (a) needs | where it lives | mine? |
|---|---|---|
| the wait to release early | `pfifo_bound_skew`, `pfifo.c:882-1000` | **no** — lane.pacing |
| `sync_vertex_ram_buffer`, the vertex read | defined `vk/draw.c:5765`, 10 call sites in `vk/draw.c` | **no** |
| `begin_pre_draw`, the texture read window | defined `vk/draw.c:3666`, 9 call sites in `vk/draw.c` | **no** |
| `get_texture_layout` | `vk/texture.c:221` | yes |
| `pgraph_vk_poll_bound_textures` | `vk/texture.c:591` | yes |

The signal's *raise* point is reachable from `vk/texture.c`, because at every
call site `sync_vertex_ram_buffer` precedes `begin_pre_draw`. Its *wait* is in
`pfifo.c` and the conjunction "both reads done for this draw" can only be
observed in `vk/draw.c`. So (a) is a three-territory change, not a one-file one.

### What of lever (b), and the two claims in it that are true

Both verified from source rather than taken on the handover's word:

- `check_texture_dirty` (`vk/texture.c:534`) really is a test-and-clear:
  `memory_region_test_and_clear_dirty(d->vram, ..., DIRTY_MEMORY_NV2A_TEX)`.
  **So (b)'s "the detection already exists" is correct**, and no page
  protection or store trapping is required.
- The granularity is **whole 4 KiB pages** — `TARGET_PAGE_ALIGN(addr + size)`
  and `addr &= TARGET_PAGE_MASK` — which this lane was told to establish for
  itself rather than inherit from #68/#69/#73, and it holds. Every `Tr` count is
  therefore an upper bound on byte-level overlap, as `vk/draw.c` already says.

### A retraction of my own, before it was published as a finding

Reading `create_texture` showed the content hash and the upload are **two
separate reads of the same guest range**: `fast_hash(texture_data, ...)` at
`vk/texture.c:1953`, then `get_texture_layout` re-deriving
`vram_ptr + texture_vram_offset` and reading it again at line 651, with
`snode->hash = content_hash` stamped at 2020 from the *first* read. Under a
61.7% race that is a cache recording `hash(bytes at T1)` beside an image built
from `bytes at T2`.

**My first reading was that this makes a torn texture PERMANENT, and it is
wrong.** Traced through: a tear means a guest store landed after the poll's
test-and-clear, so the page bit is set again — which is precisely what `Tr`
counts — so the next frame's `poll_bound_textures` re-marks the binding,
`possibly_dirty` is true, the hash is recomputed over the settled content,
compares unequal to the stored torn hash, and the texture is re-uploaded. It
self-corrects on the following frame.

What the double read actually produces is **spurious re-uploads** — the stored
hash need not match the settled content even when the upload was clean — which
is a cost, in the same direction as the measured +53% uploads, not a wrong
pixel. Recorded because the wrong version would have read as a mechanism for
#44's permanence, and because it explains why #54's race gives a one-frame tear
on a flipping title and a captured defect on a disc whose eighteen draws sit in
one frame: the observable, again, rather than the defect.

### WHAT THIS SURVEY'S INSTRUMENT CANNOT SEE, written before the run

`--perflog` landed at `c1300aa3fa`, so the binary side is solved and the cache
key carries the variant. **The capture side is not**, and the failure mode is
the same empty read from a different cause — which matters because the obvious
diagnosis would be the cache key that was just fixed.

    run_perf.sh:84     logcat -d -s hakuX-perf hakuX-phase xemu-gpu xemu-work hakuX-cpu
                       ^ the spec that produced instr1/instr2, and it NAMES the tag

    soak_title.sh:32   LOGCAT_SPEC="... hakuX-perf:I hakuX-pages:I hakuX:W ... *:S"
                       ^ the dispatcher's soak spec. hakuX-phase is ABSENT, and
                         `*:S` silences every tag not listed.

    dispatcher.sh:294  passes SERIAL, CAPTURE_LOG, PULL_GLOB, PULL_DEST,
                       AUDIO_CAPTURE_MB -- and NOT LOGCAT_SPEC, so the default
                       above applies.

So the prediction for this survey, stated so it is falsifiable rather than
argued: **`grep -c hakuX-phase` on the result's `logcat.txt` will be 0, while
`grep -c hakuX-perf` will be non-zero.** If instead the phase lines are there,
this blocker is refuted and the measurement is in hand — which is the only
reason to spend the slot rather than merely filing the claim. Three blockers in
this campaign were false, and the cheap refutation is to run it.

**The three-way discriminator, because an empty read is otherwise ambiguous.**
`hakuX-perf` (the `gfps=` pacing line) is `#ifdef __ANDROID__` only, while
`hakuX-phase` is `#if defined(__ANDROID__) && NV2A_PERF_LOG` — so the pacing
line is present in *every* build and is the control:

| `hakuX-perf` | `hakuX-phase` | what it means |
|---|---|---|
| present | present | a real measurement |
| **present** | **absent** | **the capture FILTER dropped it, or the APK was not the perflog variant** |
| absent | absent | the soak produced nothing — boot failure, guest never rendered |

The middle row is further split by the APK's own identity, which the dispatcher
now records: the build log is `build-$sha-perflog.log` and the served path ends
`-perflog.apk`, and `apk_sha` is a sha256 of the file, so a perflog APK cannot
be confused with a normal one of the same ref. **Filter fault and wrong-binary
fault are therefore distinguishable, and neither is a finding about lever (a).**

An all-zero phase read is a fourth mode and is not expected: `nv2a_clock_ns` is
a `cntvct_el0` read on aarch64 and cannot fail, so `Tot:0.0` alongside a
non-zero `gfps` would be an instrument fault, not a title that did no work.

### Validity gates on the survey, registered before it runs

Not legs about lever (a) — legs about whether the instrument is pointing at
anything, which is what caught #44's voided accuracy pair.

- **G1** at least 20 `hakuX-phase` lines in the capture. Below that the EWMA
  samples are too few to separate the runs, and my Crimson figure rests on 46.
- **G2** `READ + POST + UNCLASSIFIED == BUSY` on every sample, residual
  ≤ 0.35 ms (one-decimal printing over eight terms). This is the check that the
  parse is right, and it is not tautological: it broke once already for me, on
  `Fin == Sub + Fen`, because those are smoothed independently.
- **G3 — the workload control, and the one most likely to bite.**
  `soak_title.sh` injects **no input**, so a Galleon soak can sit in an intro or
  a menu for its whole duration and still produce frames. The phase split of a
  menu is not the phase split of gameplay, and nothing in the numbers says
  which you got. So: the capture's `gfps` band must be consistent with
  gameplay rather than a menu.

  **WEAKENED BEFORE THE RUN, not after it.** I first wrote this gate as
  "`gfps` p90 must be within ±4 of the published Galleon arm-A ceiling of 29",
  and that is not a sound comparison: the published 29 came from a **normal**
  build, this arm is a **perflog** build, and `profile.c`'s own comment says
  the profiler *"puts a clock read around every method in the puller and so
  changes the number it is measuring."* So a lower `gfps` here is expected from
  the instrumentation and would be indistinguishable from a lighter workload —
  the gate would fail for the wrong reason, or pass while hiding a menu.

  The instrumentation-independent workload control is a **draw count**, not a
  frame rate: `BE:` (`NV2A_PROF_BEGIN_ENDS`) and `TexU:` on the `xemu-work`
  line. Those cannot be perturbed into existence by a clock read. But
  `xemu-work` is **also absent from `LOGCAT_SPEC`**, so that control is
  unavailable for the same reason the measurement is — which makes the one-line
  filter fix worth more than it looks: it is what makes the survey
  *interpretable*, not merely non-empty. Until then G3 can only say "a `gfps`
  band far below anything Galleon shows in gameplay voids the run", which is a
  much weaker statement than the one I registered, and it is recorded as weaker
  rather than quietly reinterpreted once the numbers are in.
- **G4** two runs, not one. The replicate for a no-oracle measurement is the
  RUN, and my own Crimson pair moved the ceiling 34.6% → 40.3% between two runs
  of one binary. A single Galleon run cannot establish this share any more than
  one title could establish a cost.

### And the number this survey feeds

The leg to register afterwards is the ABSOLUTE, never a fall: **Galleon's
post-read share of BUSY is at most X%**, because that share caps lever (a)
whatever the baseline does. It must be read as an **upper bound** on (a) rather
than an estimate, for two reasons already established here: `Syn` covers 4 of
the 9 `sync_vertex_ram_buffer` call sites so READ under-counts, and `Tot`
double-counts `texture_upload` and `shader_compile`.

### MEASURED: the filter claim holds, and the binary fault is eliminated OFFLINE

Survey `1789318797-wt54-phase-56718`, **nova**, Galleon 240 s, ref
`49afee8889`, `--perflog`, `--no-expect` (a survey). Dispatcher log confirms
`diagnostic build requested: -Pperflog=true` and built
`49afee8889-perflog.apk` with its own `build-49afee8889-perflog.log`, apk_sha
`f77298243d53`.

    hakuX-phase lines in the capture      0
    hakuX-perf  tag lines                 216   (25 of them the gfps pacing line)

**The claim registered before the run is confirmed.** And the middle row of the
three-way discriminator — *filter fault or wrong binary* — is resolved by a
check that needed no device at all, run on the APK files themselves:

| `libxemu.so` from | `hakuX-phase` string | `hakuX-perf` string |
|---|---|---|
| `49afee8889-perflog.apk` | **1** | 1 |
| `8191d97296.apk` (normal) | **0** | **1** |

The perflog binary also carries the full format string
`Surf:%.1f Tex:%.1f Shd:%.1f Draw:%.1f [Vtx:…`, and the normal one does not.
So `-Pperflog=true` compiles `NV2A_PERF_LOG` in correctly and **the
dispatcher's plumbing works end to end**; `hakuX-perf` being present in *both*
is what makes it a valid control rather than a coincidence.

That leaves exactly one cause, and it is no longer an argument: **the capture
filter drops the line.**

**And I first named the wrong file, which is worth recording because the right
one is the only one that works.** I wrote this up as `soak_title.sh:32`. That
default is **dead while the dispatcher runs**: `dispatcher.sh:548` sets
`LOGCAT_SPEC` and **exports** it, at top-level scope above the `case` at 556,
so it wins over both `soak_title.sh:32` and `run_disc.sh:75`. Patching
`soak_title.sh` would have changed nothing and read as a fix.

The effective spec is therefore
`hakuX-crash:V hakuX-unhandled:W hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:I hakuX-rw:I VALIDATION:W … *:S`
— no `hakuX-phase`, and `*:S` silences it.

**The fix is one token at `dispatcher.sh:548`**, additive, and provably inert
for every other measurement: adding a tag to a logcat filter can only *add*
lines, and only for a tag that exists solely in perflog builds, which nothing
else currently requests.

```diff
-… hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:I hakuX-rw:I VALIDATION:W …
+… hakuX-build:I hakuX-perf:I hakuX-phase:I xemu-work:I hakuX-pages:I hakuX:I hakuX-rw:I VALIDATION:W …
```

`xemu-work` belongs in the same edit rather than later, because it carries
`BE:` and `TexU:` — the **instrumentation-independent workload control** G3
needs, and without it the survey can be non-empty and still uninterpretable.

**The comment directly above line 548 already describes this failure**, in
these words: *"A result claiming a spec that was never used is worse than one
claiming none — someone reads `logcat.spec`, sees the tag they need, finds no
lines, and concludes the code does not log rather than that the filter dropped
it."* That is exactly the wrong conclusion the APK-strings control was run to
prevent, and the same paragraph records the disc path having fallen through to
a third literal once already.

**Not applied here, and the reason is the rule this campaign already paid for.**
`dispatcher.sh` is shared infrastructure, the dispatcher re-execs when its own
script hashes change, and a request was in flight
(`1789318886-stencilregress-60547`, claimed 10:01:33) whose work a re-exec
would requeue. Editing shared infra with arms running is the failure that cost
251 requeues. It is one line in the dispatcher owner's file — the same file
`--perflog` landed in — and it should go in when the queue drains.

### Independent corroboration, and a THIRD gap: the soak records no spec

`dispatcher.sh:490-493` writes the spec it used into the result, deliberately
with no fallback literal, so a result can record its own blindness. **It does —
but only on the disc path.** Checked rather than assumed, in both directions:

    disc  z-tip-100-Zero_stride  result.json .logcat.spec =
      "hakuX-crash:V hakuX-unhandled:W hakuX-audio:I hakuX-audiocap:I
       hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:I hakuX-rw:I
       VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W *:S"
      hakuX-phase in it?  NO        xemu-work in it?  NO

    soak  1789318797-wt54-phase-56718  result.json keys =
      apk_sha kind title seconds requester purpose ref device_serial
      device_label logcat_lines pulled
      -- no `logcat` field at all

So the disc path's record is **independent confirmation of the effective
spec**, written by the dispatcher itself on an unrelated run, and it agrees
exactly with `dispatcher.sh:548`. That closes the loop without taking my own
grep on trust.

And the asymmetry is the third gap, smaller than the tag but the same shape:
**a soak's `result.json` carries `logcat_lines` but not the spec that produced
them.** A soak is exactly where it is needed — a disc has a golden to disagree
with, a soak has nothing, so "the filter dropped it" and "the code does not log
it" are indistinguishable from a soak result alone. That is the failure the
comment at 538-542 was written about, still open on the path with the weaker
oracle. Worth one line in the same edit as the tag.

**I had this wrong in my first draft**, and it is the same error twice in one
finding: I credited the soak result with recording its own spec, having read
the disc path's writer and assumed it was shared. Both halves of this section
are now read off the files rather than off the code.

**Run 2 was NOT queued.** G4 asks for two runs, but a second run of an
identically-filtered capture is a second guaranteed zero; the replicate becomes
worth spending only once the tag is in the spec.

### One thing the survey did establish, and it retires my own G3 caveat

`gfps` over the full 240 s, 65 pacing samples:

    n=65   min 2   p50 16   p90 29   max 29
    published Galleon arm A (normal build):  p50 16   p90 29   max 30

**The perflog build reproduces arm A's pacing almost exactly** — p50 16 against
16, p90 29 against 29, max 29 against 30.

I had weakened G3 before the run on the grounds that the profiler *"puts a
clock read around every method in the puller and so changes the number it is
measuring"*, so a lower ceiling would be expected and indistinguishable from a
lighter workload. **It did not lower it, and the median did not move either.**
So the weakening was right to register and is now retired by data rather than
by argument, and two things follow:

- **G3 is satisfied in its strong form.** The soak reached a Galleon workload
  pacing-identical to the one the cost arms measured, despite `soak_title.sh`
  injecting no input. That was the risk most likely to void this survey and it
  did not materialise.
- **The eventual Galleon phase figure needs no build-variant correction.** It
  can be set beside `gfps` p90 29 → 13 directly, because the instrumentation
  does not move the statistic those arms are judged on.

One limit, stated rather than left implicit: this is one run, and `#64`
established that `gfps` here is bimodal with a floor of 5-20 — `min 2` is below
even that, so the *series* is not identical, only its ceiling and median. The
ceiling is the statistic that matters, and that was fixed by `#64` before this
arm ran rather than chosen now because it agreed.

## MEASURED, lane.readfreq: the read-side frequency on Galleon was ALREADY ON DISK, and it inverts the target

#54 was kept open "for a READ-SIDE frequency counter over the DIRTY_MEMORY_NV2A
bitmap and `r->texture_vram_gen`". **That counter has existed since
`e353735028`, it has run on Galleon three times, and nothing had ever read its
output.** The three Galleon runs were queued for other questions — two as the
`draw-only-cost` arms in the section above, one as the `wt54-phase` survey —
and every one of them carries `Vr:`/`Tr:` on the `hakuX-perf` line it was
already capturing. The cost legs were read off those runs; the probe fields
were not.

So the first finding is a process one and it is the same failure as the
blocker: **the measurement #54 was waiting for had already been taken, by runs
the issue itself cites.** `docs/testing/vram_race_report.py` was committed to
read exactly these fields and was never pointed at a Galleon result.

### GALLEON, mode 0 (the shipped configuration), three runs across two refs

| run | ref | `Vr` raced/copies | rate | `Tr` raced/uploads/windows | `Xd` |
|---|---|---|---|---|---|
| `1789312621-draw-only-cost-1052604` | `5cfc236d9b` | **12 / 135,483** | 8.86e-05 | 0 / 7,518 / 560,343 | 0 |
| `1789312621-draw-only-cost-1052674` | `5cfc236d9b` | **8 / 134,597** | 5.94e-05 | 0 / 7,942 / 581,491 | 0 |
| `1789318797-wt54-phase-56718` | `49afee8889` | **5 / 126,933** | 3.94e-05 | 0 / 7,713 / 548,902 | 0 |

**Pooled: `Vr` = 25 / 397,013 = 6.30e-05, `Tr` = 0 / 23,173 uploads over
1,690,736 draw windows.** All three runs 240 s, all on the nova, `Xd` = 0
throughout.

Stated in the shape the brief asked for: **the counter fires 0.035 times per
second on Galleon, all of it at the VERTEX site, and zero times per second at
the texture site** — bounded at ≤ 3/23,173 = 1.29e-04 per upload (one-sided
95%), which is ≤ 0.0042/s. The instrument is unchanged across the two refs:
a diff of `vk/draw.c` over that span touches 660 lines and none of them is a
probe counter.

### THE TARGET IS THE VERTEX SITE ON GALLEON, WHICH INVERTS v3's LEG 4

v3's leg 4 predicted `Vr/vtx_copies < Tr/tex_uploads`, reasoning that the
texture window is orders of magnitude longer than a vertex memcpy and a race
rate scales with window length. **On Galleon the ordering is inverted**, and
the leg's own registration named the failing world: *"a title streaming
dynamic vertex buffers rewrites them immediately before drawing from them far
more often than it rewrites textures, which inverts the ordering."* Galleon is
that title.

The mechanism is not window length, it is **exposure**, and the probe already
measures it. `tex_uploads / tex_windows` is the rate at which a draw's texture
read follows an unsynced guest write:

| title | `tex_uploads/tex_windows` | `Tr/tex_uploads` | `Vr/vtx_copies` |
|---|---|---|---|
| **Crimson Skies** (nova, `5cfc236d9b`) | **0.803** | **0.617, 0.619** | 0 / 6,082 |
| Crimson Skies (thor, `e353735028`) | 0.748, 0.751 | 0.566, 0.567 | 0 / 4,560 |
| **Galleon** (nova, mode 0) | **0.0134–0.0141** | **0 / 23,173** | **6.30e-05** |
| JSRF (thor) | 0.0052 | 0 / 5,733 | 0 / 17,703 |
| Dead or Alive 3 (thor, 6 runs) | 0.00068–0.00088 | 0 / 8,944 | 2 / 273,499 |

**A 60x difference in texture exposure between Crimson and Galleon**, and the
race rate follows it. So Galleon's `Tr = 0` is a statement about Galleon's
*workload* — it barely rewrites a bound texture — and not about the emulator's
memory ordering. **The barrier arm's zero and this zero are not the same
zero**, and neither is evidence for the other: one says barriers do not repair
`2D_BorderTex_SZ`, this one says Galleon does not present the texture-side
race to be repaired.

### AND THE SKEW BOUND ELIMINATES THE VERTEX RACE ON GALLEON, p = 0.00008

The same four-run pair carries mode 2, and this was never read either:

| arm | ref | `Vr` raced/copies |
|---|---|---|
| A, mode 0 | `5cfc236d9b` | 12/135,483 and 8/134,597 — **20 / 270,080** |
| B, mode 2 | `d879e6e03b` | 0/88,762 and 0/88,739 — **0 / 177,501** |

Fisher exact, two-sided: **p = 0.00008**. The denominator is live on both arms
(88,739 copies on the quietest run), so this is elimination and not absence —
the same shape as #79's `XEMU_OPT_FIFO_SKEW_BOUND` arm taking wrong Stencil
triangles from 7 of 64 to 0 of 64, on a different workload and a different
observable, with a direct counter instead of a pixel count.

**That is a second, independent confirmation of #79's diagnosis from a title
rather than a disc**, and it was sitting in the same four result directories
the cost table above was built from. It does not attribute Galleon's 25 torn
vertex reads to any visible defect: a soak writes no captures, and this
measures a rate, not an artefact.

### WHAT THIS COUNTER CANNOT SEE ON #79's OWN DISC, and it is a DENOMINATOR

The brief asked whether the counter can see #79. On the pgraph corpus the
honest answer is **no, and the reason is measurable rather than arguable**:

    pgraph disc runs carrying the probe        83
    vtx_copies == 34 per run                   49 runs
    vtx_copies == 35..39 per run               23 runs
    Vr > 0                                      1 run
    Tr == exactly 1 per run                    77 runs

Every `4-suites:7254741c` disc containing Stencil reads **`Vr` = 0 / 34**
against ~46,000 `tex_windows`. So the whole disc performs 34 dirty
vertex-array copies while issuing tens of thousands of draws, and #79's arm
refs (`d97d506514`, `ec7f50e859`) predate the probe entirely and carry no
`Vr:` line at all.

**A zero over a denominator of 34 bounds the rate at ≤ 8.8% and settles
nothing**, and the interesting half is which of two worlds produces the 34:

- Stencil owns most of them — the site is on #79's path and the counter is
  merely **underpowered** on this disc;
- Stencil owns none of them — `DefineBiTri`'s six vertices reach pgraph by a
  path that is not `sync_vertex_ram_buffer`, and the counter is **structurally
  blind** to #79.

Those need opposite responses and one Stencil-only disc separates them, so it
is queued rather than assumed. Note the shape: this is AGENTS.md's *"before
measuring an effect on a class of input, ask whether this data contains that
class at all"*, and the `ls`-equivalent here — the vertex-copy denominator —
was printed on every one of those runs.

**The disc's `Tr` = exactly 1 in 77 of 83 runs is the same warning from the
other side.** A counter that reads the same small constant on every run of a
1,673-test disc and of a 16-capture disc alike is not measuring a rate; it is
almost certainly one boot-time event. Nothing should quote a per-run disc `Tr`
as a frequency.

**ANSWERED OFFLINE WHILE THE DISC RAN, and the answer is the second world.**
The counters are cumulative and the pacing line is emitted repeatedly, so the
*series inside one run* separates boot from tests with no device at all. On all
six Stencil-carrying runs, at the first pacing line and at the last:

| run | `vtx_copies` first → last | `tex_windows` first → last | `Tr` |
|---|---|---|---|
| `1789345024-orchestrator-1663172` | **34 → 34** | 16,770 → 46,381 | 1 → 1 |
| `1789345036-orchestrator-1663213` | **34 → 34** | 17,227 → 47,025 | 1 → 1 |
| `1789345832-orchestrator-1968847` | **34 → 34** | 16,318 → 45,312 | 1 → 1 |
| `1789347057-orchestrator-2287889` | **34 → 34** | 15,890 → 45,312 | 1 → 1 |
| `1789347057-orchestrator-2288027` | **34 → 34** | 16,318 → 45,685 | 1 → 1 |
| `1789345832-orchestrator-1968834` | **34 → 34** | 16,318 → 46,381 | 1 → 1 |

**Not one dirty vertex-array copy in ~29,500 draws per run, six of six.** All 34
land before the first pacing line, which is boot. `Tr` = 1 is boot by the same
reading, while `tex_uploads` does advance during the tests (64–69 → 104–189) —
so the texture path is live on the disc and races zero times, and the `1` is
not part of any rate.

The control that makes this a measurement rather than an absence is in the same
two numbers: `Depth buffer` on the same instrument reads `vtx_copies`
302 → 744 → 1,166 → 1,580 → 1,979 across its five pacing lines. **The
instrumented path is alive on a pgraph disc and simply unused by the suites
carrying Stencil** — which is the discriminator, and it needed no device.

**And the source says why.** Three vertex paths reach a draw and only one of
them reads guest memory at draw time:

| path | where the vertex values come from | guest read at draw? |
|---|---|---|
| `draw_arrays` / `inline_elements` | VRAM vertex arrays, via `update_memory_buffer` → `sync_vertex_ram_buffer` | **yes — this is what `Vr` counts** |
| `inline_buffer` (`NV097_SET_VERTEX_DATA*F`) | accumulated into `attr->inline_buffer` as methods are processed | **no** |
| `inline_array` (`NV097_INLINE_ARRAY`) | `pg->inline_array[len++] = parameter`, `pgraph.c:4258` | **no** |

The two inline paths carry vertex values as **pushbuffer method parameters**,
copied into pgraph-owned state at method-processing time. There is no
guest-memory read left at the draw for any read-side counter to instrument, so
`Vr` is not merely quiet on them — there is nothing there to count.

**So `Vr` is blind to #79 structurally, and a zero from it about #79 is not
evidence.** That is the shape AGENTS.md warns about: *"a guard satisfied by the
absence of the thing it guards reports success."* Stated as the brief asked:
the counter **cannot** see #79, and what that means is that #79's skew is not
at the site #54's counter watches.

**WHERE IT WOULD THEN BE, held as a hypothesis with its falsifier, not as a
diagnosis.** If the Stencil vertices travel by an inline path, the only guest
read in their journey is the **pusher's read of the pushbuffer word**, in
`pfifo.c` — and a torn vertex would be the guest overwriting published
pushbuffer words before `pfifo_run_pusher` consumed them. That is consistent
with `XEMU_OPT_FIFO_SKEW_BOUND=1` fixing #79 for a reason about the *pusher*
rather than about a vertex buffer, and with `behind/kicks = 100.0%` on the
Stencil disc. It is NOT established: I have not read `nxdk_pgraph_tests`, the
pushbuffer is not covered by `DIRTY_MEMORY_NV2A` logging so no existing counter
can see it, and the ring measured on `Texture border` is 63.98 MiB, which is
large to wrap inside a publish-to-consumed p50 of 8.65 ms. The falsifier is
cheap and needs no new code: **if the Stencil-only disc reads `vtx_copies` = 34
with no growth, the VRAM-vertex-array story is dead and the pushbuffer one is
the surviving candidate; if it grows, `Vr` is on #79's path after all and is
merely underpowered, and the fix is soak length rather than a new site.**

### Registered before the tip runs

`docs/testing/predictions/vram-read-race-probe-54-v4-galleon.json`, a
single-arm survey (`a_ref == b_ref == 1dee9e25f6`), Galleon 240 s x2 on the
**thor**. Every leg is an absolute: `Xd == 0`; denominators live
(`vtx_copies` > 50,000, `tex_uploads` > 5,000, `tex_windows` > 100,000, so a
zero cannot be read as an absence); `Tr/tex_uploads` ≤ 1e-03;
`Vr/vtx_copies` in [1e-05, 1e-03] pooled; `Vr/vtx_copies > Tr/tex_uploads`
(the inversion, which is the one leg that contradicts a previous registration
rather than replicating a number); `tex_uploads/tex_windows` ≤ 5e-02. It
records what is already on disk at the top, so no leg can be read as blind.

Why spend the slot at all when three Galleon runs exist: all three are on the
**nova**, which is offline, and this file's own rule is that a figure measured
on one device is a fact about that device until a second agrees; the refs are
~300 commits behind the tip, and the same probe on Crimson moved 9% in rate
and 53% in denominator across 128 commits; and #54's blocker asserted the
measurement needed the Nova, which running it on the Thor retires by
demonstration rather than by an `ls`.


## UNRESOLVED

- ~~**What the skew actually is.**~~ **MEASURED 2026-09-13**: a 63.98 MiB
  ring, 100.0% of 148,667 submissions made with PGRAPH behind, and a
  publish-to-consumed latency with a p50 of 8.65 ms, a p90 of ≥34.9 ms and a
  max of 528 ms. What remains open is the shape above 51.2 ms, where the
  histogram overflows and p90/p99 are floors.
- ~~**Whether the bound is affordable.**~~ **MEASURED: it is not, in this
  shape.** `gfps` p90 29 → 13 and max 30 → 15 on Galleon, with the guest
  blocked at its submissions for 40.7% of wall clock — against a predicted
  ~48% from the PFIFO thread's busy fraction, so the cost is understood and
  not merely observed. Defaulted off. What is open is the **selective**
  version: hold only at draw-publishing submissions, which preserves the
  invariant exactly and skips 148,524 of 148,704 submissions on this disc.
  Needs a pre-scan for `NV097_SET_BEGIN_END` and its own arm.
- ~~**How much of a real title the guarantee covers.**~~ **MEASURED: 94.4%.**
  `gave` is 5.603% of Galleon's submissions against 0.674% of the test disc's,
  which is the flip-every-frame difference C5 registered in advance. What is
  still unknown is the *attribution*: `gave` is one counter over four stall
  reasons, and 2,482 releases against ~14,000 flips in 240 s does not
  obviously decompose. Splitting it by `pfifo_pusher_should_stall`'s four
  conditions is a one-counter change and decides whether the residual is
  reachable at all.
- **The five blind swatches.** The true per-draw loss rate is a floor by an
  amount this capture cannot bound, before or after any fix.
- **Whether `defer_cap` could confound the skew arms.** It cannot, and this is
  now measured rather than assumed: `unl=0` on all 28 `vblphase` windows of
  arm A, so the `Texture border` disc never enters unlock mode and the
  deferral-cap change both arms carry is inert on it. The same windows also
  show the `clamp=` counter live and firing 0–8 times per window with
  `def(n)=0` — clamps with no deferral at all, which can only be a
  non-deferred lateness over a period, i.e. the host stall tail. Its max
  lateness is 725,561,719 ns, **43.5× a period**. That is exactly the residual
  #65's D9 reserves and no deferral cap can reach.
- ~~**Whether a cheaper sufficient bound exists outside this path.**~~
  **Write-tracking is RETIRED as a candidate and needs no arm.** The handover
  at `b56911f150` already withdrew store-trapping on the grounds that the
  detection exists; the #54 lane then verified that from source —
  `check_texture_dirty` is a `memory_region_test_and_clear_dirty` on
  `DIRTY_MEMORY_NV2A_TEX` at whole-4 KiB-page granularity — so there was never
  a write to stop, only a response to add.
- **What lever (a) is worth on Galleon, and it is the only open cost
  question.** Its ceiling is the post-read share of the PFIFO thread's busy
  time. Measured on **Crimson Skies** at **38-47%** (46 samples, two runs,
  reproducible to ±3 points), with the other 49-53% being the guest-memory
  reads themselves and therefore irreducible. But Crimson arm B shows the
  bound already costs `gfps` p90 −0 there, so that number is measured where
  the lever has nothing to buy. **Galleon is where the cost is, and its
  post-read share is unmeasured** — and *one title cannot establish a cost*
  applies to this figure exactly as it applies to the `~160 µs` one it
  corrects.

  **The build half of the plumbing is fixed (`c1300aa3fa`, `--perflog`) and
  VERIFIED: the APK really does compile in `NV2A_PERF_LOG`** — the tag string
  and the phase format string are present in `49afee8889-perflog.apk`'s
  `libxemu.so` and absent from a normal APK's, with `hakuX-perf` in both as
  the control. **The capture half is not.** `dispatcher.sh:548` exports a
  `LOGCAT_SPEC` that omits `hakuX-phase` and ends `*:S`, so survey
  `1789318797-wt54-phase-56718` (Galleon 240 s, nova, perflog) captured
  **0 phase lines against 65 `gfps` samples**. Measured, not argued, and the
  binary explanation was eliminated offline before the run finished. One token
  at `dispatcher.sh:548` unblocks it — plus `xemu-work:I` for the workload
  control, and the soak path's missing `logcat` provenance field. Not applied
  from this lane: it is shared infrastructure and a request was in flight.
- **What share of `pipe_bind_tex` is the guest-VRAM content hash.** `Tx` is
  **5.85 ms/frame, 29.8% of all PFIFO busy time** on Crimson, against a
  texture *upload* of **0.01 ms/frame** — so the guarantee's irreducible half
  is dominated by the decision, not the copy. Whether the hash is the bulk of
  that is an inference, not a measurement; one timer pair around the two
  `fast_hash` calls in `create_texture` settles it, inside this lane's file
  and needing no other lane. If it is, it is a cost reduction on the
  irreducible half, which lever (a) cannot touch.
