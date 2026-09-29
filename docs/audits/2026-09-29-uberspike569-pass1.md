[job.cloud] Audit pass 1 of PR #581 (lane.uberspike569, #569 P6 combiner ubershader spike): no HIGH or MEDIUM findings, three LOWs.
The default-off build is unaffected by the change, and the code that runs under the switch matches the device E leg's refs; the PR moves to needs-audit-2.

# Audit pass 1: PR #581, lane/uberspike569

- Head audited: `0b8290ff34` (`origin/lane/uberspike569`), 22 commits ahead of `origin/master`, 0 behind.
- Diff read: `git diff origin/master...HEAD`. `gh pr diff 581` currently also lists files that
  master already has (audits, jobs, other lanes' NOTES, `vk/draw.c`). GitHub's view of the PR is
  stale. The branch's own diff touches only the files on the PR body's `Files:` line.
- Code under review: `glsl/psh-uber.{c,h}` (new), `glsl/meson.build`, `vk/renderer.h`,
  `vk/shaders.c`. The lane tooling under `docs/lanes/uberspike569/` (host harnesses, carvers,
  result TSVs) is lane-local evidence and does not ship. I read it only for the claims the code
  depends on.

## What I checked

**Default-off behaviour (the path every shipped build takes).**
- `pgraph_glsl_psh_uber_enabled()` returns `HAKUX_PSH_UBER_DEFAULT` (0) when the variable is
  unset, and logs nothing then. So `bind_shaders` never substitutes a family,
  `psh_key->psh.uber` is always false, and `shader_module_compile_sync` takes the
  `pgraph_glsl_gen_psh` branch exactly as before.
- `psh_key` is `memset` to 0 before it is filled (`shaders.c` `shader_binding_build_module_keys`).
  The new `bool uber` byte is therefore 0 in every key a default build hashes, compares or
  persists.
- Both hash and compare cover `sizeof(key->psh)`. That size grows by the bool, but the grown bytes
  are always zero, so the key's identity is unchanged. Persisted keys are re-hashed when they
  load, so nothing stale results.
- Persisted key record size: `PshState` plus `GenPshGlslOptions` plus the bool is well under
  `VshState`, whose program array alone is 136×4×4 = 2176 bytes. `sizeof(ShaderModuleCacheKey)`
  is unchanged, as the header comment claims. An old `shader_module_keys.bin` still parses record
  for record.
- Old persisted fragment records were written from memset keys, so the byte where `uber` now sits
  is 0 in every one of them. A warm-up cannot bring back an `uber=1` key and so cannot reach the
  `abort()` in `shader_module_compile_sync`.
- `uber_comb_loc` comes from `uniform_index()`, which returns -1 when the name is absent
  (`vk/glsl.h:104`). It is set in `update_shader_uniform_locs` on the same paths as the existing
  `uniform_locs`, before `ready` is published. `pgraph_vk_update_shader_uniforms` returns early on
  a binding that is not ready. So a default module never uploads `ubComb`, and no uninitialised
  location is read.

**Under the switch.**
- Uniform freshness: a combiner-register write bumps `shader_state_gen`, which forces
  `bind_shaders`. That reaches `pgraph_vk_update_shader_uniforms` at its tail (`shaders.c:1619`)
  even when the family binding is unchanged. The early-hit path in `draw.c:2225` also refreshes
  uniforms. `ubComb` is written into the layout before the layout hash is taken, so a
  program-only change is uploaded.
- Only `glsl/psh.c` reads the combiner fields of `binding->state.psh`. A grep of `vk/` and `glsl/`
  finds no other reader. Substituting the family therefore changes nothing outside the combiner
  block.
- The splice in `pgraph_glsl_gen_psh_uber` checks the template's shape: uniform block, then
  `main`, then `// Stage 0`, then the final combiner's `fragColor.a =` line, and only one stage in
  between. On a mismatch it returns NULL.
- `ubComb` is the uniform the interpreter reads. `ubComb[8].z` carries `combiner_control`, and its
  stage count is clamped to 8, as `psh_num_combiner_stages` clamps it.
  `pgraph_glsl_psh_uber_comb_values` zeroes the stages beyond the count.
- Evidence covers the code: the E leg's refs are `2ca713adec` (A) and `e677a46a66` (B, differs
  only by `HAKUX_PSH_UBER_DEFAULT 1`). The only lane code commit on `hw/` since then is
  `bca7958c32`, the GPL capability probe. It is log-only, runs once under the switch, and creates
  nothing. Everything else on `hw/` since `2ca713adec` came in with master merges.

## Findings

### LOW 1: `uber_modules` counter is incremented from compile workers without synchronisation
`shaders.c`, `shader_module_compile_sync`: `static int uber_modules; ... ++uber_modules`.
Under async compile this function runs on compile-worker threads.
- Scenario: `HAKUX_PSH_UBER=1` with async compile on, and two family modules compile at the same
  time. Two log lines can then carry the same "family module N", or skip a number.
- Blast radius: log numbering only, and only under the debug switch. Nothing reads the number;
  the lane's readers count lines.
- Fix if kept: `qatomic_inc_fetch`.

### LOW 2: a text change in psh.c's combiner block aborts every switch-on run instead of falling back
`pgraph_glsl_gen_psh_uber` returns NULL when the template has an unexpected shape. The caller
then calls `abort()`, because the key already names a family state, and drawing the template
would draw the wrong program. The comment defends that choice, and it is right for a debug
switch.
- Scenario: a later PR renames `// Stage 0` or restructures the final combiner's `fragColor.a`
  line in `psh.c`. Every `HAKUX_PSH_UBER=1` boot then aborts at the first covered draw. Default
  builds are unaffected.
- The shape check is the only guard. No selftest or CI leg generates the family template and runs
  the splice, so the breakage would first show on a device arm.
- Suggestion, for the build PR (`lane/uberspike569-gpl`) rather than here: a host-side check that
  runs `pgraph_glsl_gen_psh_uber` on the template and asserts non-NULL. Better still, decide
  coverage at key time: call `covers()` together with a cached "splice works" bit, so that a
  failed splice falls back to the specialised state before the family is substituted.

### LOW 3: the spike is exact on the device suites but not bit-exact by construction
The header and the PR body both state this. On lavapipe, 2 of 548 random programs differ by
1 LSB, because the specialised shader's constant folding and reassociation are not available to
the interpreter. The device E leg found 305 of 305 identical.
- Scenario: a title whose combiner program sits on a (k+0.5)/255 boundary, with a constant input
  that NIR reassociates, draws 1 LSB off under the switch.
- This is not a defect of this PR, which is debug-only and default off. It is a condition on any
  follow-up that turns the ubershader on by default: that PR needs its own exactness leg, or the
  "exact arithmetic on both paths" fix that `psh-uber.c` names.

## Not findings
- `pgraph_glsl_psh_uber_is_family` compares whole structs with `memcmp`, padding included. A
  family is always made by struct copy plus `set_template`, which preserves the padding. A guest
  state that happens to equal the template program maps to itself either way.
- `uber_log_gpl_support` calls `vkGetPhysicalDeviceFeatures2`/`Properties2` only when the extension
  is listed, and only once, under the switch.

## Verdict
No HIGH or MEDIUM findings. The three LOWs do not have to be fixed for this debug-only,
default-off spike to fold. LOW 2 and LOW 3 are carried as conditions on the follow-up build PR.
Label: `needs-audit-2`.
