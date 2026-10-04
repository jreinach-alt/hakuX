# lane.vcpusleep (#507): what the vCPU sleeps on in Simpsons Hit & Run, and removing it

State: draft (waiting on the Simpsons B capture and the pixel arms)

Lane: vcpusleep            Issue: #507
Base: master @ 425ffe1ad1
Files: docs/lanes/vcpusleep/NOTES.md, docs/lanes/vcpusleep/OUTBOX.md, docs/lanes/vcpusleep/PR.md, docs/lanes/vcpusleep/WAITING, docs/lanes/vcpusleep/capture_simpsons_offcpu.sh, docs/lanes/vcpusleep/selftest_postput.sh, docs/testing/predictions/vcpusleep-pixels.json, docs/testing/predictions/vcpusleep-simpsons.json, hw/xbox/nv2a/nv2a_int.h, hw/xbox/nv2a/pfifo.c, hw/xbox/nv2a/user.c
Prediction: docs/testing/predictions/vcpusleep-pixels.json @ a4174c6068119136b3d1287a14fcb2b8130894b8650ac24fe4b7e67ef55f6e22; docs/testing/predictions/vcpusleep-simpsons.json @ 92394bb4c3a3014fd2ce60caf78dfba1881b83ae4f92d19ed80d33e1f575ac41
Needs device: yes (Nova: 2 pixel arms, 1 host-run Simpsons capture by lane.local)    Needs NDK: yes

Release note (performance): The Simpsons: Hit & Run's CPU no longer stalls when it hands the GPU new work while the GPU thread is busy (pending measurement).

## What R1 found

One off-CPU capture of the Simpsons vCPU in free roam (simp1, Nova, master's
code; frames confirm free roam, v_blk 8.88 ms/frame):

| site | % of attributed off-CPU |
|---|---|
| **pfifo.lock in `user_write` (the guest's DMA_PUT store)** | **79.3** |
| BQL, all callers | 16.1 |
| pgraph.lock in PGRAPH MMIO | 4.0 |

The holder: the PFIFO thread, asleep for 97% of those waits, sampled in
`wait_frame_submitted <- pgraph_vk_finish <- pgraph_vk_process_pending_reports`.
Waits are mostly 5-10 ms long.

## The change

`user_write` tries `pfifo.lock` for a DMA_PUT store. When the lock is free the
store is unchanged. When it is busy, the store is posted, as on the hardware:
DMA_PUT is stored with release, the kick is set, and the lock is taken only to
wake a PFIFO thread parked in its condition wait. The PFIFO thread sets a
`parked` flag before it checks the kick, so no wakeup is lost. The pusher
loads DMA_PUT with acquire. This is off while the skew bound is on, because
the bound holds the guest under the lock. The `fifoskew` line gains
`posted=`.

`selftest_postput.sh` compiles user.c and pfifo.c's posted-put block verbatim.
The posted store returns in 0 ms under a 400 ms hold. 100,000 stores are
consumed with no lost wakeup. Two falsifiers fail as they must: the block
without the parked wakeup loses a wakeup on the 2nd store, and the pre-fix
user.c blocks for 399 ms.

## Measurement

| arm | id | result |
|---|---|---|
| pixel A (3ff55c9ac2) | 1-1791146994-vcpusleep-base-1384096 | queued |
| pixel B (c2dfca18a1) | 1-1791146995-vcpusleep-fix-1400786 | queued |
| Simpsons B `simp2` (host capture) | lane.local | requested |

Details, legs and the next step for each outcome are in
`docs/lanes/vcpusleep/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
