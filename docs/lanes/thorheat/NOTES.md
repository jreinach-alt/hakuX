# lane.thorheat -- why the AYN Thor overheats, and what counteracts it (#507)

Base: master @ 63f23d624f. Docs only. Direct Thor access (bdc158a5) under the
owner's 2026-09-29 grant, in held blocks of at most 60 min, with every setting
restored. The Nova (ee317437) was only read: getprop, zones and settings, one
`adb shell` each, while it ran its own request. It was never held.

## 1. Same SoC, same firmware policy, same trips

| | Thor bdc158a5 | Nova ee317437 | source |
|---|---|---|---|
| model | AYN Thor | Retroid Pocket Nova | `getprop ro.product.model` |
| SoC | QCS8550 (kalama, SD 8 Gen 2 IoT bin) | QCS8550 (kalama) | `ro.soc.model` |
| build | Thor_V1.0.0.377_20260206 | (RP build) | `ro.build.display.id` |
| CPU max | 2016 / 2803 / 3187 MHz | same | `cpuinfo_max_freq`, policy0/3/7 |
| GPU max | 680 MHz (9 levels) | same | `/sys/class/kgsl/kgsl-3d0` |
| thermal trips | 95 zones | **identical, all 95** | trip_point_* per zone (`.scratch/static.sh`) |
| xo-therm trip 2 | 78 C passive, hyst 8 -> thermal-pause-F8 + kgsl | same | as above, and thermal507 section "What trips the pause" |
| vendor thermal-engine confs | `thermal-engine.conf` empty; `thermal_config/*.conf` | **byte-identical** | `cat` + `diff` |
| thermal daemon | `android.hardware.thermal@2.0-service.qti-v2` only; **no thermal-engine process**, so the confs above are inert | | `ps -A` |
| battery | 5995 mAh full (design 5938), 4 cycles | 4627 mAh full (design 5191), 9 cycles | `power_supply/battery/charge_full*` |
| USB port | SDP, `input_current_limit` 500000 uA, 4.73 V | SDP, 500000 uA, 4.73 V | `power_supply/usb` |
| displays | 1080x1920 AMOLED @ 60 Hz, brightness 158 (0.62 = ~300 nits); Screen-2 1080x1240 @ 60 Hz, level 62 | one 960x1280 @ 120 Hz, brightness 11 (0.04 = ~23 nits) | `dumpsys display`, `settings get system` |
| fan (at read) | SMART (4), duty 27500-30000/50000, tach node reads 0 | SPORT (5) at read, 25000, tach 9300 rpm | `/sys/class/gpio5_pwm2` |

The kernel policy that pauses the Thor is the Nova's too. The 78 C trip is not
a Thor quirk. **The difference is physical: how hot xo-therm gets for a given
power.**

`charge_full` answers sustain507's open ask: the Thor's pack is 5995 mAh, about
23 Wh at 3.85 V nominal.

## 2. The heart of it: the Thor runs ~25 C hotter at ~25 % less power

Every Thor and Nova soak with a clean window after minute 10 (`.scratch/hist.py`
over `$DISPATCH_DIR/results/*/thermal.jsonl`; the last third of the clean late
window, before any pause). All at the defaults (perf 0, fan SMART), except
hostops-810152 (MAX).

