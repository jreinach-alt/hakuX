# lane.lockwake1011 -- NFS Most Wanted's cold race start: which pfifo.lock site holds the guest's last 2.2 ms (#433, 0.5)

Base: master @ b9212b3462 (coldstart1010 folded), merged into the lane at b110cb4e90.

Where this starts: coldstart1010 NOTES.md sections 9 and 10. In the stacked configuration (six switches,
`HAKUX_POSTED_PUT=1`, `HAKUX_SUBMIT_FRAMES=3`) cold start 1 runs 34.79 ms per frame, and the cold guest waits
2.19 / 2.35 ms a frame for pfifo.lock (`lockw`) against 0.72 / 0.81 warm. `lock_wait_ns` is added at two sites,
and neither was a frametrace wait, so nothing said which one holds it or what the PFIFO thread was doing.

## 0. The instrument (step 1)

Both sites now go through one function, `pfifo_lock_timed(d, site)` (nv2a_int.h):

| site | where | when the vCPU takes the lock |
|---|---|---|
| `kick` | `pfifo_post_kick()` (pfifo.c, posted-put block) | a posted DMA_PUT store read `parked` true and must broadcast `fifo_cond` |
| `put` | `user_write()`'s locked branch | a DMA_PUT store `pfifo_dma_put_may_post()` refused (switch off, skew bound on, or another channel) |
| `get`, `ref`, `oth` | `user_write()`'s locked branch | a DMA_GET, REF or other USER store |

- Off (`HAKUX_FRAMETRACE` unset), the function is the old timed lock: two clock reads and `lock_wait_ns +=`,
  plus one load of `hakux_ft_on` and a branch. Neither the counters nor the frametrace wait run.
- On, `pfifo_lock_timed_ft()` (pfifo.c) makes the wait a frametrace pfifo.lock wait with holder
  `HAKUX_FT_PFIFO`, as the vCPU's pgraph.lock waits are, and books it to its site: ns, acquisitions, and
  acquisitions of 10 us or more. `lock_wait_ns` stays the sum of the sites.
- It also books `lockw_parked_ns`: the waits that ended with `parked` still set, read under the lock. Those
  ended at the PFIFO thread's condition wait or at another thread's release. A wait that ended at the end of
  the PFIFO thread's run or spin does not count here: `parked` is clear during both.
