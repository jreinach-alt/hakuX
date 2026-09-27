console I1 clock: counter / interrupt time over 2 s in 0.995..1.005: holds (1.000001)
console I7 ST_CB_1_Empty: 300 reps, 0 timeouts, 0 stale callback times, 1 callback(s) seen each: holds (reps 300, timeouts 0, stale 0)
console I8 ST_CB_3_DOA15: 300 reps, 0 timeouts, 0 stale callback times, 15 callback(s) seen each: holds (reps 300, timeouts 0, stale 0)
hakuX Thor I1 clock: counter / interrupt time over 2 s in 0.995..1.005: holds (1.000520)

| signal | console median / p95 (us) | hakuX Thor median / p95 (us) |
|---|---:|---:|
| callback: its kick -> DPC handled, empty frame, 1 callback | 13.6 / 13.9 (n=300) | 23.7 / 46.8 (n=300) |
| callback: DPC handled -> the semaphore after it visible (puller resumed), empty frame, 1 callback | 8.0 / 8.0 (n=300) | 6.8 / 19.9 (n=300) |
| frame: first draw -> semaphore visible, empty frame, 1 callback | 23.1 / 23.7 (n=300) | 31.1 / 61.0 (n=300) |
| callback: its kick -> DPC handled, 500 quads + RT switch, 1 callback | 14.5 / 14.8 (n=300) | 293.3 / 2037.0 (n=300) |
| callback: DPC handled -> the semaphore after it visible (puller resumed), 500 quads + RT switch, 1 callback | 8.0 / 8.3 (n=300) | 31.7 / 150.8 (n=300) |
| frame: first draw -> semaphore visible, 500 quads + RT switch, 1 callback | 6394.7 / 6405.6 (n=300) | 187152.6 / 216309.3 (n=300) |
| callback: its kick -> DPC handled, 500 quads + RT switch, 15 callbacks | 13.0 / 14.5 (n=4500) | 159.7 / 918.8 (n=4500) |
| callback: DPC handled -> the semaphore after it visible (puller resumed), 500 quads + RT switch, 15 callbacks | 8.0 / 8.0 (n=300) | 18.8 / 261.6 (n=300) |
| frame: first draw -> semaphore visible, 500 quads + RT switch, 15 callbacks | 6619.9 / 6630.5 (n=300) | 190346.5 / 216986.7 (n=300) |
| per extra callback: (15-callback frame - 1-callback frame) / 14, medians | 16.1 | 228.1 |
