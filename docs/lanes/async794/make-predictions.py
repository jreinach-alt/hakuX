#!/usr/bin/env python3
"""lane.async794's soak predictions, one per title, written before any run.

A is master at the lane's base, B the fix. Same device (the Nova), perflog in
both arms so [sdcall], hakuX-phase and [lock474] read the same counters; B adds
txdl[] and reuse_detach, which A cannot print (absent in A is not zero).
Judge: docs/lanes/fps20786/decompose.py over the play window of each arm, and
docs/lanes/async794/sdcallers.py for the per-caller waits.
"""
import datetime, json

A_REF = '5e4196fefd'
B_REF = 'c825e4b24f'
NOW = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
JUDGE = ('python3 docs/lanes/fps20786/decompose.py <dir> (the mark is the route\'s '
         '`mark gameplay`) for F, Ri, rcpu, rblk, ph_Fin, ph_GPU, lockw, v_blk and the '
         '2-s fps rows; python3 docs/lanes/async794/sdcallers.py <results> <id> for '
         'the per-caller waits; play shots by eye; the same on both arms')
COMMON = {
    'M0 (instrument)': '>= 100 hakuX-phase lines and >= 100 [sdcall] lines after the '
        'gameplay mark in each arm, all parse, and the play shots show play. '
        'Otherwise that arm is VOID, not a zero.',
    'F2 (no corruption)': 'B\'s play shots show no stale, torn, black or one-frame-'
        'behind surfaces that A\'s do not (render targets, reflections, HUD), and '
        'B\'s logcat has no Vulkan validation error, device-lost, assert or crash. '
        'FAILS in the world where a completion wrote VRAM out of record order or a '
        'reader read around a detached entry; then the change is wrong, not slow.',
}


def pred(name, title, route, seconds, prediction, legs, issue='794'):
    d = {
        'registered_utc': NOW,
        'who': 'lane.async794',
        'issue': issue,
        'title': title,
        'device': 'nova',
        'seconds': seconds,
        'route': route,
        'perflog': True,
        'frames_every': 0,
        'runs_per_arm': 1,
        'a_ref': A_REF,
        'b_ref': B_REF,
        'judge': JUDGE,
        'prediction': prediction,
        'legs': dict(COMMON, **legs),
        'expect': {},
        'expect_counts': {},
        'expect_note': 'EMPTY ON PURPOSE: a soak writes no captures. The legs are '
                       'read off hakuX-phase, [sdcall], [lock474] and txr lines, '
                       'and the shots by eye.',
    }
    path = 'docs/testing/predictions/async794-%s.json' % name
    json.dump(d, open(path, 'w'), indent=2)
    open(path, 'a').write('\n')
    print(path)


pred('nba2005-soak', '45410050-NBA_Live_2005.xiso.iso', 'fps786-nba2005', 880,
     'NBA Live 2005, exhibition at the Palace, 12-minute quarters. Premise '
     '(lane.fps20786, run 1-1791081646-lane.fps20786-2876934): the unshelve of a '
     'ping-ponged render target completes the staged downloads with a finish of '
     'its own once a frame ([sdcall] reuse=fin1.00/frame, 11.4 ms/frame), ph_Fin '
     '13.8, renderer cost F - Ri 35.4 ms against 33.3, so half the frames take '
     'three VBLANKs. B detaches the reused struct from its pending download and '
     'lets each download complete on its own submission\'s fence, so neither that '
     'finish nor the next frame\'s first recorded download waits for the GPU. '
     'Claim: the 11.4 ms leaves the render thread and does not come back at the '
     'flip or at frame-slot reuse. P(ph_Fin <= 2.5 ms) 0.5; P(B clears 30 fps on '
     '>= 0.90 of 2-s rows) 0.35 -- the GPU is 18.5 ms and render CPU 24.7 ms, '
     'under 33.3 only if they overlap.',
     {
         'P0 (premise, re-measured in A)': 'A\'s [sdcall] reuse fin >= 0.8 per '
             'frame and reuse wait >= 8 ms/frame, and A\'s ph_Fin >= 10 ms/frame. '
             'FAILS if this scene no longer takes that path; then P1-P3 are not '
             'about this lever.',
         'F1 (the mover)': 'B\'s [sdcall] reuse fin = 0 and reuse_detach >= 0.8 '
             'per frame (the detach happens where the finish was).',
         'P1 (the claim)': 'B\'s ph_Fin <= 2.5 ms/frame and B\'s renderer cost '
             'F - Ri <= 26 ms on the play rows (the brief\'s bar).',
         'X1 (falsifier: the wait only moved)': 'FIRES if B\'s ph_Fin > 8 ms/'
             'frame, or B\'s [sdcall] waits summed over every caller (record, '
             'prerec, range, surfupd, tobuf, ext) >= 5 ms/frame, or B\'s rblk '
             '(render thread blocked) is within 3 ms/frame of A\'s. Then the wait '
             'moved to the flip or to frame-slot reuse; it is reported as moved, '
             'not counted as a win, and no second theory is stacked on it.',
         'P2 (fps)': 'B\'s 2-s fps rows: share >= 28.5 at least 0.5 (A 0.07). A '
             'title counts only after a plain 600-s held run clears 30 and passes '
             'the frame review; this leg does not count it.',
     })

