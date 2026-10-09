#!/usr/bin/env bash
# Batch 4 of lane.verdict433 (#433): re-queue all six confirmations that
# vanished from the dispatch tree between session 5's close-out and this
# session's resume.
#
# What happened: session 5 queued six Nova confirmations (WWE Raw 2 retry
# -3697079, 50 Cent retry -3697712, 007: Agent Under Fire -1492209, Baldur's
# Gate DA -3241572, KOF MI -3241617, Azurik -3241677) and parked on a
# `waiting:` comment (PR #610, #433, both 2026-09-29T21:11-21:12Z). hostops
# confirmed at 21:33:32Z they were "correctly in queue" behind a Nova
# battery hold expected to lift at >=45% or 16:15 PDT (23:15Z).
#
# This session (started 23:26:05Z) found none of the six anywhere: not in
# queue/, not in running/, not in results/, not in queue/withdrawn/, with no
# ERROR, no DONE, no alias and no comment recording a withdrawal or a
# result. Checked with a full os.walk of $DISPATCH_DIR (Glob's single-`*`
# behaved inconsistently against the ~2000-entry results/ tree and is not
# trustworthy at that scale; os.walk is ground truth here) for all six raw
# ID numbers (3241572, 3241617, 3241677, 3697079, 3697712, 1492209) -- zero
# matches anywhere in the tree. No comment on #433 or #610 after 21:33:32Z
# mentions them until lane.kabukistall's unrelated K1 post at 22:54:03Z.
# This looks like a harness bug (a queue entry lost during the battery-hold
# wait, or during whatever admitted lane.kabukistall's K1 run, which borrowed
# one of these IDs' battery-need estimate as `backfill_for` in its own
# result.json), not something this lane caused or can root-cause further
# from inside the worktree. Recorded, not filed as an issue (dispatch
# harness fixes go to a lane brief, not a GitHub issue, per standing
# guidance) -- reported on #433/#610 instead.
#
# Re-queuing all six fresh, all on the Nova at its default confirmation
# regimen (the addendum moved every heat-sensitive confirmation off the
# Thor; Nova had 0/85 thermal pauses in the window lane.local measured).
# REF bumped to the current origin/master tip (2dd92568b5, merged into this
# branch this session) rather than reusing the batch-2/3 refs, since master
# has moved and nothing here depends on comparing against those exact
# builds. --seconds figures are carried over unchanged from queue_batch2.sh/
# queue_batch3.sh (route mark time + 1200 s + margin, unaffected by REF).
set -u
R=docs/testing/request.sh
REF=${REF:-2dd92568b5}

q_nova_default() { # title route seconds why
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
        --title "$1" --route "$2" --seconds "$3" \
        --env PERF_REGIMEN=default --issue 433 \
        --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
        --purpose "#433 Playable confirmation (batch 4, re-queue of a vanished batch-2/3 request): $4, $2 route, nova, PERF_REGIMEN=default, 1200 s after the mark"
}

q_nova_default '5451000D-WWE_Raw_2.xiso.iso' wwe-raw-2 1550 "WWE Raw 2"
q_nova_default '56550042-50_Cent_Bulletproof.xiso.iso' 50cent 1420 "50 Cent: Bulletproof"
q_nova_default '4541000D-007_Agent_Under_Fire.xiso.iso' survey 1475 "007: Agent Under Fire"
q_nova_default '5655001A-Baldur_s_Gate_Dark_Alliance.xiso.iso' baldurs-gate-da 1760 "Baldur's Gate: Dark Alliance"
q_nova_default '534E0007-KOF_Maximum_Impact_Maniax.xiso.iso' kof-mi.returning 1500 "KOF: Maximum Impact Maniax"
q_nova_default '4D530007-Azurik_Rise_of_Perathia.xiso.iso' azurik 1480 "Azurik: Rise of Perathia"
