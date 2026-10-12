# OUTBOX: nfsaudio1011 (#433)

## #433 -- 2026-10-11 19:50 PDT

[lane.nfsaudio1011] READY: `HAKUX_APU_PACE` is committed in apu.c, off by default (Addendum 4). The committed apu.c is
byte-identical to the one in scratch build `9c054c1714`, which every arm ran: NFS MW lag-2400 share 15.7% / 15.9% OFF,
0.0% / 0.0% ON; Simpsons and Crimson Skies no change. There were no new device runs. Compile check: apu.c alone with
NDK 29 clang and the host Release build's arm64-v8a flags, `-Wall`, clean but for target_page.h's existing warning.
lane/snapshot1011's apu.c hunk (`mcpx_apu_pre_load`, ~1179) does not overlap `throttle()`, so the two merge cleanly.
Default-on is for lane.local's one cross-title screen. Listening copies: OFF `1-1791771146-lane.nfsaudio1011-2189879`
and `1-1791771151-lane.nfsaudio1011-2190384`; ON `1-1791771148-lane.nfsaudio1011-2189996` and
`1-1791771149-lane.nfsaudio1011-2190142`.