| run | dev | net W | xo | pm8550b (charger PMIC) | usb-therm | battery | gpuss-0 | hottest big core |
|---|---|---|---|---|---|---|---|---|
| sustain507-589340 (Blinx) | Thor | 4.76 | 72.3 | 66.5 | 67.9 | 36.3 | 75.0 | 90.1 |
| sustain507-3238578 (Blinx) | Thor | 4.86 | 74.7 | 69.2 | 70.3 | 37.7 | 77.6 | 92.7 |
| sustain507-3238469 (Blinx) | Thor | 4.87 | 77.5 | 71.5 | 73.3 | 39.3 | 80.1 | 92.3 |
| verdict433-3467502 (Azurik) | Thor | 5.05 | 77.8 | 71.5 | 73.1 | 37.3 | 79.7 | 94.3 |
| slowtier2-black167924 (Black) | Thor | 5.10 | 76.8 | 70.4 | 72.0 | 36.0 | 79.1 | 94.6 |
| hostops-810152 (MA2, MAX) | Thor | 5.34 | 74.0 | 68.3 | 69.5 | 36.7 | 77.5 | 94.7 |
| sustain507-3238806 (AUF) | Nova | 6.06 | 46.7 | 40.5 | 41.9 | 34.5 | 51.8 | 70.8 |
| sustain507-3238659 (AUF) | Nova | 6.60 | 49.2 | 42.3 | 43.7 | 35.0 | 54.7 | 79.0 |

- **Every board sensor carries the same offset**: xo +25..28 C, the charger PMIC
  (pm8550b) +27 C, usb-therm +27 C, gpuss-0 +23 C. It is not one sensor placed
  next to a hot part. The whole board sits ~25 C higher.
- **Inside the board the gradient is the same on both**: gpuss-0 minus xo is
  ~3 C (Thor) and ~5 C (Nova), pm8550b is ~6 C under xo on both. The SoC-to-board
  coupling is alike. What differs is **board to room**.
- Room ambient is not recorded. Taking the cold-start battery zones (30-36 C)
  as an upper bound for ambient + self-heating, and 28 C for the room: the Thor
  is (74.7 - 28) / 4.86 = **~9.6 C/W** xo-to-room, the Nova (49.2 - 28) / 6.6 =
  **~3.2 C/W**. The Thor rejects heat about **3x worse per watt**. Net W includes
  the displays, whose heat mostly leaves through the glass and which draw more on
  the Thor (section 4), so the SoC-side resistance ratio is, if anything, larger.
- A same-moment read (09:0x PDT, both under load, same room): Thor xo 63.1, pmb
  57.8, usb 59.3, gpu 64.5; Nova xo 52.1, pmb 43.8, usb 44.6, gpu 58.0. The Nova's
  hottest core (95.1 C) was hotter than any Thor core (82.5 C), while its board
  was 11-14 C cooler.

### What xo-therm is

On Qualcomm reference designs, xo-therm is the NTC thermistor at the 38.4 MHz
XO crystal beside the PMK8550/PM8550 power-management complex. It is a
board-temperature sensor next to the SoC, not inside it. That placement is
inferred from the platform. No Thor schematic or teardown photo confirms it.
The data agree with a board sensor: it moves with pm8550b
and usb-therm (above), not with the cores, and lags the cores by minutes. It
is the platform's stand-in for **skin temperature**: the 78 C trip that pauses
cpu3-7 is a surface-heat limit. It is not a silicon limit. The cores' own trips are 108-110 C
(thermal507), and they read 90-95 C.

### Hardware, from public sources (section 7 has the sources)

- **One copper plate over both the SoC and the charging IC**, held by four
  screws, with a gap wide enough that the teardown guide recommends thermal
  putty over paste (handheldmodz, thermal-pad guide). Charging heat and SoC heat
  share one plate and one fan.
- **One small blower**, DC 5 V 1.6 W (part BT350505101-FPF001). No vapour
  chamber. The Thor is a clamshell: SoC, battery, fan and the 3.92" Screen-2
  are all in the lower half, which holds the controls. The main 6" screen is
  in the lid.
- Owners report the plate and pads as the weak point. A putty re-pad lowered PS2
  peaks from 61-72 C to 59-68 C, and the author says the heatpipe "doesn't become
  efficient until roughly ~50 C" (r/AynThor, anecdote with numbers).
- AYN's firmware .360 (2026-01-13) "made the smart fan speed more aggressive to
  address overheating issues in high-performance mode". This Thor runs .377
  (2026-02-06), so it already has that change.

