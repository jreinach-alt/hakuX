# bf2stall433: Battlefield 2's per-draw GPU cost is serialized draws, not vertex fetch or barriers (#433)

State: ready

Lane: bf2stall433            Issue: #433
Base: master @ b71f92a12a
Files: docs/lanes/bf2stall433/NOTES.md, docs/lanes/bf2stall433/OUTBOX.md, docs/lanes/bf2stall433/PR.md, docs/lanes/bf2stall433/armread.py, docs/testing/predictions/bf2stall433-bf2-soak.json, docs/testing/predictions/bf2stall433-syncdraw.json
Prediction: docs/testing/predictions/bf2stall433-bf2-soak.json (judged FAIL: V refuted), docs/testing/predictions/bf2stall433-syncdraw.json (judged S)
Needs device: yes (done: 3 Nova runs)    Needs NDK: no (the fix that was built is reverted)

## Outcome

The brief asked for the per-draw GPU stall and its fix. This lane built the
fix the code supported, measured it, and the measurement refuted it.
**No emulator change ships from this branch.** What it leaves is the
diagnosis: the next fix, and the measurement that sizes it.

1. **Master has no per-draw barrier, event or render-pass split** in BF2's
   heavy views. A frame has ~2,150 draws, 45 render passes and ~7 barriers,
   and 41.8 of 42.6 ms of GPU time is inside passes. The full per-draw list is
   NOTES section 1.
2. **Vertex fetch (V): refuted.** Every draw reads vertex RAM from host copies
   that are IO-coherent cached memory. The device confirmed it:
   `[vtxmirror] ... host type 1 flags 0xf cached=1 coherent=1`. A device-local
   mirror removed the snoop path, and heavy-view GPU time did not move.
3. **The draws are serialized (S).** `TU_DEBUG=sysmem,syncdraw` drains the GPU
   before every draw and adds only ~3.8 us per draw. So BF2's draws already
   run close to one at a time, and the 12-14 us per draw is exposed latency.
   That is why a faster GPU clock did not clear it.
4. **Prime suspect, and the fix that fits Adreno:** every draw rebinds the
   uniform block at a new dynamic offset, which in Turnip means a new
   descriptor set, an invalidation of the bindless caches and a constant
   reload. The fix is to pass the constants a game changes between draws as
   push constants (loaded straight from the command stream) and rebind the
   UBO only when its content changes. **That is vk/shaders.c, glsl/vsh*.c and
   draw.c, outside this lane's territory.** Size it first with a per-draw
   histogram of constant registers written (NOTES section 8).

## Measurements (Nova, default regimen, perflog, bf2mc route, 420 s; `armread.py`)

| run | ref / env | heavy rows | heavy GPU ms | fit ms/draw | verdict |
|---|---|---|---|---|---|
| A1 `1-1790948452-lane.bf2stall433-3362375` | master b71f92a12a | 17 | 35.9 | 0.0111 | baseline |
| B1 `1-1790948456-lane.bf2stall433-3362482` | 57fe561924 (mirror) | 20 | 36.0 | 0.0099 | **P1 FAIL**: B/A 1.004 (PASS needed <= 0.80); P0 premise PASS |
| syncdraw `1-1790950456-lane.bf2stall433-3764595` | master, `TU_DEBUG=sysmem,syncdraw` | 19 | 43.9 | 0.0142 | **S**: x1.249 against sysmem 35.15 (S leg <= x1.25), slope <= 0.016 |
| (baseline) `1-1790920235-lane.collapse433-601955` | 8b45e7c15c, `TU_DEBUG=sysmem` (hw/ identical) | 22 | 35.15 | 0.0121 | -- |

**Did the player move?** Yes, in all three runs. The frames show the mission
clock running (00:28 -> 00:49 in A1, 00:28 -> 01:11 in B1), ammo falling
(22|75 -> 19|50, and 22|75 -> 14|25), and the view moving from the town
square (the heavy view) to a wall by the end of the 38-61 s of play. The 420 s
cap leaves that little play after BF2's menus. The heavy rows come from the
square, which every run plays through.

The heavy-view S leg passed by 0.04 ms, on one run against a baseline from
another day. Read it as "mostly serialized", not "fully".

## What was built, measured, and reverted

57fe561924, a device-local vertex-RAM mirror (vk/draw.c), stays in this
branch's history. It is reverted at the head: draw.c equals master. The rest
of its 3+3 was not queued, because the pilot pair already refuted it at
resolution. Its pixel and band predictions are deleted, and the 4 arms the
arms job had queued for them are in `$DISPATCH_DIR/queue/withdrawn/`. Its GTA
prediction is deleted too.

## Local checks

- `docs/testing/preflight.sh --allow-tracker`: "preflight passed", rc 0.
  psh_differ, aci_vmstate, nv2a index, territory and board files ok. The
  coverage gate DID NOT RUN (gh 403, account suspended), and preflight says
  so itself.
- `armread.py` reproduces collapse433's published table from its soaks (slopes
  0.0119 / 0.0121).
- While the mirror was in the tree: NDK clang type-check of draw.c, release and
  perflog, rc 0, only pre-existing warnings.
- No emulator code at the head (`git diff --stat origin/master...HEAD` is
  docs only), so the offline fold needs no head run. Nova runs used: 3 of 6.

Release note (none): diagnosis only; no emulator change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
