# Prediction: where the evicted surface's contents are lost

Registered 2026-09-14 on `d7dfe146`, before instrumenting.

## What is established

`d7dfe146` measured the surface-alias predicate fix and found a regression whose
mechanism is proven: 8,192 pixels in a contiguous 128x64 rectangle that is
`(0,0,0,255)` in both the golden and the baseline come up `(255,255,255,255)`
once the predicate starts rejecting aliased reuses. Alpha does not move. A
perfect rectangle going uniformly white is a surface without its contents.

## What reading the code has already ruled out

The obvious explanation is wrong. `populate_surface_binding_entry_sized()` sets
**`entry->upload_pending = true`** (`gl/surface.c:2792`) on every new binding,
and `pgraph_gl_upload_surface_data()` (`:2543`) is gated on exactly that flag.
So a freshly created binding *is* marked to load itself from guest RAM. The
loss is in the sequence, not in a missing flag.

The eviction path is three statements (`:2965-2968`):

    compare_surfaces(found, &entry);
    pgraph_gl_surface_download_if_dirty(d, found);
    pgraph_gl_surface_invalidate(d, found);

and creation allocates with `glTexImage2D(..., NULL)` -- undefined contents,
which is consistent with white.

## The candidates

**H-writeback.** `pgraph_gl_surface_download_if_dirty()` is gated on
`surface->draw_dirty` (`:1765`). If `draw_dirty` is false at eviction, the GL
texture is discarded without ever reaching guest RAM, and the later upload
faithfully loads whatever stale bytes were there.

**H-upload.** The writeback happens, but the new binding's upload does not run
before the region is read -- so the undefined `glTexImage2D` contents show
through.

**H-roundtrip.** Both run, but the writeback uses the *old* binding's
`shape.color_format` and the upload uses the *new* one, so the round trip is not
the identity.

## The prediction

**H-writeback.** `draw_dirty` will be false on at least some of the seven
rejections. It is the only one of the three that needs no new machinery to be
wrong -- the flag is cleared in five places (`:2461`, `:2794`, `:3069`,
`:3227-3228`) and set in one region (`:1011-1022`), and a binding that was
populated and then had `draw_dirty` reset by any of those is discarded silently.

H-roundtrip is predicted NOT to be it, on evidence already in hand: the O/Z
distinction is the pad bit, and **alpha did not move at all** in the regression.
A format-asymmetric round trip should have shown there first.

## Discriminator

One probe, one run. At each rejection record `draw_dirty`; at each
`pgraph_gl_upload_surface_data()` record the address. Then:

- `draw_dirty` false on the rejections that matter -> H-writeback.
- `draw_dirty` true and no upload for that address afterwards -> H-upload.
- both present -> H-roundtrip, and the format pair is the thing to look at.

## Registered in advance so it cannot be retrofitted

If H-writeback holds, the fix is NOT to force the download unconditionally --
that would write undefined texture contents over good guest memory for a binding
that genuinely never was drawn to. It is to establish why `draw_dirty` is false
for a surface that visibly holds the only copy of 8,192 pixels. Naming that here
so a passing measurement cannot later be read as licence for the cheap fix.

---

## Outcome: all three candidates falsified, and so is the claim that sent me here

Two instrumented arms on `iso_surf1` under OpenGL, 236 captures each,
`QEMU_EXIT=0`. Probes verified present in the link before each run and absent
after the revert.

### The trace, identical on all seven rejections

    reject fmt 7->6 addr 26eb000 size 65536 draw_dirty 0 cleared 0
    wb     addr 26eb000 draw_dirty 0            <- writeback skipped
    upload addr 26eb000 size 65536 fmt 6        <- new binding IS refilled

**H-writeback: the fact held, the implication did not.** `draw_dirty` is 0 on
all seven, which is what I predicted. But skipping the writeback is then
**correct**: nothing was drawn to that binding, so guest memory is already
authoritative and there is nothing to preserve. I predicted the right
observation and drew the wrong conclusion from it.

**H-upload: falsified.** The upload runs immediately after every single
rejection, at the NEW format. It is never skipped.

**H-roundtrip: falsified, and it could not have been right.** There is no round
trip -- the writeback never runs at all, so no asymmetry between write and read
format can arise.

### And then my own inference was falsified too

Having established the upload runs, I reasoned that guest memory must therefore
contain white. Measured instead of assumed, and it does not. Dumping the exact
bytes the upload reads:

    src addr 26eb000 size   65536 fmt 6  ffffffff 0  00000000  16384  other 0
    src addr 26eb000 size 1228800 fmt 6  ffffffff 0  00000000 307200  other 0
    src addr 26eb000 size  614400 fmt 1  ffffffff 0  00000000 153600  other 0

Five of the seven read a region that is **entirely zero** -- black, which is
exactly what the golden wants -- and not one `0xffffffff` word among them. The
upload reads correct data.

**So the white does not come from the upload source, and the eviction machinery
is not the defect.** Every part of it -- the skip, the refill, the bytes read --
behaves as designed.

## A correction to `d7dfe146`, which is already pushed

That commit and PR comment 5666503544 conclude: *"a second defect in
`gl/surface.c`: evicting a binding does not preserve its contents ... eviction
must preserve contents before the predicate can compare `shape.color_format`."*

**The mechanism half of that is wrong and is retracted here.** Eviction
preserves contents correctly whenever there are contents to preserve. What
survives is only the operational finding, which two arms now agree on: the
predicate change regresses `Blend_surface::DstAlpha_XA_O1A7RGB8` by +24,576, and
the cause is upstream of everything I instrumented.

## A second correction, from the control rather than the experiment

The probed and unprobed fix arms differ on exactly one capture:
`Surface_pitch::Swizzle`, **22,528 against 28,996** -- on code that differs only
by inert `fprintf`s. That is a run-to-run spread of 6,468, the same order as the
10,240 I attributed to the fix in `d7dfe146`.

**So "the Swizzle move is real rather than the known coin-flip" is not
established and is retracted.** `desktop-noise-floor.md` says in as many words
to compare at least two runs on that capture; I quoted its threshold and then
did not follow its instruction. The threshold is also per-channel and I compared
summed-channel totals against it, which flatters the effect by about 3x.

This does not touch the headline. `Blend_surface::DstAlpha_XA_O1A7RGB8` is
**identical in both fix arms** at 335,872, so the regression is stable and
reproducible; and if the Swizzle gain is noise, the predicate change is worse
than `d7dfe146` reported, not better.

## What is now open, stated without a theory attached

Guest memory holds black, the upload reads black, and the capture shows white
over 8,192 pixels. Something between the upload and the readback produces it, or
the region is written after the upload by a path that does not go through these
three. The same guest address `26eb000` is bound at sizes 32,768, 65,536,
614,400 and 1,228,800 within one run, so overlapping bindings of different
extents at one address is the first thing to look at -- but that is a place to
point an instrument, not a finding, and it is not being written up as one.
