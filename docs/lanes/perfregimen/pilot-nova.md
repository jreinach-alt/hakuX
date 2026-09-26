# Nova pilot: raw session records (2026-09-26, PDT)

Three held sessions on the Nova (ee317437), 15:43:29-16:13:31 PDT. The APK was 0.4.1-j1, installed by the dispatcher at 15:18:39, and the env pref was empty.
nova-session: idle probe plus three arms. The arms were killed 33-103 s in by other sessions' Stop hooks (stop-emulator.sh), because the arms used a scratch lease. VOID.
nova-session2: MAX(2/5) and REST arms, killed the same way. The /proc watcher caught the killer (watch.txt). VOID.
nova-session3: the real per-device lease. REST, MAX(2/5), REST. Arm 3 was TERMed at 16:13:15 to keep the hold under 30 min: rc 143, REST restored.

## nova-session

### judge.txt

```
idle GPU floor by performance_mode: {0: [401, 401, 401, 401], 1: [550], 2: [615]}
idle fan duty/state/rpm by fan_mode: {0: [(0, 0, 300)], 1: [(12000, 1, 4200)], 2: [(12000, 1, 4500)], 3: [(12000, 1, 4500)], 4: [(12000, 1, 4200), (12000, 1, 4500), (12000, 1, 4800), (12000, 1, 4800)], 5: [(25000, 1, 8100)]}

| arm | fps 135-245s | gfps lines | ran at | restored | gpu MHz med | GPU floor | fan duty | fan rpm | cpu7 kHz | gpuss-0 mC |
|---|---|---|---|---|---|---|---|---|---|---|
| arm1-rest | nan | 0 | 0/4 | True | 401 | 401 | 12294 | 4800 | 1843200 | 39000 |
| arm2-max | nan | 0 | 2/3 | True | nan | nan | nan | nan | nan | nan |
| arm3-rest | nan | 0 | 0/4 | True | 401 | 401 | 13379 | 5400 | 3187200 | 45700 |

M0    FAIL every arm has >= 15 gfps lines in the window, ran at its modes, restored REST
P1    PASS idle GPU floor at performance_mode 2 [615] > at 0 [401, 401, 401, 401]
P2    FAIL idle fan duty at fan_mode 3 [12000] >= every other mode {4: 12000, 0: 0, 1: 12000, 2: 12000, 5: 25000}
P3    FAIL under the title, MAX's GPU floor and fan duty exceed every REST arm's
P4    FAIL the REST arms agree: spread nan% <= 8%
P5    FAIL MAX fps nan >= 0.97 x REST nan (non-inferiority)
P6    FAIL GUESS: MAX fps nan >= 1.05 x REST nan (gain +nan%)
VERDICT: VOID (M0)
```

### session.out

```
[15:43:42 +1s] battery 77%
[15:43:42 +1s] device nova ee317437, REST=0/4 MAX=2/3, iso /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso
    versionName=0.4.1-j1
    lastUpdateTime=2026-09-26 15:18:39
/home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh: line 58: /home/justin/hakux-work/dispatch/.env_pref.nova: No such file or directory
env_pref: 
[15:43:42 +1s] == idle probe
[15:43:43 +2s]   baseline t=1790462625 set=1/4 gpu_min_mhz=550 gpu_min_pl=2 gpuclk=550000000 busy=10 c0=2016000 c3=2803200 c7=2476800 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=29200 batt_t=260
[15:43:43 +2s] set perf=0 fan=4 -> [0 4]
[15:43:52 +11s]   t=1790462634 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=902400 c3=1920000 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4200 gpuss0=30300 batt_t=260
[15:43:52 +11s] set perf=1 fan=4 -> [1 4]
[15:44:02 +21s]   t=1790462643 set=1/4 gpu_min_mhz=550 gpu_min_pl=2 gpuclk=550000000 busy=9 c0=2016000 c3=2054400 c7=2476800 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=30700 batt_t=260
[15:44:02 +21s] set perf=2 fan=4 -> [2 4]
[15:44:11 +30s]   t=1790462653 set=2/4 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=8 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=31100 batt_t=260
[15:44:11 +30s] set perf=0 fan=4 -> [0 4]
[15:44:20 +39s]   t=1790462662 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=1113600 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=30700 batt_t=260
[15:44:20 +39s] set perf=0 fan=0 -> [0 0]
[15:44:28 +47s]   t=1790462671 set=0/0 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=0 fan_state=0 fan_rpm=300 gpuss0=31900 batt_t=260
[15:44:30 +49s] set perf=0 fan=1 -> [0 1]
[15:44:39 +58s]   t=1790462681 set=0/1 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4200 gpuss0=31500 batt_t=260
[15:44:39 +58s] set perf=0 fan=2 -> [0 2]
[15:44:48 +67s]   t=1790462690 set=0/2 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=1228800 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=32700 batt_t=260
[15:44:48 +67s] set perf=0 fan=3 -> [0 3]
[15:44:57 +76s]   t=1790462699 set=0/3 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=1459200 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=32300 batt_t=260
[15:44:57 +76s] set perf=0 fan=5 -> [0 5]
[15:45:07 +86s]   t=1790462708 set=0/5 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=902400 c3=1651200 c7=1843200 fan_duty=25000 fan_state=1 fan_rpm=8100 gpuss0=32300 batt_t=260
[15:45:07 +86s] set perf=0 fan=4 -> [0 4]
[15:45:16 +95s]   t=1790462717 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=902400 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=32300 batt_t=260
[15:45:16 +95s] set perf=2 fan=3 -> [2 3]
[15:45:24 +103s]   t=1790462727 set=2/3 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=8 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=32300 batt_t=260
[15:45:25 +104s] set perf=0 fan=4 -> [0 4]
[15:45:34 +113s]   t=1790462736 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=32300 batt_t=260
[15:45:34 +113s] == arm 1 rest (battery 77%)
[15:46:41 +180s]    arm 1 rest rc=0 PERF: regimen=rest before=[0 4] running=[0 4] PERF: restored=[0 4] perf_restored=true 
[15:46:48 +187s] == arm 2 max (battery 77%)
[15:47:23 +222s]    arm 2 max rc=0 PERF: regimen=max before=[0 4] running=[2 3] PERF: restored=[0 4] perf_restored=true 
[15:47:28 +227s] == arm 3 rest (battery 77%)
[15:49:13 +332s]    arm 3 rest rc=0 PERF: regimen=rest before=[0 4] running=[0 4] PERF: restored=[0 4] perf_restored=true 
[15:49:18 +337s] session done, 337s, battery 77%
[15:49:18 +337s] REST restored: read back [0 4] (want [0 4])
```

