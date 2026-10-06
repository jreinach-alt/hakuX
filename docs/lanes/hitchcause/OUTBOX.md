## #433 -- 2026-10-04 15:40 PDT (attempt 2 result)

hitchcause: the IDE PIO path is not what the MTV bursts are. One held MTV run (166 s of play, pathfind stopped at the main menu) with an `[ide425]` window line in `hw/ide/core.c` (lane branch `lane/hitchcause` at b559c094eb): zero PIO sector reads in 23 windows, zero data-port words in the hold. The vector-0x3e wakes at the one 210 ms hitch outnumber the IDE model's raises 200 to 7. So attempt 1's PIO claim is withdrawn. The 330 ms class did not recur in the 166 s, so its cause is not separable yet. Next: count what raises IRQ14 at the PIC input (`hw/intc/i8259.c`, needs a grant); the second MTV hold needs the owner's decision. NOTES section 10 has the table.

## #433 -- 2026-10-04 14:42 PDT

hitchcause: the MTV 330 ms hitches are on IDE sector-read bursts; the cause is not separated yet.

The 8 distinct MTV hitches of 200 ms or more each sit in a 2 s span, or the next one, that has an IRQ14 (Xbox primary IDE) sector-read burst (60 to 370 wakes per span). Across 344 spans the IRQ14 busy time against the worst frame gives r = 0.74; the spans under 100 ms have no IRQ14 wakes. Two of the five 330 ms hitches (14:05:57, 14:13:15) also have the vCPU thread asleep on the host for about 300 ms (on CPU 83 to 85%); the other three run on CPU at 92 to 94%. The PFIFO drain is not the stall except at 14:05:19 (699 ms max). The TLB storm and translation are not the cost. Offline telemetry cannot tell a guest spin or compute behind the disk stream from per-word host IDE cost. The next step is a grant for a perflog line in hw/ide (per-word read ns, storage latency per sector) and one MTV run; NOTES.md section 6 ranks it against the read-ahead and batching fixes by P x win. Orta's 277 and 386 ms hitches sit on IDE bursts too; Blood Wake's 1 to 3 s stalls are a separate class. No device run was queued.

NEW ISSUE: MTV and Orta 200-350 ms frame hitches sit on IDE (IRQ14) PIO sector-read bursts; cause not yet separated
Evidence: `perf/2026-10-04-mtv-hitches/logcat.txt` (Nova, perflog build, held run, 10-04 14:04-14:17 PDT). Hitches at 14:05:57 (349 ms), 14:08:39 (346), 14:10:25 (344), 14:13:15 (331), 14:15:21 (330), 14:05:19 (242), 14:04:41 (209), 14:13:01 (209). IRQ14 (vector 0x3e in the rr425w key) busy per 2 s span against the worst frame: r = 0.74 over 344 spans; spans under 100 ms have 0 IRQ14 busy. The 14:05:57 and 14:13:15 spans show the vCPU thread asleep about 300 ms (idlehalt run 83-85%). Scripts and tables: `docs/lanes/hitchcause/` on lane/hitchcause (ide_wake.py, NOTES.md). Blocks: MTV Playable frame pacing; Orta (ISO on SD card) shows the same link (r = 0.46). Next: hw/ide perflog grant, then one MTV run.

## #819 -- 2026-10-04 15:40 PDT (attempt 2 result)

hitchcause: the separation of the MTV hitch class, one held run. The IDE PIO hypothesis (sector-read bursts) does not hold. In a 166 s hold of MTV (pathfind, `--state any`; the run stopped at the main menu after 166 s of play) the `[ide425]` window line shows zero PIO sector reads and zero data-port words in all 23 windows. The one hitch of 100 ms or more (210 ms at 15:22:26) has 200 vector-0x3e wakes in its span while the IDE model raised 7 interrupts in its 7 s window. Evidence: `perf/2026-10-04-hitchcause/mtv-ide425/pf/logcat.txt`; the analysis is `docs/lanes/hitchcause/ide425_windows.py`. The five 330 ms hitches of the 10-04 hold did not recur in 166 s, so they are not separable. Next: count the sources of IRQ14 at the PIC input (`hw/intc/i8259.c`, needs a grant), then a second hold if the owner approves. NOTES section 10.


## #433 -- 2026-10-05 07:50 PDT (attempt 4)

hitchcause: the MTV hitch bursts are the IDE device after all, on a DMA path. The `[pic14]` smoke (`1-1791159308-lane.hitchcause-1279404`, ref d4b0169ab2, Nova, 150 s MTV) has PIC pin-14 edges equal to the IDE model's raises (537 vs 546 in one 2 s window; 3 to 14 per 2 s steady), never masked (ack = eoi = raise). Attempt 2's "200 wakes vs 7 raises" was the `[ide425]` window closing on the burst's first IRQ; the next window holds 231. So vector 0x3e = IRQ14 = IDE, and the r = 0.74 between IDE interrupt bursts and the worst frame stands. There are still zero PIO reads, so the bursts are DMA (HDD or the DVD). Added `[ide425d]` (af37f7a3ea, telemetry only): DMA start-to-IRQ, command-to-IRQ, IRQ-to-next-command and blk_drain time per 2 s, which separates the guest's own loader work from the host read. Queued its build and smoke (`1-1791210904-lane.hitchcause-2015470`); the one 700 s MTV hold follows on that build. NOTES section 12 has the decision rule.

## #819 -- 2026-10-05 07:50 PDT (attempt 4)

hitchcause: #819's source question is closed. IRQ14 is raised only by the IDE model (`[pic14]` edge = `[ide425]` irq within window alignment; smoke `1-1791159308-lane.hitchcause-1279404`). Attempt 2's 200-vs-7 mismatch was a window boundary, not a second device. The bursts move data without PIO (rd_sec = 0, w = 0), so they are DMA. The next line, `[ide425d]` (af37f7a3ea), times that path. Build and smoke `1-1791210904-lane.hitchcause-2015470` are queued, then one MTV hold.

## #433 -- 2026-10-05 08:50 PDT (attempt 5 result)

hitchcause: the two 330 ms MTV hitches in the [ide425d] hold (af37f7a3ea, Nova, 700 s, released 08:44 PDT) are guest-side waits, not the IDE host read. Both sit in IDE bursts of about 547 DMA commands per 2 s: DMA host time about 22 ms, device time about 41 ms, and the guest's IRQ-to-next-command gap 98% of the window. The vCPU was busy 98% with halts=0 and its hot PC in the guest idle loop; lock wait 0.1 ms, PFIFO drain under 17 ms. Section 12's rule picks (a). P 0.8 that the cause is a guest-side wait on a guest event; the next step is guest-side attribution at a hitch (P 0.6 it names the event; win is the whole 330 ms class, 1.15/min on MTV). Orta is not checked for the same signature. NOTES section 13.

Deviation for lane.local to confirm: the hold ran on af37f7a3ea (already built, smoked) instead of d4b0169ab2 named in the 10-05 addendum.

## #819 -- 2026-10-05 08:50 PDT (attempt 5 result)

hitchcause: the [ide425d] hold separates the 330 ms class from the IDE host read. The two 330 ms hitches (08:39:36, 08:44:03 PDT) have the IRQ14 bursts' DMA host time at about 22 ms per 2 s and device time at about 41 ms; the rest of each window is the guest between commands, with the vCPU busy and not halted. No host lock, no drain over 17 ms. Next: guest-side attribution at a hitch (needs a grant). NOTES section 13.
