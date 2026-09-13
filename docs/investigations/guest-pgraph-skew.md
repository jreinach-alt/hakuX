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
flips every frame exercises it constantly, which is why the cost arm is
registered to report `gave` as a **rate** rather than judge it. That rate is
the honest scope of the change and was unknown before this pass.

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

*Results to be filled in from the dispatcher. Judged on `stale_px` from
`docs/testing/border_swatch_origin.py`, not on differing pixels: the count
swings 40× on an unchanged binary because each swatch has a fixed cost if it
loses and a run's total is the sum over whichever subset lost, so 146 and
5,640 are the same event once and three times.*

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

## UNRESOLVED

- **What the skew actually is.** `drain` has never been measured. Everything
  above about "the guest runs ahead" is a reading of the source; its size is
  the first number this instrument produces.
- **Whether the bound is affordable.** Every submission becomes a round trip
  to the PFIFO thread where before it was a store.
  `frame-pacing-and-parallelism.md` measured the guest CPU thread busy 83% of
  the wall clock with the renderer idle 21.2 ms of a 50.2 ms frame waiting on
  it, so the two halves were already only partly overlapped — and what overlap
  remains is what this removes. `orchestration.md` is explicit about the order:
  measure the accuracy, then the cost, then hand the trade over rather than
  resolving it.
- **How much of a real title the guarantee covers.** `gave` across a title
  that flips every frame is unknown, and the guarantee genuinely does not hold
  across a flip stall.
- **The five blind swatches.** The true per-draw loss rate is a floor by an
  amount this capture cannot bound, before or after any fix.
- **Whether a cheaper sufficient bound exists outside this path.** The one
  candidate is write-tracking: trap the guest's store to a range a queued draw
  will read, rather than holding every submission. The machinery is partly
  there — the vertex path already consults `DIRTY_MEMORY_NV2A` — but a dirty
  *bit* records that a write happened, and this needs the write *stopped*,
  which is a different mechanism and lives in the texture path.
