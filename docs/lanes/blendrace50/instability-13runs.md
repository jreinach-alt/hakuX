# instability-13runs

Output of `docs/testing/fulldisc_instability_50.py` over the same 13 runs.
The RACE / DEVICE-ONLY split and the instrument cross-check.

```
=== COMPOSITIONS ON DISK for apk b0cba34acef7, suite Blend_tests
(grouped by the capture SET scored, not by disc_id -- the narrowed
 discs carry the full disc's disc_id, see this file's header)
   1673 captures  13 run(s)  devices=['nova', 'thor']  disc_id=['iso:85b525/Blend tests']
      5 captures   5 run(s)  devices=['thor']  disc_id=['iso:85b525/Blend tests']
      1 captures  10 run(s)  devices=['thor']  disc_id=['iso:85b525/Blend tests']

=== THE FULL DISC: 1673 captures, 13 runs
  blendstack-A#1                     device=nova  serial=ee317437  scorer=(absent)
  blendstack-B#1                     device=thor  serial=bdc158a5  scorer=4a6a98dce4
  blendstack-thor2#1                 device=thor  serial=bdc158a5  scorer=027fa3d552
  blendrace50-thor#1                 device=thor  serial=bdc158a5  scorer=027fa3d552
  blendrace50-thor#2                 device=thor  serial=bdc158a5  scorer=027fa3d552
  blendrace50-thor#3                 device=thor  serial=bdc158a5  scorer=027fa3d552
  blendrace50-thor#4                 device=thor  serial=bdc158a5  scorer=027fa3d552
  blendrace50-thor#5                 device=thor  serial=bdc158a5  scorer=027fa3d552
  blendrace50-nova#1                 device=nova  serial=ee317437  scorer=027fa3d552
  blendrace50-nova#2                 device=nova  serial=ee317437  scorer=027fa3d552
  blendrace50-nova#3                 device=nova  serial=ee317437  scorer=027fa3d552
  blendrace50-nova#4                 device=nova  serial=ee317437  scorer=027fa3d552
  blendrace50-nova#5                 device=nova  serial=ee317437  scorer=027fa3d552
  runs per device: {'nova': 6, 'thor': 7}
  scorer_rev is NOT constant across these runs: ['(absent)', '027fa3d552', '4a6a98dce4']
  -> the split below is taken on the capture BYTES, which no
     scorer touches; the counts are printed alongside to check.

  moved at all: 22 of 1673   (race 22, device-only 0, stable 1651)
  INSTRUMENTS DISAGREE on 2 capture(s): ['1-cA_SADD_1-srcA', '1-srcRGB_SADD_1']
  (capture, count-says-moved, bytes-say-moved) -- trust the bytes
     1-cA_SADD_1-srcA         count=False bytes=True
     1-srcRGB_SADD_1          count=False bytes=True

=== RACE -- one device disagrees with ITSELF, same binary, same disc: 22
  1-cA_ADD_1-dstA         
      nova   counts [16384, 16384, 28672, 16384, 16384, 16384]  <-- disagrees with itself
             bytes  ['a5e95c7a', 'a5e95c7a', 'ddae61a5', 'a5e95c7a', 'a5e95c7a', 'a5e95c7a']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['a5e95c7a', 'a5e95c7a', 'a5e95c7a', 'a5e95c7a', 'a5e95c7a', 'a5e95c7a', 'a5e95c7a']
  1-cA_SADD_1-srcA        
      nova   counts [76032, 76032, 76032, 76032, 76032, 76032]  <-- disagrees with itself
             bytes  ['0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '130606ac']
      thor   counts [76032, 76032, 76032, 76032, 76032, 76032, 76032]
             bytes  ['0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f', '0cb5ec1f']
  1-cRGB_SADD_1-dstA      
      nova   counts [76032, 75008, 76032, 76032, 76032, 76032]  <-- disagrees with itself
             bytes  ['0990c11c', 'ac2cd4de', '0990c11c', '0990c11c', '0990c11c', '0990c11c']
      thor   counts [76032, 76032, 76032, 76032, 76032, 76032, 76032]
             bytes  ['0990c11c', '0990c11c', '0990c11c', '0990c11c', '0990c11c', '0990c11c', '0990c11c']
  1-dstA_SADD_1-srcRGB    
      nova   counts [76032, 98304, 76032, 76032, 76032, 76032]  <-- disagrees with itself
             bytes  ['119d4475', 'c44ace8e', '119d4475', '119d4475', '119d4475', '119d4475']
      thor   counts [76032, 76032, 76032, 76032, 76032, 76032, 76032]
             bytes  ['119d4475', '119d4475', '119d4475', '119d4475', '119d4475', '119d4475', '119d4475']
  1-dstA_SUB_1-cRGB       
      nova   counts [27136, 16384, 16384, 16384, 16384, 16384]  <-- disagrees with itself
             bytes  ['447c7a9f', '87d90e03', '87d90e03', '87d90e03', '87d90e03', '87d90e03']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['87d90e03', '87d90e03', '87d90e03', '87d90e03', '87d90e03', '87d90e03', '87d90e03']
  1-dstRGB_MAX_1-cA       
      nova   counts [16384, 16384, 24576, 16384, 16384, 16384]  <-- disagrees with itself
             bytes  ['09d355bc', '09d355bc', 'd6d7ce23', '09d355bc', '09d355bc', '09d355bc']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['09d355bc', '09d355bc', '09d355bc', '09d355bc', '09d355bc', '09d355bc', '09d355bc']
  1-dstRGB_MIN_1          
      nova   counts [23552, 8192, 8192, 8192, 8192, 8192]  <-- disagrees with itself
             bytes  ['299e8b1d', 'e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93']
      thor   counts [8192, 8192, 8192, 8192, 8192, 8192, 8192]
             bytes  ['e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93', 'e2dbda93']
  1-srcRGB_ADD_1-srcRGB   
      nova   counts [16384, 16384, 16384, 16384, 16384, 28672]  <-- disagrees with itself
             bytes  ['52c38c55', '52c38c55', '52c38c55', '52c38c55', '52c38c55', '0b0522f5']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['52c38c55', '52c38c55', '52c38c55', '52c38c55', '52c38c55', '52c38c55', '52c38c55']
  1-srcRGB_SADD_0         
      nova   counts [76032, 76032, 76032, 76032, 76032, 76032]
             bytes  ['869c6adc', '869c6adc', '869c6adc', '869c6adc', '869c6adc', '869c6adc']
      thor   counts [98304, 76032, 76032, 76032, 76032, 76032, 76032]  <-- disagrees with itself
             bytes  ['04c506d5', '869c6adc', '869c6adc', '869c6adc', '869c6adc', '869c6adc', '869c6adc']
  1-srcRGB_SADD_1         
      nova   counts [76032, 76032, 76032, 76032, 76032, 76032]  <-- disagrees with itself
             bytes  ['9b0d7060', '2eceb06d', '9b0d7060', '9b0d7060', '9b0d7060', '9b0d7060']
      thor   counts [76032, 76032, 76032, 76032, 76032, 76032, 76032]
             bytes  ['9b0d7060', '9b0d7060', '9b0d7060', '9b0d7060', '9b0d7060', '9b0d7060', '9b0d7060']
  1_ADD_1                 
      nova   counts [16384, 26624, 16384, 16384, 16384, 16384]  <-- disagrees with itself
             bytes  ['3dd60145', '3555c362', '3dd60145', '3dd60145', '3dd60145', '3dd60145']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['3dd60145', '3dd60145', '3dd60145', '3dd60145', '3dd60145', '3dd60145', '3dd60145']
  1_MIN_dstRGB            
      nova   counts [8192, 8192, 8192, 8192, 25600, 8192]  <-- disagrees with itself
             bytes  ['4f17d944', '4f17d944', '4f17d944', '4f17d944', '195abf99', '4f17d944']
      thor   counts [8192, 8192, 8192, 8192, 8192, 8192, 8192]
             bytes  ['4f17d944', '4f17d944', '4f17d944', '4f17d944', '4f17d944', '4f17d944', '4f17d944']
  1_REVSUB_cRGB           
      nova   counts [16384, 25392, 16384, 16384, 16384, 16384]  <-- disagrees with itself
             bytes  ['02116a26', 'a892fc2f', '02116a26', '02116a26', '02116a26', '02116a26']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['02116a26', '02116a26', '02116a26', '02116a26', '02116a26', '02116a26', '02116a26']
  cA_MIN_srcRGB           
      nova   counts [66375, 8192, 8192, 8192, 8192, 8192]  <-- disagrees with itself
             bytes  ['bc63822b', '1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3']
      thor   counts [8192, 8192, 8192, 8192, 8192, 8192, 8192]
             bytes  ['1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3', '1746bfd3']
  dstA_MIN_1-cRGB         
      nova   counts [8192, 8192, 42560, 8192, 8192, 8192]  <-- disagrees with itself
             bytes  ['1d037d5a', '1d037d5a', 'd4be450f', '1d037d5a', '1d037d5a', '1d037d5a']
      thor   counts [8192, 8192, 8192, 8192, 8192, 8192, 8192]
             bytes  ['1d037d5a', '1d037d5a', '1d037d5a', '1d037d5a', '1d037d5a', '1d037d5a', '1d037d5a']
  srcA_MAX_1-dstA         
      nova   counts [16384, 16384, 16384, 24576, 16384, 16384]  <-- disagrees with itself
             bytes  ['184fbaa8', '184fbaa8', '184fbaa8', 'f42244fe', '184fbaa8', '184fbaa8']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['184fbaa8', '184fbaa8', '184fbaa8', '184fbaa8', '184fbaa8', '184fbaa8', '184fbaa8']
  srcA_MAX_cA             
      nova   counts [16384, 47808, 16384, 16384, 16384, 16384]  <-- disagrees with itself
             bytes  ['f1b18518', '04356594', 'f1b18518', 'f1b18518', 'f1b18518', 'f1b18518']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['f1b18518', 'f1b18518', 'f1b18518', 'f1b18518', 'f1b18518', 'f1b18518', 'f1b18518']
  srcA_MAX_cRGB           
      nova   counts [16384, 16384, 16384, 16384, 16384, 47808]  <-- disagrees with itself
             bytes  ['0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7', '8f3ac9f6']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7', '0dd701e7']
  srcA_REVSUB_1-cA        
      nova   counts [23552, 16384, 16384, 16384, 16384, 16384]  <-- disagrees with itself
             bytes  ['b2e55040', 'c4947732', 'c4947732', 'c4947732', 'c4947732', 'c4947732']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['c4947732', 'c4947732', 'c4947732', 'c4947732', 'c4947732', 'c4947732', 'c4947732']
  srcAsat_SADD_0          
      nova   counts [76032, 76032, 76032, 76032, 98304, 76032]  <-- disagrees with itself
             bytes  ['de9bb5e2', 'de9bb5e2', 'de9bb5e2', 'de9bb5e2', '98a25823', 'de9bb5e2']
      thor   counts [76032, 76032, 76032, 76032, 76032, 76032, 76032]
             bytes  ['de9bb5e2', 'de9bb5e2', 'de9bb5e2', 'de9bb5e2', 'de9bb5e2', 'de9bb5e2', 'de9bb5e2']
  srcAsat_SUB_srcAsat     
      nova   counts [16384, 16384, 16384, 27632, 16384, 16384]  <-- disagrees with itself
             bytes  ['77b46b7e', '77b46b7e', '77b46b7e', '4796714c', '77b46b7e', '77b46b7e']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['77b46b7e', '77b46b7e', '77b46b7e', '77b46b7e', '77b46b7e', '77b46b7e', '77b46b7e']
  srcRGB_ADD_0            
      nova   counts [16384, 16384, 16384, 16384, 16384, 24576]  <-- disagrees with itself
             bytes  ['c2861a65', 'c2861a65', 'c2861a65', 'c2861a65', 'c2861a65', '12e83022']
      thor   counts [16384, 16384, 16384, 16384, 16384, 16384, 16384]
             bytes  ['c2861a65', 'c2861a65', 'c2861a65', 'c2861a65', 'c2861a65', 'c2861a65', 'c2861a65']

=== DEVICE ONLY -- each device internally constant, devices differ: 0

=== INSTRUMENT CROSS-CHECK (sha256 of the capture PNG)
  captures whose BYTES differ across the full-disc runs: 22
  captures whose COUNT differs across the full-disc runs: 22
  the two instruments name the same set -- the count hid nothing here

=== THE SAME CAPTURES ON NARROWED DISCS (a different composition --
    these values are NOT poolable with the full-disc ones above)
  -- 5-capture disc, 5 runs, devices=['thor']
     1-dstA_SUB_1-cRGB        thor   [12512, 12512, 12512, 12512, 12512]   <-- COMPOSITION: thor never reads any of [12512] on the full disc (reads [16384, 16384, 16384, 16384, 16384, 16384, 16384])
     1-dstRGB_MIN_1           thor   [8192, 8192, 8192, 8192, 8192]
     1-srcRGB_SADD_0          thor   [76032, 76032, 76032, 76032, 76032]   (within the full disc's [98304, 76032, 76032, 76032, 76032, 76032, 76032] for thor -- overlapping, so no composition effect shown)
     cA_MIN_srcRGB            thor   [8192, 8192, 8192, 8192, 8192]
     srcA_REVSUB_1-cA         thor   [16384, 16384, 16384, 16384, 16384]
  -- 1-capture disc, 10 runs, devices=['thor']
     1-srcRGB_SADD_0          thor   [76032, 76032, 76032, 76032, 76032, 76032, 76032, 76032, 76032, 76032]   (within the full disc's [98304, 76032, 76032, 76032, 76032, 76032, 76032] for thor -- overlapping, so no composition effect shown)
```
