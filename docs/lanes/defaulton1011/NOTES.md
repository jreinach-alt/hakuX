# defaulton1011 notes

Two switches on by default at their readers: `vtxhz_env()` in vk/vertex.c and `apu_pace_on()` in apu/apu.c.

## Why at the readers, not in FASTPATHS_VARS

nfsdefault1011 turned its switches on by adding them to "Fast renderer paths" (`FASTPATHS_VARS`, MainActivity.kt).
These two are not speed paths. One is a rendering correctness fix and the other is audio timing. A player who turns
fast paths off to work around a renderer problem should not lose either one.

## The owner's test (2026-10-11 21:44-22:30 PDT)

- Build: master `5326de78b2`, built in the dispatcher's build tree with JDK 21 and installed on the Nova at 21:44.
- Environment: `env_vars` held `HAKUX_APU_PACE=1` and `HAKUX_VTX_HAZARD=1`. I read the value back from the device to
  confirm.
- 10 titles (listed in PR.md). The owner's report: "This is the only defect I found. Everything else is perfect." The
  only defects were Halo's speech level and its menu ring flicker, filed as #938 and #939.
- Halo menu logcat, 22:24 and 22:26 sessions: `HAKUX_VTX_HAZARD=1` and `apu_pace: on` at init, then no `vtx_hazard:`
  line in either session. The counter line appears only when a finish happens, at most once per 10 s, so this means
  zero finishes.
- A caveat on the owner's second Halo look: the env box under Settings applies only after its Save button is pressed.
  That launch still logged `HAKUX_VTX_HAZARD=1`, so it was not an OFF look. The zero-finish count is the evidence that
  the switch did not act in the menu.

## Readers of the log lines

- `docs/lanes/gtasagpu1011/scrread.py` matches `HAKUX_VTX_HAZARD=(\d+) \(finish before`. The default marker goes at
  the end of the line so this still matches.
- The nfsaudio1011 predictions grep for the `apu_pace: on` prefix, which still matches.

## Checks

- `docs/testing/preflight.sh`: passed (psh_differ, aci_vmstate, nv2a index, territory, coverage, board files).
- Android debug build of the code in this head, NDK arm64-v8a: BUILD SUCCESSFUL. `libxemu.so` carries both new log
  formats, `apu_pace: %s (HAKUX_APU_PACE%s)` and `HAKUX_VTX_HAZARD=%d (finish before ... vertices)%s`.