pred('cs-soak', '4D530036-Counter_Strike.xiso.iso', 'async794-cs', 850,
     'Counter-Strike, live rounds (route fixed: A for the card, B for the weapon '
     'wheel). Premise (2876984, 3338415): two texture binds a frame find a dirty '
     'surface at the texture address that check_surface_to_texture_compatiblity '
     'refuses, and download it synchronously (txr dl 2/frame, txw sdl 13.7 ms/'
     'frame, ph_Fin 13.8). Neither fix in B removes that wait: fix 1 moves '
     'staged downloads, and this one is download_surface_to_buffer\'s own finish, '
     'whose bytes the texture upload reads at once; fix 2 frees the vCPU, which '
     'waits 0.3 ms/frame here. So the honest prediction is INERT on the render '
     'thread, and the arm is run for B\'s txdl[] reasons, which decide the GPU-'
     'side path for the seven titles of this class.',
     {
         'P0 (premise, re-measured in A)': 'A\'s txr dl >= 1.5 per flip and A\'s '
             'ph_Fin >= 10 ms/frame.',
         'P1 (inert)': 'B\'s ph_Fin within 2 ms/frame of A\'s, and B\'s fps rows '
             'median within 1.0 of A\'s.',
         'R1 (the reading)': 'B\'s txdl[] counts sum to within 5% of B\'s txr dl, '
             'and the [txdl794] lines name the refusing test and both shapes. '
             'FAILS (instrument void) if they do not add up.',
         'X1 (falsifier of inert)': 'B\'s ph_Fin falls by more than 4 ms/frame: '
             'then something in B reaches this path that the reading above says '
             'cannot, and it is found before anything is claimed.',
     })

pred('topspin-soak', '4D530035-Top_Spin.xiso.iso', 'async794-topspin', 990,
     'Top Spin, exhibition rally (route fixed: no START after step 24). Premise '
     '(2538884): ~26 texture-bind downloads a frame each wait for the GPU with '
     'pgraph.lock held; the vCPU waits 13.6 ms/frame for that lock on reads of '
     'PGRAPH 0xb10, rd_unl 0; share at 30 is 0.89. B releases the lock across '
     'those waits (#796), and 0xb10 is not one of the two reads held to the '
     'method end. Claim: the vCPU\'s lock wait falls to <= 3 ms/frame and its '
     'frame shortens. P(lock wait <= 3 ms) 0.7; P(share >= 0.90) 0.6.',
     {
         'P0 (premise, re-measured in A)': 'A\'s [lock474] rd_wait_ms >= 8 ms per '
             'frame with 0xb10 leading, and A\'s rd_unl = 0.',
         'F1 (the mover)': 'B\'s [lock474] rd_unl > 0 (reads served across a '
             'released wait).',
         'P1 (the claim)': 'B\'s [lock474] read wait <= 3 ms/frame, and B\'s v_blk '
             'falls by >= 8 ms/frame from A\'s.',
         'P2 (fps)': 'B\'s share of 2-s rows >= 28.5 is >= 0.90 and not below '
             'A\'s.',
         'X1 (falsifier)': 'FIRES if B\'s read wait stays above 8 ms/frame with '
             'rd_unl > 0 (the reads are served unlocked but the vCPU still waits: '
             'the wait is not the lock), or B\'s fps median falls by more than '
             '1.0. Reported as such; no second theory is stacked on it.',
     }, issue='796')

pred('mc3-soak', '54540079-Midnight_Club_3_DUB_Edition.xiso.iso',
     'midnight-club-3.returning', 820,
     'Midnight Club 3, Arcade street race. Premise (2878057): one staged-download '
     'completion a frame by a range reader ([sdcall] range=fin1.00, 6.9 ms/frame, '
     'dif oth1/flip): a texture, vertex or blit range that overlaps a dirty '
     'surface needs the bytes in VRAM now. B does not remove that: the reader '
     'consumes the bytes on the CPU at once. B may still shorten it where the '
     'completion used to also wait for an older submitted batch. Prediction: '
     'range fin unchanged; ph_Fin within 2 ms/frame of A; fps rows median within '
     '1.0. The arm is a regression check on a borderline title.',
     {
         'P0 (premise, re-measured in A)': 'A\'s [sdcall] range fin >= 0.8 per '
             'frame.',
         'P1 (inert)': 'B\'s range fin within 20% of A\'s, B\'s ph_Fin within 2 '
             'ms/frame of A\'s, B\'s fps median >= A\'s - 1.0.',
     })

pred('burnoutrev-soak', '45410076-Burnout_Revenge.xiso.iso',
     'burnout-revenge.returning', 800,
     'Burnout Revenge, Traffic Attack. Already benchmarked at 0.972 of rows at '
     '30 (targets.toml, 1790801593-titleroutes-1202186), so it cannot become a '
     'new Playable from this lane; it is in the brief\'s five, and it is run as '
     'the regression check on a title that already clears the bar.',
     {
         'P1 (not worse)': 'B\'s share of 2-s rows >= 28.5 >= A\'s - 0.03, and '
             'B\'s fps median >= A\'s - 1.0.',
     })
