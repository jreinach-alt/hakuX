# Thor write proof, raw record (2026-09-26, held 17:00:14-17:02:30 PDT)

`BATT_MIN=30 ARMS=' ' SETTLE_S=8 bash held_session.sh thor <dir>`: idle probe only, no title.
The Thor had just finished a queued request (lane.tbchurn424), so it started hot (gpuss-0 73.6 C).

```
[17:00:27 +1s] battery 30%
[17:00:27 +1s] device thor bdc158a5, REST=0/4 MAX=2/5, iso /storage/388C-68F7/ROMS/xbox/4D530013-Blinx_The_Time_Sweeper.xiso.iso
    versionName=0.4.1-j1
    lastUpdateTime=2026-09-26 16:55:00
docs/lanes/perfregimen/held_session.sh: line 59: /home/justin/hakux-work/dispatch/.env_pref.thor: No such file or directory
env_pref: 
[17:00:27 +1s] == idle probe
[17:00:28 +2s]   baseline t=1790467228 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=25 c0=2016000 c3=2457600 c7=1843200 fan_duty=29000 fan_state=1 fan_rpm=0 gpuss0=73600 batt_t=410
[17:00:28 +2s] set perf=0 fan=4 -> [0 4]
[17:00:37 +11s]   t=1790467238 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=6 c0=2016000 c3=2707200 c7=1843200 fan_duty=29000 fan_state=1 fan_rpm=0 gpuss0=71600 batt_t=410
[17:00:38 +12s] set perf=1 fan=4 -> [1 4]
[17:00:47 +21s]   t=1790467247 set=1/4 gpu_min_mhz=550 gpu_min_pl=2 gpuclk=550000000 busy=0 c0=2016000 c3=2707200 c7=2476800 fan_duty=28500 fan_state=1 fan_rpm=0 gpuss0=71200 batt_t=410
[17:00:48 +22s] set perf=2 fan=4 -> [2 4]
[17:00:56 +30s]   t=1790467256 set=2/4 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=0 c0=2016000 c3=2803200 c7=3187200 fan_duty=28000 fan_state=1 fan_rpm=0 gpuss0=70400 batt_t=410
[17:00:56 +30s] set perf=0 fan=4 -> [0 4]
[17:01:05 +39s]   t=1790467266 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=2707200 c7=1843200 fan_duty=27500 fan_state=1 fan_rpm=0 gpuss0=70400 batt_t=410
[17:01:05 +39s] set perf=0 fan=0 -> [0 0]
[17:01:14 +48s]   t=1790467275 set=0/0 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=2707200 c7=1843200 fan_duty=0 fan_state=0 fan_rpm=0 gpuss0=69600 batt_t=410
[17:01:14 +48s] set perf=0 fan=1 -> [0 1]
[17:01:24 +58s]   t=1790467283 set=0/1 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=2707200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=0 gpuss0=68800 batt_t=410
[17:01:24 +58s] set perf=0 fan=2 -> [0 2]
[17:01:33 +67s]   t=1790467293 set=0/2 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=1459200 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=0 gpuss0=68400 batt_t=410
[17:01:33 +67s] set perf=0 fan=3 -> [0 3]
[17:01:41 +75s]   t=1790467302 set=0/3 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=2707200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=0 gpuss0=67700 batt_t=410
[17:01:42 +76s] set perf=0 fan=5 -> [0 5]
[17:01:51 +85s]   t=1790467311 set=0/5 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=2707200 c7=1843200 fan_duty=25000 fan_state=1 fan_rpm=0 gpuss0=66900 batt_t=410
[17:01:52 +86s] set perf=0 fan=4 -> [0 4]
[17:02:00 +94s]   t=1790467320 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=1651200 c7=1843200 fan_duty=25500 fan_state=1 fan_rpm=0 gpuss0=66900 batt_t=410
[17:02:00 +94s] set perf=2 fan=5 -> [2 5]
[17:02:09 +103s]   t=1790467329 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=0 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=0 gpuss0=66500 batt_t=410
[17:02:09 +103s] set perf=0 fan=4 -> [0 4]
[17:02:17 +111s]   t=1790467338 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=2707200 c7=1843200 fan_duty=25000 fan_state=1 fan_rpm=0 gpuss0=66100 batt_t=410
[17:02:17 +111s] session done, 111s, battery 30%
[17:02:18 +112s] REST restored: read back [0 4] (want [0 4])
```
