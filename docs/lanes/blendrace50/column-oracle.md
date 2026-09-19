# column-oracle

Output of `docs/testing/blend_race_column_oracle_50.py`: the modal capture
against the golden in each 64-wide stack column, over rows 112-367, for the
22 captures that race. 2026-09-19.

```
Modal (non-departing) capture vs golden, rows 112-367.
A 0 means the emulator is BIT-EXACT with hardware in that column.

  capture                   left diff right diff   reading
  1-cA_ADD_1-dstA                   0      16384   left is an ORACLE the race breaks
  1-cA_SADD_1-srcA              16384      16384   no oracle here
  1-cRGB_SADD_1-dstA            16384      16384   no oracle here
  1-dstA_SADD_1-srcRGB          16384      16384   no oracle here
  1-dstA_SUB_1-cRGB                 0      12512   left is an ORACLE the race breaks
  1-dstRGB_MAX_1-cA                 0      16384   left is an ORACLE the race breaks
  1-dstRGB_MIN_1                    0       8192   left is an ORACLE the race breaks
  1-srcRGB_ADD_1-srcRGB             0      16384   left is an ORACLE the race breaks
  1-srcRGB_SADD_0               16384      16384   no oracle here
  1-srcRGB_SADD_1               16384      16384   no oracle here
  1_ADD_1                           0      16384   left is an ORACLE the race breaks
  1_MIN_dstRGB                      0       8192   left is an ORACLE the race breaks
  1_REVSUB_cRGB                     0      11568   left is an ORACLE the race breaks
  cA_MIN_srcRGB                     0       8192   left is an ORACLE the race breaks
  dstA_MIN_1-cRGB                   0       8192   left is an ORACLE the race breaks
  srcA_MAX_1-dstA                   0      16384   left is an ORACLE the race breaks
  srcA_MAX_cA                       0      16384   left is an ORACLE the race breaks
  srcA_MAX_cRGB                     0      16384   left is an ORACLE the race breaks
  srcA_REVSUB_1-cA                  0      11568   left is an ORACLE the race breaks
  srcAsat_SADD_0                16384      16384   no oracle here
  srcAsat_SUB_srcAsat               0      12512   left is an ORACLE the race breaks
  srcRGB_ADD_0                      0      16384   left is an ORACLE the race breaks

  16 of 22 movers have a bit-exact left column in the modal run.
  On those, the race corrupts pixels the emulator otherwise gets
  exactly right -- which is what makes it separable from the
  structural defect, and is a free regression oracle for a fix.
```