## 3. Block 1 (held 09:03-09:50 PDT; device time 09:23-09:50): idle census, performance modes, fan at idle

Taken right after `verdict433-2378176` (Azurik) released the Thor hot (xo 70 C), with
both screens on the Daijishou launcher and the 500 mA port. The sampler is
`.scratch/sampler.sh`: one `adb shell` loop, one line every ~2.5 s with
xo/battery/pm8550b/usb-therm/gpuss-0/cpu-1-9/pa/ddr, battery and USB current and
voltage, fan duty, `thermal-pause-F8`, policy3/7 and GPU clocks. The segment table is
from `.scratch/seg.py` (the first 20 s of each segment dropped). Battery W is +
while discharging. Net = battery + USB, the device's draw.

### E1: what each user setting costs at idle

| segment (60 s each, in order) | battery W | USB W | net W | xo C/min |
|---|---|---|---|---|
| baseline (perf 0, SMART, main 158, Screen-2 62) | -0.20 | 2.13 | **1.93** | -3.1 |
| Screen-2 level 0 | -0.21 | 2.13 | 1.92 | -2.3 |
| baseline | -0.30 | 2.13 | 1.83 | -1.9 |
| main brightness 30 | -0.28 | 2.13 | 1.85 | -1.6 |
| baseline | -0.35 | 2.13 | 1.78 | -1.3 |
| bypass (`restrict_chg` 1, `restrict_cur` 0) | -0.10 | 2.04 | 1.93 | -1.1 |
| baseline | -0.34 | 2.14 | 1.79 | -1.1 |
| **both screens off** (KEYCODE_SLEEP) | +1.15 | 2.14 | **0.98** | -1.8 |
| baseline | -0.48 | 2.13 | 1.65 | -0.7 |

The standard error of each net mean is 0.06-0.11 W. The baseline drifts from 1.93 to
1.65 W as the board cools from 70 to 55 C. That drift is silicon leakage, and it is
itself a finding: **a hot Thor draws ~0.3 W more at idle than a warm one**.

- **Brightness does not matter.** Main 158 -> 30 and Screen-2 62 -> 0 each moved net
  W by less than the noise (< 0.1 W). The launcher is mostly dark pixels on AMOLED
  panels.
- **Lit screens cost ~0.7 W** (0.98 vs 1.65-1.79 W). That is panel drive, the
  composition of two displays and the launcher's own rendering, not brightness.
  `dual_screen_display_mode` 1 and 2 do not power display 4 off (`.scratch/s2probe.sh`:
  display 4 stays `ON`), and no setting found here turns Screen-2 off by itself.
- **Bypass at idle only stops charging.** With the pack at 74-76 %, the 500 mA port
  delivers 2.13 W, and at idle ~0.2-0.5 W of it charges the battery. Bypass makes the
  battery current ~0 and changes net draw by nothing.
- **Charging heat on this port is small.** The port supplies 2.13 W whatever the load.
  Under a title the battery supplies the other ~3 W (`pw` in every soak). The
  charger's conversion loss on 2.1 W is ~0.1-0.2 W. That matters only because
  the charging IC shares the SoC's cooling plate (section 2).

### E2: what performance_mode changes (read back after each write)

| performance_mode | policy3 / policy7 max | GPU `min_pwrlevel` (floor) | fan_mode the tile rewrites |
|---|---|---|---|
| 0 NORMAL | 2803 / 3187 MHz | 4 = **401 MHz** | 1 (Quiet) |
| 1 STANDARD | 2803 / 3187 | 2 = **550 MHz** | 4 |
| 2 HIGH | 2803 / 3187 | 1 = **615 MHz** | 4 |