### idle.log

```
[15:43:42 +1s] device nova ee317437, REST=0/4 MAX=2/3, iso /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso
    versionName=0.4.1-j1
    lastUpdateTime=2026-09-26 15:18:39
/home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh: line 58: /home/justin/hakux-work/dispatch/.env_pref.nova: No such file or directory
env_pref: 
[15:43:42 +1s] == idle probe
[15:43:43 +2s]   baseline t=1790462625 set=1/4 gpu_min_mhz=550 gpu_min_pl=2 gpuclk=550000000 busy=10 c0=2016000 c3=2803200 c7=2476800 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=29200 batt_t=260
[15:43:43 +2s] set perf=0 fan=4 -> [0 4]
[15:43:52 +11s]   t=1790462634 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=902400 c3=1920000 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4200 gpuss0=30300 batt_t=260
[15:43:52 +11s] set perf=1 fan=4 -> [1 4]
[15:44:02 +21s]   t=1790462643 set=1/4 gpu_min_mhz=550 gpu_min_pl=2 gpuclk=550000000 busy=9 c0=2016000 c3=2054400 c7=2476800 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=30700 batt_t=260
[15:44:02 +21s] set perf=2 fan=4 -> [2 4]
[15:44:11 +30s]   t=1790462653 set=2/4 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=8 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=31100 batt_t=260
[15:44:11 +30s] set perf=0 fan=4 -> [0 4]
[15:44:20 +39s]   t=1790462662 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=1113600 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=30700 batt_t=260
[15:44:20 +39s] set perf=0 fan=0 -> [0 0]
[15:44:28 +47s]   t=1790462671 set=0/0 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=0 fan_state=0 fan_rpm=300 gpuss0=31900 batt_t=260
[15:44:30 +49s] set perf=0 fan=1 -> [0 1]
[15:44:39 +58s]   t=1790462681 set=0/1 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4200 gpuss0=31500 batt_t=260
[15:44:39 +58s] set perf=0 fan=2 -> [0 2]
[15:44:48 +67s]   t=1790462690 set=0/2 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=1228800 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=32700 batt_t=260
[15:44:48 +67s] set perf=0 fan=3 -> [0 3]
[15:44:57 +76s]   t=1790462699 set=0/3 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=1459200 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=32300 batt_t=260
[15:44:57 +76s] set perf=0 fan=5 -> [0 5]
[15:45:07 +86s]   t=1790462708 set=0/5 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=902400 c3=1651200 c7=1843200 fan_duty=25000 fan_state=1 fan_rpm=8100 gpuss0=32300 batt_t=260
[15:45:07 +86s] set perf=0 fan=4 -> [0 4]
[15:45:16 +95s]   t=1790462717 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=902400 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=32300 batt_t=260
[15:45:16 +95s] set perf=2 fan=3 -> [2 3]
[15:45:24 +103s]   t=1790462727 set=2/3 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=8 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=32300 batt_t=260
[15:45:25 +104s] set perf=0 fan=4 -> [0 4]
[15:45:34 +113s]   t=1790462736 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=32300 batt_t=260
```

### arm1-rest

run.log:

