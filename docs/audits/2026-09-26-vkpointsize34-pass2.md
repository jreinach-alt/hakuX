# Audit pass 2: PR #371 (lane/vkpointsize34), #34

Head verified: b7400fd8d1 (pass-1 file on b00f39daf5; no code change since).
CI green on that head, mergeable, `verified` label from the arm.

**Result: clean.** Pass 1 had no HIGH or MEDIUM. Both LOWs were re-checked
against the head. Next state: `fold-ready`.

## Pass-1 claims re-checked on the head

- `glsl/geom.c:193`, `:729`, `:824`: every `gl_PointSize` write in the GS is
  under `!opts.gles && !opts.no_point_size`. Those are the only three
  `gl_PointSize` sites in the file.
- Every caller of `pgraph_glsl_gen_geom` (`vk/shaders.c:1034`,
  `vk/compile_worker.c:40`, `gl/shaders.c:309`) passes the key's `glsl_opts`,
  so the flag set in `shader_binding_build_module_keys` is the one generated.
  That function memsets `geom_key` before setting the flag. GL memsets its key,
  so `no_point_size` is 0 there.
- `r->enabled_physical_device_features` (`renderer.h:1127`) is the struct
  passed as `pEnabledFeatures` (`instance.c:1209`), so the flag reads what the
  device was actually created with.
- `SHADER_STATE_LAYOUT_VERSION` is 4, with 3 still documented as #286's
  `aa_offset_x`, so the versions do not collide.

## LOW-1 (1 px points for POLY_MODE_POINT on a driver without the feature)

This can still happen. Pass 1 recorded it as a deliberate trade, not a
defect: without the feature the old shader module was invalid; now the size
is defined as 1.0. It only affects a driver the fleet does not ship (the
system Adreno driver) and one polygon mode. No change is expected, and the
fix direction (expand to quads in the GS) is recorded in pass 1 and NOTES.

## LOW-2 ("2 -> 3" wording)

- PR body: fixed. It now says the version bumps to 4 and that master's 3 is
  #286's.
- Prediction prose (`vkpointsize34-fleet-inert.json`): still says "2 -> 3".
  That is left as it is on purpose. The prediction was registered at `b_ref`
  97f221cac0, before the merge, and at that ref the prose was accurate.
  Editing a judged prediction after its verdict would be the wrong fix. The
  merge only renumbers the version, so the arm's verdict still describes the
  shader text.

## Other

The pass-1 note on a stale `needs-rebase` label no longer applies: the PR no
longer carries it.
