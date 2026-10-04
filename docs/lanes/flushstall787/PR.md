flushstall787: time translation, TLB refill and flush work per window, to answer "is the guest-late stall the flush?" (#787)

State: ready

Lane: flushstall787     Issue: #787
Base: master @ 5d5d2c51a5 (origin/master 4a3308a21e merged in after the runs)
Files: accel/tcg/translate-all.c, accel/tcg/cputlb.c, accel/tcg/cpu-exec.c, docs/testing/predictions/flushstall787-kabuki.json, docs/testing/predictions/flushstall787-tron.json, docs/lanes/flushstall787/PR.md, docs/lanes/flushstall787/NOTES.md, docs/lanes/flushstall787/OUTBOX.md, docs/lanes/flushstall787/fs_windows.py, docs/lanes/flushstall787/fs_pages.py, docs/lanes/flushstall787/fs_jcx.py, docs/lanes/flushstall787/fs_judge.py, docs/lanes/flushstall787/ndk_check.py, docs/lanes/flushstall787/build.sh, docs/lanes/flushstall787/fs_guest.py, docs/lanes/flushstall787/watch.py, docs/lanes/flushstall787/waitfor.py, docs/lanes/flushstall787/fs_gs_scan.py
Prediction: docs/testing/predictions/flushstall787-kabuki.json @ 08f17e8e7ec965bb8d5660f60d0f58c36bd09c665b4f0e949a6362b76d5e6070, docs/testing/predictions/flushstall787-tron.json @ fc9d4b5e88525111873ef247084f456f2cd1153126b577eaaaa26d200d236d41 (single-run measurements, queued by the lane)
Needs device: yes (Nova, two perflog soaks)    Needs NDK: yes

Release note (none): instrumentation only, compiled in perflog builds only; two log lines ([tcg787], [tpc787]) and a timer around tb_gen_code.

A TLB flush discards no translated block in this tree: tlb_flush_by_mmuidx_async_work() clears the TLB and the
jump cache, and blocks are found by physical address. So the flush's fallout is its own work, the TLB refills
every page pays afterwards (inside TB execution, invisible to [rr425]), and whatever translation follows for
another reason. This PR times all three per [tlb68] window as `[tcg787]` and adds `[tpc787]`, a
duration-weighted profile of TB time by entry pc.

| [tcg787] field | what |
|---|---|
| gc gus cgus gmax | tb_gen_code calls that returned, total us, us of those that generated code, longest call |
| cg disc tbf | generations; blocks discarded by code-page writes (#68); tb_flush()es |
| ffus pfus | full-flush and INVLPG worker us |
| tf tfx tfus pl | tlb_fill_align calls, faults, us (timed in perflog builds only, pl=1) |

Measurement runs (Nova, ref 1fe520a709, perflog): Kabuki `1-1791072687-lane.flushstall787-1209260`,
Tron `1-1791072697-lane.flushstall787-1209966`. Validity holds in both.

**Answer: the late stall is not the TLB flush.** Kabuki (G PASS, F PASS): per stall, tb_gen_code takes
5.7-41.7 ms and everything a flush can cost takes 17.5-83.4 ms, against stalls of 401-705 ms. The stall windows
spend 0.4-1.3 s in the title's own x87 routines and kernel memory management, where a quiet window spends
0.07-0.27 s. Tron: tb_gen_code peaks at 189 ms per 2-s window, mostly first-time code with no tb_flush; the
flush fallout is <= 117 ms; the stall windows run guest kernel code after a code load. Side finding: unchained
two-page TBs (`[rr425]` gs) cost 175-372 ms of loop time in 2-3 Kabuki stalls. No fix, per the brief's
guest-side branch. Details and ranked next steps: docs/lanes/flushstall787/NOTES.md section 5.

Every hook compiles only when XBOX && NV2A_PERF_LOG (HAKUX_TCG787), so the plain build is the pre-#787 code path:
`ndk_check.py` compiles the three files plain and perflog with the dispatcher build tree's NDK command and counts
#787 symbols per object, plain 0/0/0, perflog 4/20/4. Head run for the fold: `1-1791098627-lane.flushstall787-847488`
(Kabuki, perflog, Nova, ref 0b8b63bef1): `[tcg787]` on 421 of 421 `[tlb68]` windows, validity V1-V5 hold, and it
repeats the answer: 9 stalls of 408-689 ms (8 with a flush burst), worst span tb_gen_code 60.5 ms (G PASS < 100),
worst span flush cost 100.3 ms (F PASS < 250). No desktop build on this host (AGENTS.md's known gap); the counter's own checks are the
predictions' validity legs, read off the run.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
