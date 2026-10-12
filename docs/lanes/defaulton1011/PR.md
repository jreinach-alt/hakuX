defaulton1011: HAKUX_VTX_HAZARD and HAKUX_APU_PACE on by default -- GTA San Andreas sky, NFS Most Wanted audio (#433, 0.5)
State: ready

Lane: defaulton1011      Issue: #433 (umbrella), none filed
Base: master @ 5326de78b2 (gtasagpu1011 and nfsaudio1011 both folded)
Files: hw/xbox/nv2a/pgraph/vk/vertex.c, hw/xbox/mcpx/apu/apu.c, docs/lanes/defaulton1011/PR.md, docs/lanes/defaulton1011/NOTES.md
Prediction: none; the evidence is the owner's hands-on test of this exact emulator code with both switches set (below)
Needs device: yes (Nova)    Needs NDK: yes

Release note (other): GTA San Andreas: fixed hard-edged white polygons in the sky. Need for Speed Most Wanted: fixed stuttering and repeated audio in movies and speech.

## What changed

Two switches that master already carries, off by default, are now on by default. Each is read once, where it was
read before; only what an unset variable means changes.

| switch | file | before | now | turn it off |
|---|---|---|---|---|
| `HAKUX_VTX_HAZARD` | `hw/xbox/nv2a/pgraph/vk/vertex.c`, `vtxhz_env()` | on only for a value > 0 | unset is on | `HAKUX_VTX_HAZARD=0` |
| `HAKUX_APU_PACE` | `hw/xbox/mcpx/apu/apu.c`, `apu_pace_on()` | on only for exactly `1` | unset is on | any value but `1`, e.g. `HAKUX_APU_PACE=0` |

Both still log once in logcat. When the variable is unset, the line now says so:
`HAKUX_VTX_HAZARD=1 (finish before an upload that rewrites an earlier draw's vertices) (default)` and
`apu_pace: on (HAKUX_APU_PACE, default)`. The existing readers still match: `gtasagpu1011/scrread.py` keys on
`HAKUX_VTX_HAZARD=<v> (finish before`, and the nfsaudio1011 predictions on the `apu_pace: on` prefix.

Neither switch joins "Fast renderer paths" (`FASTPATHS_VARS`, MainActivity.kt). The vertex hazard is a correctness
fix, and the pacing is audio. Neither is a speed path that a player should lose when they turn that toggle off.

**`HAKUX_VTX_HAZARD`** (gtasagpu1011). When an upload would rewrite vertex RAM bytes that an earlier draw in the same
command buffer reads, the renderer finishes the command buffer first. GTA SA's sky band is drawn through RenderWare's
one immediate-mode buffer, which later draws rewrite before submit, so without the switch the sky draw runs with their
vertices. Where no such upload happens, the switch costs a few loads per draw and changes nothing. vertex.c is shared
code, so the desktop Vulkan build gets the same default.

**`HAKUX_APU_PACE`** (nfsaudio1011). On Android, `throttle()` now runs the low-watermark pacing that every other build
already runs. Without it, the voice processor runs a whole device period of frames back to back after each drain, and
NFS MW's movie and speech ring is overrun and replays audio from 50 ms earlier. The code is under `#ifdef __ANDROID__`,
so other builds are unchanged.

## Evidence

The owner played 10 titles on the Nova on a build of master `5326de78b2` with `HAKUX_APU_PACE=1` and
`HAKUX_VTX_HAZARD=1` set (2026-10-11, 21:44-22:30 PDT). That is the emulator code this branch ships, with the switches
set by environment instead of by default. Titles: GTA San Andreas, Need for Speed: Most Wanted, SpongeBob: Battle for
Bikini Bottom, The Simpsons: Hit & Run, Indigo Prophecy, Legacy of Kain: Defiance, Max Payne 2, Halo: Combat Evolved,
Jet Set Radio Future and Mortal Kombat: Armageddon.

- No stutter, dragged speech, repeats or gaps in any title.
- Nine titles had no defect at all.
- Halo had two defects, and neither comes from these switches:
  - #938: speech is much quieter than music and effects. It is a known Halo issue, not specific to hakuX. The pacing
    changes when audio is handed to the device, not how loud it is.
  - #939: the ring world on the main menu flickers. The vertex hazard finished nothing in two menu sessions with the
    switch on (no `vtx_hazard:` line in either), so the menu ran the same path as with the switch off.

The per-switch measurements are in the two source lanes' PRs: `docs/lanes/gtasagpu1011/PR.md` (sky: 0 defects in 136
stills and 240 video frames with the switch, against 5 in 67 and 7 in 120 without) and `docs/lanes/nfsaudio1011/PR.md`.

## Checks

- `docs/testing/preflight.sh`: see NOTES.md.
- Android build of this head: see NOTES.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