**No mode caps or raises a CPU clock.** The modes differ only in the GPU's
**minimum** clock. The fan row is fanduty507's decode, and it held here: perf 0 left
`fan_mode` 1 until the driver restored 4. So "MAX" on the Thor means a GPU that
never drops below 615 MHz. The halt-on Azurik run at the defaults held the GPU at
401-401 MHz for its whole 1480 s (`THERMAL:` line of `verdict433-2378176`): it sat
on the floor and never needed more. This is why sustain507 found MAX and the
defaults alike in fps and watts: on CPU-bound emulation the GPU floor is most
of the difference, and 401 vs 615 MHz at low utilisation is a small share of
~5 W.

### E3: fan at idle, Customize 100 (perf 2) vs Off (perf 0), 210 s each

| segment | fan duty | net W | xo start -> end | xo C/min |
|---|---|---|---|---|
| Customize 100, r1 | 50000 | 1.73 | 54.5 -> 52.6 | -0.54 |
| Off, r1 | 0 | 1.54 | 52.4 -> 50.3 | -0.55 |
| Customize 100, r2 | 50000 | 1.70 | 50.2 -> 49.3 | -0.25 |
| Off, r2 | 0 | 1.54 | 49.2 -> 48.0 | -0.33 |

- The fan and perf 2 together cost +0.16-0.19 W: the motor plus the 615 MHz GPU floor.
- **At idle near 50 C, full fan did not cool the board faster than no fan.** Each Off
  segment cooled at least as fast as the full-fan segment before it, from a lower
  temperature. A fan pulling heat off the plate would have shown the opposite. At
  ~1.6 W the heat flux is small, and the owner-reported heatpipe threshold
  (~50 C) may apply, so this is a hint and not a verdict. Block 2 repeats it
  under load.
- The Thor's tach node (`speed`) reads 0, so the fan's rotation cannot be confirmed
  in software. Only an ear or a hand at the vent can confirm it.

### After block 1

Every setting read back equal to its before value (`settings-before.txt` /
`settings-after.txt`: perf 0, fan 4, fan_speed null, brightness 158, Screen-2 62,
dual mode 0, separation 0, restrict_chg 0, restrict_cur 1000000). The hold was
released at 09:50. The GPU floor read 4 again.

### The Azurik halt-on run, finished during this block (verdict433's, not this lane's)

`1-1790696366-lane.verdict433-2378176`: Azurik at the defaults, halt on, from xo 48.3 C.
**No pause in 1480 s**, net 4.35 W (battery 2.23 + USB 2.12). The halt-off arm
(`3467502`), at 5.05 W from 48.6 C, paused at +938 s. But this run was not at a
plateau. xo read 69.2 (+884 s), 72.6 (+1144), 74.8 (+1275) and 76.2 C (+1405),
still rising at ~0.7 C/min. A 30-min window would likely have tripped. Near
4.4 W net is the edge for 20 min at this room temperature, from a cold start.

## 4. Block 2 (held 10:17-10:49 PDT): the fan under a steady CPU load

Cool start: xo 49.5 C, battery 34 C, nothing had run for a while. Two
`sh -c "while :; do :; done"` loops (killed by PID on exit;
`busy loops left: 0`), screens on as in a soak, perf 0 / SMART. At 70 C the
fan alternated Customize 100 (perf 2) and Off (perf 0) every 4.5 min.
`.scratch/block2.sh`, `.scratch/b2/`.

| segment | net W | fan duty | xo start -> end | xo C/min | pm8550b | f7 MHz |
|---|---|---|---|---|---|---|
| idle, SMART | 1.68 | 13300 | 49.0 -> 48.6 | -0.37 | 45.4 | 1843 |
| load, SMART (rise, capped at 70 C) | 4.89 (5.87 in the first minute) | 32400 | **48.7 -> 70.0 in 8.7 min** | +2.49 | 59.5 | 3155 |
| load, Customize 100 | 4.32 | 50000 | 70.2 -> 71.9 | +0.39 | 65.7 | 3187 |
| load, **Off** | 4.10 | 0 | 72.0 -> 72.4 | +0.10 | 66.7 | 2833 |
| load, Customize 100 | 4.13 | 50000 | 72.4 -> 73.2 | +0.17 | 67.3 | 3187 |
| load, **Off** | 3.99 | 0 | 73.2 -> 73.3 | +0.01 | 67.7 | 2736 |
| load, SMART | 4.15 | 35200 | 73.3 -> 73.7 | +0.12 | 67.9 | 2725 |

