console I1 clock: counter / interrupt time over 2 s in 0.995..1.005: holds (1.000001)
console I2 vblank rate 59.94 +/- 0.05 Hz: FAILS (59.9999 Hz)
console I3 spin: 0 timeouts, median 16683 +/- 20 us: holds (timeouts 0, median 16683.3 us)
console I4 tiny: 0 semaphore timeouts: holds (0)
console I5 flip: 0 PCRTC_START timeouts: holds (0)
hakuX Thor I1 clock: counter / interrupt time over 2 s in 0.995..1.005: holds (1.000018)

| signal | console median / p95 (us) | hakuX Thor median / p95 (us) | hakuX / console (median) |
|---|---:|---:|---:|
| vblank interval, ISR/DPC counter (spin) | 16683.3 / 16684.1 (n=300) | 16679.3 / 16896.9 (n=300) | 1.00 |
| vblank jitter |interval - median|, spin | 0.3 / 1.2 (n=300) | 54.7 / 263.3 (n=300) | 184.50 |
| last kick -> semaphore visible, 1 quad | 2.7 / 3.0 (n=300) | 275.3 / 1159.7 (n=300) | 103.22 |
| last kick -> NOTIFY write visible, 1 quad | 4.1 / 4.4 (n=300) | no data |  |
| submit (first draw -> kick), 1 quad | 16.0 / 16.3 (n=300) | 90.2 / 179.3 (n=300) | 5.64 |
| last kick -> semaphore visible, 500 quads + RT switch | 2.7 / 3.0 (n=300) | 13768.1 / 16861.3 (n=300) | 5163.06 |
| last kick -> NOTIFY write visible, 500 quads + RT switch | 4.1 / 4.4 (n=300) | no data |  |
| submit (first draw -> kick), 500 quads + RT switch | 6376.9 / 6388.7 (n=300) | 11034.1 / 51201.5 (n=300) | 1.73 |
| last kick -> semaphore visible, 500 quads + RT switch + CPU read | 2.7 / 3.0 (n=300) | 13789.8 / 17143.4 (n=300) | 5171.17 |
| last kick -> NOTIFY write visible, 500 quads + RT switch + CPU read | 4.1 / 4.4 (n=300) | no data |  |
| submit (first draw -> kick), 500 quads + RT switch + CPU read | 6378.7 / 6389.6 (n=300) | 11044.3 / 57612.1 (n=300) | 1.73 |
| CPU read of the back buffer, after the semaphore | 31073.5 / 31081.8 (n=300) | 23269.3 / 25222.5 (n=300) | 0.75 |
| flip: pb_finished -> NV_PCRTC_START written (vblank ISR) | 16179.6 / 16181.0 (n=300) | 24117.5 / 24549.6 (n=300) | 1.49 |
| flip: NV_PCRTC_START change seen -> next vblank counter tick | 16681.8 / 16682.7 (n=300) | 8252.0 / 8505.5 (n=300) | 0.49 |

v2 (the vblank event wake, `ST_VBlank_Event`; console 10:00 PDT, hakuX dry run on the **Nova**):

| signal | console median / p95 (us) | hakuX Nova median / p95 (us) |
|---|---:|---:|
| vblank interval, event wake (`pb_wait_for_vbl()`) | 16683.3 / 16683.6 (n=300) | 16683.3 / 16799.1 (n=300) |
| vblank jitter \|interval - median\|, event wake | 0.0 / 0.3 (n=300) | 6.1 / 141.6 (n=300) |
