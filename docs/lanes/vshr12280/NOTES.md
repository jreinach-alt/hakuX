# lane.vshr12280 -- #280 Multioutput: R12 must read the oPos the instruction started with

Started 2026-09-25 on master @ d92ae5d7f3; merged master @ d709a8d1fa (no `hw/`
change between them) before registering.

## The test's own program

`nxdk_pgraph_tests/src/shaders/vertex_shader_mac_independence_tests.vsh`
(tokens from `build-xbe/src/shaders/*.vshinc`):

| slot | instruction | MAC dest | ILU dest | reads R12 |
|---|---|---|---|---|
| 0 | `mov oPos, v3` (diffuse) | oPos | - | - |
| 1 | `sge oPos.w, r0.w, r0.w` | oPos.w | - | - |
| 2 | `add oPos.xyz, r12, v4 + add r0.xyz, r12, v4` | oPos.xyz **and** R0.xyz (one MAC op, output + temp) | - | yes |
| 3 | `mov oD0, r0` | oD0 | - | - |
| 4 | `rcp oPos.x, v3.x` | - | oPos.x | - |
| 5 | `rcp oPos.x, r12.x + rcp r1.x, r12.x` | - | oPos.x **and** R1.x (one unpaired ILU op, output + temp) | yes |
| 6 | `mov oD1, r1.x` | oD1 | - | - |
| 7 | `mov oPos, v0` (final) | oPos | - | - |

Neither "+" pairs a MAC with an ILU. Each is **one** unit's op writing its single
result to an output register and to a temporary at once. So "MAC vs ILU, and in
which order" does not apply. Silicon (the golden: two uniform rows matching the
left-hand controls) computes each result once from the oPos the instruction
started with, and sends it to both destinations:
R0 = diffuse + specular = (0.5, 0.5, 0), and R1.x = 1/(1/0.5) = 0.5 grey.

## Mechanism

`vsh-prog.c:decode_opcode` emitted the output write first and then the temp
write as a second statement with the same inputs. Master's GLSL for slot 2 and slot 5:

```
ADD(oPos,xyz, R12, v4);   ADD(R0,xyz, R12, v4);
RCP(oPos,x, R12.x);       RCP(R1,x, R12.x);
```

`#define R12 oPos` (line 580, the issue's guess) is **not** itself the fault:
R12 genuinely is oPos. The fault is statement order. The temp statement reads
R12 after the output statement changed it, so R0 got specular twice (green
0.5 -> 1.0) and R1 got a double reciprocal (0.5 -> 2 -> white). Both 128x128
right-hand quads were wrong: 2 x 16384 = 32768 px, max_rgb 127, which is the
score in the sweeps.

The same ordering bug hits a paired MAC that writes oPos while its ILU reads R12
as input C. The paired MAC's output write was emitted before the ILU statement.

## Fix

`decode_opcode` takes an `opos_suffix`. When the output register is oPos and
anything else in the same instruction follows (a temp write of the same unit,
or a paired ILU), the op writes `_opos_tmp` instead, and
`oPos.<mask> = _opos_tmp.<mask>;` is appended at the very end of the token (after
the ILU and the MAC's `_temp_vec` suffix). `vec4 _opos_tmp;` joins `_temp_vec`
in the header. Patched GLSL for slot 2:

```
ADD(_opos_tmp,xyz, R12, v4);
ADD(R0,xyz, R12, v4);
oPos.xyz = _opos_tmp.xyz;
```

## What else it touches (desktop emitter diff)

`nv2a_index.py blast hw/xbox/nv2a/pgraph/glsl/vsh-prog.c` returns nothing, so I
diffed master's vs the patched `pgraph_glsl_gen_vsh_prog` body output over
**every** vertex program in nxdk_pgraph_tests. That is 47 programs: the 33 `.vsh`
-> `.vshinc`, the Cg `attribute_explicit_setter_tests.inl`, and every static
`uint32_t x[] = {...}` token array under `src/`. **Only one program's body
changes:** vertex_shader_mac_independence_tests. No other program has the shape
(an oPos write plus a temp write or a paired ILU), so there is no "legitimately
reads the second write" program to register a leg for. For every other program
the only change is the unused header global. The must-not-move legs guard that
line: if it broke compilation, every vertex-program draw would blank.

The harness was a scratch `gcc` build of `vsh-prog.c` against glib, with a stub
`qemu/osdep.h` and the tokens on stdin. It is not committed. To rebuild it:
`-Istub -I. -Iinclude -I<glib>`, then call `pgraph_glsl_gen_vsh_prog` and
print the body.

## Prediction

`docs/testing/predictions/vshr12280-multioutput.json`, a=d709a8d1fa (master),
b=8dce0cf12e. Must move: `Vertex_shader_independence_tests/Multioutput` 32768 -> 0.
Must not move: MAC_ILU_Independence, Vertex shader rounding/swizzle, Attrib
carryover, Fog vsh, Fog coord vec4, W param.

## Not chased

- **Constant-file sibling.** An *unpaired* op that writes a constant register
  and a temp, where the temp write reads that same constant, has the same
  order bug in the `c_rw` path. The paired case is already handled via
  `_c_rw_tmp`. No program in the corpus has this shape. I left it alone to keep
  this change to R12.
- **R12 as a temp *destination*** (`R%d` with reg 12 writes oPos through the
  define). No known program does this, and silicon behaviour is unmeasured.
- Console set K (hardware/runs/2026-09-19-calib) does not cover this suite. The
  golden is the only silicon reference, and it agrees with the test's stated
  intent.