- **A CPU-only load heats the board exactly as a title does.** 4.9 W took the board
  from 48.7 to 70 C in 8.7 min, the pace of GTA and Blinx (thermal507, sustain507).
  So the pause follows watts, not a title's CPU/GPU mix. The GPU stayed at its 401 MHz
  floor throughout.
- **Switching the fan between off and full made no visible step.** xo approached a
  plateau of ~73.5-74 C at ~4.1 W along one smooth curve. The Off segments rose
  no faster than the full-fan segments before them. They drew 0.1-0.3 W less
  (no motor, the 401 vs 615 MHz GPU floor, and a lower walt prime clock at perf
  0), which at ~9.6 C/W is worth 1-2 C at the plateau. A working blower moving
  heat off the plate would show several C per switch at ΔT ~45 C over the room:
  with a ~5 min board time constant, a 5 C plateau shift shows as ~1 C/min
  within a 4.5 min segment. **The fan's effect on xo-therm is bounded under ~2 C
  between off and 100 %.**
- That is the plateau the soaks show. ~4.1 W net gives ~74 C from a cold start,
  and ~4.9 W gives 75-78 C. The trip sits 4 C above the ~4.1 W plateau.

## 5. Block 3 (held 10:50-11:43 PDT; the Thor ran an arm until 11:34): what the fan draws

Screens off (KEYCODE_SLEEP) for a low, quiet baseline. Each fan pair was taken at one
performance_mode, so the GPU floor does not confound it. 60 s per segment, two reps.
`.scratch/block3.sh`, `.scratch/b3/`.

| segment | duty | net W r1 | net W r2 |
|---|---|---|---|
| perf 0, Off | 0 | 0.78 | 0.76 |
| perf 0, Sport | 25000 | 1.01 | 0.99 |
| perf 2, Sport | 25000 | 0.76 | 0.81 |
| perf 2, Customize 100 | 50000 | 0.81 | 0.80 |

- The perf-0 Sport excess is not the fan. Per sample it is a few 1.6-2.9 W spikes
  (background wakeups) on a 0.5-0.9 W floor, the same floor as Off. perf 2 Sport,
  at the same 25000 duty, reads the Off baseline.
- **Going from duty 0 to 25000 to 50000 moves the device's draw by under ~0.05 W.** The
  part is a DC 5 V 1.6 W blower (handheldmodz). At full speed a blower of that
  class draws a few hundred mW. Every milliwatt the device uses passes through
  the battery or USB meter read here.
- Together with block 2 (no thermal step between off and full under 4 W), **the
  fan's PWM duty changes neither the heat removed nor the power drawn.** Two worlds fit:
  - (a) the fan does not spin: stalled, unplugged, or an open motor supply;
  - (b) it runs at one fixed speed that ignores the duty (a 4-wire fan runs
    flat out when its PWM line floats).
  The Thor's `speed` (tach) reads 0 in every mode, so software cannot tell them
  apart. **Listening decides it:** at Customize 100 vs Off, silent in both is (a),
  loud in both is (b). A pitch change means this measurement is wrong. DROIX
  measured a working Thor at 47 dB (Smart) to 63 dB (max), so it is audible.

All settings were restored (`settings-after.txt`: perf 0, fan 4, fan_speed null,
awake). The hold was released at 11:43.

**Device time used today: ~88 min of the 3 h** (09:23-09:50, 10:17-10:49, 11:34-11:43).
Hold spans were 47, 32 and 53 min, the last mostly waiting on an arm already
running.

## 6. Root causes, with confidence

