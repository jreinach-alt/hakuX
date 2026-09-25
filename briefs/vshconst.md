# #233: a vertex program that writes a constant register must not abort, and must compute what silicon computes

Lane: vshconst            Issue: #233 (ROADMAP priority 1: a guest-reachable crash)
Base: origin/master (fetch first).
Files: hw/xbox/nv2a/pgraph/glsl/vsh-prog.c, hw/xbox/nv2a/pgraph/glsl/vsh-prog.h,
hw/xbox/nv2a/pgraph/glsl/vsh.c, hw/xbox/nv2a/pgraph/glsl/vsh.h,
docs/testing/predictions/vshconst-*.json, docs/lanes/vshconst/**.
If the fix needs the renderers' constant upload (for example gl/shaders.c or
vk/shaders.c), say so in a board request. Do not edit them unclaimed.
Needs device: yes (the must-not-move arm). Needs NDK: no.

## The crash, verified on master 2026-09-25 before this brief was written

- `vsh-prog.c:382-383`, `decode_opcode`: when `FLD_OUT_ORB == OUTPUT_C` (a
  write to a CONSTANT register) it runs
  `assert(!"TODO: Emulate writeable const registers")`. Past the assert it
  emits `cN` as the output anyway. It is the only such TODO under `hw/`, and
  the GLSL translator is shared by GL and Vulkan.
- `android/app/src/main/cpp/CMakeLists.txt:918,1027,1064` pass `-UNDEBUG` for
  every release config, so the assert is LIVE on the handhelds and the
  emulator aborts.
- Reproduced: desktop GL aborts in nxdk_vsh_tests' ILU RCP Tests
  (lane.toolsmith, #112).

## The oracle

The console ran `ILU RCP Tests::IluRcpTests` to completion twice, byte-identical
(lane.xbox, PR #225):

- `/home/justin/hakux-work/hardware/runs/2026-09-25-vsh/stage1b/console/ILU_RCP_Tests/IluRcpTests.txt`
  holds the exact printed values. That is the golden.
- `IluRcpTests.png` sits beside it.

The program is at `~/nxdk_vsh_tests`, branch `hakux/completion-marker` (`c3dde45`),
built with nxdk `bafba08`. The build needs `NXDK_DIR` and
`BISON_PKGDATADIR=~/.local/nxdk-tools/root/usr/share/bison`. Run it on a desktop
build and diff the printed text exactly. Once PR #229 folds, `request.sh --program
vsh` plus `vsh_score.py` do the same on a handheld, and the handheld is the run
that counts.

## Open question, settle it and do not assume it

Do constant writes persist ACROSS draws, or only within one program run?
Nothing has measured it. Read ILU RCP Tests' source in `~/nxdk_vsh_tests` for
what it depends on. If that doesn't settle it, ask for a targeted console run
on #233. lane.xbox owns the console, and the host session routes the request.

## The job

1. Grep every path that translates a vertex program's output select, in case
   OUTPUT_C is mishandled somewhere without a TODO.
2. Emulate the write. At minimum it must be visible to later reads in the same
   program run. Implement cross-draw persistence ONLY if step "open question"
   shows silicon does it.
3. Do NOT just delete the assert. That turns a loud crash into silently wrong
   values.
4. Proof:
   - ILU RCP Tests' printed values match the silicon `.txt` exactly (desktop
     now, handheld after #229).
   - AND an arm registered BEFORE the device run
     (`docs/testing/ab_compare.py --register`) whose must_not_move covers the
     vertex-program suites: `Vertex shader independence tests`, `Vertex shader
     rounding tests`, `Vertex shader swizzle tests`, plus W param and any other
     suite `nv2a_index.py blast hw/xbox/nv2a/pgraph/glsl/vsh-prog.c` names.
     Name the patch change that would move each leg. A change in how constants
     are READ touches every program, so those legs are live.

## Done when

- The printed-value match and the arm verdict are posted on #233.
- NOTES record the persistence answer and its source.
- The PR carries the lane template with its `Files:` line, preflight passes,
  and the PR is marked ready.
