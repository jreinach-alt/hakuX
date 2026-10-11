postput1010: post the guest's DMA_PUT store when pfifo.lock is busy, behind HAKUX_POSTED_PUT=1 (#433, 0.5)
State: not ready (the A/B is queued; reportasync1010 is not on master yet)

Lane: postput1010       Issue: #433 (umbrella), none filed
Base: master @ b74cff74ed, with origin/lane/reportasync1010 @ 4b50801b21 merged in (0d7948085e). The A/B runs on c63ec9774f.
Files: hw/xbox/nv2a/user.c, hw/xbox/nv2a/nv2a_int.h, hw/xbox/nv2a/pfifo.c, docs/lanes/postput1010/**, docs/testing/predictions/postput1010-*.json
Prediction: docs/testing/predictions/postput1010-nfs.json @ 1987085cd7bf0642c4678302bef5b9b9f9157bad3d9a6a341b318fec7446d7a5 (race start, A/B/B/A, plain build, ref c63ec9774f): pending
Prediction: docs/testing/predictions/postput1010-ftpair.json @ 45cb51e232b56881d4eb20f03dc5214f05db490463f6f8adea009865377849de (race-start frametrace pair, perflog, ref c63ec9774f): pending
Needs device: yes (Nova)
Needs NDK: yes

Release note (none): opt-in switch, off by default.

Step 2b of docs/lanes/nfs30plan1010/PLAN.md. With `HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1` at NFS Most Wanted's race
start, the guest vCPU waits 6.3 ms per warm frame (7.3 per heavy frame) for `pfifo.lock` to store DMA_PUT, while the
PFIFO thread parses under that lock. The PFIFO thread then idles 13.6 ms waiting for the guest's next push
(`1-1791671434-reportasync1010-3857196`, perflog). `HAKUX_POSTED_PUT=1` re-arms lane.vcpusleep's posted store
(`c2dfca18a1`, reverted in `f6ac723228`) as a runtime switch. When the lock is busy, the store is posted the way the
hardware posts it, and the lock is taken only to wake a parked PFIFO thread. With the switch off, `user_write`, the
pusher and the PFIFO thread's wait run master's statements.

Changes from `c2dfca18a1`: a runtime switch instead of a compile-time default-on; the kick is stored with release,
and the park re-reads DMA_PUT against what the loop top saw, which closes a hole on ARMv8 where the kick could become
visible before DMA_PUT; the poster's wake lock is counted in `lockw`. NOTES.md section 2.1 explains how every
wakeup is kept.

`docs/lanes/postput1010/selftest_postput.sh` compiles user.c and the posted-put block verbatim and passes with the
switch on and off: 100,000 stores against the real park and kick, with no lost wakeup, and a store-buffering race of
3.2 M rounds with none lost. Its five mutants each go red, including one per barrier (NOTES.md section 3).

Pilot (A1 `1-1791680038-postput1010-1949730`, B1 `1-1791680039-postput1010-1954673`): warm countdown A1 33.90 ms
and B1 33.99 ms; post-GO 33.50 and 33.49 ms. B1 posted 16 % of the countdown's stores. A's baseline is 3.5 ms faster
than the one the prediction registered (37.5 ms on 3cd9d6b7e3); NOTES.md section 4.1 explains why. B2, A2 and the
frametrace pair are queued (`docs/lanes/postput1010/WAITING`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