- The frametrace record gets per frame `lw_<site>` (us), `ln_<site>`, `lb_<site>`, `lw_parked` and
  `vhp_<holder>`. `vhp_<holder>` is the holder split over the pfifo.lock waits alone (`vh_*` covers all the
  vCPU's holder waits, pgraph.lock included). The 1 Hz `hakuX-ft1` summary and a `hakuX-perf lockw` line every
  60 flips carry the same split.
- What `vhp` cannot see: the PFIFO thread's park and its own pgraph.lock acquisition in the puller are not
  frametrace waits, so both book `run`. `lw_parked` separates the first. The second shows up as `run` in a
  wait that did not end parked.
- profile.h's attribution table: lockw that is not seen as a pfifo.lock wait was UNATTR. Both sites are now
  pfifo.lock waits, so UNATTR keeps only the skew between the two counters.

Checks run on the instrument:
- `docs/lanes/frametrace/selftest.py` (the real profile.h, 43 checks, 21 mutants): PASS.
- `docs/lanes/lockwake1011/selftest_wake.sh`: PASS, about 2 min 15 s. It replaces postput1010's selftest,
  which no longer compiles against user.c. It keeps that selftest's checks 1-6 and falsifiers F1-F5, and adds:
  - check 7 SITES: off, only `lock_wait_ns` moves. On, each held-lock store books >= 300 ms, one acquisition
    and one long one to its own site, through one frametrace wait with holder PFIFO, and `lock_wait_ns` moves by
    exactly the sum. The posted store's wake to a parked PFIFO thread books `kick` and `parked`.
  - falsifiers F6-F9, all caught: GET booked as OTHER, the frametrace branch removed, the `lock_wait_ns` add
    removed, the posted wake booked as PUT.
- pfifo.c, user.c, nv2a.c, pgraph.c and profile.c compile with the NDK's clang under the dispatcher build's
  own flags (Release, arm64), with and without `NV2A_PERF_LOG`. No new warnings.
- `check_android_guards.py`: ok.

Reader: `lwsite.py <run dir>` (this directory). It prints the site table for cold, warm and post-GO from the
frametrace CSV, and cross-checks it against the perf line. On section 9's run 1, with synthetic site columns, it
reproduces that run's lockw, 2.19 / 0.72.

Already in section 9's CSVs, before any new run (runs 4044114 / 4044180, `lockw` column, countdown window):

| | cold | warm |
|---|---|---|
| lockw, ms per frame | 2.19 / 2.35 | 0.72 / 0.81 |
| frames with lockw >= 4 ms | 27 / 27 % | 7 / 8 % |
| their mean lockw, ms | 7.5 / 8.1 | 5.5 / 5.4 |
| their share of the window's lockw | **91 / 94 %** | 53 / 50 % |
| largest, ms | 14.1 / 23.3 | 14.5 / 23.8 |

So the cold wait is one long wait of about 8 ms on a quarter of the frames, not a toll on every store. Over
that long, the PFIFO thread keeps pfifo.lock through a stretch with no release the vCPU wins. Its puller drops
the lock at every slow method, so either the stretch has no slow method, or the vCPU loses the lock back to
the PFIFO thread at each drop (a mutex without handoff). Step 1's holder split and wait counts tell these
apart.

## 1. Which site holds the cold wait

Two plain runs of the stacked configuration with `HAKUX_FRAMETRACE=1` at ee62b4edb5:
0-1791714330-lockwake1011-1625482 and 0-1791714331-lockwake1011-1625531. They were queued at 03:25 PDT as `1-`
requests, behind 54 fastpaths1010 screen requests (about 4.3 h of Nova time). lane.local moved them to tier 0.
Both are 12 of 12 marks, with `[postput] on, skew bound mode 0`. The moving-car check in the g11 frames passed,
and there was no boot input failure.

Readings, each cell run 1 / run 2:
- `lwsite.py` output: `census_lwsite.txt`.
- The long-wait frame split: `census_longwait.txt`.

What a reading has to tell apart, written before the data (03:25 PDT). With `HAKUX_POSTED_PUT=1` a DMA_PUT store that finds
the lock busy does not wait for it. It takes the lock (`kick`) only when it reads `parked` set, and the PFIFO thread
holds the lock with `parked` set only for the instructions on either side of its condition wait. So:
- **A long `kick` wait** means the store read `parked` while the PFIFO thread was in its wait, and then lost the
  lock: to a third thread that kicked, or to the PFIFO thread itself, woken by that kick and now running its loop.
  Once the PFIFO thread is awake, the store no longer needs the lock at all, so the wait is pure waste and
  a lock-free wake removes it. Expected signature: `vhp_run` high, `lw_parked` low.
- **A long `put` wait** means `pfifo_dma_put_may_post()` refused the store, which in this configuration should only
  happen on a channel switch. A non-zero `put` is a finding in itself.
- **A long `get`, `ref` or `oth` wait** is a register the XDK writes that no lane has looked at. Name it, and price
  posting it against shortening what PFIFO does under the lock.
- **`lw_parked` high with `vhp_run` low**: the waits ended while the PFIFO thread was parked, so another thread held
  the lock. The pfifo.lock takers off the PFIFO thread are the Vulkan display path
  (`pgraph_vk_get_framebuffer_surface`, which can wait on a fence under the lock when external memory is used),
  the surface download waits (`vk/surface.c`, kick and release), and PGRAPH MMIO writes from the vCPU
  (`pgraph.c`, not counted in `lockw`).

The first and last signatures were wrong about `vhp_run`. The park is not a frametrace wait, so a wait that ends with
the PFIFO thread parked books `run` as well. `vhp_run` is high in every case, and `lw_parked` alone tells the
two apart. It came out high: the third-thread case.

### The site table (ms per frame unless marked; -2..+1.5 s window; post = +1.5..+12 s)

| | cold | warm | post-GO |
|---|---|---|---|
| frames | 101 / 100 | 1158 / 1156 | 3455 / 3465 |
| `lockw` | 1.53 / 1.57 | 0.64 / 0.81 | 0.31 / 0.19 |
| **`kick`** (`pfifo_post_kick`) | **1.53 / 1.57** | **0.64 / 0.81** | **0.31 / 0.19** |
| `put`, `get`, `ref`, `oth` | 0 / 0 | 0 / 0 | 0 / 0 |
| kick waits per frame | 0.28 / 0.29 | 0.23 / 0.25 | 0.11 / 0.10 |
| of them >= 10 us | 0.28 / 0.29 | 0.22 / 0.24 | 0.10 / 0.09 |
| us per kick wait | 5501 / 5423 | 2833 / 3268 | 2703 / 1880 |
| ended with PFIFO parked (`lw_parked`) | 1.49 / 1.57 | 0.63 / 0.80 | 0.30 / 0.19 |
| `vhp_run` (all of `vhp`) | 1.52 / 1.57 | 0.64 / 0.81 | 0.31 / 0.19 |
| share of `lockw` in frames >= 4 ms | 87 / 87 % | 44 / 57 % | 65 / 41 % |
| perf line `lockw` (cross-check) | 1.35 / 1.21 | 0.42 / 0.61 | |

Over the whole run, every pfifo.lock wait was a `kick` wait:
- `lockw` = `kick` = 2639 / 2248 ms in total.
- 1098 / 1151 acquisitions, 969 / 1033 of them 10 us or longer.
- 98 / 99 % of the time ended with `parked` set.

The `put` site is 0, so `pfifo_dma_put_may_post()` refused no store: no channel switch and no skew bound. GET, REF
and the other USER registers were never written while the lock was busy, and probably never at all.

**`kick` is the whole wait.**

### What the PFIFO thread was doing: parked, with a third thread holding the lock

- Every `kick` wait ended with `parked` still set (`lw_parked` = `kick`).
- The PFIFO thread clears `parked` under the lock as soon as its condition wait returns. So for the whole wait it
  was in `pfifo_park()`: in its condition wait, or woken but not yet holding the lock.
- So neither the vCPU nor the PFIFO thread held pfifo.lock. A third thread did.
- `vhp_run` takes all of the time only because the park is not a frametrace wait (section 0).

The cold frames whose kick wait is >= 3 ms (22 / 21 of them), against those under 1 ms (76 / 74):

| ms per frame | kick wait >= 3 ms | kick wait < 1 ms |
|---|---|---|
| frame period `P` | 39.88 / 39.79 | 33.17 / 33.39 |
| `lw_kick` | 6.69 / 6.89 | 0.01 / 0.02 |
| vCPU run `v_run` | 30.27 / 30.04 | 30.64 / 30.08 |
| vCPU blocked `v_blk` | 9.35 / 9.44 | 2.31 / 3.24 |
| guest idle `gidle` | 3.38 / 3.44 | 8.93 / 6.96 |
| PFIFO run `p_run` | 20.75 / 20.46 | 20.90 / 20.05 |
| PFIFO idle `pidle` | 18.24 / 17.18 | 10.66 / 10.76 |
| unregistered threads' fence wait `o_fence` | **28.49 / 29.30** | 16.86 / 18.76 |
| unregistered threads' pfifo.lock wait `o_pfl` | 0 / 0 | 0 / 0 |

- In a long-wait frame, the vCPU and the PFIFO thread both sleep for the wait. The vCPU sleeps on the lock. The
  PFIFO thread is parked and idles 7 ms longer.
- Meanwhile an unregistered thread spends 10.5-11.6 ms more in `vkWaitForFences` (`profile.c` times every call on
  every thread).
- The off-thread pfifo.lock takers in the tree:
  - `pgraph_vk_get_framebuffer_surface()` (vk/renderer.c:2798), from the UI's display refresh. On the Nova it
    takes the external-memory branch: logcat says `external memory interop=enabled`. It calls
    `vkWaitForFences(ready->fence, UINT64_MAX)` **with pfifo.lock held** whenever the ready display image's
    fence is still in flight.
  - The scale-factor setters and the two download kicks in vk/surface.c. Each holds the lock for a few
    statements.
  - The renderer switch. It does not run here.
- So the holder is the display refresh waiting for the GPU to finish the display image. That is inferred, not
  measured: the UI thread is unregistered, so its fence wait is pooled in `o_fence`. But nothing else can hold
  pfifo.lock for 5-7 ms with the PFIFO thread parked.

Why the cold wait costs the frame and the warm one mostly does not:
- In the cold long-wait frames, the guest's own idle drops from 7-9 ms to 3.4, and the frame grows by about the
  whole wait: 6.6 ms of `P` for 6.7-6.9 ms of wait. The cold frame is short of vCPU time.
- Warm long-wait frames (124 / 146 of about 1100) wait 4.3-4.9 ms but grow only 0.5-1.4 ms. There the guest has
  11 ms of idle to absorb it.

### Did the instrument change the regime?

The brief's check is the instrumented `lockw` against section 9's: 2.19 / 2.35 cold, within about 0.3.

| | section 9 (786f82d4bb) | here (ee62b4edb5) |
|---|---|---|
| `lockw` cold | 2.19 / 2.35 | **1.53 / 1.57** |
| `lockw` warm | 0.72 / 0.81 | 0.64 / 0.81 |
| frames with `lockw` >= 4 ms, cold | 27 / 27 % | 22 / 21 % (>= 3 ms) |
| their mean wait, ms | 7.5 / 8.1 | 6.7 / 6.9 |
| census `P` cold | 34.85 / 35.27 | 34.67 / 34.96 |
| cold frames past 2 VBLANKs on either thread | 24 / 27 % | 20 / 28 % |

**Cold `lockw` moved by 0.65-0.8, outside the brief's 0.3. Warm did not move.**
- The emulator diff between the two binaries is this lane's instrument and nothing else.
- So the instrument may have changed the regime. The data cannot rule it out: two runs a side, and the two
  pairs agree within themselves (0.16 and 0.04).
- What did not move is the frame: the cold `P`, and the share of cold frames past 2 VBLANKs.

The split is still taken, because:
- What is left is 1.55 ms per frame. That is 70 % of section 9's figure, and above the brief's 1.0 stop line.
- It is all one site, in both runs. A share of 100 % does not depend on the level.

The A/B below runs without `HAKUX_FRAMETRACE`. Its arm A gives the uninstrumented level the switch acts on.

## 2. Decision

Written 2026-10-11, before anything was built.

**`kick` dominates (100 %), and cold `lockw` is 1.53 / 1.57 > 1.0. So, per the brief: a pfifo.lock-free wake,
`HAKUX_LOCKFREE_WAKE=1`, default off.**
- The PFIFO thread parks on a QemuEvent (util/event.c, a futex on Linux and Android). Every `fifo_cond` waker
  also sets it.
- A posted DMA_PUT store then sets `fifo_kick` and the event and returns. It never takes the lock.

What the switch can and cannot do (the mechanism, checked against the measurement):
- **It removes the vCPU's wait and nothing else.** The woken PFIFO thread still has to retake pfifo.lock to leave
  `pfifo_park()`. While the display refresh holds the lock, it waits there, as it does today.
- So the PFIFO thread's start does not move. The vCPU keeps the 6.7 ms it now spends asleep, and runs ahead
  posting pushbuffer: further DMA_PUT stores find the lock busy and post.
- It pays where the frame is short of vCPU time: the cold long-wait frames (guest idle 3.4 ms, `P` + 6.6).
- It does not pay where the guest's next step is to wait for the PFIFO thread anyway, for example polling
  DMA_GET or a report. That wait would move rather than vanish.

Expected:

| | probability | win at full scale |
|---|---|---|
| the lock-free wake (this lane) | 0.55-0.65 | 0.8-1.5 ms cold; ~0.2 warm; ~0 post-GO |
| release pfifo.lock around the display fence wait (not this lane) | 0.35 | the same, plus the PFIFO thread's own wait for the holder |

- The probability for the wake rests on the cold frames: the frame grows by the wait, one for one, and the
  vCPU's run time is unchanged. The brief's B ~33.6-33.9 sits in that range.
- **Releasing pfifo.lock around the display fence wait** in `pgraph_vk_get_framebuffer_surface()` removes the
  cause rather than one victim.
  - Its probability is lower because pfifo.lock is what orders that wait against `render_display()`, which
    reuses and resets the same fence on the render thread (two display images).
  - Taking the lock away needs another guard on the image, and vk/renderer.c is outside this lane's files.
  - Recorded in OUTBOX.md for the next lane. It is the larger fix if the wake leaves the PFIFO thread's
    start as the new bound.

### The wake, and why no wakeup is lost

The waker side:
- `pfifo_post_kick()`: store-release `fifo_kick = true` (DMA_PUT was stored with release just before), then
  `smp_mb()`, then read `parked`. If set, `qemu_event_set(&wake)`. No lock.
- `pfifo_kick()`: as now, plus `qemu_event_set(&wake)` next to the broadcast, inside the same `if (!fifo_kick)`.
- `nv2a_lock_fifo()` (nv2a.c) sets the event after its kick and broadcast.
- `nv2a_exitfn()` sets it after `exiting = true`.
- Neither nv2a.c site is a hot path, so both set the event whether or not the switch is on. With the switch off,
  nothing waits on the event and the set changes nothing.

The PFIFO thread side, `pfifo_park()` under pfifo.lock:
1. `qemu_event_reset(&wake)`. This is an atomic or with a full barrier after it (`smp_mb__after_rmw`).
2. `parked = true`, then `smp_mb()`.
3. Read `fifo_kick`, DMA_PUT (against `put_seen`) and `exiting`. If any says there is work, skip the wait.
4. Otherwise unlock pfifo.lock, `qemu_event_wait(&wake)`, relock.
5. `parked = false`.

`qemu_event_wait()` returns at once if the event was set at any point after step 1.

The argument. Each waker stores its condition and then reads the sleeper's state, with a full barrier between.
The sleeper stores its state (the reset, `parked`) and then reads the conditions, with a full barrier between.
That is the store-buffering pattern: at least one side sees the other's store.
- **The posted store.**
  - If the PFIFO thread sees the new `fifo_kick` or DMA_PUT in step 3, it does not wait.
  - If it does not, the poster's read of `parked` sees true and the poster sets the event.
  - That set is ordered after the reset: the poster saw `parked`, which was stored after the reset with a full
    barrier between, and `qemu_event_set()` starts with `smp_mb()` before it reads the event.
  - So the set either finds FREE or BUSY and makes it SET, waking a waiter, or finds SET from some later set.
    Either way step 4's wait returns.
- **The DMA_PUT re-read** carries postput1010's argument over unchanged. A PFIFO thread that took up a kick set
  by another thread just after the poster's has consumed the kick without seeing the poster's DMA_PUT. In step 3
  it still sees DMA_PUT != `put_seen`.
- **A kick under the lock.**
  - `pfifo_kick()` stores `fifo_kick`, then `qemu_event_set()` begins with `smp_mb()` and reads the event: the
    same pattern on (event, `fifo_kick`).
  - A `pfifo_kick()` that finds `fifo_kick` already set skips the set. That is safe because `fifo_kick` is
    cleared only by the PFIFO thread, under the lock, at its loop top, and every store of true is followed on
    its own thread by a wake: the event set, or the poster's `parked` check.
  - So a set kick seen under the lock has not been consumed yet, and the PFIFO thread will take it, and the
    caller's state, after the caller unlocks.
- **Exit.** `exiting` is a condition in step 3, and `nv2a_exitfn()` sets the event after storing it.
  - Master's exit broadcasts `fifo_cond` without the lock and without a predicate, which can be lost.
  - In wake mode it cannot be.
- **Spurious wakes** (a set left over from before the reset is erased by the reset; a set meant for the previous
  park) cost one turn of the loop: take the kick, find nothing, park again.

What the switch changes for the instruments:
- In wake mode the `kick` site never takes the lock, so the uninstrumented `lockw` reading in arm B should fall
  by the `kick` share. In this configuration that is all of it.
- A `lockw` that does not fall means the switch did not engage. Check `[lockwake] on` in logcat.

### Built and checked (step 2)

The wake is in pfifo.c's posted-put block (`pfifo_park()`, `pfifo_post_kick()`, and a new `pfifo_wake()` that
`pfifo_kick()` now calls), nv2a_int.h (`QemuEvent wake` in the pfifo struct) and nv2a.c (init, and the set in
`nv2a_lock_fifo()` and `nv2a_exitfn()`). Every `fifo_cond` broadcast in the tree is one of those four. Without
`HAKUX_POSTED_PUT=1` the switch is inert and says so in logcat (`[lockwake] off (inert: ...)`).

