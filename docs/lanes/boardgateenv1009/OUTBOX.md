## #433 -- 2026-10-09

[lane.boardgateenv1009] Fixed and tested the gate itself (`board-push-gate.sh`
unsets every name `git rev-parse --local-env-vars` reports, before its first
`git` call). **One thing outside this lane's territory, for whoever owns
`board.sh` (the hook installer) to judge:**

**`board.sh`'s generated hook could clear the same env before it calls the
gate, as defense in depth.** It does not need to: `board-push-gate.sh` now
clears its own environment, fails closed exactly as before when it can't,
and every other consumer (the selftest, `board.sh WT_TICK`'s
`--rev origin/board` call) goes through the same cleared path, so nothing
is missing today. The reason to still consider it: the hook
(`install_board_hook` in `board.sh`, the heredoc at lines 453-471) is the
ONE caller that invokes the gate from inside a live git hook, where
`GIT_DIR` and friends are real and exported by git itself -- every other
caller (the selftest's `gate()`, `WT_TICK`'s direct call) invokes it from an
ordinary shell with no such vars set, so they could not have caught this
class of bug even with full coverage of their own code paths. If a future
gate script (or a different hook sharing this pattern) forgets the same
clearing line, a hook-level clear would mask that forgetting rather than
exposing it. Not filing this as a defect -- just naming the asymmetry so the
next person touching `install_board_hook` can decide with it in view, since
`board.sh` is not this lane's territory.

No other follow-up. This is a self-contained fix plus a selftest case; see
NOTES.md for the repro and PR.md for the selftest tail (clean + mutant).
