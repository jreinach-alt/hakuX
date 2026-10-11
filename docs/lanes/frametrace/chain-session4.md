## 1-1791245535-lane.frametrace-680559

port check: 9085 of 9085 frames (100.00%) match the device cls under the old rule

### 1. Is the guest on the VBLANK grid?

VBLANK period (median vbp) 17.17 ms; periods within 1.5 ms of k x vbp: 2.0%
[vblphase] in the window: 11801 VBLANKs, 11801 deferred (100%), 11801 in unlock mode (100%)

### 2. Pacemaker with the period-late rule

| class | all (device, old rule) | all (period-late) | late (period-late) |
|---|---|---|---|
| vsync | 69.5% | 2.8% | 0.0% |
| run | 6.6% | 14.5% | 14.9% |
| unattr | 23.8% | 82.7% | 85.1% |

late: 8832 of 9085 (97.2%) against 30.5% under the old rule
P - D, ms: p5 2.42 p50 5.25 p95 7.71 p99 11.22; deadline D = 17.17 ms (ireq 1)

### 3. The vCPU chain, ms per frame (mean), against P = 22.37

| part | ms/frame | of P | corr with P |
|---|---|---|---|
| guest on-CPU (work + idle loop) | 15.73 | 70.3% | 0.73 |
| run queue | 0.04 | 0.2% | 0.09 |
| DMA_PUT pfifo.lock (lockw) | 6.34 | 28.3% | 0.59 |
| BQL | 0.37 | 1.6% | 0.28 |
| pgraph.lock | 0.00 | 0.0% | - |
| halt | 0.00 | 0.0% | - |
| other named waits | 0.00 | 0.0% | - |
| blocked, no named wait | 0.12 | 0.5% | 0.05 |
| sum | 22.59 | 101.0% |  |

| other side | ms/frame | corr with P | corr with lockw |
|---|---|---|---|
| PFIFO on-CPU | 5.69 | -0.01 | -0.31 |
| PFIFO idle (waiting for work) | 9.17 | 0.80 | 0.46 |
| PFIFO blocked, no hooked wait | 7.44 | 0.36 | 0.55 |
| GPU execution (main CBs, timestamps) | 5.11 | 0.23 | 0.35 |

## 1-1791225335-lane.frametrace-2925645

port check: 6980 of 6980 frames (100.00%) match the device cls under the old rule

### 1. Is the guest on the VBLANK grid?

VBLANK period (median vbp) 16.69 ms; periods within 1.5 ms of k x vbp: 50.0%
[vblphase] in the window: 15565 VBLANKs, 7969 deferred (51%), 0 in unlock mode (0%)

### 2. Pacemaker with the period-late rule

| class | all (device, old rule) | all (period-late) | late (period-late) |
|---|---|---|---|
| vsync | 53.9% | 33.1% | 0.0% |
| run | 44.2% | 62.5% | 93.4% |
| block | 0.2% | 0.2% | 0.2% |
| unattr | 1.8% | 4.2% | 6.3% |

late: 4669 of 6980 (66.9%) against 46.1% under the old rule
P - D, ms: p5 -1.47 p50 8.04 p95 17.98 p99 24.03; deadline D = 33.38 ms (ireq 2)

### 3. The vCPU chain, ms per frame (mean), against P = 37.20

| part | ms/frame | of P | corr with P |
|---|---|---|---|
| guest on-CPU (work + idle loop) | 35.33 | 95.0% | 0.76 |
| run queue | 0.04 | 0.1% | 0.09 |
| DMA_PUT pfifo.lock (lockw) | 0.03 | 0.1% | 0.13 |
| BQL | 1.75 | 4.7% | -0.00 |
| pgraph.lock | 0.00 | 0.0% | - |
| halt | 0.08 | 0.2% | -0.01 |
| other named waits | 0.00 | 0.0% | - |
| blocked, no named wait | 1.44 | 3.9% | 0.31 |
| sum | 38.67 | 104.0% |  |

| other side | ms/frame | corr with P | corr with lockw |
|---|---|---|---|
| PFIFO on-CPU | 16.21 | 0.80 | 0.04 |
| PFIFO idle (waiting for work) | 6.12 | -0.48 | 0.08 |
| PFIFO blocked, no hooked wait | 14.61 | 0.77 | 0.02 |
| GPU execution (main CBs, timestamps) | 17.53 | 0.75 | -0.03 |

