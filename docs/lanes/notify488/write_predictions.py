#!/usr/bin/env python3
"""Write the #488 hand-read predictions (timing and DOA A/B). Run once, before
any device run; the files, not this script, are the registration."""
import datetime
import json

now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
A = 'dffb7a8a660e1fc367dbb27ee0c30a17b1f8269b'
B = '9f80bc887aee554dec249e2c3978853faec3f44d'

timing = {
    "registered_utc": now,
    "who": "lane.notify488",
    "issue": "488",
    "device": "nova",
    "program": "pgraph",
    "base_iso": "/home/justin/hakux-work/hardware/runs/2026-09-27-timing462/timing462.iso",
    "suites": ["Alpha func", "Signal timing"],
    "only_tests": ["Alpha func::AlphaFuncAlways_Disabled",
                   "Signal timing::ST_Calibrate",
                   "Signal timing::ST_VBlank_Spin",
                   "Signal timing::ST_Done_Tiny",
                   "Signal timing::ST_Done_DOA",
                   "Signal timing::ST_Done_DOA_Read"],
    "runs_per_arm": 1,
    "a_ref": A,
    "b_ref": B,
    "queue_order": "PILOT: B alone first (the owner's pilot rule; <= 5 min). Then A. Each: HAKUX_RELEASE_PRIO=1 request.sh --device nova --base-iso <above> --suites 'Alpha func,Signal timing' --only-tests <above> --ref <ref> --no-expect (hand-read; this file is the registration)",
    "judge": "python3 docs/lanes/notify488/timing_judge.py <A result> <B result>; --pilot <B result> for the pilot. The judge was run on the console's own files (docs/lanes/xbox/signal-timing/console): every B-only leg passes on silicon, N2 at 0.9996.",
    "prediction": "#488 on lane.xbox's signal-timing XBE (PR #486, tests commit 4fd5b45, ISO timing462.iso), both arms on the Nova. A = dffb7a8a66: master db8cc66396 plus a perflog-only counter line and the NV097_NOTIFY define (a shipping build is master's code). B = 9f80bc887a: A plus (1) an NV097 NOTIFY handler that writes the 16-byte notifier at offset 0 of the notifies DMA (PTIMER time, info32 0, status 0) and (2) BACK_END_WRITE_SEMAPHORE_RELEASE, under TCG on Vulkan with no GET_REPORT since the last release, records the queued draws instead of downloading the bound surfaces; the surface watch downloads on the guest's read. ST_Flip and ST_VBlank_Event are left out: neither change touches them. The Thor A numbers (13.8 ms DOA, 275 us Tiny) are a different device, so A is re-measured on the Nova.",
    "legs": {
        "I1 (instrument)": "counter_over_interrupt in 0.995..1.005 in both arms; every Done test has 300 reps and 0 busy_timeouts. Otherwise VOID, rerun once.",
        "M1 (the impossible row)": "A: notify_timeouts == 300 in each of ST_Done_Tiny, ST_Done_DOA, ST_Done_DOA_Read (A has no NOTIFY handler). A written notifier in A means the arms carry the wrong binaries.",
        "N1 (NOTIFY written)": "B: notify_timeouts == 0 and kick_to_notify median <= 16683 us (one frame) in all three Done tests. FAILS in the world where the handler is not reached, the notifies DMA object cannot be mapped (limit < 15), or the status word is not at +12 where the test polls.",
        "N2 (the timestamp is PTIMER nanoseconds)": "B, ST_Done_Tiny: the median over consecutive reps of (notifier timestamp delta) / (kick delta in ns) is in 0.95..1.05 (the console reads 0.9996). FAILS if the timestamp is PTIMER's raw clock without the <<5 (ratio ~1/32) or a different clock.",
        "S1 (the brief's leg: semaphore within a frame)": "B, ST_Done_DOA: kick_to_semaphore median <= 16683 us AND <= 0.5 x A's median. KILL: B/A > 0.5 -- refuted: the release's wait is not the download (e.g. it is PFIFO's backlog of the 500 draws, which B keeps).",
        "S2 (a guess, labelled as one)": "B's ST_Done_DOA median <= 3 ms, and B's ST_Done_Tiny median <= 0.5 x A's. About 60% confident: what is left after the download is PFIFO reaching the release, and the Thor's p5 of 11.6 us says it can be immediate.",
        "S3 (the cost moved to the reader, not vanished)": "B's cpu_read_back_buffer median in ST_Done_DOA_Read >= A's - 1 ms: the first read traps into the surface watch and downloads there. FAILS -- and is then a correctness alarm, not a speed win -- if B's read is faster: the read did not wait for the download and may have seen stale VRAM. A failure here blocks shipping until explained.",
        "P0 (pixels)": "the ST_Done_Tiny, ST_Done_DOA and ST_Done_DOA_Read captures are byte-identical A vs B (the harness reads the back buffer back after each test through the same watch).",
        "H0 (no new hang)": "both arms complete with progress-log proof and no fatal signal in logcat."
    },
    "expect": {},
    "expect_counts": {},
    "expect_note": "EMPTY ON PURPOSE: the Signal timing suite has no goldens (the table is console vs hakuX); the legs are read by timing_judge.py."
}

