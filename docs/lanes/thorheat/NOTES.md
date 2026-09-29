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

xo-therm is the NTC thermistor the kalama reference design places at the 38.4
MHz XO crystal beside the PMK8550/PM8550 power-management complex, a
board-temperature sensor next to (not inside) the SoC. It moves with pm8550b
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

(sections 4-7 follow as measured)
