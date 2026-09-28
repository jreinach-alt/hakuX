# slowtier2-cold-20260928: #462 phase 2b, eight Thor perflog soaks on master

Parked 2026-09-28 by lane.slowtier2 (PR on lane/slowtier2-cold; the plan is
docs/lanes/slowtier2/NOTES.md, section 5). Every request is pinned to the
Thor, is a `-Pperflog=true` build of master @ 97a6fa2b51 (it carries #479,
#504, #518, #528 and #536), sets PERF_REGIMEN=max (the regimen of the readings),
and uses the title's own route with its `mark gameplay`. Each needs a COLD
start: `coldslot.sh thor bdc158a5 <this dir>/<id>.req`, one at a time.

Order (by what each run decides):

| # | id | title | s | decides |
|---|---|---|---|---|
| 1 | 1-1790609660-lane.slowtier2-otogi762702 | Otogi | 550 | the renderer split (PFIFO CPU / GPU / downloads / compiles) on the purest renderer-side title. **The pilot** |
| 2 | 1-1790609661-lane.slowtier2-mm3184014 | Midtown Madness 3 | 580 | title or pause (the 3.1 reading started warm), and whether the vCPU's off-CPU time is its pfifo.lock wait (`Lw` on the `hakuX-cpu` line, profile.c:648) |
| 3 | 1-1790609662-lane.slowtier2-black167924 | Black | 760 | the vCPU's 42 ms/frame off-CPU and the 17.8 ms/frame of TLB resets on other threads (#548), on master |
| 4 | 1-1790609663-lane.slowtier2-burnout968727 | Burnout | 460 | the renderer split for a second renderer-side title |
| 5 | 1-1790609664-lane.slowtier2-alias942359 | Alias | 450 | guest-side (vCPU on-CPU 95%) on master, with the renderer rows |
| 6 | 1-1790609665-lane.slowtier2-pgr365442 | PGR | 420 | re-measure: did this week's fixes move it (reading 14.3 on a593d8eb85) |
| 7 | 1-1790609666-lane.slowtier2-crash627374 | Crash Twinsanity | 420 | re-measure (15.7 on a593d8eb85) |
| 8 | 1-1790609667-lane.slowtier2-bloodrayne201189 | BloodRayne | 420 | re-measure (22.3/24.9 on e884ad260e) |

Device time: 4,060 s of soak + 8 x 90 s of setup = about 80 min, plus the cool-downs.

**Pilot rule.** Run 1 is the pilot. Slot run 2 after it, but slot runs 3-8
only once `$DISPATCH_DIR/pilots/lane.slowtier2.ok` exists. lane.slowtier2
writes it after reading run 1: the logcat carries `hakuX-phase`, `hakuX-cpu`, `xemu-gpu`
and `hakuX-stall`, and the route reached `mark gameplay`. If lane.slowtier2
is not running when run 1 lands, handback.sh resumes it on the result.

Not served here: the held simpleperf sessions (`--trace-offcpu` for MM3 and
Black, on-CPU for Alias) of the phase-2 plan. The dispatcher cannot run
simpleperf. The perflog soaks above give the vCPU's pfifo.lock wait (`Lw` on the `hakuX-cpu` line, profile.c:648),
not a full off-CPU split. If `Lw` does not account for the off-CPU time, the
held session is still needed, and it is lane.local's to run by hand.