game = {
    "registered_utc": now,
    "who": "lane.notify488",
    "issue": "488",
    "title": "54430006-Dead_or_Alive_1_Ultimate.xiso.iso",
    "device": "nova",
    "seconds": 300,
    "route": "survey",
    "perflog": True,
    "frames_every": 0,
    "runs_per_arm": 2,
    "a_ref": A,
    "b_ref": B,
    "window_s": [151, 288],
    "queue_order": "after the timing pilot is read: A1 B1 A2 B2, each HAKUX_RELEASE_PRIO=1 request.sh --title <above> --device nova --route survey --seconds 300 --perflog --ref <ref> --no-expect (hand-read soak)",
    "judge": "python3 docs/lanes/notify488/notify_read.py --from 151 --to 288 <A1> <B1> <A2> <B2>",
    "prediction": "#488 on DOA Ultimate's fight (#474; lane.flip474's window 151-288 s on the survey route). Before any run: DOA never sends NV097 NOTIFY -- 'method 0x0104' is absent from the unhandled lines of every DOA and AUF soak on disk (1790491858-flip474-658414, the aufire412 and slowdown462 soaks) -- so the NOTIFY half cannot move this title, and this arm is about the semaphore half. Whether DOA sends BACK_END_WRITE_SEMAPHORE_RELEASE at all is not known: the perflog method histogram (hakuX-mhist) never reached the dispatcher's logcat filter. Both arms now print [notify488] sem_release/notify counts per 60 frames, so A answers it. flip474 placed DOA's 51-56 ms/frame PFIFO wait in the first surface_update after each flip (the flip's display download), not in a semaphore; if that is the whole wait, B cannot move the frame rate.",
    "legs": {
        "M0 (instrument)": ">= 20 gfps lines and >= 2 [notify488] lines in 151-288 s in every run. Otherwise VOID, rerun once.",
        "F0 (the mechanism is reachable)": "A's sem_release sum in the window >= 1 per [notify488] line (one release a second or more). If it is 0 the arm is INERT for DOA: P2 is not judged, P1 and H0 still are. notify == 0 in both arms (the prior above); a nonzero notify count refutes that prior.",
        "P1 (no regression)": "median over runs of each run's gfps median in the window: B >= A - 1.",
        "P2 (the mover, a guess labelled as one; judged only if F0 holds)": "if A's sem_release is >= 30 per line (about one per frame): B - A >= +1 fps. KILL with F0 holding: B - A < 0.5 -- DOA's releases do not carry its wait. About 35% confident, because flip474 put the wait in the flip's download.",
        "H0 (no new hang)": "in every B run: longest gap between hakuX-perf lines in the window <= 3 s, and no fatal signal."
    },
    "must_not_move": ["pgraph: docs/testing/predictions/notify488-pgraph.json"],
    "expect": {},
    "expect_counts": {},
    "expect_note": "EMPTY ON PURPOSE: a soak writes no captures. The legs are read by notify_read.py."
}

for name, obj in (('timing', timing), ('doa-ab', game)):
    text = json.dumps(obj, indent=2, ensure_ascii=False) + '\n'
    json.loads(text)
    open('docs/testing/predictions/notify488-%s.json' % name, 'w').write(text)
print('ok', now)
