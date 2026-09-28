# lane.litcompile569 -- B1: the lighting unit's helpers, cheap to compile and bit-exact (#569)

P2 phase B1 of #569, as proposed in `docs/lanes/turnipcost569/NOTES.md` section 6 (PR #573).
The change is in `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`, `append_lighting_header()`.

## 0. Pre-registration (committed before the first timed run of the new forms)

### Gate 2: host compile time per lit pipeline

- **Harness:** lane.turnipcost569's, unchanged. Mesa Turnip `4c18636110f0` for an Adreno 740
  via drm-shim, NDEBUG -O2, and glslang `b5782e52` with the device's options. Its built Mesa
  and glslang are reused read-only. `compare.sh` interleaves A and B, 5 reps, thread CPU
  time.
- **A** = the harness variant `old_lt` (this directory's `old_lt.py`). It turns the new block
  off (`#if 0`), so the Vulkan build compiles the forms master ships. Before this commit it was
  checked to give SPIR-V **byte-identical** to master's for all 27 shaders of the catalogue.
- **B** = this branch.
  - The only SPIR-V that differs from A is the four lit fixed-function vertex shaders (`ff_lit2`
    and `ff_skin_texgen`, with and without the prefixed outputs).
  - Unlit, program, geometry and fragment shaders are byte-identical.
- **Measure:** the factor A/B for each lit `+gtri` pipeline of the fixed set: `ff_lit2` x 8
  pixel states, and `ff_skin_texgen`. The leg is their geometric mean.
- **Prediction:** the geomean is **>= 1.9x**. That is C7p's measured factor for `ltA3` alone
  (1.90-2.18x). It is bounded above by C7's float-arithmetic ceiling of 4.5-5.8x, because the
  exact forms keep all the integer work.
- **Reading, decided now:**
  - **>= 1.9x:** B1 holds on the host. The factor is the one the device leg (gate 4) scales.
  - **between 1.15x and 1.9x:** the rewrite of the other helpers costs back part of C7p's gain.
    It ships only if the arms pass. The NOTES say which helper form to revisit, from a
    per-helper probe.
  - **< 1.15x:** inside the harness's A/A noise (0.83-1.12x per pipeline). The leg is refuted.
- **Control:** the non-lit `+gtri` rows (`ff_unlit`, and the five `prog_*`) are byte-identical
  on both sides. Their A/B is the run's own A/A, and it must stay within 0.85-1.15x. If it does
  not, the run is noise-limited and is repeated.

### Gate 1 (CPU bit-exactness) -- done before this pre-registration, stated for the record

`lt_check.c` transcribes both the old forms (the `#else` branch) and the new forms to C, line
by line. It compares them:
- `ltR` over all 2^32 inputs;
- `ltMkU` over every sign, e in [-64, 320] and m in [0, 2^16);
- `ltM`, `ltsM`, `ltVM`, `ltA3`, `ltVA`, `ltsA` and `ltDp` over the special-value products,
  random words, and nearby-exponent inputs.

It also has 10 mutants, one or more per rewritten helper, and each must be caught. The 1 M run
gave **0 mismatches** and **10 of 10 mutants caught**. The 50 M run is in section 1.
