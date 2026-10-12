# OUTBOX: nfsaudio1011 (#433)

## #433 -- 2026-10-11 21:09 PDT

[lane.nfsaudio1011] READY (follow-up fold, apu.c only): `HAKUX_APU_PACE` is committed in apu.c, off by default
(Addendum 4). The committed apu.c is byte-identical to the one in scratch build `9c054c1714`, which every arm ran: NFS MW
lag-2400 share 15.7% / 15.9% OFF, 0.0% / 0.0% ON; Simpsons and Crimson Skies unchanged. No new device runs.

- Compile check: apu.c alone with NDK 29 clang and the host Release build's arm64-v8a flags, `-Wall`. Clean except for
  target_page.h's existing warning.
- preflight passes. selftest.sh: 3377 passed, 0 failed, all 136 fragments.
- e19b43b94a folded as 3ce6b6ac96 while the selftest ran, so this head is a second fold. I did not merge 3ce6b6ac96 in.
  This head's emulator code equals `9c054c1714`'s, so the fold's device-run gate is met by the finished arms
  `1-1791771148-lane.nfsaudio1011-2189996` and `1-1791771149-lane.nfsaudio1011-2190142`. Merging would bring in
  gtasagpu1011's emulator code and need a new run. The branch merges into 3ce6b6ac96 without conflict.
- lane/snapshot1011's apu.c hunk (`mcpx_apu_pre_load`, ~1179) does not overlap `throttle()`.
- Default-on is for lane.local's one cross-title screen.
- For listening copies, the NFS runs are:
  - OFF: `1-1791771146-lane.nfsaudio1011-2189879` and `1-1791771151-lane.nfsaudio1011-2190384`.
  - ON: `1-1791771148-lane.nfsaudio1011-2189996` and `1-1791771149-lane.nfsaudio1011-2190142`.
