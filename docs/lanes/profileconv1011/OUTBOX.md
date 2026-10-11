# lane.profileconv1011 outbox

## #433 -- 2026-10-11 13:42 PDT

[lane.profileconv1011] waiting: one Nova soak, `1-1791749881-profileconv1011-1652106`
(Amped 2 re-run, `amped2` route, 900s/frames_every 60, no env). It is queued
behind ~7560s of device time (the running `lane.gtasagpu1011` request plus 25
queued requests ahead of mine, mostly `nfsdefault1011`), at `priority: study`
-- no hold taken, nothing jumps the line. It resolves when
`dispatch/results/1-1791749881-profileconv1011-1652106/result.json` exists;
NOTES.md section 7 has the frame-comparison method to apply once it does.

GTA SA is already CONFIRMED (NOTES.md section 6, run
`1-1791746513-profileconv1011-1034280`). Amped 2 attempt 1
(`1-1791746520-profileconv1011-1034452`) hit a device/WSL adb flake at 536s of
900s, not a route problem (NOTES.md section 7); this re-run is to get a clean,
complete frame set. 3 of the 4 allowed device runs are used/committed; the
budget allows one more if this re-run also needs a retry, but not for an
infra flake a second time without the frames saying so.
