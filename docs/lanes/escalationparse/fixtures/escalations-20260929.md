- 09-27 07:27 PDT (hostops) OWNER, Windows side: C: has 16.6 GB free (1.9 TB drive, 100%). The WSL VHDX is 298 GB (ext4.vhdx under CanonicalGroupLimited.Ubuntu.../LocalState, NOT sparse) while ext4 uses 242 GB, so about 56 GB can be reclaimed, but only with WSL shut down. If C: fills, WSL and the pagefile both fail. Options in a restart window (winddown/spin-up.sh): (1) wsl --shutdown, then wsl --manage Ubuntu --set-sparse true (future frees return automatically) or Optimize-VHD; (2) wsl --manage Ubuntu --move D:\\WSL; (3) free space elsewhere on C:. Host side: sudo is unavailable, and Linux / has 715 GB free, so nothing here shrinks the file. Tried: sparse queryflag (not set). Nothing else possible from WSL. RESOLVED 09-27 09:28 PDT (hostops): C: now has 98 GB free (df /mnt/c, 95%), so the immediate WSL/pagefile risk is gone; the VHDX sparse/compact remains an optional restart-window task.
- 09-27 10:10 PDT (hostops) OWNER HANDS: the Thor (bdc158a5) is off USB. It dropped at 10:01 PDT after a battery hold at 9% (device_reality 09:50). It never climbed on the 500 mA port, and Windows PnP shows it Present=False, with not even a VID_05C6 charging entry, so it is most likely powered off with a flat battery. Please plug it into a 1.5-3 A charger or PD hub, power it on, then reconnect it to the Intel port. adb reconnect cannot reach it. Meanwhile its four #424 Blinx arms are re-pinned to the Nova. Two Thor-only title benchmarks (Azurik, D&D Heroes) wait for it. The battery hold lifts itself at 80%. RESOLVED 11:13 PDT (hostops): the owner put the Thor back in production at about 11:05 PDT; it reads 87% on USB with no hold.
- RESOLVED 09-27 14:28 PDT (hostops; first line marked by lane.local 17:06, see the line below). Was: 09-27 10:36 PDT (hostops) OWNER HANDS (adds to the 10:10 Thor line): the Nova is also on the 500 mA port, at 54% and draining 13%/h under the fps-focus queue. It reaches the 15% battery hold at about 13:26 PDT. With the Thor already off, NO handheld serves the queue after that: notify488/flip474/forza414/tbflip424 arms and the titles pipeline all stop. One 1.5-3 A charger or PD hub for either handheld prevents it; the Thor (flat, off) needs one to boot at all. Nothing else is possible from the host: the hold is the only battery lever, and it stops work. UPDATE 11:13 PDT (hostops): the Thor is back at 87%, so the queue no longer stops at the Nova's hold. The Nova reads 40% and still reaches its 15% hold at about 12:40 PDT; the owner's 20:00-21:00 top-up is the plan.
  RESOLVED 09-27 14:28 PDT (hostops): the Thor is back in service since 11:05 (82% now), so the queue never stopped; the Nova reads 50% at -18.5%/h and its 15% hold is automatic (devwatch tracks it). The 1.5-3 A charger / PD hub remains the owner-hands fix for both handhelds (known; no new action).