| # | cause | evidence | confidence |
|---|---|---|---|
| 1 | **The Thor's board rejects heat ~3x worse per watt than the Nova's.** At 4.8-5.3 W net its xo plateaus at 72-78 C; the Nova sits at 47-49 C on 6.1-6.6 W. Every board sensor shows the same ~25 C offset | section 2 (8 soaks, a same-moment read) | high |
| 2 | **The Thor's fan is not doing thermal work, on this unit.** Off vs full made no step under 4 W (bound < 2 C), and the duty moves the draw by < 0.05 W. Whether it is dead or stuck at one speed is open, and decides #1's remedy | sections 3-5 | medium-high that the PWM duty does nothing (two independent reads). **Open** whether any air moves: needs an ear |
| 3 | **The trip is a skin limit on a board sensor, the same on both devices.** xo-therm trip 2 at 78 C (hyst 8) pauses cpu3-7. The silicon is nowhere near its limit (cores 90-95 C against 108-110 C trips). The Thor reaches 78 C at a power the Nova never reaches its trip at | section 1, thermal507 | high |
| 4 | **Heat soak sets the margin.** The plateau at ~4.1-4.9 W is 72-75 C, 3-6 C under the trip. A start at 58-65 C (chassis and battery soaked) spends that margin in 5-8 min. A start at 43-48 C does not | sustain507 section 6/9; block 2 (48.7 -> 70 C in 8.7 min, then ~74 C) | high |
| 5 | **Hot silicon leaks.** The idle draw fell from 1.93 to 1.65 W as the board cooled from 70 to 55 C: +0.3 W at the top, which feeds the heat back | section 3, E1 | medium (confounded with the cool-down's own trend) |
| 6 | **Not causes** (measured small): screen brightness (< 0.1 W each screen); charging on the 500 mA port (0.1-0.2 W of conversion loss; the port gives 2.13 W at any load); performance_mode (it only moves the GPU **floor**, 401/550/615 MHz; no CPU cap); the vendor thermal-engine confs (no daemon runs them) | sections 1, 3 | high |
| 7 | Lit screens cost ~0.7 W (panel drive and two-display composition). Part of that heat stays in the lid (main screen), and part is Screen-2, over the board | section 3, E1 | medium on the split |

**Why the Nova does not pause:** the same trips and the same SoC, but its board sits
~25 C cooler per watt. Its fan measurably spins (tach 9300 rpm at 25000). Its
chassis is a slab with the SoC's heat spread over one body. The Thor puts the
SoC, battery, charger IC, fan and Screen-2 in the lower half of a clamshell, and
this unit's fan does no measurable work.

### Is 20 min of sustained play at the defaults achievable for moderate titles?

**Yes, from a cold start, at up to ~4.4-4.8 W net in this room. Not from a
58-65 C start.**
- Blinx at 4.76-4.86 W from 43.5 and 48.3 C: no pause in 30 min, plateau 72-75 C.
- Azurik halt on, 4.35 W from 48.3 C: no pause in 25 min, but still climbing (76.2 C).
- Azurik halt off, 5.05 W from 48.6 C: paused at +938 s.

The budget is about **2.5 W above the ~1.9 W screen-on idle floor**, so ~4.4 W
net holds 20 min, and ~4.1 W net plateaus at ~74 C with margin (block 2). Room
ambient is not recorded, and each 1 C of room is ~1 C of plateau.

## 7. Counter-measures, ranked by probability x size of win

| rank | counter-measure | level | p it works | win at full scale | evidence / what decides it |
|---|---|---|---|---|---|
| 1 | **Find out whether this Thor's fan spins; if it does not, repair it** (the owner listens at Customize 100 vs Off; a fan is a documented user-replaceable part, handheldmodz) | hardware (owner) | 0.5-0.6 that it is not spinning (two reads; the alternative is a fixed speed); if not, ~0.8 that a working fan lifts the budget by >= 1 W | **Largest.** The 3x gap is the whole problem; the Nova holds 6.6 W at 49 C. A dead fan also means the harness Thor is not a player's Thor | Not a fan-setting lever (the owner ruled those out): it asks whether the hardware works. One minute with an ear decides it |
| 2 | **Regimen: a sustained or confirmation run starts cold**: xo <= 50 C **and** battery zone <= 36 C at the first sample, with a cool gap after any heavy run. Record the room temperature. A player's Thor starts at room temperature, not heat-soaked | harness | 0.9 | Turns 20-30 min confirmations at <= ~4.5 W net from FAIL to PASS (Blinx 2/2, Azurik halt-on 1/1). From 58-65 C starts, 6/6 paused in 5-8 min | sustain507 sections 6 and 9; the coldslot tooling exists (hostops). Cost: ~20-30 min of cooling per sustained run |
| 3 | **Emulator watts: idle halt default-on (#566), then energymap507's ranked levers** (Forza leak #583; GPU shader execution #3; vCPU code quality #4) | emulator | 0.8 for the halt on titles with guest idle >= 0.15 | ~0.5-0.7 W on those titles: Azurik 5.05 -> 4.35 W moved a +938 s pause to none in 1480 s. That is the size of the margin a moderate title lacks. The later levers are each 1-2 W-scale only in sum | energymap507 section 3; verdict433's pair (section 3 above) |
| 4 | Settings to recommend on the Thor: performance_mode 0 (MAX only raises the GPU floor to 615 MHz: no sustained gain, sustain507); **do not play on a fast charger**, or use Charge Separation when you do (the charging IC shares the SoC's plate; owners report ~88 C charging on a 45 W Steam Deck charger). Brightness is not worth changing | player | 0.7 for the charger advice; ~0 for brightness | Charger: several W out of the plate for a player; nothing for the harness's 500 mA port (<= 0.2 W) | section 3; section 8 |
| 5 | Screen-2 dark in the regimen | harness | 0.3 | <= ~0.3-0.4 W (part of the 0.7 W for both screens). **No settings key turns display 4 off** (`dual_screen_display_mode` does not), and level 0 saves nothing measurable | section 3, E1. Needs the OEM key or tile that blanks the bottom screen, found by hand |
| 6 | Thermal re-pad of the plate (putty) | hardware | 0.5 | 2-4 C (owner-reported, anecdotal) | section 8. Hardware work: the owner's call; not attempted |
| - | Fan settings (Smart / Sport / Customize 100) | - | ~0 on this unit | measured: no effect (sections 3-4) | owner-ruled-out as a lever, and inert here |

## 8. What Thor owners report (public sources; WebSearch was unavailable, so fetched pages and Brave snippets)

- **Heat complaints are common; the pause is not reported.** r/AynThor threads: "Thor Max
  Overheating?", "Is it normal for it to get very hot?", "Thor Bottom Screen Temps"; owners
  quote low-80s C in games as typical (snippets):
  https://www.reddit.com/r/AynThor/comments/1srao35/thor_max_overheating/ ,
  https://www.reddit.com/r/AynThor/comments/1r60aku/thor_bottom_screen_temps/ ,
  https://www.reddit.com/r/SBCGaming/comments/1qdwx8x/ayn_thor_running_hot/ . No independent
  source describes cores going offline. The only such hits were hakuX's own #507/#557
  (excluded as circular).
- **Charging heat:** 88 C reported at 65 % while charging on a Steam Deck charger;
  replies advise a 15-20 W charger:
  https://www.reddit.com/r/OdinHandheld/comments/1onjq7y/attention_ayn_thor_gets_very_hot_while_charging/
- **Firmware:** v1.0.0.360 (2026-01-13) "made the smart fan speed more aggressive to address
  overheating issues in high-performance mode", and added custom Smart curves and charge limits;
  v1.0.0.293 (2025-11-20) enabled max fan in custom mode; .372/.377 carry no thermal change
  (community changelog: https://raw.githubusercontent.com/ChimeraGaming/AYN-OTA-Changelogs/main/Thor.md ;
  Notebookcheck headline, page refused:
  https://www.notebookcheck.net/AYN-Thor-gets-a-price-increase-alongside-a-software-update-to-help-with-overheating-and-battery-life.1203338.0.html ).
  This Thor runs .377.
- **Hardware:** 6000 mAh, 6" 120 Hz AMOLED + 3.92" AMOLED, fan and copper heat sink
  (https://www.ayntec.com/products/ayn-thor , https://droix.net/product/ayn-thor/ ). One fan, two
  screws; a cooling plate on four screws over the SoC **and the charging IC**, with a gap
  large enough that putty is recommended
  (https://handheldmodz.com/ayn-thor-replacing-the-thermal-pads/ ). Fan part BT350505101-FPF001,
  DC 5 V 1.6 W (https://handheldmodz.com/ayn-thor-fan-replacement/ ).
- **Measured by a reviewer (DROIX):** fan 47 dB Smart, 58 dB Sport, 63 dB max; peak surface ~45 C
  under the Y/B buttons; the second screen costs "a noticeable drop" in Geekbench 6
  (https://droix.net/blogs/ayn-thor-handheld-review/ ).
- **Community workarounds:** a putty re-pad took PS2 peaks from 61-72 to 59-68 C, and the author
  says the heatpipe "doesn't become efficient until roughly ~50 C"
  (https://www.reddit.com/r/AynThor/comments/1rq71qa/thermal_putty_mod_discovery_the_thor_cooling/ ).
  Owners underclock with ClusterTune, a no-root app that caps clocks through AYN's PServer
  (https://github.com/AurelioB/cluster-tune ; claims unmeasured). Owners also edit the Smart curve.
- **Not found:** sustained-power or stress-test measurements a source can stand behind (one site's
  98.1 % Wild Life Extreme claim contradicts known specs), Discord/AYN-forum content, and any
  report of emulator fps decaying over a session.

## 9. Settings before and after each block

| | before (all blocks) | after block 1 | after block 2 | after block 3 |
|---|---|---|---|---|
| performance_mode | 0 | 0 | 0 | 0 |
| fan_mode / fan_speed | 4 / null | 4 / null | 4 / null | 4 / null |
| screen_brightness | 158 | 158 | 158 | (untouched) |
| dual_screen_brightness_level | 62 | 62 | 62 | (untouched) |
| dual_screen_display_mode | 0 | 0 (probe restored) | 0 | (untouched) |
| is_charging_separation | 0 | 0 | 0 | (untouched) |
| restrict_chg / restrict_cur | 0 / 1000000 | 0 / 1000000 | 0 / 1000000 | (untouched) |
| screens | on | on | on | on (woken) |
| busy loops | - | - | 0 left | - |

Source: `.scratch/b{1,2,3}/settings-{before,after}.txt` (scratch, not committed; the values are
copied here).

## 10. For the next lane

- **Do not test fan settings on this Thor as a heat lever.** The duty moves neither heat nor
  watts. Ask first whether the fan spins.
- **Do not chase brightness or the 500 mA charging path.** Each is < 0.2 W.
- performance_mode does not cap the CPU. It sets the GPU floor. Read `min_pwrlevel`, not
  `scaling_max_freq`.
- A 2-loop `sh` busy load is a title-equivalent heater (4.9 W; 48.7 -> 70 C in 8.7 min). Use it
  for thermal A/Bs that need no title and no route.
- `dual_screen_display_mode` does not power off Screen-2. Find the OEM key or tile before
  planning a Screen-2-dark regimen.
- Not done here: a GPU-only load (no tool on the device), and bypass under load (on the 500 mA
  port, a 5 W load needs the battery, and restrict_cur 0 under load risks a brown-out).
