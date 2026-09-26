#!/bin/bash
# Register lane.pshqueue's three predictions, one per hunk commit. Each a_ref
# is the hunk's parent, so a regression names one hunk. runs_per_arm is added
# afterwards (the flag does not exist), as texvol283-bytes16.json did.
set -eu
cd "$(dirname "$0")/../../.."
P=docs/testing/predictions
AB=docs/testing/ab_compare.py

python3 $AB --register $P/pshqueue-279-dotzw.json --who lane.pshqueue --issue 279 \
  --a-ref 5d23f1fec8 --b-ref 24546d197b \
  --disc-suites 'Pixel shader' \
  --expect-count better=1 --expect-count worse=0 \
  --must-not-move 'Pixel_shader/BumpEnvMap' \
  --must-not-move 'Pixel_shader/BumpEnvMapLuminance' \
  --must-not-move 'Pixel_shader/ClipPlane' \
  --must-not-move 'Pixel_shader/DotST' \
  --must-not-move 'Pixel_shader/Passthru' \
  --must-not-move 'Pixel_shader/StageDependentAlphaRed' \
  --must-not-move 'Pixel_shader/StageDependentGreenBlue' \
  --prediction "#279 (docs/lanes/cloud-279/NOTES.md): DOT_ZW (texm3x2depth) overrides the fragment depth with dot(i-1)/dot(i) in depth-word units, floored and clamped to clipRange.y, emitted only where depth_needed is set (non-GL path; the handheld arm runs Vulkan). MUST MOVE: Pixel_shader/DotZW 65,536 -> at most ~137 px (the rule fits 65,399 of 65,536 px exact offline; the misses sit within 0.0093 of an integer z/w, float-divide precision). Machine-checked as better=1, worse=0; the magnitude is read off the verdict, and a DotZW that moves but lands far above ~137 refutes the model (report it, do not tune). MUST NOT MOVE, with what would move each: Pixel_shader/DotST shares DotZW's stage setup and dot1/dot2 and is 0 px today, its shader text is byte-identical under the hunk, so a move means the edit leaked outside the DOT_ZW case; the other six Pixel_shader captures set no DOT_ZW stage (only pixel_shader_tests.cpp names DOT_ZW, per docs/lanes/pshqueue/mode_users.py), so a move is a shader-cache or build artefact, not the rule."

python3 $AB --register $P/pshqueue-285-g8b8.json --who lane.pshqueue --issue 285 \
  --a-ref 24546d197b --b-ref a389648b0b \
  --disc-suites 'Surface format,Surface clip,Blend surface' \
  --expect-count better=2 --expect-count worse=0 \
  --must-not-move 'Surface_format/Fmt_A8R8G8B8' \
  --must-not-move 'Surface_format/Fmt_R5G6B5' \
  --must-not-move 'Surface_format/Fmt_X1A7R8G8B8_*' \
  --must-not-move 'Surface_format/Fmt_X1R5G5B5_*' \
  --must-not-move 'Surface_format/Fmt_X8R8G8B8_*' \
  --must-not-move 'Surface_clip/*' \
  --must-not-move 'Blend_surface/*' \
  --prediction "#285 (docs/lanes/g8b8285/NOTES.md): on a B8 or G8B8 surface, a uniform gated on the live guest colour format swaps fragColor.rb after the #59 pad block, so the host R channel (byte 0) stores the combiner's b as silicon does. MUST MOVE (better=2, worse=0): Surface_format/Fmt_G8B8 32,552 -> at most ~100 px (bottom half to 0 by the model, top half by argument), and Surface_format/Fmt_B8 16,144 (label-differs, scored) down by its quad pixels; B8 not moving would refute the B8 half of the gate. MUST NOT MOVE, with what would move each: Surface_format/Fmt_R5G6B5 is the discriminating leg, 0 today and the next test after G8B8 in std::map order, so a stale uniform reaching a non-B8/G8B8 draw moves it first; the other Surface_format rows and Blend_surface/* likewise move only on a gate leak. Surface_clip/*_B8 and *_G8B8 are an inert control, not a measurement: they draw only r == b colours, so the swap cannot change them; they move only if clipping leaks. The rest of Surface_clip draws non-B8 formats (leak guard)."

python3 $AB --register $P/pshqueue-315-brdf.json --who lane.pshqueue --issue 315 \
  --a-ref a389648b0b --b-ref e3b13f5b45 \
  --disc-suites 'Texture BRDF,Pixel shader,Volume texture' \
  --expect-count better=3 --expect-count worse=0 \
  --must-not-move 'Pixel_shader/*' \
  --must-not-move 'Volume_texture/*' \
  --prediction "#315 (docs/lanes/brdf315/NOTES.md): a BRDF stage gets a sampler3D and reads texture(texSamp_i, vec3(t[i-2].r, t[i-1].r, fract(t[i-1].g - t[i-2].g))), requiring no dot product of its feeding stages. MUST MOVE (better=3, worse=0): Texture_BRDF/BRDF_e0_l0, BRDF_e0_l1, BRDF_e1_l0, each 614 -> at most 30 px (offline 605/610 wedge pixels whole-texel exact, about 9 expected). The value falsifier, read by hand off the B capture: pixel (639,479) reads (198,246,222,255), not (18,18,18,254). MUST NOT MOVE, with what would move each: Pixel_shader/* and Volume_texture/* set no BRDF stage (only texture_brdf_tests.cpp does), and Volume_texture is where 3D samplers are declared, so a move there means the new get_sampler_type case changed another mode's sampler (a case falling into it), or a stale shader-key cache served a program from the other build."

python3 - "$P" <<'PY'
import json, sys
for n in ('pshqueue-279-dotzw', 'pshqueue-285-g8b8', 'pshqueue-315-brdf'):
    p = '%s/%s.json' % (sys.argv[1], n)
    d = json.load(open(p))
    d['runs_per_arm'] = 2
    s = json.dumps(d, indent=2) + '\n'
    json.loads(s)
    open(p, 'w').write(s)
    print(p, d['a_ref'], d['b_ref'], d['disc']['suites'], d['expect_counts'])
PY