- `selftest_wake.sh`: PASS, about 3.5 min. It now runs three modes, off (with `HAKUX_LOCKFREE_WAKE=1` set, to
  show it inert), on (posted put alone) and wake. Checks 1-7 keep their off and on expectations unchanged.
  It compiles util/event.c's futex QemuEvent verbatim. New:
  - check 8 LOCKFREE: a posted store to a parked PFIFO thread under a 400 ms third-thread hold. Wake: 0 ms, one
    event set, no `lockw`. On: 400 ms and 400 ms of `lockw`, the wait this lane measured.
  - check 9 IDLE: with a stale set on the event, the idle stand-in turns 0 times in 200 ms (all modes).
  - check 10 EXIT: 2,000 exits as `nv2a_exitfn()` makes them, at random points of the loop; all joined.
  - check 7 in wake mode: the posted store books nothing; GET and REF still book their own sites.
  - check 4 in wake mode: 100,000 stores, 36,929 posted and 63,071 locked, none lost. Check 5: 4.5 M rounds,
    1.2 M would-sleep, none lost.
- Falsifiers, all caught:
  - F1, F3, F4 and F5 now also run in wake mode, and lose wakeups or rounds there too. Without
    `pfifo_park()`'s barrier, wake mode lost 319 of 4.5 M rounds; without `pfifo_post_kick()`'s, 439.
  - F10, no reset: the idle thread spins (7,839 turns in 200 ms).
  - F11, the reset moved after the check: 1,550 rounds lost.
  - F12, `pfifo_wake()` without its set: the first locked kick is lost.
  - F13, no `exiting` predicate: the exit hangs (8th exit).
  - F14, `pfifo_post_kick()` without the lock-free branch: check 8 waits 399 ms.
- pfifo.c, nv2a.c, user.c, pgraph.c and profile.c compile with the NDK's clang under the dispatcher's flags,
  with and without `NV2A_PERF_LOG`. No new warnings: profile.c's two (lines 1013 and 1108) are master's.
- `check_android_guards.py`: ok (3,305 files).

What the selftest does not show: whether the woken PFIFO thread starts any sooner. It does not, by design; it
still waits for the holder to retake the lock. The A/B measures whether the vCPU's freed time moves the frame.