## 1-1791216614-lane.frametrace-2373212

port check: 13017 of 13017 frames (100.00%) match the device cls under the old rule

### 1. Is the guest on the VBLANK grid?

VBLANK period (median vbp) 16.70 ms; periods within 1.5 ms of k x vbp: 8.3%
[vblphase] in the window: 20088 VBLANKs, 19993 deferred (100%), 19963 in unlock mode (99%)

### 2. Pacemaker with the period-late rule

| class | all (device, old rule) | all (period-late) | late (period-late) |
|---|---|---|---|
| vsync | 49.6% | 0.6% | 0.0% |
| run | 50.3% | 98.7% | 99.4% |
| block | 0.0% | 0.0% | 0.0% |
| unattr | 0.1% | 0.6% | 0.6% |

late: 12934 of 13017 (99.4%) against 50.4% under the old rule
P - D, ms: p5 3.02 p50 7.35 p95 20.05 p99 28.44; deadline D = 16.70 ms (ireq 1)

### 3. The vCPU chain, ms per frame (mean), against P = 25.74

| part | ms/frame | of P | corr with P |
|---|---|---|---|
| guest on-CPU (work + idle loop) | 24.85 | 96.5% | 0.99 |
| run queue | 0.04 | 0.1% | 0.01 |
| DMA_PUT pfifo.lock (lockw) | 0.28 | 1.1% | -0.15 |
| BQL | 0.78 | 3.0% | 0.03 |
| pgraph.lock | 0.00 | 0.0% | - |
| halt | 0.04 | 0.2% | 0.02 |
| other named waits | 0.00 | 0.0% | - |
| blocked, no named wait | 0.31 | 1.2% | -0.11 |
| sum | 26.30 | 102.2% |  |

| other side | ms/frame | corr with P | corr with lockw |
|---|---|---|---|
| PFIFO on-CPU | 13.72 | -0.30 | 0.27 |
| PFIFO idle (waiting for work) | 5.31 | 0.71 | -0.17 |
| PFIFO blocked, no hooked wait | 6.58 | -0.08 | -0.14 |
| GPU execution (main CBs, timestamps) | 7.43 | -0.08 | -0.14 |

## 1-1791216620-lane.frametrace-2374008

port check: 11642 of 11642 frames (100.00%) match the device cls under the old rule

### 1. Is the guest on the VBLANK grid?

VBLANK period (median vbp) 16.69 ms; periods within 1.5 ms of k x vbp: 56.3%
[vblphase] in the window: 15479 VBLANKs, 9353 deferred (60%), 13558 in unlock mode (88%)

### 2. Pacemaker with the period-late rule

| class | all (device, old rule) | all (period-late) | late (period-late) |
|---|---|---|---|
| vsync | 76.4% | 52.1% | 0.0% |
| run | 21.0% | 34.7% | 72.4% |
| block | 0.0% | 0.0% | 0.1% |
| unattr | 2.6% | 13.2% | 27.5% |

late: 5573 of 11642 (47.9%) against 23.6% under the old rule
P - D, ms: p5 -1.05 p50 0.61 p95 21.19 p99 40.64; deadline D = 16.69 ms (ireq 1)

### 3. The vCPU chain, ms per frame (mean), against P = 22.32

| part | ms/frame | of P | corr with P |
|---|---|---|---|
| guest on-CPU (work + idle loop) | 19.46 | 87.2% | 0.98 |
| run queue | 0.03 | 0.2% | 0.38 |
| DMA_PUT pfifo.lock (lockw) | 2.32 | 10.4% | 0.26 |
| BQL | 0.41 | 1.8% | 0.87 |
| pgraph.lock | 0.00 | 0.0% | - |
| halt | 0.00 | 0.0% | - |
| other named waits | 0.00 | 0.0% | - |
| blocked, no named wait | 0.31 | 1.4% | 0.56 |
| sum | 22.53 | 100.9% |  |

| other side | ms/frame | corr with P | corr with lockw |
|---|---|---|---|
| PFIFO on-CPU | 7.03 | 0.59 | 0.49 |
| PFIFO idle (waiting for work) | 12.95 | 0.87 | -0.08 |
| PFIFO blocked, no hooked wait | 2.54 | 0.31 | 0.96 |
| GPU execution (main CBs, timestamps) | 4.77 | 0.22 | 0.79 |

