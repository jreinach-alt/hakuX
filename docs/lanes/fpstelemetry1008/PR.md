# fpstelemetry1008: one cause table for the below-bar titles -- perflog + GPU xfr + frame trace on the Nova (#433)

State: in progress — waiting (see WAITING.md)

Lane: fpstelemetry1008      Issue: #433 (dispatched directly, no tracker issue)
Base: master @ 93fbc525fc (unchanged from attempt 2; no new merge this attempt)
Files: docs/lanes/fpstelemetry1008/NOTES.md, docs/lanes/fpstelemetry1008/PR.md
Prediction: none: telemetry survey, no golden, no A/B arm
Needs device: yes (Nova; 2 fresh requests DONE from attempt 2 — MechAssault 2, Buffy;
  3 more queued this attempt, not yet landed — see NOTES.md §8)
Needs NDK: no
Release note (none): analysis only; no emulator or Android code touched.

**Not ready. Addenda 2 and 3 (route-resolution fix; re-measure the CPU-only-attributed
titles with fresh perflog+GPUXFR+FRAMETRACE runs; Fantastic 4 now on the Nova) landed
around the time attempt 2 marked this ready, and attempt 2's table does not reflect
them** (NOTES.md §8 works out exactly why from the commit/addendum timestamps). This
attempt corrected the gate audit (every below-bar title this lane touched clears for
telemetry — attempt 2 read several owner-holds rows as blocking when their text is the
same cleared reason in different words, NOTES.md §8), confirmed Fantastic 4's ISO and
re-verified ISO presence for the whole Addendum-3 list, found `doa3.route` undisclosed as
never having run as a timed route (fixed by queuing a pilot), generated 8 of the 10
missing routes via `steps2route.py` from pathfind's own recorded gameplay (NFS Most
Wanted and Midnight Club II are blocked by an unrelated `steps2route.py` token-handling
bug, not by a decision — NOTES.md §9), and queued three device requests (NBA Live 2005
full telemetry; DOA3 and MK Shaolin Monks pilots). A fourth (Arctic Thunder) was refused
by the device-time pilot gate (owner rule: no more than 30 min queued+running without a
reviewed `pilots/fpstelemetry1008.ok`) — that review needs the three queued results,
which had not landed by the time this session's budget required writing up and handing
off. See NOTES.md §8-9 for the full state and the exact next commands.

Still true from attempt 2, carried forward: the original cause table (§7) covering
MechAssault 2 and Buffy (fresh) plus 9 existing-data attributions (NFS Most Wanted, LOTR
ROTK, Hulk UD, NHL 2K3, Spider-Man 2, Midnight Club II, Ninja Gaiden Black, Dead or Alive
3, NBA Live 2005) is unchanged and still in the file — it is the CPU-only-sourced version
Addendum 3 asks this lane to replace with fresh GPU-telemetry rows once the queued/pending
runs land. Findings worth flagging on their own, still standing: MechAssault 2 splits into
two regimes (guest-CPU-bound in most windows, render-thread-saturated in the worst decile,
not explained by surface-download finishes); `HAKUX_FRAMETRACE=1` produced no frame-trace
data in either fresh run so far; Buffy's fresh-run fps share (3%) disagrees sharply with
its recorded verdict (55%) because the two runs take different routes through the title,
not a regression.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
