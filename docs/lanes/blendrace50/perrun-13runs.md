# perrun-13runs

Output of `docs/testing/blend_race_perrun_50.py` over the 13 full-disc runs
on apk b0cba34acef7 (6 nova, 7 thor), 2026-09-19. Committed verbatim: the
tables in NOTES.md are read off this.

```
=== 13 full-disc runs, apk b0cba34acef7
  nova  6 runs: ['blendstack-A#1', 'blendrace50-nova#1', 'blendrace50-nova#2', 'blendrace50-nova#3', 'blendrace50-nova#4', 'blendrace50-nova#5']
  thor  7 runs: ['blendstack-B#1', 'blendstack-thor2#1', 'blendrace50-thor#1', 'blendrace50-thor#2', 'blendrace50-thor#3', 'blendrace50-thor#4', 'blendrace50-thor#5']

=== DEPARTURES PER RUN  (a departure is a run whose capture bytes
    are not that device's modal bytes for that capture)
  blendstack-A#1         nova   4 departure(s)  1-dstA_SUB_1-cRGB, 1-dstRGB_MIN_1, cA_MIN_srcRGB, srcA_REVSUB_1-cA
  blendstack-B#1         thor   1 departure(s)  1-srcRGB_SADD_0
  blendstack-thor2#1     thor   0 departure(s)
  blendrace50-thor#1     thor   0 departure(s)
  blendrace50-thor#2     thor   0 departure(s)
  blendrace50-thor#3     thor   0 departure(s)
  blendrace50-thor#4     thor   0 departure(s)
  blendrace50-thor#5     thor   0 departure(s)
  blendrace50-nova#1     nova   6 departure(s)  1-cRGB_SADD_1-dstA, 1-dstA_SADD_1-srcRGB, 1-srcRGB_SADD_1, 1_ADD_1, 1_REVSUB_cRGB, srcA_MAX_cA
  blendrace50-nova#2     nova   3 departure(s)  1-cA_ADD_1-dstA, 1-dstRGB_MAX_1-cA, dstA_MIN_1-cRGB
  blendrace50-nova#3     nova   2 departure(s)  srcA_MAX_1-dstA, srcAsat_SUB_srcAsat
  blendrace50-nova#4     nova   2 departure(s)  1_MIN_dstRGB, srcAsat_SADD_0
  blendrace50-nova#5     nova   4 departure(s)  1-cA_SADD_1-srcA, 1-srcRGB_ADD_1-srcRGB, srcA_MAX_cRGB, srcRGB_ADD_0
  total departures: 22 over 13 runs, 22 distinct captures
  every moving capture had a clear modal value (no 50/50 splits),
  which is what makes 'the odd run' a well-defined thing to say

=== PER CAPTURE, every run's value  (no mean, no pooled rate)
  1-cA_ADD_1-dstA          nova  odd=blendrace50-nova#2
      bytes  ['a5e95c7a', 'a5e95c7a', 'ddae61a5', 'a5e95c7a', 'a5e95c7a', 'a5e95c7a']
      counts [16384, 16384, 28672, 16384, 16384, 16384]
  1-cA_SADD_1-srcA         nova  odd=blendrace50-nova#5
      bytes  ['0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '130606ac']
      counts [76032, 76032, 76032, 76032, 76032, 76032]
  1-cRGB_SADD_1-dstA       nova  odd=blendrace50-nova#1
      bytes  ['0990c11c', 'ac2cd4de', '0990c11c', '0990c11c', '0990c11c', '0990c11c']
      counts [76032, 75008, 76032, 76032, 76032, 76032]
  1-dstA_SADD_1-srcRGB     nova  odd=blendrace50-nova#1
      bytes  ['119d4475', 'c44ace8e', '119d4475', '119d4475', '119d4475', '119d4475']
      counts [76032, 98304, 76032, 76032, 76032, 76032]
  1-dstA_SUB_1-cRGB        nova  odd=blendstack-A#1
      bytes  ['447c7a9f', '87d90e03', '87d90e03', '87d90e03', '87d90e03', '87d90e03']
      counts [27136, 16384, 16384, 16384, 16384, 16384]
  1-dstRGB_MAX_1-cA        nova  odd=blendrace50-nova#2
      bytes  ['09d355bc', '09d355bc', 'd6d7ce23', '09d355bc', '09d355bc', '09d355bc']
      counts [16384, 16384, 24576, 16384, 16384, 16384]
  1-dstRGB_MIN_1           nova  odd=blendstack-A#1
      bytes  ['299e8b1d', 'e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93']
      counts [23552, 8192, 8192, 8192, 8192, 8192]
  1-srcRGB_ADD_1-srcRGB    nova  odd=blendrace50-nova#5
      bytes  ['52c38c55', '52c38c55', '52c38c55', '52c38c55', '52c38c55', '0b0522f5']
      counts [16384, 16384, 16384, 16384, 16384, 28672]
  1-srcRGB_SADD_0          thor  odd=blendstack-B#1
      bytes  ['04c506d5', '869c6adc', '869c6adc', '869c6adc', '869c6adc', '869c6adc', '869c6adc']
      counts [98304, 76032, 76032, 76032, 76032, 76032, 76032]
  1-srcRGB_SADD_1          nova  odd=blendrace50-nova#1
      bytes  ['9b0d7060', '2eceb06d', '9b0d7060', '9b0d7060', '9b0d7060', '9b0d7060']
      counts [76032, 76032, 76032, 76032, 76032, 76032]
  1_ADD_1                  nova  odd=blendrace50-nova#1
      bytes  ['3dd60145', '3555c362', '3dd60145', '3dd60145', '3dd60145', '3dd60145']
      counts [16384, 26624, 16384, 16384, 16384, 16384]
  1_MIN_dstRGB             nova  odd=blendrace50-nova#4
      bytes  ['4f17d944', '4f17d944', '4f17d944', '4f17d944', '195abf99', '4f17d944']
      counts [8192, 8192, 8192, 8192, 25600, 8192]
  1_REVSUB_cRGB            nova  odd=blendrace50-nova#1
      bytes  ['02116a26', 'a892fc2f', '02116a26', '02116a26', '02116a26', '02116a26']
      counts [16384, 25392, 16384, 16384, 16384, 16384]
  cA_MIN_srcRGB            nova  odd=blendstack-A#1
      bytes  ['bc63822b', '1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3']
      counts [66375, 8192, 8192, 8192, 8192, 8192]
  dstA_MIN_1-cRGB          nova  odd=blendrace50-nova#2
      bytes  ['1d037d5a', '1d037d5a', 'd4be450f', '1d037d5a', '1d037d5a', '1d037d5a']
      counts [8192, 8192, 42560, 8192, 8192, 8192]
  srcA_MAX_1-dstA          nova  odd=blendrace50-nova#3
      bytes  ['184fbaa8', '184fbaa8', '184fbaa8', 'f42244fe', '184fbaa8', '184fbaa8']
      counts [16384, 16384, 16384, 24576, 16384, 16384]
  srcA_MAX_cA              nova  odd=blendrace50-nova#1
      bytes  ['f1b18518', '04356594', 'f1b18518', 'f1b18518', 'f1b18518', 'f1b18518']
      counts [16384, 47808, 16384, 16384, 16384, 16384]
  srcA_MAX_cRGB            nova  odd=blendrace50-nova#5
      bytes  ['0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7', '8f3ac9f6']
      counts [16384, 16384, 16384, 16384, 16384, 47808]
  srcA_REVSUB_1-cA         nova  odd=blendstack-A#1
      bytes  ['b2e55040', 'c4947732', 'c4947732', 'c4947732', 'c4947732', 'c4947732']
      counts [23552, 16384, 16384, 16384, 16384, 16384]
  srcAsat_SADD_0           nova  odd=blendrace50-nova#4
      bytes  ['de9bb5e2', 'de9bb5e2', 'de9bb5e2', 'de9bb5e2', '98a25823', 'de9bb5e2']
      counts [76032, 76032, 76032, 76032, 98304, 76032]
  srcAsat_SUB_srcAsat      nova  odd=blendrace50-nova#3
      bytes  ['77b46b7e', '77b46b7e', '77b46b7e', '4796714c', '77b46b7e', '77b46b7e']
      counts [16384, 16384, 16384, 27632, 16384, 16384]
  srcRGB_ADD_0             nova  odd=blendrace50-nova#5
      bytes  ['c2861a65', 'c2861a65', 'c2861a65', 'c2861a65', 'c2861a65', '12e83022']
      counts [16384, 16384, 16384, 16384, 16384, 24576]

=== DIRECTION AND CONTENT OF EACH DEPARTURE
  'golden RGB' columns count, over the moved mask only, how many
  pixels each side matches hardware on -- so a departure that is
  a CORRECTION would show odd > mode.

  capture                  run      moved a-only   grey% odd==gold mode==gold    idx rows/cols moved  
  1-cA_ADD_1-dstA          0-nova#2   24576      0   83.3%         0     12288    208 r112-351 c16-623 
  1-cA_SADD_1-srcA         0-nova#5   24576      0  100.0%      3064         0    270 r112-303 c16-623 
  1-cRGB_SADD_1-dstA       0-nova#1   16384      0   50.0%      2048         0    373 r112-303 c16-623 
  1-dstA_SADD_1-srcRGB     0-nova#1   25772      0   86.4%         0     22272    481 r112-367 c24-623 
  1-dstA_SUB_1-cRGB        tack-A#1   21504   1024   90.5%         0     12688    507 r112-351 c16-623 
  1-dstRGB_MAX_1-cA        0-nova#2   16384      0   50.0%         0      8192    536 r112-303 c16-623 
  1-dstRGB_MIN_1           tack-A#1   21504   1024   90.5%      1024     15360    550 r112-351 c16-623 
  1-srcRGB_ADD_1-srcRGB    0-nova#5   24576      0  100.0%      1024     12288    736 r112-303 c16-623 
  1-srcRGB_SADD_0          tack-B#1   22880      0   97.3%         0     22272    789 r112-367 c24-615 
  1-srcRGB_SADD_1          0-nova#1    1470      0    0.0%         0         0    790 r112-123 c16-623 
  1_ADD_1                  0-nova#1   20480      0   80.0%         0     10240    835 r112-303 c16-623 
  1_MIN_dstRGB             0-nova#4   22536   2040   90.9%      1024     16392    875 r112-351 c16-623 
  1_REVSUB_cRGB            0-nova#1   20488   2040  100.0%      1728     11688    888 r112-303 c16-623 
  cA_MIN_srcRGB            tack-A#1   61502      0   74.9%         0     58183    983 r112-367 c24-623 
  dstA_MIN_1-cRGB          0-nova#2   39808      0   82.3%         0     34368   1182 r112-367 c16-623 
  srcA_MAX_1-dstA          0-nova#3   21504      0   71.0%         0      8192   1378 r112-367 c16-623 
  srcA_MAX_cA              0-nova#1   40576      0   54.9%         0     31424   1382 r112-367 c16-623 
  srcA_MAX_cRGB            0-nova#5   40576      0   54.9%         0     31424   1383 r112-367 c16-623 
  srcA_REVSUB_1-cA         tack-A#1   14336      0   71.4%      1728      8592   1406 r112-303 c16-623 
  srcAsat_SADD_0           0-nova#4   28498      0   78.2%         0     22272   1524 r112-367 c24-623 
  srcAsat_SUB_srcAsat      0-nova#3   22536   2040   90.9%         0     13224   1567 r112-351 c16-623 
  srcRGB_ADD_0             0-nova#5   16384      0  100.0%         0      8192   1569 r112-239 c16-623 

  DIRECTION: odd matches hardware on FEWER px than the mode on 19 event(s), MORE on 2, equal on 1.
  -> 'the odd run is always the wrong one', recorded on 5 events,
     does NOT hold at 22.  Read those rows before reusing it.
  CONTENT: grey share of the moved pixels ranges 0.0%-100.0%
    below 10%: 1 event(s); above 50%: 21 of 22

=== WHERE IN THE RUN, and do departures cluster?
  blendrace50-nova#1     indices [373, 481, 790, 835, 888, 1382]   gaps [108, 309, 45, 53, 494]
  blendrace50-nova#2     indices [208, 536, 1182]   gaps [328, 646]
  blendrace50-nova#3     indices [1378, 1567]   gaps [189]
  blendrace50-nova#4     indices [875, 1524]   gaps [649]
  blendrace50-nova#5     indices [270, 736, 1383, 1569]   gaps [466, 647, 186]
  blendstack-A#1         indices [507, 550, 983, 1406]   gaps [43, 433, 423]
  blendstack-B#1         indices [789]
  all 22 departures span index 208-1569 of 1673; spread over the disc
  moved-pixel row extent, every event: r112-367
  (#50's stack is 64x256; a band confined to those rows is the
   stack region and not a whole-framebuffer event)

=== SHAPE OF EACH CORRUPTED BAND
  capture                  run                       r0    r1   rows contig  w-max w-last
  1-cA_ADD_1-dstA          blendrace50-nova#2       112   351    192     NO    128    128
  1-cA_SADD_1-srcA         blendrace50-nova#5       112   303    192    yes    128    128
  1-cRGB_SADD_1-dstA       blendrace50-nova#1       112   303    128     NO    128    128
  1-dstA_SADD_1-srcRGB     blendrace50-nova#1       112   367    256    yes    320    256
  1-dstA_SUB_1-cRGB        blendstack-A#1           112   351    192     NO    128    128
  1-dstRGB_MAX_1-cA        blendrace50-nova#2       112   303    128     NO    128    128
  1-dstRGB_MIN_1           blendstack-A#1           112   351    192     NO    128    128
  1-srcRGB_ADD_1-srcRGB    blendrace50-nova#5       112   303    192    yes    128    128
  1-srcRGB_SADD_0          blendstack-B#1           112   367    256    yes    320    256
  1-srcRGB_SADD_1          blendrace50-nova#1       112   123     12    yes    128     62
  1_ADD_1                  blendrace50-nova#1       112   303    160     NO    128    128
  1_MIN_dstRGB             blendrace50-nova#4       112   351    192     NO    128    128
  1_REVSUB_cRGB            blendrace50-nova#1       112   303    192    yes    128    128
  cA_MIN_srcRGB            blendstack-A#1           112   367    256    yes    320    256
  dstA_MIN_1-cRGB          blendrace50-nova#2       112   367    256    yes    384    384
  srcA_MAX_1-dstA          blendrace50-nova#3       112   367    208     NO    128     64
  srcA_MAX_cA              blendrace50-nova#1       112   367    256    yes    320    256
  srcA_MAX_cRGB            blendrace50-nova#5       112   367    256    yes    320    256
  srcA_REVSUB_1-cA         blendstack-A#1           112   303    128     NO    128    128
  srcAsat_SADD_0           blendrace50-nova#4       112   367    256    yes    320    256
  srcAsat_SUB_srcAsat      blendrace50-nova#3       112   351    192     NO    128    128
  srcRGB_ADD_0             blendrace50-nova#5       112   239    128    yes    128    128
  first moved row, over all 22 events: [112]
  heights: [12, 128, 160, 192, 208, 256]
  all contiguous: False   any partial last row (w-last < w-max): ['1-dstA_SADD_1-srcRGB', '1-srcRGB_SADD_0', '1-srcRGB_SADD_1', 'cA_MIN_srcRGB', 'srcA_MAX_1-dstA', 'srcA_MAX_cA', 'srcA_MAX_cRGB', 'srcAsat_SADD_0']

  the runs themselves, (start,length) -- rows then columns:
    1-cA_ADD_1-dstA          rows [(112, 128), (256, 16), (288, 32), (336, 16)]
                             cols [(16, 64), (560, 64)]
    1-cA_SADD_1-srcA         rows [(112, 192)]
                             cols [(16, 64), (560, 64)]
    1-cRGB_SADD_1-dstA       rows [(112, 80), (208, 16), (256, 16), (288, 16)]
                             cols [(16, 64), (560, 64)]
    1-dstA_SADD_1-srcRGB     rows [(112, 256)]
                             cols [(24, 56), (192, 256), (568, 56)]
    1-dstA_SUB_1-cRGB        rows [(112, 128), (256, 16), (288, 32), (336, 16)]
                             cols [(16, 64), (560, 64)]
    1-dstRGB_MAX_1-cA        rows [(112, 80), (208, 16), (256, 16), (288, 16)]
                             cols [(16, 64), (560, 64)]
    1-dstRGB_MIN_1           rows [(112, 128), (256, 16), (288, 32), (336, 16)]
                             cols [(16, 64), (560, 64)]
    1-srcRGB_ADD_1-srcRGB    rows [(112, 192)]
                             cols [(16, 64), (560, 64)]
    1-srcRGB_SADD_0          rows [(112, 256)]
                             cols [(24, 16), (56, 16), (192, 256), (568, 16), (600, 16)]
    1-srcRGB_SADD_1          rows [(112, 12)]
                             cols [(16, 64), (560, 64)]
    1_ADD_1                  rows [(112, 128), (256, 16), (288, 16)]
                             cols [(16, 64), (560, 64)]
    1_MIN_dstRGB             rows [(112, 128), (256, 16), (288, 32), (336, 16)]
                             cols [(16, 64), (560, 64)]
    1_REVSUB_cRGB            rows [(112, 192)]
                             cols [(16, 64), (560, 64)]
    cA_MIN_srcRGB            rows [(112, 256)]
                             cols [(24, 24), (56, 24), (192, 256), (568, 24), (600, 24)]
    dstA_MIN_1-cRGB          rows [(112, 256)]
                             cols [(16, 64), (192, 256), (560, 64)]
    srcA_MAX_1-dstA          rows [(112, 80), (208, 16), (256, 112)]
                             cols [(16, 64), (560, 64)]
    srcA_MAX_cA              rows [(112, 256)]
                             cols [(16, 64), (192, 256), (560, 64)]
    srcA_MAX_cRGB            rows [(112, 256)]
                             cols [(16, 64), (192, 256), (560, 64)]
    srcA_REVSUB_1-cA         rows [(112, 80), (208, 16), (256, 16), (288, 16)]
                             cols [(16, 64), (560, 64)]
    srcAsat_SADD_0           rows [(112, 256)]
                             cols [(24, 56), (192, 256), (568, 56)]
    srcAsat_SUB_srcAsat      rows [(112, 128), (256, 16), (288, 32), (336, 16)]
                             cols [(16, 64), (560, 64)]
    srcRGB_ADD_0             rows [(112, 128)]
                             cols [(16, 64), (560, 64)]
  distinct row-run lengths:    [12, 16, 32, 80, 112, 128, 192, 256]
  distinct column-run lengths: [16, 24, 56, 64, 256]
  distinct column-run starts:  [16, 24, 56, 192, 560, 568, 600]

=== IS THE CORRUPT BLOCK A COPY OF THE OTHER BLOCK? (x=16 vs x=560)
  capture                  run                    odd L==R mode L==R
  1-cA_ADD_1-dstA          blendrace50-nova#2        31.2%     6.2%
  1-cA_SADD_1-srcA         blendrace50-nova#5        54.2%     6.2%
  1-cRGB_SADD_1-dstA       blendrace50-nova#1         6.2%     6.2%
  1-dstA_SUB_1-cRGB        blendstack-A#1            19.6%     6.2%
  1-dstRGB_MAX_1-cA        blendrace50-nova#2        22.9%     6.2%
  1-dstRGB_MIN_1           blendstack-A#1            19.6%     6.2%
  1-srcRGB_ADD_1-srcRGB    blendrace50-nova#5        37.5%     6.2%
  1-srcRGB_SADD_1          blendrace50-nova#1         6.2%     6.2%
  1_ADD_1                  blendrace50-nova#1        22.9%     6.2%
  1_MIN_dstRGB             blendrace50-nova#4        31.2%     6.2%
  1_REVSUB_cRGB            blendrace50-nova#1        37.5%     6.2%
  dstA_MIN_1-cRGB          blendrace50-nova#2         6.2%     6.2%
  srcA_MAX_1-dstA          blendrace50-nova#3         3.5%     6.2%
  srcA_MAX_cA              blendrace50-nova#1         6.2%     6.2%
  srcA_MAX_cRGB            blendrace50-nova#5         6.2%     6.2%
  srcA_REVSUB_1-cA         blendstack-A#1             6.2%     6.2%
  srcAsat_SUB_srcAsat      blendrace50-nova#3        31.2%     6.2%
  srcRGB_ADD_0             blendrace50-nova#5        53.1%     6.2%
  events where the odd run's two columns agree MORE than the
  mode's do: 11 -- a block copy would make this large.

=== THE CLOCK EXCURSION, tested against the departures
  blendstack-A#1         1-dstA_SUB_1-cRGB        dur=     646 ms   (run has 44/1673 negative, 2.63%)
  blendstack-A#1         1-dstRGB_MIN_1           dur=     644 ms   (run has 44/1673 negative, 2.63%)
  blendstack-A#1         cA_MIN_srcRGB            dur=     626 ms   (run has 44/1673 negative, 2.63%)
  blendstack-A#1         srcA_REVSUB_1-cA         dur=     616 ms   (run has 44/1673 negative, 2.63%)
  blendstack-B#1         1-srcRGB_SADD_0          dur=     524 ms   (run has 38/1673 negative, 2.27%)
  blendrace50-nova#1     1-cRGB_SADD_1-dstA       dur=     585 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#1     1-dstA_SADD_1-srcRGB     dur=     603 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#1     1-srcRGB_SADD_1          dur=     628 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#1     1_ADD_1                  dur=     569 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#1     1_REVSUB_cRGB            dur=     610 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#1     srcA_MAX_cA              dur=     604 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#2     1-cA_ADD_1-dstA          dur=     607 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#2     1-dstRGB_MAX_1-cA        dur=     587 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#2     dstA_MIN_1-cRGB          dur=     548 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#3     srcA_MAX_1-dstA          dur=     633 ms   (run has 43/1673 negative, 2.57%)
  blendrace50-nova#3     srcAsat_SUB_srcAsat      dur=     619 ms   (run has 43/1673 negative, 2.57%)
  blendrace50-nova#4     1_MIN_dstRGB             dur=     609 ms   (run has 43/1673 negative, 2.57%)
  blendrace50-nova#4     srcAsat_SADD_0           dur=     603 ms   (run has 43/1673 negative, 2.57%)
  blendrace50-nova#5     1-cA_SADD_1-srcA         dur=     615 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#5     1-srcRGB_ADD_1-srcRGB    dur=     648 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#5     srcA_MAX_cRGB            dur=     615 ms   (run has 42/1673 negative, 2.51%)
  blendrace50-nova#5     srcRGB_ADD_0             dur=     584 ms   (run has 42/1673 negative, 2.51%)
  coincidences: 0 of 22 departures; expected under independence 0.56
  -> the excursion does not select the departing tests. It is
     not the mechanism, and this is now a 22-event refutation
     rather than the 1-event one recorded before.
```
