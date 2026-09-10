# The Nova does not charge on the adb cable

Measured 2026-09-10, Retroid Pocket Nova (serial `ee317437`), plugged into the
Windows host that runs WSL2 and adb.

| `/sys/class/power_supply` | value | meaning |
|---|---|---|
| `usb/usb_type` | **`[SDP]`** | a PC data port, not a charger |
| `usb/input_current_limit` | 500 mA | the SDP ceiling |
| `usb/current_now`, `voltage_now` | 447 mA, 4.79 V | ~2.1 W in |
| `ucsi…/usb_type`, `current_max` | `[C] PD PD_PPS`, **0** | Type-C, no PD contract |
| `battery/current_now` | −261 mA (emulator running) | net discharge under load |
| `dumpsys battery` charge counter, 6 min, emulator off, screen asleep | **flat** | net zero at idle; it never charges |

So "stops trickle-charging when the emulator runs" is really: the link
supplies about 2 W, which covers idle and not much more. Across the day the
level went 100% → 86% with the emulator up most of the time.

Independently, the firmware's **80% charge limit is on**
(`settings get system percent_80_charge_limit` = 1; there is a
`charge_limit` quick-settings tile). On a real charger the device would hold
at 80%. That is a healthy setting for a bench device and this note does not
change it.

## What fixes it

Power from the Nova's own charger (or a PD hub with data passthrough) and run
adb over WiFi. The harness only needs adb: 5 MB ISO pushes and a ~1.5 GB
`hdd.img` pull per run, which WiFi handles in a minute or two. Once the
device is on WiFi and USB debugging has been enabled once over the cable:

    adb -s ee317437 tcpip 5555          # over the cable, once
    adb connect 192.168.4.127:5555
    SERIAL=192.168.4.127:5555 bash docs/testing/run_disc.sh ...

Every script takes `SERIAL`. `adb tcpip` restarts `adbd`, so do it between
runs, not during one.

## Why the emulator still has to be force-stopped

None of the above changes the standing rule. On this link the device drains
whenever the emulator is up, so a run left running after its captures are in
costs battery for nothing — and discs built without `--shutdown-on-completion`
reboot and rerun the suite forever (see `check_disc.py`'s warning).
