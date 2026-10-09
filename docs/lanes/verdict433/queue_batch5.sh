#!/usr/bin/env bash
# Batch 5 of lane.verdict433 (#433): two reruns from batch 4's Nova results.
#
# AUF (007: Agent Under Fire, -1456591): "guest never appeared in 1475s --
# title did not boot". logcat shows xemu reaching qemu_init/
# sdl2_display_early_init and then nothing for the rest of the run -- no
# crash, no further log line, until "soak end" 25 min later. This run
# started before hostops's 20:10 PDT chmod-660 fix for titles.qcow2 (the
# shared HDD file every one of this batch's six runs opens): WWE Raw 2 and
# 50 Cent, which ran just before AUF, were marked void for the diagnosed
# cause (VOID.txt: "titles.qcow2 on nova was pushed with adb push's default
# rw-r--r--, one group-write bit short... xemu's -drive open failed
# 'Permission denied' every launch"). Baldur's Gate DA, which ran right
# after AUF, booted cleanly -- consistent with the fix landing in between.
# AUF's silent hang at exactly the qemu_init stage matches the same known
# bug's signature (see memory: pushed disk needs 660, SIGSEGV/hang 2-7ms
# into qemu_init on a bad HDD open), not a real read on the title. Rerun.
#
# Baldur's Gate DA (-1456665): booted fine, played the full route into
# gameplay, and ran 1684 s of a planned 1760 s (title_verdict reads
# gameplay=1190.0s, 10s short of the 1200s bar) before adb went unreadable
# for 5 straight polls ("foreground-unreadable: adb failed (exit 1)") and
# the soak aborted. No crash, no hang, audio_short=0.0 through the readable
# portion. This reads as a single adb capture flake very close to the
# finish line, not a low-fps or crash result -- per memory, a single-run
# device flake gets a rerun before any conclusion.
set -u
R=docs/testing/request.sh
REF=${REF:-2dd92568b5}

q_nova_default() { # title route seconds why
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
        --title "$1" --route "$2" --seconds "$3" \
        --env PERF_REGIMEN=default --issue 433 \
        --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
        --purpose "#433 Playable confirmation (batch 5, rerun of a batch-4 result): $4, $2 route, nova, PERF_REGIMEN=default, 1200 s after the mark"
}

q_nova_default '4541000D-007_Agent_Under_Fire.xiso.iso' survey 1475 "007: Agent Under Fire (rerun: pre-chmod-fix boot hang on titles.qcow2)"
q_nova_default '5655001A-Baldur_s_Gate_Dark_Alliance.xiso.iso' baldurs-gate-da 1760 "Baldur's Gate: Dark Alliance (rerun: adb capture flake at 1684s of 1760s)"