```
PERF: regimen=rest before=[0 4] running=[0 4]
guest exited after 63s of 250s
adb_failures=0
held Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso for 63s
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "rest",
  "perf_mode": 0,
  "fan_mode": 4,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 3
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790462737 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=32300 batt_t=260
t=1790462748 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=37800 batt_t=260
t=1790462759 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1651200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=39400 batt_t=260
t=1790462770 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=40200 batt_t=260
t=1790462780 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=2188800 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=41000 batt_t=260
t=1790462791 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=2054400 c7=3187200 fan_duty=12154 fan_state=1 fan_rpm=4500 gpuss0=41400 batt_t=260
t=1790462802 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=4 c0=2016000 c3=1651200 c7=1843200 fan_duty=12294 fan_state=1 fan_rpm=4800 gpuss0=39000 batt_t=260
```

### arm2-max

run.log:

```
PERF: regimen=max before=[0 4] running=[2 3]
guest exited after 33s of 250s
adb_failures=0
held Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso for 33s
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "max",
  "perf_mode": 2,
  "fan_mode": 3,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 3
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790462810 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=0 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=35900 batt_t=260
t=1790462821 set=2/3 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=42200 batt_t=260
t=1790462832 set=2/3 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=43800 batt_t=260
t=1790462842 set=2/3 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=6 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=41000 batt_t=260
```

### arm3-rest

run.log:

```
PERF: regimen=rest before=[0 4] running=[0 4]
guest exited after 103s of 250s
adb_failures=0
held Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso for 103s
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "rest",
  "perf_mode": 0,
  "fan_mode": 4,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 3
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790462850 set=0/4 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=0 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=37100 batt_t=260
t=1790462861 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=2 c0=1900800 c3=1651200 c7=3187200 fan_duty=12714 fan_state=1 fan_rpm=5100 gpuss0=43400 batt_t=260
t=1790462872 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=13099 fan_state=1 fan_rpm=5100 gpuss0=44200 batt_t=260
t=1790462883 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1651200 c7=3187200 fan_duty=12714 fan_state=1 fan_rpm=5100 gpuss0=44200 batt_t=260
t=1790462894 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1785600 c3=1651200 c7=3187200 fan_duty=12959 fan_state=1 fan_rpm=5100 gpuss0=44600 batt_t=260
t=1790462905 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1785600 c3=1651200 c7=3187200 fan_duty=13099 fan_state=1 fan_rpm=5100 gpuss0=44900 batt_t=260
t=1790462916 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=13239 fan_state=1 fan_rpm=5400 gpuss0=44900 batt_t=260
t=1790462927 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=13379 fan_state=1 fan_rpm=5400 gpuss0=45700 batt_t=260
t=1790462938 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=2054400 c7=3187200 fan_duty=13379 fan_state=1 fan_rpm=5400 gpuss0=45700 batt_t=270
t=1790462948 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1785600 c7=3187200 fan_duty=13519 fan_state=1 fan_rpm=5400 gpuss0=45700 batt_t=270
```

## nova-session2

### session.out

```
[15:51:26 +0s] battery 77%
[15:51:26 +0s] device nova ee317437, REST=0/4 MAX=2/5, iso /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso
    versionName=0.4.1-j1
    lastUpdateTime=2026-09-26 15:18:39
/home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh: line 58: /home/justin/hakux-work/dispatch/.env_pref.nova: No such file or directory
env_pref: 
[15:51:27 +1s] == idle probe skipped
[15:51:27 +1s] == arm 1 max (battery 77%)
[15:52:33 +67s]    arm 1 max rc=0 PERF: regimen=max before=[0 4] running=[2 5] PERF: restored=[0 4] perf_restored=true 
[15:52:38 +72s] == arm 2 rest (battery 77%)
[15:53:13 +107s]    arm 2 rest rc=0 PERF: regimen=rest before=[0 4] running=[0 4] PERF: restored=[0 4] perf_restored=true 
[15:53:18 +112s] session done, 112s, battery 77%
[15:53:19 +113s] REST restored: read back [0 4] (want [0 4])
```

### watch.txt

```
    <- 843151:bash /home/justin/hakux-work/host-tools/hostops.sh
    <- 425:/usr/lib/systemd/systemd --user
    <- 843151:bash /home/justin/hakux-work/host-tools/hostops.sh
    <- 425:/usr/lib/systemd/systemd --user
15:52:38 1073987 timeout 120 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1073967:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1050206:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session2
    <- 425:/usr/lib/systemd/systemd --user
15:52:38 1073990 /init /usr/local/bin/adb adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1073987:timeout 120 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1073967:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1050206:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session2
    <- 425:/usr/lib/systemd/systemd --user
15:52:39 1074510 timeout 120 adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/storage/E6C6-D7AA/Games/XBox/Crimson Skies - 
    <- 1073967:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1050206:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session2
    <- 425:/usr/lib/systemd/systemd --user
15:52:39 1074512 /init /usr/local/bin/adb adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/storage/E6C6-D7AA/Games/XBox/Cri
    <- 1074510:timeout 120 adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/stora
    <- 1073967:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1050206:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session2
    <- 425:/usr/lib/systemd/systemd --user
15:53:07 1084726 /init /usr/local/bin/adb adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1084642:bash /home/justin/hakux-work/wt/cloud-audit1-419/docs/testing/stop-emulator.sh
    <- 1084640:/bin/sh -c $CLAUDE_PROJECT_DIR/docs/testing/stop-emulator.sh
    <- 1018928:claude -p # cloud: audit1 PR #419 -- lane.yuv10: #10 SET_CONTROL0 colour-space conversion as silicon measured it

This worktree is DETACHED at `origin/lane/yuv1
    <- 1018897:/usr/bin/bash -c claude -p "$(cat '/home/justin/hakux-work/briefs/cloud-audit1-419.md')" --model 'claude-opus-5-5' --max-turns 120 --output-format json --permis
    <- 425:/usr/lib/systemd/systemd --user
