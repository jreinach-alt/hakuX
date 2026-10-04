# Castlevania perflog A/B: abread.py output

```
# abread.py output, the A/B pair, both on ref a971c31220
# plain  = 1-1791070366-lanelocal-968308 (plain)
# second = 1-1791072308-lanelocal-1173788 (perflog)

== same +30..+180 s
                       plain n/med/mean     perflog n/med/mean   d(mean)
gfps               150   59.00   59.00     150   59.00   59.00     +0.00
Ri_ms              150    8.00    8.02     150    6.90    6.90     -1.12
tcpu_ms_per_s      149  248.35  248.16     149  325.67  321.67    +73.51
vcpu_run_pct        75   98.45   98.40      75   98.58   98.57     +0.18
guest_idle_pct      75    1.44    1.34      75    0.76    1.09     -0.25
pace_max_ms        150   19.70   21.90     150   18.40   19.22     -2.68

== steady (no compile within 3 s)
                       plain n/med/mean     perflog n/med/mean   d(mean)
gfps               652   59.00   59.01     634   59.00   58.99     -0.02
Ri_ms              652    8.10    8.12     634    6.70    6.52     -1.60
tcpu_ms_per_s      652  247.00  247.46     633  326.57  326.20    +78.74
vcpu_run_pct       326   98.20   98.20     318   98.58   98.58     +0.37
guest_idle_pct     323    1.43    1.39     314    0.77    6.31     +4.93
pace_max_ms        652   20.30   21.73     634   18.40   19.20     -2.53

== all gameplay
                       plain n/med/mean     perflog n/med/mean   d(mean)
gfps               682   59.00   59.01     676   59.00   58.90     -0.12
Ri_ms              682    8.10    8.08     676    6.70    6.45     -1.63
tcpu_ms_per_s      682  247.28  248.00     676  327.89  328.89    +80.89
vcpu_run_pct       341   98.20   98.19     340   98.58   98.46     +0.27
guest_idle_pct     339    1.42    1.40     337    0.77    7.15     +5.75
pace_max_ms        682   20.20   21.87     676   18.40   22.48     +0.60

== compile windows after the mark (offset s)
plain    [28]
perflog  [24, 186, 189, 190, 224]

== verdict
fps_ok_share                     1.0            0.9965
fps_window_median                59.94          59.94
g_fps_mean_reported_not_judged   59.87          59.86
gameplay_s                       674.6          670.2
pass                             True           False
failing                          None           hitches: a 1426 ms stall after the first 60 s (bar 500 ms)
power.net_w                      6.832          6.968
power.j_per_frame                0.1141         0.1167
power.flips                      40740          40380


# abread.py output, the noise control, plain against plain (refs 34e6e8dcba, a971c31220); the column headed perflog is the second PLAIN run
# plain  = 1-1791063303-lanelocal-3700348 (castlevania-960, plain)
# second = 1-1791070366-lanelocal-968308 (plain)

== same +30..+180 s
                       plain n/med/mean     perflog n/med/mean   d(mean)
gfps               150   59.00   58.93     150   59.00   59.00     +0.07
Ri_ms              150    7.75    7.84     150    8.00    8.02     +0.18
tcpu_ms_per_s      150  263.02  261.97     149  248.35  248.16    -13.81
vcpu_run_pct        75   98.28   98.21      75   98.45   98.40     +0.19
guest_idle_pct      74    1.46    1.75      75    1.44    1.34     -0.41
pace_max_ms        150   19.45   20.64     150   19.70   21.90     +1.27

== steady (no compile within 3 s)
                       plain n/med/mean     perflog n/med/mean   d(mean)
gfps               653   59.00   58.99     652   59.00   59.01     +0.03
Ri_ms              653    7.90    7.95     652    8.10    8.12     +0.17
tcpu_ms_per_s      653  259.54  259.75     652  247.00  247.46    -12.29
vcpu_run_pct       327   98.37   98.37     326   98.20   98.20     -0.16
guest_idle_pct     324    1.45    1.58     323    1.43    1.39     -0.20
pace_max_ms        653   19.20   20.35     652   20.30   21.73     +1.38

== all gameplay
                       plain n/med/mean     perflog n/med/mean   d(mean)
gfps               683   59.00   58.94     682   59.00   59.01     +0.07
Ri_ms              683    7.90    7.91     682    8.10    8.08     +0.17
tcpu_ms_per_s      683  259.74  260.45     682  247.28  248.00    -12.45
vcpu_run_pct       342   98.36   98.30     341   98.20   98.19     -0.12
guest_idle_pct     339    1.45    1.80     339    1.42    1.40     -0.40
pace_max_ms        683   19.20   20.51     682   20.20   21.87     +1.36

== compile windows after the mark (offset s)
plain    [26]
perflog  [28]

== verdict
fps_ok_share                     1.0            1.0
fps_window_median                59.94          59.94
g_fps_mean_reported_not_judged   59.93          59.87
gameplay_s                       677.0          674.6
pass                             True           True
failing                          None           None
power.net_w                      6.864          6.832
power.j_per_frame                0.1146         0.1141
power.flips                      40860          40740
```