- RESOLVED 09-27 12:10 PDT (hostops set dual_screen_display_mode 0; first line marked by lane.local 17:06). Was: 09-27 11:51 PDT (hostops) OWNER HANDS/CALL: every Thor frame since 11:06 PDT is black because a system overlay covers hakuX. Lime3DS (Animal Crossing, at Rover's name prompt) was started on the Thor at 11:06:02 PDT, right after it came back. Since then com.odin.dualscreen.assistant (the AYN dual-screen assistant) holds a full-screen BOOT_PROGRESS window ('primaryScreenTopLayout') on display 0 above hakuX: a display-0 screencap is 10,899 B all black, and the 3DS game shows on the second display. The device is Awake with no keyguard, so wake is not the cause. The hakuX runs render black and GTA stops flipping (lane.gta482, titleroutes). I placed hold/thor (hostops-display) so no more void runs start. The Thor needs Lime3DS closed (or dual-screen mode exited). I did NOT force-stop your game. If you are not using it, reply 'force-stop ok' and I will do it and lift the hold.
  UPDATE 09-27 12:04 PDT (hostops): lane.local reports the route's injected input likely launched Lime3DS, not the owner. After the owner closed it I force-stopped Lime3DS's leftover process, then soft-rebooted the Thor (12:03, back on adb in 20 s). hakuX (GameLibrary) on top still captures ALL BLACK on display 0 after the reboot, and the dual-screen assistant's primaryScreenTopLayout overlay returns at boot, so a PERSISTED setting changed; suspect dual_screen_display_mode=2, likely toggled by injected buttons. OWNER HANDS: on the Thor, open the AYN dual-screen settings (quick-settings / Odin settings) and restore the normal top-screen display mode, so a hakuX game shows on the top screen. hold/thor stays until a display-0 screencap is not black. RESOLVED 12:13 PDT (hostops): hostops set dual_screen_display_mode back to 0 (adb settings put) with no hands needed; the overlay is gone, GTA renders at 59 fps on display 0, and hold/thor is lifted. device_reality.sh --fix now restores it on an idle Thor.
- RESOLVED 09-27 18:09 PDT (lane.local): the owner moved the Thor back. It is on the Intel USB 3.0 xHCI (PCI VEN_8086 DEV_A12F), shows as "device" on adb, and is running a titleroutes soak. Was: 09-27 17:52 PDT (hostops) OWNER HANDS: the Thor (bdc158a5) has been adb "offline" since 17:41 PDT. Windows sees it (PnP OK), but on the ASMedia USB 3.1 controller (PCI VEN_1B21 DEV_1242), the rear port it was moved to at ~17:03. That controller dropped the Thor before (2026-09-12); the working one is the Intel xHCI the Nova uses. It dropped right after a 1.2 GB title push, and adb reconnect (x3) and pnputil /restart-device did not recover it ("reboot needed"). Please move its cable to an Intel-controller port (the one the Nova is on, or its neighbours). If it was moved for charging current, a powered hub on an Intel port does both. Meanwhile: drain474's #474 Blinx A/B pilot is re-pinned to the Nova; the six titleroutes soaks, the thermal507/forza414 Thor runs and lane.xbox's copies (paused at 21/200) wait for the Thor.
- RESOLVED 09-27 23:38 PDT (hostops): no hands needed; `pnputil /restart-device USB\VID_18D1&PID_4EE2\EE317437` brought it back on adb in 15 s (uptime 1:07, so it never rebooted: the Windows USB stack, not the device). Its worker started and claimed the idlehalt A1 r2. device_reality.sh --fix now does this itself. Was: 09-27 23:33 PDT (hostops) OWNER HANDS: the Nova (ee317437) hung at 23:11 PDT mid-soak (idlehalt Blinx A1). Its logcat stopped mid-frame with no crash line, and adb has not listed it since. Windows still shows its ADB Interface OK with no re-enumeration since the 22:30 replug, so the device or its adbd is frozen, not unplugged. Tried: adb reconnect, then adb kill-server (the Thor recovered, the Nova did not). Please hold the Nova's power button to restart it; on reconnect, tick Always allow if the USB-debugging prompt shows. Meanwhile 6 Blinx runs (the forza414 A/B pair and idlehalt's boot checks) are moved to the Thor. 21 critical-path runs (#525 AUF, #526 pacing Kabuki/DOA, #474 rendermode AUF/DOA, #413) exist only on the Nova and wait for it.
- RESOLVED 09-28 07:11 PDT (hostops): both handhelds are back on adb, charged; device_reality lifted the battery holds at 07:06 (Thor 85%, Nova 80%), and the Nova is running #507's cold run. Was: 09-28 01:34 PDT (hostops) OWNER HANDS (no action possible from the host): the Nova (ee317437) has been on its battery hold since 01:10 PDT at 10%, asleep, and it is charging (+410 mA, voltage rising). At that rate it takes about 10 h to reach the 80% lift, so roughly 11:00 PDT. 16 critical-path runs are Nova-only and wait for it: lane.pacing Kabuki/DOA (8), idlehalt AUF/Blinx (6), pipeline413 DOA (1), titleroutes Kabuki (1). The Thor has none of those titles, and the one-copy rule forbids copying them. The Thor keeps serving its 18 requests. A 1.5-3 A charger or PD hub on the Nova in the morning brings it back hours sooner. Lowering the 80% lift is your bar, so I have not changed it. UPDATE 09-28 02:11 PDT (hostops): the real charge rate on the 500 mA port is about +4%/h (10% at 01:10, 14% at 02:10, asleep and held), so the 80% lift lands at about 18:30 PDT, not 11:00. Until then forza414's Blinx pilot (#543), idlehalt's 6 post-fold runs (#525), lane.pacing's Kabuki/DOA leg and pipeline413 all wait. A 1.5-3 A charger or PD hub on the Nova this morning is the only lever that brings it back sooner. UPDATE 09-28 03:12 PDT (hostops): the Nova reads 23% (+4.5%/h, held). The Thor now serves the whole queue at 37% and drains about 11%/h, so it reaches its own 15% hold at about 05:10 PDT. After that NO handheld runs until one of them charges to 80% (Nova about 17:30 PDT). I moved the adpf pilot (#544) and the pacing Thor pair (#526) up so they run before then. A faster charger on either handheld is the only way to avoid a dead stop of about 12 h. UPDATE 09-28 03:31 PDT (hostops): the Thor's cool-down hold lifted at 03:31, and it is running the sustain507 MAX-vs-defaults soak at 30%. Its 15% hold is now due about 04:40 PDT, not 05:10, and the adpf pilot and the pacing pair are next behind that soak. The Nova reads 24% (held). No change otherwise: a 1.5-3 A charger or PD hub is the only lever. UPDATE 09-28 03:50 PDT (hostops): the Thor reads 24% while running the lane.pacing Thor pair, and its 15% hold is due about 04:40 PDT. The Nova reads 28% (held, climbing about +4%/h). 33 requests wait: 25 critical-path and 8 title benchmarks, which are 8 h old and wait behind the critical path by policy. After about 04:40 NO handheld runs until one reaches 80%, around 18:00 PDT for the Nova. A 1.5-3 A charger or PD hub is still the only lever. UPDATE 09-28 04:32 PDT (hostops): the Thor reads 18% while running the sustain507 cold soak, and its 15% hold is due about 04:47 PDT. The Nova reads 34% (held, about +4%/h). The Thor's next run is lane.rendermode474's #474 run, moved to its head, followed by one title benchmark (Azurik, waiting since 21:02). A 1.5-3 A charger or PD hub is still the only lever. UPDATE 09-28 04:50 PDT (hostops): the Thor is now on its battery hold at 11%. Its cool-down hold had been masking the flat battery, so device_reality never placed one; it now retags a cool-down hold as the battery hold below 15%. Its sustain507 cold soak runs to about 04:58, then NO handheld runs. The Nova reads 37% (held, about +4%/h), so it reaches its 80% lift at about 15:30 PDT. 31 requests wait, 23 of them critical-path. A 1.5-3 A charger or PD hub on either handheld is still the only lever. UPDATE 09-28 05:10 PDT (hostops): both handhelds are asleep on their battery holds and charging, nothing runs. The Thor reads 5% at +310 mA after the sustain507 soak ended at about 05:00 PDT. The Nova reads 40% at +280 mA, so it reaches the 80% lift at about 15:00 PDT. 31 requests wait. The dispatcher tree was fast-forwarded to 9d777502fa and restarted while nothing ran. A 1.5-3 A charger or PD hub is still the only lever. UPDATE 09-28 05:30 PDT (hostops): both handhelds are asleep on their battery holds and charging faster than earlier. The Thor reads 7% at +442 mA. The Nova reads 44% at +397 mA, about +10%/h since 05:10, so its 80% lift lands at about 09:15 PDT, not 15:00. 31 requests wait, 23 of them critical-path. Nothing else is jammed: no lane is stranded, no unit has failed, and fold is clear. A 1.5-3 A charger or PD hub is still the only lever. UPDATE 09-28 05:53 PDT (hostops): both are asleep on their battery holds and charging: the Thor at 8% (+448 mA) and the Nova at 48% (+401 mA, about +9%/h), so the Nova lifts at 80% around 09:30 PDT. The Nova's queue starts with sustain507's cold run, then lane.pacing, pipeline413, idlehalt and dirtytlb. 35 requests wait. A 1.5-3 A charger or PD hub is still the only lever.
- RESOLVED 09-28 07:11 PDT (hostops): see the line above. Was: 09-28 06:13 PDT (hostops) OWNER HANDS (adds to the 01:34 line): the Thor (bdc158a5) dropped off USB at 06:07 PDT. It was asleep on its battery hold at 9% and charging (+448 mA at 05:53). Windows now lists no Thor device at all, not even a VID_05C6 charging entry, so it was either unplugged or powered off; adb reconnect cannot reach it. If you moved it to a faster charger, that is the fix: power it on and put it back on the Intel port when it is charged. Its hold lifts itself at 80%. The Nova reads 50% (held), charging about +4%/h on the 500 mA port, so it lifts at 80% around 13:30 PDT, not 09:30. 38 requests wait, 13 of them pinned to the Thor. A 1.5-3 A charger or PD hub on the Nova is still the only lever that brings a handheld back sooner.
  UPDATE 09-28 06:49 PDT (hostops): the Nova (ee317437) left USB too, at 06:17 PDT, ten minutes after the Thor. It was asleep on its battery hold at 50%. Windows lists neither handheld now (every VID_18D1 and VID_05C6 entry is Present=False), so both were unplugged or powered off; adb cannot reach either one. If you moved them to a faster charger, that fixes it: put each back on an Intel-controller port when it is charged. Each hold lifts at 80%. Nothing runs until then. 38 requests wait: 13 pinned to the Thor, 21 to the Nova.
- RESOLVED 09-28 18:31 PDT (hostops): both handhelds back on adb at 18:28 (owner: "Handhelds are back in service"), Thor 93%, Nova 80%; lane.local lifted hold/nova at 18:29 and the Nova is serving. Was: 09-28 17:42 PDT (hostops) OWNER HANDS / FYI: both handhelds left USB at 17:40 PDT (Windows PnP: every VID_18D1/VID_05C6 entry Present=False, adb lists none), probably the ~18:00 top-up. It voided the Thor's forzadecay414 BASE arm run 2 (pull failed; the Thor worker requeues the orphan when it returns). Before that, the Nova (held, 24%, charging about 3%/h on the 500 mA port) lost its adb link 60-100 s after every pnputil re-enumeration since 16:51 (3 ticks). Windows-side read failures, reproduced twice this tick; PR #595 shows the Nova's link fails below 30%. Host fix: none beyond the hold. Needed: plug both back into the Intel xHCI ports; a fast charger for the Nova. device_reality + the dispatcher pick them up on return.
- RESOLVED 09-28 19:03 PDT (hostops): NOT the cable, no hands needed. The Nova's Forza drops are memory exhaustion: xemu grows from 1.3 GB to 4.4 GB PSS about 3.5 min into Forza, and lmkd kills everything, then xemu (logcat -b events am_pss/am_proc_died 18:33, 18:53:49, 18:57:46). adb drops in the same second. This is #414 (fix PR #583); lane.forzadecay414 and lane.idlehaltdefault were told. Was: 09-28 18:38 PDT (hostops) OWNER HANDS (low urgency): the Nova (ee317437) dropped off adb again at 18:33-18:34 PDT, at 80% charge, 4 min into a Forza soak, on the Intel xHCI (VEN_8086 DEV_A12F; uptime 20 h, so it did not reboot). adb.log shows write I/O errors every 5 s for 45 s. So the <30% explanation (#595) does not cover every drop. Both cut Forza runs on the Nova today (r2 at 276 s, r3 at 215 s) were this. I re-queued the run as r4. The Nova is serving again (#525 idle-halt pairs). If it recurs, try a different cable or port for the Nova.
- RESOLVED 09-29 02:13 PDT (hostops): hold/nova lifted at >= 45% by hakux-novacharge; the Nova is serving at 44% (#525 head pairs, 02:01 and 02:08 runs admitted). Was: 09-28 23:50 PDT (hostops) OWNER HANDS (once): the Nova (ee317437) sits at 36-37% since 22:50 PDT, asleep and USB-charging (status 2, +154 mA) but not climbing measurably; the dispatcher's battery admission needs 39.9-49.6% for every Nova request, so 40 requests (incl. #525 idlehaltdefault env pairs, #474 gmem474, #569 litcompile/uberspike) wait. Host side: nothing to fix (no hold, jamcheck no longer nudges on it, the Thor serves its own queue after the #507 cold slot). Needed: the owner's fast charger for the Nova; it resumes by itself once it clears ~40%.
  UPDATE 09-29 00:53 PDT (hostops): still owner hands. The Nova is at 35% (status 2, asleep), and its adb link dropped 4 times in 30 min, one of them mid-run at 00:49; one reconnect restored it and the run (litcompile569 gate 4) completed with its logcat. No lmkd wave (xemu PSS 1.5 GB). Admission admits about 1 run per 40 min at 38-39%, and each run takes it back to 35%. Its head requests (#525 idlehaltdefault) are Fuzion/Blinx 2 soaks for titles only the Nova has, so they cannot be re-pinned. Needed: the fast charger.
  UPDATE 09-29 01:17 PDT (hostops): still owner hands. The Nova is at 37%, asleep and charging at about 1%/h. I placed hold/nova (charge-hostops) so no run is admitted at a marginal 38%, since that is where its link dropped at 00:48. Waiter hakux-novacharge lifts the hold at >= 45% or at 04:30 PDT. 29 Nova-pinned requests wait (#525, #474, #414, #569, #507).

## 2026-09-29 13:06 PDT -- WSL restart needed: sync wedged since ~07:48 PDT, 254 leaked D-state processes
OWNER-LEVEL: clearing this needs a WSL VM restart (wsl.exe --shutdown from Windows), which would
kill this very session and every held device/session on this box -- outside hostops authority
(not in the granted list: dispatcher restart, hakux-* services, systemctl reset-failed, timers).

DIAGNOSIS (reproduced live): `sync` under `wsl.exe -u root` hangs indefinitely on this WSL
instance's storage (confirmed with a bare 30s and 60s timeout, both timed out with zero output;
plain `wsl.exe -u root echo` returns in 0.1s, so root interop itself is fine -- only `sync` is
wedged). defrag_memory.sh's ROOT COMPACT fallback (jamcheck, every 10 min when order-7 blocks run
low) calls `sync; drop_caches; compact_memory` in a 40-try retry loop; since `sync` never
returns, `timeout` kills the wsl.exe client but the inner `sync` cannot be signalled (D state is
uninterruptible) and leaks forever. This has been running since 07:48 PDT today (2026-09-29):
every ROOT COMPACT attempt before then succeeded "on try 1"; every one since has failed all 40
tries. 254 stuck `sync` processes have piled up, driving load average to 250 on this 8-core box
(actual CPU stayed ~85% idle -- this is a leaked-process count, not real CPU starvation, but it
matches the exact pattern flagged as preceding the 2026-09-26 08:24 crash).

FIXED THIS TICK: patched defrag_memory.sh with a circuit breaker (host-tools/defrag_memory.sh,
backup at .bak-20260929-synchang) -- probes `sync` with an 8s timeout before attempting the
retry loop; on failure it backs off 20 min instead of leaking a new process every cycle. Verified:
stopped the in-flight old-code run (systemctl --user stop hakux-defrag.service, capped its leak at
2 processes instead of running out its remaining ~32 tries), confirmed the patched script runs
clean when order-7 blocks are healthy (no new D-state processes) and its probe correctly detects
the still-wedged sync. Also added a [memory] dstate-leak check to harness_health.py so a future
recurrence is caught directly instead of requiring manual ps/vmstat digging.

WHAT REMAINS, NEEDS THE OWNER OR INTERACTIVE HOST: the 254 already-leaked processes are D-state
(uninterruptible) and cannot be cleared by any signal -- they need the underlying storage stall to
clear or a WSL restart. recover.sh (host-tools/recover.sh) is built for exactly this: bring
everything back in one step after a restart. Current window looks low-risk to do it in: 0 lanes
running, 0 dispatchable, both handhelds already held (nova charging, thor host maintenance).
Recommend: from Windows, `wsl.exe --shutdown`, then relaunch and run `recover.sh`.
Mark RESOLVED here once done.

  UPDATE 09-29 13:28 PDT (hostops): still owner hands, not worse -- the circuit breaker is holding.
  At 13:18-13:23 the count sat flat at 254 (confirmed across a 70s watch, no new sync spawns) while
  the still-in-flight OLD-code invocation's last leaked process (started 13:02:52) finished aging in;
  the kill at 13:02:57 (journalctl: hakux-defrag.service killed, status=15/TERM) had stopped the
  33s-cadence runaway (30s timeout + 3s sleep per try) at exactly that point. Then at 13:26:11-19 the
  patched script's own probe (8s timeout) hit the still-wedged sync again, logged `SYNC WEDGED`, and
  correctly backed off 20 min instead of looping -- but that probe itself is a `sync` call, so it
  leaked exactly ONE more stuck process (pid 2719153) before backing off. Count is now 255 (sync-only;
  ps briefly showed 256 from an unrelated, normal, since-cleared D-state `stage_xiso.py`). So the
  underlying storage stall has NOT cleared on its own in the last 20+ min, and the leak is not zero --
  it is bounded to about 1 process per 20-min backoff cycle (~3/hour) instead of up to 40 per 33s.
  That is a real fix (prevents the runaway that hit 254 in ~5h), but it does not cure the wedge, so
  the count will keep creeping up until the restart happens. Enhanced harness_health.py's dstate-leak
  check to report climbing-vs-flat trend explicitly (tracks count+time in .dstate-track.json) so the
  next tick sees "+N in M min: active leak" or "flat since HH:MM: needs a restart" at a glance instead
  of re-deriving it. Still recommend the `wsl.exe --shutdown` + recover.sh window above; no change to
  urgency (slow trickle, nothing keyed off host load average, no functional impact found this tick).

  UPDATE 09-29 13:57 PDT (hostops): still owner hands, unchanged since the 13:28 update -- count flat at
  255 (checked twice, ~6 min apart), no new leak since the 13:26:19 wedge probe's one process. The
  circuit breaker is holding (no new SYNC WEDGED entries in logs/defrag_memory.log since 13:26:19;
  next probe is due once the 20-min backoff ages out and a low-order-7 tick triggers it). Separately
  this tick: nova (ee317437) went adb-offline at ~13:51 PDT (21 requests waiting); ran
  `device_reality.sh --fix` by hand rather than wait for the 14:00 jamcheck timer -- one reconnect
  cleared it (same known pattern as 2026-09-26/27), confirmed back to `device` and harness_health.py
  now reports only the D-state violation. No change to the WSL-restart recommendation: still
  `wsl.exe --shutdown` + recover.sh in a low-risk window. Not marking RESOLVED -- that is the
  owner's/interactive host's call to make and execute.

  UPDATE 09-29 14:16 PDT (hostops): still owner hands. Count moved 255 -> 256: the 20-min backoff from
  13:26:19 aged out and the next low-order-7 BALLOON tick (14:16:09) re-triggered the probe, which hit
  SYNC WEDGED again at 14:16:17 and leaked exactly one more process -- precisely the "~1 per 20-min
  cycle, ~3/hour" bound the circuit breaker predicted at 13:28, not a new or faster leak. Same
  tick: nova is on its 5th 500 mA-port marginal-charge cycle today (37% oscillating, 30+ requests
  skipped by battery admission) -- re-armed hold/nova (charge-hostops) + hakux-novacharge waiter
  (lifts at >=45% or 16:15 PDT), same fix as the 01:17/02:58/12:19 PDT recurrences; not re-escalating,
  this is the already-acknowledged 500 mA-port limit. Thor is mid-run at 21% with a cooldown hold
  (xo-therm 75.7C, devwatch's own cooldown-devwatch hold) queued to take effect after; its own 15%
  battery hold is device_reality.sh's normal automatic path, not a new issue. Not marking RESOLVED.

  UPDATE 09-29 14:37 PDT (hostops): still owner hands, unchanged since the 14:16 update -- count flat
  at 256 (checked at 14:29 and 14:37, both reads identical, no new SYNC WEDGED line in
  logs/defrag_memory.log since 14:16:17). Circuit breaker still holding at its ~1-per-20-min bound.
  Separately this tick: retired lane.armsrequeue's board row (PR #620 merged, arms.sh returned to
  lane.toolsmith), fast-forwarded the dispatcher tree to 5071d47b31, and answered lane.xbox (#462,
  investigation-copy push done) and the tcg424flip/verdict433 queue-status asks (#605, #610) -- all
  three are correctly queued behind the Nova's charge-hostops hold (oscillating 37-45%, waiter lifts
  at >=45% or 16:15 PDT) and the Thor's battery-hostops hold (12-14%, device_reality lifts at >=20%);
  not re-escalating either, both are the already-acknowledged 500 mA-port limit with working waiters.
  No change to the WSL-restart recommendation for the D-state residual. Not marking RESOLVED.

  UPDATE 09-29 14:57 PDT (hostops): still owner hands, count moved 256 -> 257 (seen 105 min this
  tick). Investigated whether this is a NEW leak class before accepting it as the same bound: the new
  process (pid 3680089, started 14:38:19) has PPID 800 (systemd --user), unlike the prior breaker-caused
  leaks which reparent to PID 1 -- checked this was not a second, unguarded caller of `sync`. Grepped the
  full hakux-work and hakuX trees for any bare `sync` or `wsl.exe -u root` invocation outside
  defrag_memory.sh: none found. hakux-defrag.service's own journal shows every 14:36-14:44 tick starting
  and finishing in the same second (fast top-of-script exit, never reaching the wedge-probe code), so
  this increment is not explained by a logged SYNC WEDGED line either -- most likely a systemd
  cgroup/subreaper reparenting difference for the same underlying wedge, not a new source, but flagging
  the gap plainly rather than papering over it: no second caller found, rate (254->255->256->257 over
  ~13:00-14:38, roughly 1 per 20-50 min) is unchanged and still consistent with the circuit breaker's
  predicted bound, not accelerating. No new fix applied. Still needs `wsl.exe --shutdown` + recover.sh
  in an owner-scheduled low-risk window. Not marking RESOLVED.

  UPDATE 09-29 15:15 PDT (hostops): still owner hands, count moved 257 -> 258 (one new leak since
  14:57, consistent with the ~1-per-20-50min circuit-breaker bound, not accelerating -- newest D-state
  sync pid started 14:58:xx, matching the 14:58:18 SYNC WEDGED line in logs/defrag_memory.log). No new
  fix applied; same recommendation stands: `wsl.exe --shutdown` + recover.sh in a low-risk window
  (currently: 0 lanes running, 0 dispatchable, nova on a charge hold, thor on a battery hold -- still
  looks low-risk). Not marking RESOLVED.

  UPDATE 09-29 15:32 PDT (hostops): still owner hands, count unchanged at 258 (checked 15:29 and 15:32,
  identical both times; matches the 15:15 update's 258 too -- flat for at least 17 min, no new SYNC
  WEDGED line in logs/defrag_memory.log since 14:58:18). Circuit breaker confirmed still holding. No
  new fix applied or needed; same recommendation stands: `wsl.exe --shutdown` + recover.sh in a
  low-risk window (0 lanes running, 0 dispatchable this tick too). Not marking RESOLVED.

## 2026-09-29 15:55 PDT (hostops) -- 258 stuck D-state `sync` processes: root cause found, growth stopped, clearing existing ones needs an owner-scheduled WSL restart
[memory] violation: 258-259 processes in uninterruptible (D) state (32x nproc=8 threshold=256), first seen ~13:26 PDT.

**Root cause (confirmed via `wsl.exe -u root cat /proc/<pid>/stack`):** a bare `sync` calls `iterate_supers` -> `fuse_sync_fs` on every mounted filesystem, including the DrvFs/9p mounts (/mnt/c, /mnt/d). The Windows-side plan9 server has stopped answering the FSYNC verb specifically (normal read/write to /mnt/c is still instant -- tested live, 0.022s) so `fuse_sync_fs`'s `request_wait_answer` blocks forever in D state. `timeout 8` kills the `wsl.exe` client but cannot signal the inner wedged `sync`, so every probe leaked one more zombie. defrag_memory.sh's own 13:00 PDT circuit breaker made this worse, not better: it still probed with a bare `sync` every ~42 min, leaking one more stuck process per cycle even while "backing off."

**Fix applied (host-tools/defrag_memory.sh, backup at .bak-20260929):** the probe now runs `sync -f /root` (GNU coreutils, syncs only the filesystem containing the given path) instead of bare `sync`, so it never touches the wedged DrvFs mounts. Verified: ran `defrag_memory.sh --force` after the fix -- probe returned immediately, ROOT COMPACT succeeded on try 1, D-state count stayed flat at 258 (no new leak). This stops the growth; it does not retroactively unstick the 258 already-wedged processes, which cannot be reaped from inside the VM (uninterruptible, waiting on a FUSE answer that plan9 will never send for that request).

**What's needed from you:** an owner-scheduled WSL restart window to clear the 258 zombies (`host-tools/recover.sh` brings the harness back after). Not urgent by itself -- they're blocked, not spinning, so no CPU/memory pressure -- but the count will sit above the health check's 256 threshold until then. Escalating per the runbook's own rule for this exact case ("flat-but-over-threshold needs an owner-scheduled WSL restart window since it cannot be reaped from inside the VM") and because a WSL restart is outside hostops' authority (kills the dispatcher and every running lane/device run).

- 2026-09-29 16:00 PDT (hostops) OWNER HANDS (recurring, no new lever): neither handheld serves the queue right now. Thor is battery-held at 19% (hold since 14:20, lifts itself at >=20%, USB-charging, climbing). Nova is at 35%, not held, but the dispatcher's own per-run battery admission (PR #587) skips every one of its 32 queued requests: at a learned -22.9%/h drain rate the shortest queued run still needs 37-47% to finish above the 30% floor + 5% margin. This is the same 500 mA PC-port charge-rate ceiling escalated repeatedly since 09-27 (see the block above) -- nothing new to action from the host; a 1.5-3 A charger or PD hub on either handheld is still the only lever. Not marking RESOLVED (recurring).

  UPDATE 09-29 17:23 PDT (hostops): still owner hands, count unchanged at 258 (checked 17:17 and
  17:23, identical; no new SYNC WEDGED line in logs/defrag_memory.log since 14:58:18, and ROOT COMPACT
  has succeeded on every try since 15:55 -- ROOT COMPACT on try 1 at 15:55:13, 16:28:15 and 17:04:13,
  ordinary BALLOON cycles in between). The `sync -f /root` fix continues to hold: flat for 87+ min now.
  Same recommendation stands: `wsl.exe --shutdown` + recover.sh in an owner-scheduled low-risk window
  (0 lanes-critical stranded this tick; both handhelds are mid owner-authorized top-up/route work, not
  idle, so this may not be the lowest-risk window right now -- defer to the owner's timing). Not
  marking RESOLVED.

  UPDATE 09-29 17:56 PDT (hostops): still owner hands, count unchanged at 258 (checked
  17:48 and 17:56, identical; no new SYNC WEDGED line in logs/defrag_memory.log since
  14:58:18, ROOT COMPACT still succeeding on every try). The `sync -f /root` fix
  continues to hold: flat for 178+ min now. Same recommendation stands: `wsl.exe
  --shutdown` + recover.sh in an owner-scheduled low-risk window. Not marking RESOLVED.

  UPDATE 09-29 18:09 PDT (hostops): still owner hands, count unchanged at 258 (checked
  18:04 and 18:09, identical; youngest D-state process is 187 min old, matching the last
  SYNC WEDGED at 14:58:18 -- no new leak since; ROOT COMPACT has succeeded on every try
  since 15:55, most recently 17:36:19). The `sync -f /root` fix continues to hold: flat
  for 191+ min now. Also this tick: harness_health.py's owner-hold recognition only matched
  the literal tag 'owner', so both handhelds' current lanelocal-topup charging holds
  (topup_release.sh, owner-authorized 17:12/17:20 PDT) were misreported as bare device-absent
  jams instead of the gentler owner-hold path. Fixed (OWNER_HOLD_TAGS now covers both tags,
  3 call sites, host-tools/harness_health.py, backup at .bak-<timestamp>); verified thor's
  false "absent" violation is gone and nova now reports correctly via the owner-hold path.
  Both handhelds remain legitimately off adb for the owner's topup (self-releasing at >=60%,
  6h cap); no device serves the queue until one returns, which is expected, not a jam.
  Same WSL-restart recommendation stands for the D-state zombies. Not marking RESOLVED.

  UPDATE 2026-09-29 18:33 PDT (hostops): still owner hands, count unchanged at 258
  (flat since 14:58:18, no new SYNC WEDGED line, oldest D-state pid 12525 / youngest 38149
  match prior checks). Also this tick: both handhelds went under the owner's evening
  top-up hold (17:11 thor / 17:20 nova, lanelocal-topup, self-releasing at >=60%) --
  unrelated to the D-state residual, noted only because harness_health flagged device
  queues stalled on both at once. Same WSL-restart recommendation stands. Not marking
  RESOLVED.
