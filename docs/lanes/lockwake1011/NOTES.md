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

(pending: two plain runs of the stacked configuration with `HAKUX_FRAMETRACE=1` at this lane's head)

## 2. Decision

(written here before anything is built)