15:53:12 1085966 timeout 120 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1073967:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1050206:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session2
    <- 425:/usr/lib/systemd/systemd --user
15:53:18 1089392 timeout 30 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1050206:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session2
    <- 425:/usr/lib/systemd/systemd --user
15:53:18 1089393 /init /usr/local/bin/adb adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1089392:timeout 30 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1050206:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session2
    <- 425:/usr/lib/systemd/systemd --user
15:56:26 1148014 timeout -k 5 2 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1147795:bash /tmp/hakux-selftest.0OnGU5/dh/drive.sh /tmp/hakux-selftest.0OnGU5/dh/stub /tmp/hakux-selftest.0OnGU5/dh/f 1-lost
    <- 1147794:timeout -k 2 60 bash /tmp/hakux-selftest.0OnGU5/dh/drive.sh /tmp/hakux-selftest.0OnGU5/dh/stub /tmp/hakux-selftest.0OnGU5/dh/f 1-lost
    <- 882828:bash docs/testing/jobs/selftest.sh
    <- 882826:/bin/bash -c source /home/justin/.claude/shell-snapshots/snapshot-bash-1790462357411-py2ynp.sh 2>/dev/null || true && shopt -u extglob 2>/dev/null || true && { 
    <- 831462:claude -p # relprio432: 0.5 device runs queue ahead of everything but probes and heads

Lane: relprio432            Issue: #432 (item 2)
Base: origin/master (me
    <- 831454:/usr/bin/bash -c claude -p "$(cat '/home/justin/hakux-work/briefs/relprio432.md')" --model 'claude-opus-5-5' --max-turns 300 --output-format json --permission-m
    <- 425:/usr/lib/systemd/systemd --user
15:56:26 1148015 bash /tmp/hakux-selftest.0OnGU5/dh/fakebin/adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1148014:timeout -k 5 2 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1147795:bash /tmp/hakux-selftest.0OnGU5/dh/drive.sh /tmp/hakux-selftest.0OnGU5/dh/stub /tmp/hakux-selftest.0OnGU5/dh/f 1-lost
    <- 1147794:timeout -k 2 60 bash /tmp/hakux-selftest.0OnGU5/dh/drive.sh /tmp/hakux-selftest.0OnGU5/dh/stub /tmp/hakux-selftest.0OnGU5/dh/f 1-lost
    <- 882828:bash docs/testing/jobs/selftest.sh
    <- 882826:/bin/bash -c source /home/justin/.claude/shell-snapshots/snapshot-bash-1790462357411-py2ynp.sh 2>/dev/null || true && shopt -u extglob 2>/dev/null || true && { 
    <- 831462:claude -p # relprio432: 0.5 device runs queue ahead of everything but probes and heads

Lane: relprio432            Issue: #432 (item 2)
Base: origin/master (me
    <- 831454:/usr/bin/bash -c claude -p "$(cat '/home/justin/hakux-work/briefs/relprio432.md')" --model 'claude-opus-5-5' --max-turns 300 --output-format json --permission-m
    <- 425:/usr/lib/systemd/systemd --user
15:58:11 1188624 timeout 120 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1188619:bash /home/justin/hakux-work/dispatch/bin/soak_title.sh /storage/388C-68F7/ROMS/xbox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso 480
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
15:58:11 1188625 /init /usr/local/bin/adb adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1188624:timeout 120 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1188619:bash /home/justin/hakux-work/dispatch/bin/soak_title.sh /storage/388C-68F7/ROMS/xbox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso 480
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
15:59:45 1226565 timeout -k 5 2 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1226307:bash /tmp/hakux-selftest.Bey6nu/dh/drive.sh /home/justin/hakux-work/wt/claimrace/docs/testing /tmp/hakux-selftest.Bey6nu/dh/c2 1-hang
    <- 1226305:timeout -k 2 40 bash /tmp/hakux-selftest.Bey6nu/dh/drive.sh /home/justin/hakux-work/wt/claimrace/docs/testing /tmp/hakux-selftest.Bey6nu/dh/c2 1-hang
    <- 1091656:bash docs/testing/jobs/selftest.sh
    <- 1091641:/usr/bin/bash -c bash docs/testing/jobs/selftest.sh > selftest.out 2>&1; echo "EXIT=$?" > selftest.exit
    <- 425:/usr/lib/systemd/systemd --user
```

### arm1-max

run.log:

```
PERF: regimen=max before=[0 4] running=[2 5]
guest exited after 64s of 250s
adb_failures=0
held Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso for 64s
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "max",
  "perf_mode": 2,
  "fan_mode": 5,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 5
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790463089 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=10 c0=1900800 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=32300 batt_t=270
t=1790463100 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=8400 gpuss0=39400 batt_t=270
t=1790463111 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=8400 gpuss0=41000 batt_t=270
t=1790463122 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=8700 gpuss0=41800 batt_t=270
t=1790463133 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=42600 batt_t=270
t=1790463144 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=8700 gpuss0=43400 batt_t=270
t=1790463155 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=41400 batt_t=270
```

### arm2-rest

run.log:

```
PERF: regimen=rest before=[0 4] running=[0 4]
guest exited after 32s of 250s
adb_failures=0
held Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso for 32s
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "rest",
  "perf_mode": 0,
  "fan_mode": 4,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 5
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790463161 set=0/4 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=0 c0=2016000 c3=2803200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=5400 gpuss0=36700 batt_t=270
t=1790463172 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=12854 fan_state=1 fan_rpm=5400 gpuss0=43400 batt_t=270
t=1790463183 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=12854 fan_state=1 fan_rpm=5400 gpuss0=44600 batt_t=270
t=1790463194 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=5100 gpuss0=39000 batt_t=270
```

## nova-session3

### judge.txt

```
idle GPU floor by performance_mode: {0: [401, 401, 401, 401], 1: [550], 2: [615]}
idle fan duty/state/rpm by fan_mode: {0: [(0, 0, 300)], 1: [(12000, 1, 4200)], 2: [(12000, 1, 4500)], 3: [(12000, 1, 4500)], 4: [(12000, 1, 4200), (12000, 1, 4500), (12000, 1, 4800), (12000, 1, 4800)], 5: [(25000, 1, 8100)]}

| arm | fps 135-245s | gfps lines | ran at | restored | gpu MHz med | GPU floor | fan duty | fan rpm | cpu7 kHz | gpuss-0 mC |
|---|---|---|---|---|---|---|---|---|---|---|
| arm1-rest | 29.00 | 55 | 0/4 | True | 401 | 401 | 13729 | 5700 | 3187200 | 46700 |
| arm2-max | 29.00 | 55 | 2/5 | True | 615 | 615 | 25000 | 9000 | 3187200 | 48900 |
| arm3-rest | 29.00 | 33 | 0/4 | True | 401 | 401 | 15024 | 6300 | 3187200 | 50100 |

M0    PASS every arm has >= 15 gfps lines in the window, ran at its modes, restored REST
P1    PASS idle GPU floor at performance_mode 2 [615] > at 0 [401, 401, 401, 401]
P2    PASS idle fan duty at fan_mode 5 [25000] >= every other mode {4: 12000, 0: 0, 1: 12000, 2: 12000, 3: 12000}
P3    PASS under the title, MAX's GPU floor and fan duty exceed every REST arm's
P4    PASS the REST arms agree: spread 0.0% <= 8%
P5    PASS MAX fps 29.00 >= 0.97 x REST 29.00 (non-inferiority)
P6    FAIL GUESS: MAX fps 29.00 >= 1.05 x REST 29.00 (gain +0.0%)
VERDICT: FAIL P6
```

### session.out

```
[16:01:14 +0s] battery 77%
[16:01:14 +0s] device nova ee317437, REST=0/4 MAX=2/5, iso /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso
    versionName=0.4.1-j1
    lastUpdateTime=2026-09-26 15:18:39
/home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh: line 58: /home/justin/hakux-work/dispatch/.env_pref.nova: No such file or directory
env_pref: 
[16:01:15 +1s] == idle probe skipped
[16:01:15 +1s] == arm 1 rest (battery 77%)
[16:05:28 +254s]    arm 1 rest rc=0 PERF: regimen=rest before=[0 4] running=[0 4] PERF: restored=[0 4] perf_restored=true 
[16:05:34 +260s] == arm 2 max (battery 77%)
[16:09:47 +513s]    arm 2 max rc=0 PERF: regimen=max before=[0 4] running=[2 5] PERF: restored=[0 4] perf_restored=true 
[16:09:53 +519s] == arm 3 rest (battery 76%)
[16:13:17 +723s]    arm 3 rest rc=143 PERF: regimen=rest before=[0 4] running=[0 4] PERF: restored=[0 4] perf_restored=true 
[16:13:23 +729s] session done, 729s, battery 76%
[16:13:24 +730s] REST restored: read back [0 4] (want [0 4])
```

### watch.txt

```
    <- 843151:bash /home/justin/hakux-work/host-tools/hostops.sh
    <- 425:/usr/lib/systemd/systemd --user
    <- 843151:bash /home/justin/hakux-work/host-tools/hostops.sh
    <- 425:/usr/lib/systemd/systemd --user
    <- 1318943:bash /home/justin/hakux-work/host-tools/hostops.sh
    <- 425:/usr/lib/systemd/systemd --user
    <- 1318943:bash /home/justin/hakux-work/host-tools/hostops.sh
    <- 425:/usr/lib/systemd/systemd --user
16:05:34 1330645 timeout 120 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1330631:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
16:05:34 1330646 /init /usr/local/bin/adb adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1330645:timeout 120 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1330631:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
16:05:35 1330837 timeout 120 adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/storage/E6C6-D7AA/Games/XBox/Crimson Skies - 
    <- 1330631:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
16:05:35 1330839 /init /usr/local/bin/adb adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/storage/E6C6-D7AA/Games/XBox/Cri
    <- 1330837:timeout 120 adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/stora
    <- 1330631:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
16:06:13 1344505 timeout 120 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1188619:bash /home/justin/hakux-work/dispatch/bin/soak_title.sh /storage/388C-68F7/ROMS/xbox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso 480
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
16:06:13 1344506 /init /usr/local/bin/adb adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1344505:timeout 120 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1188619:bash /home/justin/hakux-work/dispatch/bin/soak_title.sh /storage/388C-68F7/ROMS/xbox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso 480
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
16:06:29 1348290 timeout -k 5 120 adb -s fake shell am force-stop com.jreinach.hakux.debug
    <- 1348263:bash /tmp/hakux-selftest.Bey6nu/vsh/rundisc/testing/run_disc.sh /tmp/hakux-selftest.Bey6nu/vsh/vsh.iso nxdk_vsh_tests /tmp/hakux-selftest.Bey6nu/vsh/rundisc/cap
    <- 1091656:bash docs/testing/jobs/selftest.sh
    <- 1091641:/usr/bin/bash -c bash docs/testing/jobs/selftest.sh > selftest.out 2>&1; echo "EXIT=$?" > selftest.exit
    <- 425:/usr/lib/systemd/systemd --user
16:06:29 1348292 bash /tmp/hakux-selftest.Bey6nu/vsh/rundisc/bin/adb -s fake shell am force-stop com.jreinach.hakux.debug
    <- 1348290:timeout -k 5 120 adb -s fake shell am force-stop com.jreinach.hakux.debug
    <- 1348263:bash /tmp/hakux-selftest.Bey6nu/vsh/rundisc/testing/run_disc.sh /tmp/hakux-selftest.Bey6nu/vsh/vsh.iso nxdk_vsh_tests /tmp/hakux-selftest.Bey6nu/vsh/rundisc/cap
    <- 1091656:bash docs/testing/jobs/selftest.sh
    <- 1091641:/usr/bin/bash -c bash docs/testing/jobs/selftest.sh > selftest.out 2>&1; echo "EXIT=$?" > selftest.exit
    <- 425:/usr/lib/systemd/systemd --user
16:07:00 1352675 timeout -k 5 120 adb -s fake shell am force-stop com.jreinach.hakux.debug
    <- 1352655:bash /tmp/hakux-selftest.Bey6nu/pullverify/mut/run_disc.sh /tmp/hakux-selftest.Bey6nu/pullverify/disc.iso nxdk_pgraph_tests /tmp/hakux-selftest.Bey6nu/pullverif
    <- 1352654:timeout 60 bash /tmp/hakux-selftest.Bey6nu/pullverify/mut/run_disc.sh /tmp/hakux-selftest.Bey6nu/pullverify/disc.iso nxdk_pgraph_tests /tmp/hakux-selftest.Bey6n
    <- 1352653:bash docs/testing/jobs/selftest.sh
    <- 1351520:bash docs/testing/jobs/selftest.sh
    <- 1091656:bash docs/testing/jobs/selftest.sh
    <- 1091641:/usr/bin/bash -c bash docs/testing/jobs/selftest.sh > selftest.out 2>&1; echo "EXIT=$?" > selftest.exit
    <- 425:/usr/lib/systemd/systemd --user
16:08:07 1370455 timeout -k 5 30 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
16:08:07 1370456 /init /usr/local/bin/adb adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1370455:timeout -k 5 30 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
16:08:07 1370522 timeout -k 5 30 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
16:08:07 1370523 /init /usr/local/bin/adb adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 1370522:timeout -k 5 30 adb -s bdc158a5 shell am force-stop com.jreinach.hakux.debug
    <- 135635:bash /home/justin/hakux-work/dispatch/bin/dispatcher.sh worker bdc158a5
    <- 135564:bash /home/justin/hakuX/docs/testing/dispatcher.sh serve
    <- 425:/usr/lib/systemd/systemd --user
16:09:47 1468972 timeout 120 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1330631:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
16:09:47 1468973 /init /usr/local/bin/adb adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1468972:timeout 120 adb -s ee317437 shell am force-stop com.jreinach.hakux.debug
    <- 1330631:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
16:09:54 1479987 timeout 120 adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/storage/E6C6-D7AA/Games/XBox/Crimson Skies - 
    <- 1478709:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
16:09:54 1479990 /init /usr/local/bin/adb adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/storage/E6C6-D7AA/Games/XBox/Cri
    <- 1479987:timeout 120 adb -s ee317437 shell am start -a android.intent.action.VIEW -n com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '/stora
    <- 1478709:bash /home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh /storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)
    <- 1250832:bash /home/justin/hakux-work/wt/perfregimen/docs/lanes/perfregimen/held_session.sh nova /home/justin/hakux-work/wt/perfregimen/.scratch/nova-session3
    <- 425:/usr/lib/systemd/systemd --user
```

### arm1-rest

run.log:

```
PERF: regimen=rest before=[0 4] running=[0 4]
/home/justin/hakux-work/wt/perfregimen/docs/testing/soak_title.sh: line 319: printf: write error: Broken pipe
adb_failures=0
held Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso for 250s
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "rest",
  "perf_mode": 0,
  "fan_mode": 4,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 5
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790463678 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=31500 batt_t=270
t=1790463688 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=37400 batt_t=270
t=1790463699 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1670400 c3=1651200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=39800 batt_t=270
t=1790463710 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1785600 c3=1651200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4500 gpuss0=40600 batt_t=270
t=1790463721 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1459200 c3=1651200 c7=3187200 fan_duty=12000 fan_state=1 fan_rpm=4800 gpuss0=41400 batt_t=270
t=1790463732 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=12154 fan_state=1 fan_rpm=4800 gpuss0=42600 batt_t=270
t=1790463742 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1785600 c3=1651200 c7=3187200 fan_duty=12434 fan_state=1 fan_rpm=4800 gpuss0=43400 batt_t=270
t=1790463753 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1651200 c7=3187200 fan_duty=12714 fan_state=1 fan_rpm=5100 gpuss0=44200 batt_t=270
t=1790463764 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=2188800 c7=3187200 fan_duty=12959 fan_state=1 fan_rpm=5100 gpuss0=44200 batt_t=270
t=1790463775 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1651200 c7=3187200 fan_duty=12854 fan_state=1 fan_rpm=5400 gpuss0=44900 batt_t=270
t=1790463786 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=13239 fan_state=1 fan_rpm=5100 gpuss0=44900 batt_t=270
t=1790463797 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=6 c0=2016000 c3=1651200 c7=3187200 fan_duty=13379 fan_state=1 fan_rpm=5400 gpuss0=45300 batt_t=270
t=1790463807 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=2016000 c3=1651200 c7=3187200 fan_duty=13379 fan_state=1 fan_rpm=5400 gpuss0=45700 batt_t=270
t=1790463818 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=2016000 c3=1651200 c7=3187200 fan_duty=13799 fan_state=1 fan_rpm=5700 gpuss0=46500 batt_t=280
t=1790463829 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=2016000 c3=1651200 c7=3187200 fan_duty=13659 fan_state=1 fan_rpm=5400 gpuss0=46900 batt_t=280
t=1790463840 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=1459200 c3=2803200 c7=3187200 fan_duty=13659 fan_state=1 fan_rpm=5700 gpuss0=47300 batt_t=280
t=1790463851 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=13799 fan_state=1 fan_rpm=5700 gpuss0=46500 batt_t=280
t=1790463862 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=13939 fan_state=1 fan_rpm=5700 gpuss0=46900 batt_t=280
t=1790463872 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=13939 fan_state=1 fan_rpm=5700 gpuss0=47300 batt_t=280
t=1790463883 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1651200 c7=3187200 fan_duty=14079 fan_state=1 fan_rpm=5700 gpuss0=47700 batt_t=280
t=1790463894 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1651200 c7=3187200 fan_duty=14219 fan_state=1 fan_rpm=5700 gpuss0=48100 batt_t=280
t=1790463905 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1900800 c3=1651200 c7=3187200 fan_duty=14359 fan_state=1 fan_rpm=6000 gpuss0=47700 batt_t=280
t=1790463915 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=14359 fan_state=1 fan_rpm=5700 gpuss0=47300 batt_t=280
t=1790463926 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=14219 fan_state=1 fan_rpm=6000 gpuss0=47700 batt_t=280
```

### arm2-max

run.log:

```
PERF: regimen=max before=[0 4] running=[2 5]
adb_failures=0
held Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso for 251s
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "max",
  "perf_mode": 2,
  "fan_mode": 5,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 5
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790463937 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=9 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=5100 gpuss0=42200 batt_t=280
t=1790463947 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=8700 gpuss0=46900 batt_t=280
t=1790463958 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48100 batt_t=290
t=1790463969 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=8700 gpuss0=48100 batt_t=290
t=1790463979 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48500 batt_t=290
t=1790463990 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48100 batt_t=290
t=1790464001 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48500 batt_t=290
t=1790464012 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48100 batt_t=290
t=1790464023 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48500 batt_t=300
t=1790464034 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9300 gpuss0=48900 batt_t=300
t=1790464045 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48500 batt_t=300
t=1790464055 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=5 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9300 gpuss0=48500 batt_t=300
t=1790464066 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=5 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48900 batt_t=300
t=1790464077 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=5 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=49300 batt_t=300
t=1790464088 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=5 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48900 batt_t=300
t=1790464099 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=5 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9300 gpuss0=49300 batt_t=300
t=1790464109 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9300 gpuss0=48900 batt_t=300
t=1790464120 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48500 batt_t=300
t=1790464131 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48900 batt_t=300
t=1790464142 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9300 gpuss0=48900 batt_t=300
t=1790464152 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=49300 batt_t=300
t=1790464163 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9300 gpuss0=49300 batt_t=300
t=1790464174 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48900 batt_t=300
t=1790464185 set=2/5 gpu_min_mhz=615 gpu_min_pl=1 gpuclk=615000000 busy=2 c0=2016000 c3=2803200 c7=3187200 fan_duty=25000 fan_state=1 fan_rpm=9000 gpuss0=48900 batt_t=300
```

### arm3-rest

run.log:

```
PERF: regimen=rest before=[0 4] running=[0 4]
PERF: restored=[0 4] perf_restored=true
```

perf_regimen.json:

```
{
  "regimen": "rest",
  "perf_mode": 0,
  "fan_mode": 4,
  "perf_restored": true,
  "before": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "restored": {
    "perf_mode": 0,
    "fan_mode": 4
  },
  "max": {
    "perf_mode": 2,
    "fan_mode": 5
  },
  "rest": {
    "perf_mode": 0,
    "fan_mode": 4
  }
}
```

samples.txt:

```
t=1790464195 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=12 c0=2016000 c3=1651200 c7=1843200 fan_duty=12000 fan_state=1 fan_rpm=5400 gpuss0=42600 batt_t=300
t=1790464206 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=2054400 c7=3187200 fan_duty=14359 fan_state=1 fan_rpm=6000 gpuss0=47300 batt_t=300
t=1790464217 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1228800 c3=1651200 c7=3187200 fan_duty=14639 fan_state=1 fan_rpm=6300 gpuss0=48500 batt_t=300
t=1790464228 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1670400 c3=1651200 c7=3187200 fan_duty=14639 fan_state=1 fan_rpm=6000 gpuss0=48900 batt_t=300
t=1790464239 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=14779 fan_state=1 fan_rpm=6000 gpuss0=49300 batt_t=300
t=1790464250 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=2592000 c7=3187200 fan_duty=14884 fan_state=1 fan_rpm=6000 gpuss0=49300 batt_t=300
t=1790464261 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=14779 fan_state=1 fan_rpm=6000 gpuss0=49300 batt_t=300
t=1790464271 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=14779 fan_state=1 fan_rpm=6300 gpuss0=49300 batt_t=310
t=1790464282 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=14884 fan_state=1 fan_rpm=6300 gpuss0=50100 batt_t=310
t=1790464294 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1017600 c3=1651200 c7=3187200 fan_duty=14884 fan_state=1 fan_rpm=6000 gpuss0=49300 batt_t=310
t=1790464304 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=1344000 c3=1920000 c7=3187200 fan_duty=15024 fan_state=1 fan_rpm=6000 gpuss0=49700 batt_t=310
t=1790464315 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=1017600 c3=2457600 c7=3187200 fan_duty=14779 fan_state=1 fan_rpm=6300 gpuss0=50500 batt_t=310
t=1790464326 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=1017600 c3=1651200 c7=3187200 fan_duty=15024 fan_state=1 fan_rpm=6000 gpuss0=50100 batt_t=310
t=1790464337 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=2016000 c3=1651200 c7=3187200 fan_duty=15304 fan_state=1 fan_rpm=6300 gpuss0=50500 batt_t=310
t=1790464348 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=2016000 c3=2188800 c7=3187200 fan_duty=15024 fan_state=1 fan_rpm=6300 gpuss0=50500 batt_t=310
t=1790464359 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=7 c0=2016000 c3=1651200 c7=3187200 fan_duty=15304 fan_state=1 fan_rpm=6300 gpuss0=50500 batt_t=310
t=1790464369 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=15304 fan_state=1 fan_rpm=6000 gpuss0=50100 batt_t=310
t=1790464381 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=15024 fan_state=1 fan_rpm=6300 gpuss0=50500 batt_t=310
t=1790464393 set=0/4 gpu_min_mhz=401 gpu_min_pl=4 gpuclk=401000000 busy=3 c0=2016000 c3=1651200 c7=3187200 fan_duty=15164 fan_state=1 fan_rpm=6300 gpuss0=50100 batt_t=310
```

