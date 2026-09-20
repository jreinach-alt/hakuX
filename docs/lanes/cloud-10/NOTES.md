# lane.cloud-10 -- #10, the `Bump map` Y16 class

Base: master @ `4c28b2d352`. No device. Everything offline against
`/home/justin/goldens/results` and `z-repeat-c866527e03-011-Bump_map` /
`-010-Bump_env_lum` (ref `c866527e03`) -- the same set `nv2a_issues.toml`'s
`blocker_tested` cites, so these numbers sit beside the ones already in the
entry. No code change; `glsl/psh.c` is `lane.remote`'s and nothing here names
an unambiguous fix site anyway.

Full write-up: [`docs/investigations/bump-y16-class.md`](../../investigations/bump-y16-class.md).
Every number in it re-runs with `python3 docs/testing/bump_y16_class.py --all`:
`--identity`, `--stored` and `--control` for the tables, and `--parity` for
the inversion's structure and the size bound, which used to be prose.

## Outcome

**Characterised, not solved, and three rivals plus the obvious fourth are
measured dead.** The class is bounded much more tightly than "a separate and
much larger problem":

- we render `BumpMap_Y16` **byte-identically to our own `BumpMap_Y8`** (0 px),
  and our Y16 sits at the 1,576 px #38 floor against the **Y8** golden. So the
  geometry, the filtering of TEX1, the blend and the combiner are all right;
  only the two bump offset values are wrong.
- hardware separates them: gold Y16 vs gold Y8 is 21,472 px.
- SZ_Y16's stored word is **byte-replicated** (`Y8 * 257` exactly), so no
  byte-order or channel-assignment rival can even produce a difference.
- all 21,472 px sit in columns 44..102 of 168 in every quad, **zero outside**,
  and every differing column is colour-inverted with its vertical checker
  transitions on identical rows -- a horizontal cell-parity flip that toggles
  30 times across the band.
- **hardware varies the horizontal offset with `u`; it does not shift it by a
  constant.** In columns 78..102 the base checkerboard has no horizontal
  boundary in 150 of the quad's 168 rows, and the gold Y16 quad has 11 in
  every row. A constant shift, of any size, can only invert at the base's own
  period. Counting both images' boundaries per row bounds the *cumulative*
  movement of the relative cell index at **>= 19 cells, ~250 byte units** of
  `b`, against our single 82 -> 83 step. Its *excursion* is not bounded by
  this data at all (oscillation inside one cell toggles forever), so size a
  rival by cumulative movement, not by swing.
- `BumpEnvLum_Y16` is at the floor over the same format, the same seam and the
  same kind of byte-replicated field, with a *larger* bump matrix. That is the
  control that kills the one rival with the right magnitude (reading the low
  byte of a 16-bit filtered value), and that region is measured non-blind.

## What the next lane should not repeat

- **Do not run `bump16_oracle.py` on this class.** The brief asked for it; it
  models `Test16bit`, the HILO dot-product path, which `bump_map_tests.cpp`
  instantiates only for `SZ_R16B16`. Y16 never reaches `dotmap_hilo_1`.
- **Do not score Y16 rivals against a forward render.** `bump_oracle.py` is an
  80% instrument on this suite -- 21,839 px wrong of 111,496 on
  `BumpMap_A8R8G8B8` under its own best rival -- and the whole Y16 effect is
  5,400 px per quad. I wrote a Y16 forward oracle first; every rival scored
  between 46,000 and 55,000, including the one that *is* what `psh.c` emits
  against our own capture. It was deleted rather than committed. Compare
  images the same geometry produced.
- **Two more model-shaped instruments lied before I noticed**: a per-column
  vertical-phase fit returned the same phase (0.19 texels) for every capture in
  the suite, formats whose `dT` differs by 45 byte units included; and a
  "where does the row go constant" scan reported column 126 for the gold Y8
  quad and 77 for ours -- images that differ by 1,576 px in total. The right
  half of each quad carries almost no horizontal information and any threshold
  scan across it answers confidently.
- **Do not bound a swing with a flip count.** The first draft of this document
  turned "the inversion toggles 30 times" into "the offset sweeps at least
  ~200 byte units", by halving the toggles into cells and then claiming the
  true swing could only be larger. Every step of that is wrong: a count of
  sign changes bounds *cumulative* travel, never an excursion (oscillation
  inside one cell toggles arbitrarily often with a range of one cell), the
  halving had nothing behind it, and some of the toggles belong to the base
  texture's own 5.29-column period rather than to hardware. The audit on #187
  caught it. The instrument that answers it honestly counts the two images'
  own checker boundaries per row and takes the difference -- `--parity` -- and
  it also says which quantity is bounded, because the next reader is going to
  use that number as a sieve.
- **Do not patch `append_bump_channel` on a format test.** Any rule keyed on
  `SZ_Y16` that moves `BumpMap_Y16` also moves `BumpEnvLum_Y16`, which is
  already exact at 1,576. That is a must-not-move leg with a number attached.

## The next measurement, and why it is not an arm

`bump_map_tests.cpp:112` already holds the line, commented out:

```c
    stage.SetBumpEnv(0.3, 0.0, 0.0, 0.5, 0.0, 0.0);
    // stage.SetBumpEnv(0.3, 0.0, 0.0, 5.0, 0.0, 0.0);
```

`m11` is one of exactly three things that differ between the suite where the
defect fires and the suite where it does not (the others being the stage
program, BUMPENVMAP against BUMPENVMAP_LUM, and the luminance values 82/83
against 46/47). Building a disc with that second line live and capturing
`Bump map` once either collapses `BumpMap_Y16` to the floor -- in which case
this is a vertical-scale interaction and not a Y16 read at all -- or
eliminates `m11` and leaves two candidates for a second capture.

That is a change to `nxdk_pgraph_tests`, so it is a disc build rather than an
`ab_compare.py` prediction; a lane cannot reach the dispatch directory from
its sandbox, so it is the board's to schedule. **Prediction: none** -- there is
no emulator-side change to register, and registering one against a mechanism
this document does not name would be fitting.
