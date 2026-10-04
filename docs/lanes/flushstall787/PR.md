flushstall787: time translation, TLB refill and flush work per window, to answer "is the guest-late stall the flush?" (#787)

State: draft

Lane: flushstall787     Issue: #787
Base: master @ 5d5d2c51a5
Files: accel/tcg/translate-all.c, accel/tcg/cputlb.c, accel/tcg/cpu-exec.c, docs/testing/predictions/flushstall787-kabuki.json, docs/testing/predictions/flushstall787-tron.json, docs/lanes/flushstall787/PR.md, docs/lanes/flushstall787/NOTES.md, docs/lanes/flushstall787/OUTBOX.md, docs/lanes/flushstall787/fs_windows.py, docs/lanes/flushstall787/fs_pages.py, docs/lanes/flushstall787/fs_jcx.py, docs/lanes/flushstall787/fs_judge.py, docs/lanes/flushstall787/ndk_check.py, docs/lanes/flushstall787/build.sh
Prediction: docs/testing/predictions/flushstall787-kabuki.json @ 08f17e8e7ec965bb8d5660f60d0f58c36bd09c665b4f0e949a6362b76d5e6070, docs/testing/predictions/flushstall787-tron.json @ fc9d4b5e88525111873ef247084f456f2cd1153126b577eaaaa26d200d236d41 (single-run measurements, queued by the lane)
Needs device: yes (Nova, two perflog soaks)    Needs NDK: yes

Release note (none): instrumentation only; two log lines ([tcg787], [tpc787]) and a timer around tb_gen_code.

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
Tron `1-1791072697-lane.flushstall787-1209966`. Results and the answer go here and in NOTES.md.

Checks so far: the three files compile with the dispatcher build tree's NDK command, plain and NV2A_PERF_LOG=1
(`ndk_check.py`). No desktop build on this host (AGENTS.md's known gap); the counter's own checks are the
predictions' validity legs, read off the run.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
