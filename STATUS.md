# hakuX harness

_updated 2026-10-13 23:50 PDT_

1. 0.6: Measured 203 / 300 · Playable 68 / 110; gate met on the newest soaks, no candidate yet.
2. Now: 18 lanes: 14 stranded, 2 waiting on audit, 2 no word in 48 h.
3. Needs a person: 34 items (20 owner decisions).
4. Machines: thor in use by lanelocal-offline; nova in use by lanelocal-ownerplay; no queue: the devices are not the constraint.

## 1. How close is 0.6?

Measured **203** / 300&nbsp;&nbsp;`▓▓▓▓▓▓▓░░░`

Playable **68** / 110&nbsp;&nbsp;`▓▓▓▓▓▓░░░░`

### How close is 0.6?

![Titles over time](chart.svg)

### How close is 1.0?

![Titles toward 1.0](chart2.svg)

| release | Measured target | projected date | Playable target | projected date |
|---|---|---|---|---|
| 0.6 | 300 | 2026-10-22 | 110 | 2026-10-23 |
| 0.7 | 425 | 2026-11-02 | 185 | 2026-11-08 |
| 0.8 | 575 | 2026-11-16 | 300 | 2026-12-03 |
| 0.9 | 725 | 2026-11-29 | 480 | 2027-01-12 |
| 1.0 | 876 | 2026-12-13 | 789 | 2027-03-20 |

Measured: any gameplay fps reading (the median frame rate in the play window) on either handheld, at any build and mode. Each title is plotted at its first reading (a soak's finish, a verdict, a held run, or the pass-1 review's date). Playable: the Playable ledger, each title at its acceptance (a 600 s held run with every kept frame reviewed). The 1.0 projection uses each series' rolling 7-day rate (titles gained in the last 7 days / 7), not the all-time rate.

Ships when both are met. At the last 48 h rate: about 2026-10-18.

Target: 0.6 ships when 300 titles are measured and 110 are Playable on the Thor/Nova handhelds (#433).

Decided: owner, 2026-10-13 ~18:00 PDT: track 0.6 next, on a curve toward 1.0 (300/110, then 425/185, 575/300, 725/480, and 876/789 at 1.0) ([#433 comment](https://github.com/jreinach-alt/hakuX/issues/433)). Read from `release-0.6.toml`.

Key -- fps cell: handheld, date, then its performance mode when recorded (max perf or default perf) and how the reading was made (hand-reviewed, screen: 90-240 s only, or soak).<br>Status: red blocked, green Playable, orange soak pending, yellow below 30, purple inputs ready, blue copied, grey not copied.

| Title and next step | Status | fps |
|---|---|---|
| **187: Ride or Die**<br>done | 🟢 Playable | **59.9**<br>97% at 28.5+<br>Nova · 10-11 · max perf |
| **25 to Life**<br>done | 🟢 Playable | **59.9**<br>97% at 28.5+<br>Nova · 10-13<br>Thor 35.7 |
| **Alien Hominid**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Thor · 10-01 · default perf |
| **AMF Bowling 2004**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-05 |
| **ATV: Quad Power Racing 2**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **Auto Modellista**<br>reach gameplay | 🟣 inputs ready | **59.9**<br>100% at 28.5+<br>Nova · 10-06 |
| **Baldur's Gate: Dark Alliance**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 09-30 · default perf |
| **Battlestar Galactica USA**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **Black Stone: Magic & Steel**<br>reach gameplay | 🟣 inputs ready | **59.9**<br>100% at 28.5+<br>Nova · 10-02 · max perf |
| **Bruce Lee: Quest of the Dragon**<br>**blocked: hang: 21.2 s without 60 guest flips after the mark** | 🔴 blocked | **59.9**<br>81% at 28.5+<br>Thor · 09-26 · max perf |
| **Capcom Classics Collection Vol. 2**<br>**blocked: crash: guest exited after 390s** | 🔴 blocked | **59.9**<br>100% at 28.5+<br>Thor · 09-30 · max perf |
| **Castlevania: Curse of Darkness**<br>done | 🟢 Playable | **59.9**<br>97% at 28.5+<br>Thor · 10-01 · max perf<br>Nova 59.9 |
| **Crazy Taxi 3 High Roller USA**<br>reach gameplay | 🔵 copied | **59.9**<br>77% at 28.5+<br>Nova · 10-13 |
| **Darkwatch**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **Future Tactics: The Uprising**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-07 |
| **Genma Onimusha**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **Guilty Gear XX #Reload: The Midnight Carnival**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-06 |
| **Gunvalkyrie**<br>done | 🟢 Playable | **59.9**<br>99% at 28.5+<br>Nova · 10-03 · default perf |
| **Kabuki Warriors**<br>done | 🟢 Playable | **59.9**<br>95% at 28.5+<br>Nova · 10-03 · default perf |
| **KOF: Maximum Impact - Maniax**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-12 · max perf |
| **Manhunt USA**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-08 |
| **Max Payne 2 The Fall of Max Payne USA**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-08 |
| **Max Payne 2: The Fall of Max Payne**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-11 · max perf, screen: 90-240 s only |
| **MLB SlugFest 2003**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-05 |
| **NFL Blitz 2002 USA**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-11 · max perf, screen: 90-240 s only |
| **Nickelodeon Avatar The Last Airbender USA**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-07 |
| **Nickelodeon SpongeBob SquarePants Battle for Bikini Bottom USA**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-07 |
| **Ninja Gaiden**<br>**blocked: reached_gameplay: unconfirmed (generic route) -- review the contact sheet, then rerun with --reviewed-gameplay yes\|no** | 🔴 blocked | **59.9**<br>64% at 28.5+<br>Thor · 09-30 · max perf, soak |
| **Pac-Man World 2**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **Petit Copter**<br>reach gameplay | 🔵 copied | **59.9**<br>78% at 28.5+<br>Thor · 10-01 · max perf, screen: 90-240 s only |
| **Phantom Crash**<br>reach gameplay | 🟣 inputs ready | **59.9**<br>100% at 28.5+<br>Nova · 10-04 · default perf |
| **Plus Plumb 2**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **RalliSport Challenge**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-04 |
| **Rayman 3: Hoodlum Havoc**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **Rent a Hero No 1 Japan**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-07 |
| **Scooby Doo Unmasked Europe**<br>reach gameplay | 🔵 copied | **59.9**<br>99% at 28.5+<br>Nova · 10-13 |
| **Sonic Heroes**<br>**blocked: crash: guest exited after 247s** | 🔴 blocked | **59.9**<br>100% at 28.5+<br>Thor · 10-01 · max perf |
| **Spikeout: Battle Street**<br>done<br>#303 open · nothing in flight | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-03 |
| **Strike Force Bowling**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-05 |
| **Tecmo Classic Arcade**<br>reach gameplay | 🟣 inputs ready | **59.9**<br>100% at 28.5+<br>Nova · 10-06 |
| **TimeSplitters 2**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-13 |
| **Whacked!**<br>**blocked: reached_gameplay: unconfirmed (generic route) -- review the contact sheet, then rerun with --reviewed-gameplay yes\|no** | 🔴 blocked | **59.9**<br>66% at 28.5+<br>Nova · 10-04 · default perf |
| **World Soccer Winning Eleven 9**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-06 |
| **WWE Raw 2**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-11 · max perf, soak |
| **XIII USA Europe En Fr De Es It**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-07 |
| **Deathrow**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Thor · 09-30 · max perf, screen: 90-240 s only |
| **Fantastic 4**<br>reach gameplay | 🔵 copied | **59.9**<br>43% at 28.5+<br>Nova · 10-07 |
| **Indigo Prophecy USA**<br>reach gameplay | 🔵 copied | **59.9**<br>99% at 28.5+<br>Nova · 10-07 |
| **LEGO Star Wars: The Video Game**<br>reach gameplay | 🟣 inputs ready | **59.9**<br>98% at 28.5+<br>Nova · 10-05 |
| **Lemony Snicket s A Series of Unfortunate Events USA**<br>reach gameplay | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-12 |
| **Medal of Honor Frontline USA**<br>reach gameplay | 🔵 copied | **59.9**<br>86% at 28.5+<br>Nova · 10-07 |
| **Tony Hawk's Pro Skater 3**<br>**blocked: crash: guest exited after 205s** | 🔴 blocked | **59.9**<br>100% at 28.5+<br>Thor · 10-01 · max perf, soak |
| **Tony Hawk's Pro Skater 2x**<br>done | 🟢 Playable | **59.8**<br>100% at 28.5+<br>Thor · 10-01 · max perf<br>Nova 59.8 |
| **Capcom vs. SNK 2 EO**<br>done | 🟢 Playable | **59.8**<br>100% at 28.5+<br>Nova · 10-07 |
| **Tony Hawk s Underground 2 USA Europe En Fr De**<br>reach gameplay | 🔵 copied | **59.7**<br>100% at 28.5+<br>Nova · 10-13 |
| **Mortal Kombat: Armageddon**<br>done | 🟢 Playable | **59.2**<br>100% at 28.5+<br>Nova · 10-06 |
| **MLB SlugFest: Loaded**<br>done | 🟢 Playable | **58.9**<br>100% at 28.5+<br>Nova · 10-05 |
| **Rogue Trooper**<br>done | 🟢 Playable | **58.9**<br>100% at 28.5+<br>Nova · 10-06 |
| **AMF Xtreme Bowling**<br>**blocked: crash: exiting due to SIG_DFL handler for signal 11, ucontext 0x6fcde81e20** | 🔴 blocked | **58.7**<br>100% at 28.5+<br>Nova · 10-05 |
| **Gui Yi Taiwan**<br>reach gameplay | 🔵 copied | **57.7**<br>94% at 28.5+<br>Nova · 10-07 |
| **Ghost Master The Gravenville Chronicles Europe En Fr De Es It**<br>reach gameplay | 🔵 copied | **57.6**<br>100% at 28.5+<br>Nova · 10-13 |
| **MTV Celebrity Deathmatch**<br>done | 🟢 Playable | **57.2**<br>99% at 28.5+<br>Nova · 10-04 |
| **NBA 2K2**<br>done | 🟢 Playable | **57.0**<br>100% at 28.5+<br>Nova · 10-05 |
| **Tony Hawk's Pro Skater 4**<br>done | 🟢 Playable | **56.6**<br>98% at 28.5+<br>Nova · 10-13 |
| **Batman: Dark Tomorrow**<br>reach gameplay | 🔵 copied | **56.5**<br>98% at 28.5+<br>Nova · 10-07 |
| **Project Gotham Racing 2**<br>**blocked: void: thermal-pause: thermal-pause-F8 1/1 began after +140 s and by +172 s (device 09-29 13:22:54); still paused at the last reading, relative to the mark** | 🔴 blocked | **55.7**<br>40% at 28.5+<br>Thor · 09-29 · max perf, screen: 90-240 s only |
| **Burnout Revenge**<br>done | 🟢 Playable | **54.8**<br>100% at 28.5+<br>Nova · 10-12 · max perf |
| **Tron 2.0 - Killer App (USA, Europe).iso**<br>reach gameplay | 🔵 copied | **54.8**<br>92% at 28.5+<br>Nova · 10-06 · default perf |
| **Panzer Dragoon Orta**<br>done | 🟢 Playable | **54.1**<br>100% at 28.5+<br>Nova · 10-03 |
| **Mercenaries USA Europe**<br>reach gameplay | 🔵 copied | **53.3**<br>100% at 28.5+<br>Nova · 10-12 |
| **4x4 Evo 2**<br>reach gameplay | 🔵 copied | **53.2**<br>100% at 28.5+<br>Nova · 10-13 |
| **Disney/Pixar Ratatouille**<br>done | 🟢 Playable | **52.8**<br>100% at 28.5+<br>Nova · 10-06 |
| **Dead or Alive 3**<br>soak for Playable | soak pending | **50.1**<br>100% at 28.5+<br>Nova · 10-12 · max perf<br>Thor 52.2 |
| **X Men The Official Game Europe**<br>reach gameplay | 🔵 copied | **49.3**<br>100% at 28.5+<br>Nova · 10-12 |
| **Super Monkey Ball Deluxe**<br>**blocked: crash: guest exited after 250s** | 🔴 blocked | **48.1**<br>100% at 28.5+<br>Thor · 10-01 · max perf |
| **Ty the Tasmanian Tiger Night of the Quinkan USA Australia**<br>reach gameplay | 🔵 copied | **47.8**<br>79% at 28.5+<br>Nova · 10-07 |
| **Legacy of Kain Defiance USA**<br>reach gameplay | 🔵 copied | **47.6**<br>97% at 28.5+<br>Nova · 10-07 |
| **Crash Bandicoot: The Wrath of Cortex**<br>reach gameplay | 🟣 inputs ready | **46.9**<br>100% at 28.5+<br>Nova · 10-07 |
| **Dark Summit**<br>done | 🟢 Playable | **45.9**<br>93% at 28.5+<br>Nova · 10-04 |
| **Mortal Kombat: Shaolin Monks**<br>reach gameplay | 🟣 inputs ready | **45.9**<br>49% at 28.5+<br>Nova · 10-06 |
| **NFL Blitz 2002**<br>done | 🟢 Playable | **45.0**<br>100% at 28.5+<br>Nova · 10-05 |
| **MLB SlugFest 2004**<br>done | 🟢 Playable | **44.4**<br>100% at 28.5+<br>Nova · 10-05 |
| **Tenchu 3 Kaiki no Shou Japan**<br>reach gameplay | 🔵 copied | **44.3**<br>100% at 28.5+<br>Nova · 10-12 |
| **Arx Fatalis**<br>reach gameplay | 🔵 copied | **43.9**<br>100% at 28.5+<br>Nova · 10-07 |
| **Fight Club**<br>done | 🟢 Playable | **43.4**<br>94% at 28.5+<br>Nova · 10-06 |
| **NBA 2K3**<br>done | 🟢 Playable | **42.9**<br>96% at 28.5+<br>Nova · 10-06 |
| **ToeJam & Earl III: Mission to Earth**<br>done | 🟢 Playable | **42.1**<br>73% at 28.5+<br>Nova · 10-03 |
| **RalliSport Challenge 2**<br>reach gameplay | 🟣 inputs ready | **41.7**<br>96% at 28.5+<br>Nova · 10-07 |
| **Harry Potter and the Philosopher's Stone**<br>done | 🟢 Playable | **41.5**<br>95% at 28.5+<br>Nova · 10-13 |
| **Conflict Desert Storm II Back to Baghdad USA**<br>reach gameplay | 🔵 copied | **41.1**<br>93% at 28.5+<br>Nova · 10-13 |
| **Dead or Alive 1 Ultimate**<br>reach gameplay<br>#413 open · nothing in flight | 🟣 inputs ready | **40.4**<br>100% at 28.5+<br>Nova · 10-07 |
| **007: Nightfire**<br>reach gameplay | 🟣 inputs ready | **40.0**<br>89% at 28.5+<br>Nova · 10-06 |
| **Mortal Kombat: Deadly Alliance**<br>reach gameplay | 🟣 inputs ready | **39.9**<br>100% at 28.5+<br>Nova · 10-06 |
| **Ninja Gaiden Black**<br>reach gameplay | 🔵 copied | **38.0**<br>97% at 28.5+<br>Nova · 10-12 · max perf |
| **The Simpsons: Hit & Run**<br>done | 🟢 Playable | **37.9**<br>100% at 28.5+<br>Nova · 10-04 |
| **NHL Hitz Pro**<br>reach gameplay | 🔵 copied | **37.4**<br>75% at 28.5+<br>Nova · 10-05 |
| **Blood Wake**<br>**blocked: hang: 10.6 s without 60 guest flips after the mark** | 🔴 blocked | **37.4**<br>30% at 28.5+<br>Thor · 09-27 · max perf<br>Nova 59.9 |
| **Tron 2.0 - Killer App**<br>reach gameplay | 🔵 copied | **37.2**<br>98% at 28.5+<br>Nova · 10-04 |
| **NBA Live 2004**<br>done | 🟢 Playable | **35.5**<br>100% at 28.5+<br>Nova · 10-06 |
| **NHL 2K3**<br>reach gameplay | 🔵 copied | **35.0**<br>69% at 28.5+<br>Nova · 10-05 |
| **Bistro Cupid**<br>reach gameplay | 🔵 copied | **34.4**<br>87% at 28.5+<br>Thor · 09-30 · max perf, soak |
| **Top Spin**<br>soak for Playable | soak pending | **32.6**<br>91% at 28.5+<br>Nova · 10-09 · max perf |
| **Aliens Versus Predator: Extinction**<br>reach gameplay | 🟣 inputs ready | **31.0**<br>100% at 28.5+<br>Nova · 10-05 |
| **Fuzion Frenzy**<br>**blocked: hang: 13.4 s without 60 guest flips after the mark** | 🔴 blocked | **30.6**<br>54% at 28.5+<br>Nova · 09-27 · max perf |
| **Panzer Elite Action Fields of Glory Europe**<br>reach gameplay | 🔵 copied | **30.4**<br>90% at 28.5+<br>Nova · 10-07 |
| **Crimson Skies: High Road to Revenge**<br>done | 🟢 Playable | **30.0**<br>95% at 28.5+<br>Nova · 10-13 · default perf<br>Thor **23.4** |
| **50 Cent: Bulletproof**<br>done<br>#382 open · nothing in flight | 🟢 Playable | **30.0**<br>99% at 28.5+<br>Nova · 09-30 · default perf, soak |
| **Azurik: Rise of Perathia**<br>done | 🟢 Playable | **30.0**<br>95% at 28.5+<br>Nova · 09-29 · default perf<br>Thor 30.0 |
| **Blade II**<br>done | 🟢 Playable | **30.0**<br>100% at 28.5+<br>Nova · 10-07 |
| **Blazing Angels Squadrons of WWII USA Europe En Fr De Es It**<br>reach gameplay | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-13 |
| **BloodRayne 2 USA**<br>reach gameplay | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-08 |
| **Blowout**<br>done | 🟢 Playable | **30.0**<br>100% at 28.5+<br>Nova · 10-06 |
| **Buffy the Vampire Slayer**<br>done | 🟢 Playable | **30.0**<br>100% at 28.5+<br>Nova · 10-12 · max perf |
| **Conan Europe En Fr De Es It**<br>reach gameplay | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-12 |
| **Conflict Global Terror USA**<br>reach gameplay | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-13 |
| **Family Guy: Video Game!**<br>soak for Playable | soak pending | **30.0**<br>98% at 28.5+<br>Thor · 10-01 · max perf |
| **GoldenEye: Rogue Agent**<br>**blocked: reached_gameplay: no `mark gameplay` in logcat** | 🔴 blocked | **30.0**<br>94% at 28.5+<br>Nova · 09-27 · max perf, screen: 90-240 s only |
| **Grabbed by the Ghoulies**<br>done<br>#311 closed | 🟢 Playable | **30.0**<br>98% at 28.5+<br>Nova · 10-12 · max perf<br>Thor 30.0 |
| **Grand Theft Auto III**<br>done | 🟢 Playable | **30.0**<br>100% at 28.5+<br>Nova · 10-12 · max perf |
| **Grand Theft Auto: Vice City**<br>done | 🟢 Playable | **30.0**<br>99% at 28.5+<br>Nova · 10-13 · max perf |
| **Halo 2**<br>reach gameplay | 🔵 copied | **30.0**<br>96% at 28.5+<br>Nova · 10-03 · default perf |
| **Halo: Combat Evolved**<br>done | 🟢 Playable | **30.0**<br>99% at 28.5+<br>Nova · 10-03 · default perf |
| **Marvel Nemesis: Rise of the Imperfects**<br>reach gameplay | 🟣 inputs ready | **30.0**<br>99% at 28.5+<br>Nova · 10-06 |
| **MTV Music Generator 3 This Is the Remix USA En Es**<br>reach gameplay | 🔵 copied | **30.0**<br>88% at 28.5+<br>Nova · 10-07 |
| **Prince of Persia: The Sands of Time**<br>reach gameplay | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-13 |
| **Shadow of Memories Europe**<br>reach gameplay | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-13 |
| **Aeon Flux**<br>reach gameplay | 🔵 copied | **30.0**<br>85% at 28.5+<br>Nova · 10-13 |
| **Area 51**<br>reach gameplay | 🟣 inputs ready | **30.0**<br>73% at 28.5+<br>Nova · 10-08 |
| **Batman Begins**<br>reach gameplay | 🟣 inputs ready | **30.0**<br>95% at 28.5+<br>Nova · 10-06 |
| **Beyond Good & Evil**<br>reach gameplay | 🟣 inputs ready | **30.0**<br>93% at 28.5+<br>Nova · 10-06 |
| **Grand Theft Auto: San Andreas**<br>soak for Playable | soak pending | **30.0**<br>98% at 28.5+<br>Nova · 10-12 · max perf |
| **Lord of the Rings The The Fellowship of the Ring USA**<br>reach gameplay | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-07 |
| **MechAssault 2: Lone Wolf**<br>reach gameplay | 🟣 inputs ready | **30.0**<br>89% at 28.5+<br>Nova · 10-08 · max perf, soak |
| **Shin Megami Tensei: NINE**<br>soak for Playable | soak pending | **30.0**<br>97% at 28.5+<br>Thor · 09-30 · max perf |
| **Tork: Prehistoric Punk**<br>done | 🟢 Playable | **30.0**<br>59% at 28.5+<br>Thor · 09-30 · max perf<br>Nova 30.0 |
| **Battlefield 2: Modern Combat**<br>reach gameplay | 🟣 inputs ready | **29.9**<br>67% at 28.5+<br>Nova · 10-01 · default perf |
| **Cel Damage**<br>reach gameplay | 🔵 copied | **29.9**<br>98% at 28.5+<br>Nova · 10-07 |
| **Star Wars Knights of the Old Republic II The Sith Lords Europe**<br>reach gameplay | 🔵 copied | **29.9**<br>66% at 28.5+<br>Nova · 10-12 |
| **Turok: Evolution**<br>reach gameplay | 🔵 copied | **29.9**<br>84% at 28.5+<br>Nova · 10-07 |
| **Half-Life 2**<br>reach gameplay | 🔵 copied | **29.8**<br>74% at 28.5+<br>Nova · 10-13 |
| **Shrek 2**<br>done | 🟢 Playable | **29.8**<br>92% at 28.5+<br>Nova · 10-13 |
| **Call of Duty 3**<br>done | 🟢 Playable | **29.4**<br>100% at 28.5+<br>Nova · 10-06 |
| **Star Wars The Clone Wars USA**<br>reach gameplay | 🔵 copied | **29.4**<br>61% at 28.5+<br>Nova · 10-08 |
| **Phantom Dust**<br>reach gameplay | 🔵 copied | **29.4**<br>74% at 28.5+<br>Thor · 09-30 · max perf, screen: 90-240 s only |
| **Ultimate Spider-Man**<br>reach gameplay | 🔵 copied | **29.4**<br>89% at 28.5+<br>Nova · 10-07 |
| **Blinx 2: Battle of Time & Space ~ Blinx 2: Masters of Time & Space**<br>reach gameplay | 🟣 inputs ready | **29.3**<br>57% at 28.5+<br>Nova · 09-27 · max perf<br>Thor **21.7** |
| **The Incredible Hulk: Ultimate Destruction**<br>reach gameplay | 🟣 inputs ready | **29.2**<br>64% at 28.5+<br>Nova · 10-05 |
| **Dragon Ball Z: Sagas**<br>reach gameplay | 🔵 copied | **29.2**<br>57% at 28.5+<br>Nova · 10-07 |
| **Forza Motorsport**<br>reach gameplay<br>#414 open · nothing in flight | 🔵 copied | **29.0**<br>45% at 28.5+<br>Nova · 09-30 · default perf<br>Thor **16.7** |
| **Scooby Doo Mystery Mayhem Europe**<br>reach gameplay | 🔵 copied | **29.0**<br>100% at 28.5+<br>Nova · 10-12 |
| **Legacy of Kain: Defiance**<br>done | 🟢 Playable | **29.0**<br>37% at 28.5+<br>Nova · 10-11 · max perf, screen: 90-240 s only |
| **Forgotten Realms Demon Stone USA**<br>reach gameplay | 🔵 copied | **28.9**<br>51% at 28.5+<br>Nova · 10-08 |
| **Midnight Club 3: DUB Edition**<br>below the bar | below 30 | **28.9**<br>40% at 28.5+<br>Nova · 10-12 · max perf, soak |
| **Star Wars: Episode III: Revenge of the Sith**<br>reach gameplay | 🟣 inputs ready | **28.5**<br>47% at 28.5+<br>Nova · 10-06 · default perf |
| **Amped 2**<br>reach gameplay | 🔵 copied | **28.4**<br>44% at 28.5+<br>Nova · 10-04 |
| **Otogi: Myth of Demons**<br>reach gameplay | 🟣 inputs ready | **28.1**<br>35% at 28.5+<br>Thor · 09-30 · default perf |
| **The Lord of the Rings: The Return of the King**<br>reach gameplay | 🟣 inputs ready | **27.7**<br>33% at 28.5+<br>Nova · 10-05 |
| **Dino Crisis 3**<br>**blocked: hang: 17.3 s without 60 guest flips after the mark** | 🔴 blocked | **27.2**<br>16% at 28.5+<br>Nova · 10-02 · max perf |
| **Oddworld: Stranger's Wrath**<br>reach gameplay | 🔵 copied | **27.0**<br>38% at 28.5+<br>Nova · 10-13 |
| **Counter-Strike**<br>below the bar | below 30 | **25.9**<br>0% at 28.5+<br>Nova · 10-03 · max perf, soak |
| **Spider-Man 2**<br>reach gameplay | 🟣 inputs ready | **25.8**<br>29% at 28.5+<br>Nova · 10-05 |
| **Need for Speed: Most Wanted**<br>done | 🟢 Playable | **25.8**<br>19% at 28.5+<br>Nova · 10-05 |
| **BloodRayne**<br>below the bar | below 30 | **25.6**<br>8% at 28.5+<br>Thor · 09-28 · max perf, soak |
| **Galleon**<br>below the bar | below 30 | **24.7**<br>10% at 28.5+<br>Thor · 09-30 · max perf |
| **JSRF: Jet Set Radio Future**<br>below the bar | below 30 | **24.2**<br>11% at 28.5+<br>Thor · 09-27 · max perf<br>Nova 59.9 |
| **Tom Clancy s Splinter Cell Double Agent USA**<br>reach gameplay | 🔵 copied | **23.5**<br>3% at 28.5+<br>Nova · 10-12 |
| **Pilot Down Behind Enemy Lines Europe**<br>reach gameplay | 🔵 copied | **23.3**<br>23% at 28.5+<br>Nova · 10-07 |
| **Midnight Club II**<br>reach gameplay | 🟣 inputs ready | **23.1**<br>0% at 28.5+<br>Nova · 10-05 |
| **007: Agent Under Fire**<br>reach gameplay<br>#412 open · nothing in flight | 🟣 inputs ready | **22.1**<br>0% at 28.5+<br>Nova · 09-30 · default perf |
| **Burnout 3: Takedown**<br>reach gameplay | 🟣 inputs ready | **22.0**<br>0% at 28.5+<br>Thor · 09-28 · max perf, soak |
| **Psychonauts**<br>reach gameplay | 🔵 copied | **22.0**<br>0% at 28.5+<br>Thor · 09-30 · max perf, screen: 90-240 s only |
| **Arctic Thunder**<br>below the bar | below 30 | **21.4**<br>9% at 28.5+<br>Thor · 09-27 · max perf<br>Nova 30.2 |
| **Amped: Freestyle Snowboarding**<br>reach gameplay | 🟣 inputs ready | **20.6**<br>9% at 28.5+<br>Nova · 10-04 |
| **Alias**<br>below the bar | below 30 | **20.4**<br>0% at 28.5+<br>Thor · 09-28 · max perf, soak |
| **Dead or Alive Xtreme Beach Volleyball**<br>reach gameplay | 🟣 inputs ready | **20.0**<br>12% at 28.5+<br>Nova · 09-27 · max perf, screen: 90-240 s only |
| **NBA Live 07**<br>reach gameplay | 🟣 inputs ready | **20.0**<br>1% at 28.5+<br>Nova · 10-06 |
| **NBA Live 06**<br>reach gameplay | 🟣 inputs ready | **20.0**<br>0% at 28.5+<br>Nova · 10-06 |
| **NBA Live 2005**<br>reach gameplay | 🟣 inputs ready | **20.0**<br>0% at 28.5+<br>Nova · 10-03 |
| **Conker: Live & Reloaded**<br>reach gameplay | 🔵 copied | **15.8**<br>16% at 28.5+<br>Nova · 10-03 · max perf, screen: 90-240 s only |
| **Crash Twinsanity**<br>below the bar | below 30 | **15.7**<br>0% at 28.5+<br>Thor · 09-27 · max perf |
| **Blinx: The Time Sweeper**<br>reach gameplay<br>#372 open · nothing in flight | 🟣 inputs ready | **14.8**<br>0% at 30+<br>Thor · 09-26 · hand-reviewed |
| **Project Gotham Racing**<br>**blocked: hang: 11.6 s without 60 guest flips after the mark** | 🔴 blocked | **14.3**<br>0% at 28.5+<br>Thor · 09-26 · max perf |
| **Gauntlet: Dark Legacy**<br>reach gameplay | 🟣 inputs ready | **14.2**<br>0% at 28.5+<br>Thor · 09-30 · max perf, screen: 90-240 s only |
| **Brute Force**<br>below the bar | below 30 | **13.2**<br>0% at 28.5+<br>Thor · 09-27 · max perf |
| **Dungeons & Dragons Heroes**<br>reach gameplay | 🟣 inputs ready | **12.5**<br>0% at 28.5+<br>Nova · 10-06 · default perf |
| **Burnout**<br>below the bar | below 30 | **10.8**<br>7% at 28.5+<br>Thor · 09-27 · max perf |
| **Bloody Roar: Extreme**<br>below the bar | below 30 | **9.8**<br>0% at 28.5+<br>Nova · 10-02 · max perf |
| **Black**<br>below the bar | below 30 | **7.5**<br>0% at 28.5+<br>Thor · 09-26 · max perf |
| **Mission Impossible Operation Surma USA**<br>**blocked: hang: 10.0 s without 60 guest flips after the mark** | 🔴 blocked | **6.9**<br>0% at 28.5+<br>Nova · 10-12 |
| **Midtown Madness 3**<br>**blocked: hang: 12.0 s without 60 guest flips after the mark** | 🔴 blocked | **3.1**<br>0% at 28.5+<br>Thor · 09-27 · max perf |
| **54540082**<br>**blocked: booted: the guest never appeared or never flipped 60 frames** | 🔴 blocked |  |
| **Die Hard Vendetta Europe En Fr Es It**<br>**blocked: booted: the guest never appeared or never flipped 60 frames** | 🔴 blocked |  |
| **SSX Tricky**<br>**blocked: reached_gameplay: unconfirmed (generic route) -- review the contact sheet, then rerun with --reviewed-gameplay yes\|no** | 🔴 blocked |  |
| **Avatar: The Last Airbender**<br>done | 🟢 Playable |  |
| **BloodRayne 2**<br>done | 🟢 Playable |  |
| **Conan**<br>done | 🟢 Playable |  |
| **Indigo Prophecy**<br>done | 🟢 Playable |  |
| **Jet Set Radio Future**<br>done | 🟢 Playable |  |
| **Mercenaries**<br>done | 🟢 Playable |  |
| **Scooby-Doo! Mystery Mayhem**<br>done | 🟢 Playable |  |
| **Scooby-Doo! Unmasked**<br>done | 🟢 Playable |  |
| **Shadow of Memories**<br>done | 🟢 Playable |  |
| **SpongeBob SquarePants: Battle for Bikini Bottom**<br>done | 🟢 Playable |  |
| **The Lord of the Rings: The Fellowship of the Ring**<br>done | 🟢 Playable |  |
| **Tony Hawk's Underground 2**<br>done | 🟢 Playable |  |
| **X-Men: The Official Game**<br>done | 🟢 Playable |  |
| **Dungeons & Dragons: Heroes**<br>reach gameplay | 🟣 inputs ready |  |
| **Shin Megami Tensei: Nine**<br>reach gameplay | 🟣 inputs ready |  |
| **Antz Extreme Racing**<br>reach gameplay | 🔵 copied |  |
| **Aoi Namida**<br>reach gameplay | 🔵 copied |  |
| **MechAssault**<br>reach gameplay | 🔵 copied |  |
| **AFL Live 2003**<br>reach gameplay | ⚪ not copied |  |
| **AFL Live 2004**<br>reach gameplay | ⚪ not copied |  |
| **AFL Live Premiership Edition**<br>reach gameplay | ⚪ not copied |  |
| **AFL Premiership 2005**<br>reach gameplay | ⚪ not copied |  |
| **Aggressive Inline**<br>reach gameplay | ⚪ not copied |  |
| **All-Star Baseball 2003 featuring Derek Jeter**<br>reach gameplay | ⚪ not copied |  |
| **All-Star Baseball 2004 featuring Derek Jeter**<br>reach gameplay | ⚪ not copied |  |
| **All-Star Baseball 2005 featuring Derek Jeter**<br>reach gameplay | ⚪ not copied |  |
| **Alter Echo**<br>reach gameplay | ⚪ not copied |  |
| **America's Army: Rise of a Soldier**<br>reach gameplay | ⚪ not copied |  |

<details><summary>363 more not copied</summary>

| Title and next step | Status | fps |
|---|---|---|
| **American Chopper**<br>reach gameplay | ⚪ not copied |  |
| **American Chopper 2: Full Throttle**<br>reach gameplay | ⚪ not copied |  |
| **American McGee Presents Scrapland**<br>reach gameplay | ⚪ not copied |  |
| **AND 1 Streetball**<br>reach gameplay | ⚪ not copied |  |
| **Angelic Concert**<br>reach gameplay | ⚪ not copied |  |
| **Animaniacs: The Great Edgar Hunt**<br>reach gameplay | ⚪ not copied |  |
| **Aquaman: Battle for Atlantis**<br>reach gameplay | ⚪ not copied |  |
| **Arena Football**<br>reach gameplay | ⚪ not copied |  |
| **Armed and Dangerous**<br>reach gameplay | ⚪ not copied |  |
| **Army Men: Major Malfunction**<br>reach gameplay | ⚪ not copied |  |
| **Army Men: Sarge's War**<br>reach gameplay | ⚪ not copied |  |
| **Atari Anthology**<br>reach gameplay | ⚪ not copied |  |
| **Backyard Wrestling 2: There Goes the Neighborhood**<br>reach gameplay | ⚪ not copied |  |
| **Backyard Wrestling: Don't Try This at Home**<br>reach gameplay | ⚪ not copied |  |
| **Bad Boys: Miami Takedown**<br>reach gameplay | ⚪ not copied |  |
| **Baldur's Gate: Dark Alliance II**<br>reach gameplay | ⚪ not copied |  |
| **Barbarian**<br>reach gameplay | ⚪ not copied |  |
| **Barbie Horse Adventures: Wild Horse Rescue**<br>reach gameplay | ⚪ not copied |  |
| **Bass Pro Shops: Trophy Bass 2007**<br>reach gameplay | ⚪ not copied |  |
| **Bass Pro Shops: Trophy Hunter 2007**<br>reach gameplay | ⚪ not copied |  |
| **Batman: Rise of Sin Tzu**<br>reach gameplay | ⚪ not copied |  |
| **Batman: Vengeance**<br>reach gameplay | ⚪ not copied |  |
| **Battle Engine Aquila**<br>reach gameplay | ⚪ not copied |  |
| **Battlestar Galactica**<br>reach gameplay | ⚪ not copied |  |
| **Beat Down: Fists of Vengeance**<br>reach gameplay | ⚪ not copied |  |
| **Bicycle Casino Includes: Texas Hold'em**<br>reach gameplay | ⚪ not copied |  |
| **Big Bumpin'**<br>reach gameplay | ⚪ not copied |  |
| **Big Mutha Truckers**<br>reach gameplay | ⚪ not copied |  |
| **Big Mutha Truckers 2**<br>reach gameplay | ⚪ not copied |  |
| **Bionicle**<br>reach gameplay | ⚪ not copied |  |
| **Bistro Cupid 2**<br>reach gameplay | ⚪ not copied |  |
| **Blazing Angels: Squadrons of WWII**<br>reach gameplay | ⚪ not copied |  |
| **Blitz: The League**<br>reach gameplay | ⚪ not copied |  |
| **Blood Omen 2: The Legacy of Kain Series**<br>reach gameplay | ⚪ not copied |  |
| **BMX XXX**<br>reach gameplay | ⚪ not copied |  |
| **Braveknight: Lieveland Eiyuuden**<br>reach gameplay | ⚪ not copied |  |
| **Breakdown**<br>reach gameplay | ⚪ not copied |  |
| **Breeders' Cup: World Thoroughbred Championships**<br>reach gameplay | ⚪ not copied |  |
| **Brian Lara International Cricket 2005**<br>reach gameplay | ⚪ not copied |  |
| **Broken Sword: The Sleeping Dragon**<br>reach gameplay | ⚪ not copied |  |
| **Buffy the Vampire Slayer: Chaos Bleeds**<br>reach gameplay | ⚪ not copied |  |
| **Burnout 2: Point of Impact**<br>reach gameplay | ⚪ not copied |  |
| **C.A.T: Cyber Attack Team**<br>reach gameplay | ⚪ not copied |  |
| **Cabela's Big Game Hunter 2005 Adventures**<br>reach gameplay | ⚪ not copied |  |
| **Cabela's Dangerous Hunts**<br>reach gameplay | ⚪ not copied |  |
| **Cabela's Dangerous Hunts 2**<br>reach gameplay | ⚪ not copied |  |
| **Cabela's Deer Hunt: 2004 Season**<br>reach gameplay | ⚪ not copied |  |
| **Cabela's Deer Hunt: 2005 Season**<br>reach gameplay | ⚪ not copied |  |
| **Cabela's Outdoor Adventures**<br>reach gameplay | ⚪ not copied |  |
| **Call of Cthulhu: Dark Corners of the Earth**<br>reach gameplay | ⚪ not copied |  |
| **Call of Duty 2: Big Red One**<br>reach gameplay | ⚪ not copied |  |
| **Capcom Classics Collection Vol. 1**<br>reach gameplay | ⚪ not copied |  |
| **Capcom Fighting Evolution ~ Capcom Fighting Jam**<br>reach gameplay | ⚪ not copied |  |
| **Carmen Sandiego: The Secret of the Stolen Drums**<br>reach gameplay | ⚪ not copied |  |
| **Catwoman**<br>reach gameplay | ⚪ not copied |  |
| **CDS II**<br>reach gameplay | ⚪ not copied |  |
| **Championship Bowling**<br>reach gameplay | ⚪ not copied |  |
| **Championship Manager 2006**<br>reach gameplay | ⚪ not copied |  |
| **Championship Manager 5**<br>reach gameplay | ⚪ not copied |  |
| **Championship Manager: Season 01/02**<br>reach gameplay | ⚪ not copied |  |
| **Championship Manager: Season 02/03**<br>reach gameplay | ⚪ not copied |  |
| **Charlie and the Chocolate Factory**<br>reach gameplay | ⚪ not copied |  |
| **Chase: Hollywood Stunt Driver**<br>reach gameplay | ⚪ not copied |  |
| **Chessmaster**<br>reach gameplay | ⚪ not copied |  |
| **Chicago Enforcer**<br>reach gameplay | ⚪ not copied |  |
| **Circus Maximus: Chariot Wars**<br>reach gameplay | ⚪ not copied |  |
| **Classified: The Sentinel Crisis**<br>reach gameplay | ⚪ not copied |  |
| **Close Combat: First to Fight: United States Marines**<br>reach gameplay | ⚪ not copied |  |
| **Club Football**<br>reach gameplay | ⚪ not copied |  |
| **Club Football 2005**<br>reach gameplay | ⚪ not copied |  |
| **Codename: Kids Next Door: Operation: V.I.D.E.O.G.A.M.E.**<br>reach gameplay | ⚪ not copied |  |
| **Cold Fear**<br>reach gameplay | ⚪ not copied |  |
| **Cold War**<br>reach gameplay | ⚪ not copied |  |
| **Colin McRae Rally 04**<br>reach gameplay | ⚪ not copied |  |
| **Colin McRae Rally 2005**<br>reach gameplay | ⚪ not copied |  |
| **Colin McRae Rally 3**<br>reach gameplay | ⚪ not copied |  |
| **College Hoops 2K6**<br>reach gameplay | ⚪ not copied |  |
| **College Hoops 2K7**<br>reach gameplay | ⚪ not copied |  |
| **Combat Elite: WWII Paratroopers**<br>reach gameplay | ⚪ not copied |  |
| **Commandos 2: Men of Courage**<br>reach gameplay | ⚪ not copied |  |
| **Commandos: Strike Force**<br>reach gameplay | ⚪ not copied |  |
| **Conflict: Desert Storm**<br>reach gameplay | ⚪ not copied |  |
| **Conflict: Global Storm**<br>reach gameplay | ⚪ not copied |  |
| **Conflict: Vietnam**<br>reach gameplay | ⚪ not copied |  |
| **Conspiracy: Weapons of Mass Destruction**<br>reach gameplay | ⚪ not copied |  |
| **Constantine**<br>reach gameplay | ⚪ not copied |  |
| **Corvette**<br>reach gameplay | ⚪ not copied |  |
| **Crash 'n' Burn**<br>reach gameplay | ⚪ not copied |  |
| **Crash Tag Team Racing**<br>reach gameplay | ⚪ not copied |  |
| **CRAZY TAXI 3 High Roller**<br>reach gameplay | ⚪ not copied |  |
| **Cricket 2005**<br>reach gameplay | ⚪ not copied |  |
| **Crime Life: Gang Wars**<br>reach gameplay | ⚪ not copied |  |
| **Crouching Tiger, Hidden Dragon**<br>reach gameplay | ⚪ not copied |  |
| **Crusty Demons**<br>reach gameplay | ⚪ not copied |  |
| **CSI: Crime Scene Investigation**<br>reach gameplay | ⚪ not copied |  |
| **Curious George**<br>reach gameplay | ⚪ not copied |  |
| **Curse: The Eye of Isis**<br>reach gameplay | ⚪ not copied |  |
| **Daisenryaku VII**<br>reach gameplay | ⚪ not copied |  |
| **Dakar 2**<br>reach gameplay | ⚪ not copied |  |
| **Dance Dance Revolution Ultramix**<br>reach gameplay | ⚪ not copied |  |
| **Dance Dance Revolution Ultramix 2**<br>reach gameplay | ⚪ not copied |  |
| **Dance Dance Revolution Ultramix 3**<br>reach gameplay | ⚪ not copied |  |
| **Dance Dance Revolution Ultramix 4**<br>reach gameplay | ⚪ not copied |  |
| **Dance:UK**<br>reach gameplay | ⚪ not copied |  |
| **Dave Mirra Freestyle BMX 2**<br>reach gameplay | ⚪ not copied |  |
| **David Beckham Soccer**<br>reach gameplay | ⚪ not copied |  |
| **Dead Man's Hand**<br>reach gameplay | ⚪ not copied |  |
| **Dead to Rights**<br>reach gameplay | ⚪ not copied |  |
| **Dead to Rights II**<br>reach gameplay | ⚪ not copied |  |
| **Defender**<br>reach gameplay | ⚪ not copied |  |
| **Delta Force: Black Hawk Down**<br>reach gameplay | ⚪ not copied |  |
| **Dennou Taisen: DroneZ**<br>reach gameplay | ⚪ not copied |  |
| **Destroy All Humans!**<br>reach gameplay | ⚪ not copied |  |
| **Destroy All Humans! 2**<br>reach gameplay | ⚪ not copied |  |
| **Deus Ex: Invisible War**<br>reach gameplay | ⚪ not copied |  |
| **Die Hard: Vendetta**<br>reach gameplay | ⚪ not copied |  |
| **Digimon Battle Chronicle**<br>reach gameplay | ⚪ not copied |  |
| **Digimon World X**<br>reach gameplay | ⚪ not copied |  |
| **Dinotopia: The Sunstone Odyssey**<br>reach gameplay | ⚪ not copied |  |
| **Disney's Chicken Little**<br>reach gameplay | ⚪ not copied |  |
| **Disney's Extreme Skate Adventure**<br>reach gameplay | ⚪ not copied |  |
| **Disney's The Haunted Mansion**<br>reach gameplay | ⚪ not copied |  |
| **Disney/Pixar Cars**<br>reach gameplay | ⚪ not copied |  |
| **Disney/Pixar Finding Nemo**<br>reach gameplay | ⚪ not copied |  |
| **Disney/Pixar The Incredibles**<br>reach gameplay | ⚪ not copied |  |
| **Disney/Pixar The Incredibles: Rise of the Underminer**<br>reach gameplay | ⚪ not copied |  |
| **Doom 3**<br>reach gameplay | ⚪ not copied |  |
| **Doom 3: Resurrection of Evil**<br>reach gameplay | ⚪ not copied |  |
| **Dr. Seuss' The Cat in the Hat**<br>reach gameplay | ⚪ not copied |  |
| **Dragon's Lair 3D: Return to the Lair**<br>reach gameplay | ⚪ not copied |  |
| **Drake of the 99 Dragons**<br>reach gameplay | ⚪ not copied |  |
| **Dreamfall: The Longest Journey**<br>reach gameplay | ⚪ not copied |  |
| **DreamWorks Madagascar**<br>reach gameplay | ⚪ not copied |  |
| **DreamWorks Shark Tale**<br>reach gameplay | ⚪ not copied |  |
| **DreamWorks Shrek: SuperSlam**<br>reach gameplay | ⚪ not copied |  |
| **Drihoo**<br>reach gameplay | ⚪ not copied |  |
| **Driver: Parallel Lines**<br>reach gameplay | ⚪ not copied |  |
| **Dynasty Warriors 4**<br>reach gameplay | ⚪ not copied |  |
| **Dynasty Warriors 5**<br>reach gameplay | ⚪ not copied |  |
| **Ed, Edd n Eddy: The Mis-Edventures**<br>reach gameplay | ⚪ not copied |  |
| **Eggo Mania**<br>reach gameplay | ⚪ not copied |  |
| **Enclave**<br>reach gameplay | ⚪ not copied |  |
| **England International Football: 2004 Edition**<br>reach gameplay | ⚪ not copied |  |
| **Enter the Matrix**<br>reach gameplay | ⚪ not copied |  |
| **Eragon**<br>reach gameplay | ⚪ not copied |  |
| **ESPN College Hoops**<br>reach gameplay | ⚪ not copied |  |
| **ESPN College Hoops 2K5**<br>reach gameplay | ⚪ not copied |  |
| **ESPN International Winter Sports 2002**<br>reach gameplay | ⚪ not copied |  |
| **ESPN Major League Baseball**<br>reach gameplay | ⚪ not copied |  |
| **ESPN MLS ExtraTime 2002**<br>reach gameplay | ⚪ not copied |  |
| **ESPN NBA 2K5**<br>reach gameplay | ⚪ not copied |  |
| **ESPN NBA Basketball**<br>reach gameplay | ⚪ not copied |  |
| **ESPN NFL 2K5**<br>reach gameplay | ⚪ not copied |  |
| **ESPN NFL PrimeTime 2002**<br>reach gameplay | ⚪ not copied |  |
| **ESPN NHL 2K5**<br>reach gameplay | ⚪ not copied |  |
| **ESPN NHL Hockey**<br>reach gameplay | ⚪ not copied |  |
| **ESPN Winter X Games Snowboarding 2002**<br>reach gameplay | ⚪ not copied |  |
| **Evil Dead: A Fistful of Boomstick**<br>reach gameplay | ⚪ not copied |  |
| **Evil Dead: Regeneration**<br>reach gameplay | ⚪ not copied |  |
| **Ex-Chaser**<br>reach gameplay | ⚪ not copied |  |
| **Exaskeleton**<br>reach gameplay | ⚪ not copied |  |
| **F1 2001**<br>reach gameplay | ⚪ not copied |  |
| **F1 Career Challenge**<br>reach gameplay | ⚪ not copied |  |
| **Fable: The Lost Chapters**<br>reach gameplay | ⚪ not copied |  |
| **Fallout: Brotherhood of Steel**<br>reach gameplay | ⚪ not copied |  |
| **Far Cry Instincts**<br>reach gameplay | ⚪ not copied |  |
| **Far Cry Instincts: Evolution**<br>reach gameplay | ⚪ not copied |  |
| **Fatal Frame**<br>reach gameplay | ⚪ not copied |  |
| **FIFA 07**<br>reach gameplay | ⚪ not copied |  |
| **FIFA Football 2004**<br>reach gameplay | ⚪ not copied |  |
| **FIFA Soccer 06**<br>reach gameplay | ⚪ not copied |  |
| **FIFA Soccer 2003**<br>reach gameplay | ⚪ not copied |  |
| **FIFA Soccer 2005**<br>reach gameplay | ⚪ not copied |  |
| **FIFA Street**<br>reach gameplay | ⚪ not copied |  |
| **FIFA Street 2**<br>reach gameplay | ⚪ not copied |  |
| **FIFA World Cup Germany 2006**<br>reach gameplay | ⚪ not copied |  |
| **Fight Night 2004**<br>reach gameplay | ⚪ not copied |  |
| **Fight Night Round 2**<br>reach gameplay | ⚪ not copied |  |
| **Fight Night Round 3**<br>reach gameplay | ⚪ not copied |  |
| **FILA World Tour Tennis**<br>reach gameplay | ⚪ not copied |  |
| **Final Fight: Streetwise**<br>reach gameplay | ⚪ not copied |  |
| **FlatOut**<br>reach gameplay | ⚪ not copied |  |
| **FlatOut 2**<br>reach gameplay | ⚪ not copied |  |
| **Flight Academy**<br>reach gameplay | ⚪ not copied |  |
| **Ford Mustang: The Legend Lives**<br>reach gameplay | ⚪ not copied |  |
| **Ford Racing 2**<br>reach gameplay | ⚪ not copied |  |
| **Ford Racing 3**<br>reach gameplay | ⚪ not copied |  |
| **Ford Street Racing**<br>reach gameplay | ⚪ not copied |  |
| **Forgotten Realms: Demon Stone**<br>reach gameplay | ⚪ not copied |  |
| **Frankie Dettori Racing**<br>reach gameplay | ⚪ not copied |  |
| **Freaky Flyers**<br>reach gameplay | ⚪ not copied |  |
| **Freedom Fighters**<br>reach gameplay | ⚪ not copied |  |
| **Freestyle Metal X**<br>reach gameplay | ⚪ not copied |  |
| **Frogger Beyond**<br>reach gameplay | ⚪ not copied |  |
| **Frogger: Ancient Shadow**<br>reach gameplay | ⚪ not copied |  |
| **Full Spectrum Warrior**<br>reach gameplay | ⚪ not copied |  |
| **Full Spectrum Warrior: Ten Hammers**<br>reach gameplay | ⚪ not copied |  |
| **Furious Karting**<br>reach gameplay | ⚪ not copied |  |
| **Futurama**<br>reach gameplay | ⚪ not copied |  |
| **Gauntlet: Seven Sorrows**<br>reach gameplay | ⚪ not copied |  |
| **Gene Troopers**<br>reach gameplay | ⚪ not copied |  |
| **Ghost Master: The Gravenville Chronicles**<br>reach gameplay | ⚪ not copied |  |
| **Gladiator: Sword of Vengeance**<br>reach gameplay | ⚪ not copied |  |
| **Gladius**<br>reach gameplay | ⚪ not copied |  |
| **Goblin Commander: Unleash the Horde**<br>reach gameplay | ⚪ not copied |  |
| **Godzilla: Destroy All Monsters Melee**<br>reach gameplay | ⚪ not copied |  |
| **Godzilla: Save the Earth**<br>reach gameplay | ⚪ not copied |  |
| **Gotcha!**<br>reach gameplay | ⚪ not copied |  |
| **Gravity Games Bike: Street. Vert. Dirt.**<br>reach gameplay | ⚪ not copied |  |
| **Greg Hastings' Tournament Paintball**<br>reach gameplay | ⚪ not copied |  |
| **Greg Hastings' Tournament Paintball Max'd**<br>reach gameplay | ⚪ not copied |  |
| **Grooverider: Slot Car Thunder**<br>reach gameplay | ⚪ not copied |  |
| **Group S Challenge**<br>reach gameplay | ⚪ not copied |  |
| **Guilty Gear Isuka**<br>reach gameplay | ⚪ not copied |  |
| **Gun**<br>reach gameplay | ⚪ not copied |  |
| **Gun Metal**<br>reach gameplay | ⚪ not copied |  |
| **Gungriffon: Allied Strike**<br>reach gameplay | ⚪ not copied |  |
| **Halo 2 Multiplayer Map Pack**<br>reach gameplay | ⚪ not copied |  |
| **Harry Potter and the Chamber of Secrets**<br>reach gameplay | ⚪ not copied |  |
| **Harry Potter and the Goblet of Fire**<br>reach gameplay | ⚪ not copied |  |
| **Harry Potter and the Prisoner of Azkaban**<br>reach gameplay | ⚪ not copied |  |
| **Harry Potter: Quidditch World Cup**<br>reach gameplay | ⚪ not copied |  |
| **Headhunter: Redemption**<br>reach gameplay | ⚪ not copied |  |
| **Hello Kitty: Roller Rescue**<br>reach gameplay | ⚪ not copied |  |
| **Heroes of the Pacific**<br>reach gameplay | ⚪ not copied |  |
| **High Heat Major League Baseball 2004**<br>reach gameplay | ⚪ not copied |  |
| **High Rollers Casino**<br>reach gameplay | ⚪ not copied |  |
| **Hitman 2: Silent Assassin**<br>reach gameplay | ⚪ not copied |  |
| **Hot Wheels: Stunt Track Challenge**<br>reach gameplay | ⚪ not copied |  |
| **Hulk**<br>reach gameplay | ⚪ not copied |  |
| **Hummer Badlands**<br>reach gameplay | ⚪ not copied |  |
| **Hunter: The Reckoning**<br>reach gameplay | ⚪ not copied |  |
| **Hyper Sports 2002 Winter**<br>reach gameplay | ⚪ not copied |  |
| **I-Ninja**<br>reach gameplay | ⚪ not copied |  |
| **Ice Age 2: The Meltdown**<br>reach gameplay | ⚪ not copied |  |
| **IHRA Drag Racing 2004**<br>reach gameplay | ⚪ not copied |  |
| **IHRA Drag Racing: Sportsman Edition**<br>reach gameplay | ⚪ not copied |  |
| **IHRA Professional Drag Racing 2005**<br>reach gameplay | ⚪ not copied |  |
| **Indiana Jones and the Emperor's Tomb**<br>reach gameplay | ⚪ not copied |  |
| **IndyCar Series**<br>reach gameplay | ⚪ not copied |  |
| **IndyCar Series 2005**<br>reach gameplay | ⚪ not copied |  |
| **Innocent Tears**<br>reach gameplay | ⚪ not copied |  |
| **Inside Pitch 2003**<br>reach gameplay | ⚪ not copied |  |
| **Intellivision Lives!**<br>reach gameplay | ⚪ not copied |  |
| **International Superstar Soccer 2**<br>reach gameplay | ⚪ not copied |  |
| **Iron Phoenix**<br>reach gameplay | ⚪ not copied |  |
| **Jacked**<br>reach gameplay | ⚪ not copied |  |
| **Jade Empire**<br>reach gameplay | ⚪ not copied |  |
| **James Cameron's Dark Angel**<br>reach gameplay | ⚪ not copied |  |
| **Jaws Unleashed**<br>reach gameplay | ⚪ not copied |  |
| **Jikkyou World Soccer 2002**<br>reach gameplay | ⚪ not copied |  |
| **Judge Dredd: Dredd vs. Death**<br>reach gameplay | ⚪ not copied |  |
| **Juiced**<br>reach gameplay | ⚪ not copied |  |
| **Jurassic Park: Operation Genesis**<br>reach gameplay | ⚪ not copied |  |
| **Just Cause**<br>reach gameplay | ⚪ not copied |  |
| **Justice League Heroes**<br>reach gameplay | ⚪ not copied |  |
| **Knight's Apprentice: Memorick's Adventures**<br>reach gameplay | ⚪ not copied |  |
| **Knights of the Temple II**<br>reach gameplay | ⚪ not copied |  |
| **Knockout Kings 2002**<br>reach gameplay | ⚪ not copied |  |
| **KOF: Maximum Impact: Maniax**<br>reach gameplay | ⚪ not copied |  |
| **Kung Fu Chaos**<br>reach gameplay | ⚪ not copied |  |
| **Largo Winch: Empire Under Threat**<br>reach gameplay | ⚪ not copied |  |
| **Legends of Wrestling**<br>reach gameplay | ⚪ not copied |  |
| **Legends of Wrestling II**<br>reach gameplay | ⚪ not copied |  |
| **Lemony Snicket's A Series of Unfortunate Events**<br>reach gameplay | ⚪ not copied |  |
| **LMA Manager 2003**<br>reach gameplay | ⚪ not copied |  |
| **Loons: The Fight for Fame**<br>reach gameplay | ⚪ not copied |  |
| **Mace Griffin: Bounty Hunter**<br>reach gameplay | ⚪ not copied |  |
| **Madden NFL 07**<br>reach gameplay | ⚪ not copied |  |
| **Madden NFL 08**<br>reach gameplay | ⚪ not copied |  |
| **Madden NFL 2002**<br>reach gameplay | ⚪ not copied |  |
| **Magi Death Fight!**<br>reach gameplay | ⚪ not copied |  |
| **Manhunt**<br>reach gameplay | ⚪ not copied |  |
| **Mashed: Drive to Survive**<br>reach gameplay | ⚪ not copied |  |
| **Mat Hoffman's Pro BMX 2**<br>reach gameplay | ⚪ not copied |  |
| **Max Payne**<br>reach gameplay | ⚪ not copied |  |
| **Maximum Chase**<br>reach gameplay | ⚪ not copied |  |
| **Medal of Honor: European Assault**<br>reach gameplay | ⚪ not copied |  |
| **Medal of Honor: Frontline**<br>reach gameplay | ⚪ not copied |  |
| **Metal Arms: Glitch in the System**<br>reach gameplay | ⚪ not copied |  |
| **Metal Dungeon**<br>reach gameplay | ⚪ not copied |  |
| **Metal Gear Solid 2: Substance**<br>reach gameplay | ⚪ not copied |  |
| **Micro Machines**<br>reach gameplay | ⚪ not copied |  |
| **Midway Arcade Treasures**<br>reach gameplay | ⚪ not copied |  |
| **Midway Arcade Treasures 2**<br>reach gameplay | ⚪ not copied |  |
| **Mission: Impossible: Operation Surma**<br>reach gameplay | ⚪ not copied |  |
| **Monopoly Party**<br>reach gameplay | ⚪ not copied |  |
| **Monster Garage**<br>reach gameplay | ⚪ not copied |  |
| **Motor Trend Presents Lotus Challenge**<br>reach gameplay | ⚪ not copied |  |
| **MVP Baseball 2003**<br>reach gameplay | ⚪ not copied |  |
| **Namco Museum**<br>reach gameplay | ⚪ not copied |  |
| **NBA 2K6**<br>reach gameplay | ⚪ not copied |  |
| **NBA 2K7**<br>reach gameplay | ⚪ not copied |  |
| **NBA Inside Drive 2004**<br>reach gameplay | ⚪ not copied |  |
| **Need for Speed: Hot Pursuit 2**<br>reach gameplay | ⚪ not copied |  |
| **Neighbours from Hell**<br>reach gameplay | ⚪ not copied |  |
| **NFL 2K2**<br>reach gameplay | ⚪ not copied |  |
| **Psi-Ops: The Mindgate Conspiracy**<br>reach gameplay | ⚪ not copied |  |
| **Psyvariar 2: Extend Edition**<br>reach gameplay | ⚪ not copied |  |
| **RAW**<br>reach gameplay | ⚪ not copied |  |
| **Ricky Ponting International Cricket 2005**<br>reach gameplay | ⚪ not copied |  |
| **RLH: Run Like Hell**<br>reach gameplay | ⚪ not copied |  |
| **Robotech: Invasion**<br>reach gameplay | ⚪ not copied |  |
| **RollerCoaster Tycoon**<br>reach gameplay | ⚪ not copied |  |
| **Rugby League 2**<br>reach gameplay | ⚪ not copied |  |
| **Sega GT 2002**<br>reach gameplay | ⚪ not copied |  |
| **Sega GT 2002 + JSRF: Jet Set Radio Future**<br>reach gameplay | ⚪ not copied |  |
| **Shadow The Hedgehog**<br>reach gameplay | ⚪ not copied |  |
| **Shrek**<br>reach gameplay | ⚪ not copied |  |
| **Ski Racing 2005**<br>reach gameplay | ⚪ not copied |  |
| **Slam Tennis**<br>reach gameplay | ⚪ not copied |  |
| **Spartan: Total Warrior**<br>reach gameplay | ⚪ not copied |  |
| **Splat Magazine Renegade Paintball**<br>reach gameplay | ⚪ not copied |  |
| **Stake**<br>reach gameplay | ⚪ not copied |  |
| **Star Wars: Battlefront**<br>reach gameplay | ⚪ not copied |  |
| **Star Wars: Battlefront II**<br>reach gameplay | ⚪ not copied |  |
| **Star Wars: Knights of the Old Republic II: The Sith Lords**<br>reach gameplay | ⚪ not copied |  |
| **Star Wars: Starfighter Special Edition**<br>reach gameplay | ⚪ not copied |  |
| **Star Wars: The Clone Wars**<br>reach gameplay | ⚪ not copied |  |
| **Still Life**<br>reach gameplay | ⚪ not copied |  |
| **Super Bubble Pop**<br>reach gameplay | ⚪ not copied |  |
| **Superman Returns**<br>reach gameplay | ⚪ not copied |  |
| **Takahashi Junko no Mahjong Seminar**<br>reach gameplay | ⚪ not copied |  |
| **Tetris Worlds**<br>reach gameplay | ⚪ not copied |  |
| **The Bard's Tale**<br>reach gameplay | ⚪ not copied |  |
| **The Baseball 2002: Battle Ball Park Sengen**<br>reach gameplay | ⚪ not copied |  |
| **The Bible Game**<br>reach gameplay | ⚪ not copied |  |
| **The Hustle: Detroit Streets**<br>reach gameplay | ⚪ not copied |  |
| **The King of Fighters 2002**<br>reach gameplay | ⚪ not copied |  |
| **The Lord of the Rings: The Third Age**<br>reach gameplay | ⚪ not copied |  |
| **The Matrix: Path of Neo**<br>reach gameplay | ⚪ not copied |  |
| **The Simpsons: Road Rage**<br>reach gameplay | ⚪ not copied |  |
| **The Urbz: Sims in the City**<br>reach gameplay | ⚪ not copied |  |
| **The Wild Rings**<br>reach gameplay | ⚪ not copied |  |
| **Tiger Woods PGA Tour 06**<br>reach gameplay | ⚪ not copied |  |
| **Tiger Woods PGA Tour 07**<br>reach gameplay | ⚪ not copied |  |
| **Tiger Woods PGA Tour 2003**<br>reach gameplay | ⚪ not copied |  |
| **Tiger Woods PGA Tour 2004**<br>reach gameplay | ⚪ not copied |  |
| **Tiger Woods PGA Tour 2005**<br>reach gameplay | ⚪ not copied |  |
| **TimeSplitters: Future Perfect**<br>reach gameplay | ⚪ not copied |  |
| **Tom Clancy's Splinter Cell: Double Agent**<br>reach gameplay | ⚪ not copied |  |
| **Torino 2006**<br>reach gameplay | ⚪ not copied |  |
| **Total Club Manager 2004**<br>reach gameplay | ⚪ not copied |  |
| **Triangle Again**<br>reach gameplay | ⚪ not copied |  |
| **Triple Play 2002**<br>reach gameplay | ⚪ not copied |  |
| **Trivial Pursuit: Unhinged**<br>reach gameplay | ⚪ not copied |  |
| **TY the Tasmanian Tiger**<br>reach gameplay | ⚪ not copied |  |
| **UEFA Champions League 2004-2005**<br>reach gameplay | ⚪ not copied |  |
| **Ultimate Pro Pinball**<br>reach gameplay | ⚪ not copied |  |
| **Umezawa Yukari no Igo Seminar**<br>reach gameplay | ⚪ not copied |  |
| **Unreal Championship**<br>reach gameplay | ⚪ not copied |  |
| **Virtual Pool: Tournament Edition**<br>reach gameplay | ⚪ not copied |  |
| **Voodoo Vince**<br>reach gameplay | ⚪ not copied |  |
| **Whiteout**<br>reach gameplay | ⚪ not copied |  |
| **World Series Baseball**<br>reach gameplay | ⚪ not copied |  |
| **World Snooker Championship 2005**<br>reach gameplay | ⚪ not copied |  |
| **World Soccer Winning Eleven 8: International**<br>reach gameplay | ⚪ not copied |  |
| **World War II Combat: Road to Berlin**<br>reach gameplay | ⚪ not copied |  |
| **Xbox Live Arcade**<br>reach gameplay | ⚪ not copied |  |
| **Xiaolin Showdown**<br>reach gameplay | ⚪ not copied |  |
| **XIII**<br>reach gameplay | ⚪ not copied |  |
| **Yetisports Arctic Adventures**<br>reach gameplay | ⚪ not copied |  |
| **Yonenaga Kunio no Shougi Seminar**<br>reach gameplay | ⚪ not copied |  |

</details>

584 titles: 19 blocked, 68 Playable, 5 soak pending, 12 below 30, 37 inputs ready, 70 copied, 373 not copied. Measured = any gameplay fps reading, on either handheld, any build or mode. fps: the gameplay median (at the bar green, 25 to the bar amber, under 25 red), the share of play at the bar it names (title_verdict.py's playable_fps x fps_tolerance, which a soak is scored at too); the build is in the title's detail. Sources: titles/already-on-handhelds.json, logs/titlepipe/batch-\*.tsv, targets.toml, the xiso manifest, pathfind held runs, the Playable ledger, pass1-backfill.json, dispatch results/\*/verdict.json, soaks (results/\*/logcat, 60-flip windows 90-240 s); registry: docs/testing/titles/targets.toml, routes/ and titlestate.py's registry.

Hand-reviewed rows: pass 1 of #397 ([[lane.titleplay], 2026-09-26 12:09 PDT](https://github.com/jreinach-alt/hakuX/issues/397#issuecomment-5849041338)), performance mode unrecorded.

**Gate:** Ghoulies median >= 25 gfps over 90-240 s on the candidate APK, on the Nova: no candidate is cut yet, so no soak is on the candidate's APK; on the newest soaks it is met; nova **29** gfps (n=74, 14:38 (33h 12m ago), ref cf628f179f).

| lever | owner lane | measured effect |
|---|---|---|
| #424 stop the translation cache's code-write invalidation and dirty re-arm churn | none | not measured yet: no lane holds it (IN FLIGHT (hostops 2026-09-29T05:35Z): lane.tcg424flip flips HAKUX_TCG424_RANGE to default ON -- the three valid Thor tbflip424-blinx2 pairs pass every leg (issuecomment-5884276103); it runs the Arctic Thunder A/B and the pgraph must-not-move arm before PR-ready.) |
| #425 fewer jump-cache flushes and an inline indirect-branch probe | none | not measured yet: no lane holds it (UPDATED hostops 2026-09-28T02:40Z: lane.flip474 retired (PRs #475/#485/#516 folded; Turnip sysmem measured AUF 16 -> 24, DOA 13 -> 21 gfps on the Nova); the #474 remedies are lane.rendermode474 (PR #530: per-title Turnip sysmem default for DOA and AUF; DOA A/B 1790559549/-550 and arms 1-1790561511 in the queue), lane.drain474 (PR #517 FOLDED 2026-09-28T03:43Z as 9cfa11b64f, row retired: AUF bind_textures 4.55 -> 0.10 ms/flip, fps +1.7%, J/frame -9.5% on one pair) and lane.forza414 (PR #518: the display pre-download deferral; DOA and AUF A/B soaks 1-1790561463..-468 in the Nova queue).) |
| #426 split renderer command capture from Vulkan translation | lane.remote | not measured yet: no arm or device run registered |
| #427 build with native TLS, inline LSE atomics and no intra-library PLT calls | none | BOARD job.board 2026-09-26T21:55Z: not dispatchable, a lane owns it (draft PR #435, handback resumes). |
| #428 run the emulated CPU thread on the prime core | none | CLOSED (hostops 2026-09-26T23:20Z) as refuted by lane.vcpuprime428 (PR #437): six 480 s Crimson Skies runs on the Thor, one binary; pinned to the prime core 20.56 fps mean vs 26.20 unpinned (-21.5%). |
| #429 smaller translation blocks on often-rewritten pages | none | CLOSED 2026-09-27 (hostops) as refuted in gameplay: lane.tbsize429 (PR #459, docs only) read the always-on hakuX-pages counters -- stores touching translated code (ov) are 0 in every gameplay window (Crimson A/B, Blinx survey, blinx372 runs); real codegen is ~1 block/frame at ~5.6 insns; the 19% tb_gen_code share is whole-page-invalidation recycles, which #424's range test removes (PRs #434/#456), not block size. |

## 2. What is happening right now?

14 stranded; 2 waiting on audit; 2 no word in 48 h.

- **lane.collapse433** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-01 23:27; latest result: I've found why Battlefield 2 falls short on the Nova; it is not a collapse.
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.defecttriage433** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 09-30 10:47; latest result: Matches `docs/lanes/defecttriage433/` exactly, docs-only, no emulator code, no territory/nv2a_issues edits.
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.framereview** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-04 22:10; latest result: retro-tron has finished and I reviewed it: REJECT.
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.gpuclock** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #827 is a draft; since: 10-05 16:13; latest result: The lane is waiting again, this time on four new Nova runs, the Simpsons host session and the profile.c grant. (PR #827)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.holdfollow1013** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: -; latest result: -
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.issuemirror1012** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-12 22:51; latest result: Everything is confirmed pushed and matches.
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.nfsroute1011** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #929 is a draft; since: 10-11 16:37; latest result: Comment posted. (PR #929)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.pathfindhold1012** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: -; latest result: -
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.playsecs1013** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: -; latest result: -
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.routefix1002** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #683 is a draft; since: 10-03 10:17; latest result: The Gunvalkyrie v5 route is ready, but it is in no live queue yet. lane.local has to change one line before Star Wars III (`1791045669`, queued now) finishes, or the Nova will run the old route instead. (PR #683)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.selftestclean1011** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-11 16:23; latest result: Good progress — shards 1-3 are well into their fragment lists; shard 0 is stuck on the heavy `20-arms-queue.sh` (413s and counting).
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.selftestshard** -- kind: local lane; issue: (harness work, no tracker issue); state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 09-27 22:21; latest result: `jobs selftest` now runs as four parallel jobs instead of one.
- **lane.toolsmith** -- kind: local lane; issue: #94 request.sh silently drops all but the last --only-tests/--skip-tests/--tests/--suites, and it nearly published a bracket that excluded the true answer; #95 The prediction schema has no composition field, so the comparability rule cannot be enforced -- and disc_id conflates composition with the skip list; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-04 16:02; latest result: I've fixed the libfolders pref problem from the 10-04 addendum, and the work is pushed to `lane/toolsmith` with `State: ready`.
  - board note NOT BLOCKED. docs/testing/ab_compare.py and docs/testing/request.sh are both held by the instruments standing lane, per the owner's division of labour on dispatch scripts. Needs no device and no build. Note the ordering constraint if it lands while arms are live: adding a field is backward-compatible, but step (2)'s refusal is NOT -- it would invalidate every prediction registered without the field, which is 106 of 107, so (2) needs a grandfathering rule decided BEFORE it ships.
- **lane.verdict433** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #653 is a draft; since: 10-01 21:11; latest result: Summary Session 19 picked up where session 18 left off (which had finished cleanly and parked with nothing outstanding — the resume was the harness's normal idle-lane pickup, not a stall). (PR #653)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.alwaystelemetry** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: waiting on audit; waiting on: PR #824: an audit label (the PR is ready and unlabelled); since: 10-05 07:50; latest result: Part 1 of #433 was already finished before this session: the perflog overhead is measured and the two-tier design is posted. (PR #824)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.statusfix1013** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: waiting on audit; waiting on: PR #987: an audit label (the PR is ready and unlabelled); since: -; latest result: - (PR #987)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.remote** -- kind: cloud session; issue: #426 Performance: split renderer command capture from Vulkan translation; #184 Vulkan: the Clear suite's surface-format captures are worse than GL on four of them, two of which GL gets pixel-exact -- and no arm scores that suite; state: no word in 48 h; waiting on: -; since: -; latest result: -
- **lane.xbox** -- kind: console session; issue: #112 xbox-hardware: the experiments that need real silicon, in the order they pay; #110 PVIDEO overlay: no size cap and no pitch handling (pvideo.c is 77 lines of register stubs); state: no word in 48 h; waiting on: -; since: -; latest result: -

### Finished today (16)

- lane.statuspage1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #985; merged: 22:58; result: -
- lane.holdinput1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #981; merged: 17:51; result: Lane `holdinput1013` is done and pushed.
- lane.hangstall1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: -; merged: 16:23; result: Done. `lane/hangstall1013` is pushed and ready for `forge_prsync.py` to open the PR.
- lane.compatrefresh1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #978; merged: 15:20; result: -
- lane.statusalloc1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #980; merged: 14:31; result: -
- lane.pathrules1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #979; merged: 14:00; result: PR #979 is pushed, ready, and carries a `waiting:` comment naming the exact blocking condition (pathtele1013's fold landing on `origin/master`) and the resolving signal.

<details><summary>10 more finished earlier today</summary>

- lane.pathtele1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #972; merged: 12:33; result: PR #972 opened, ready (both Part A and Part B complete, selftest passes, PR.md already states `State: ready`).
- lane.forgealloc1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #977; merged: 11:59; result: All five tasks (#433) are now complete and pushed.
- lane.driverline1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #971; merged: 11:24; result: -
- lane.pathvoid1012 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: -; merged: 10:42; result: -
- lane.rootclean1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #970; merged: 10:38; result: -
- lane.x1port1012 -- issue: #939 Halo: Combat Evolved (4D530004): the ring world on the main menu flickers in and out on the Nova; #938 Halo: Combat Evolved (4D530004): speech is much quieter than music and effects on the Nova; PR: #965; merged: 07:45; result: This session's work is done and the lane is at a genuine stopping point.
- lane.docsrewrite1012 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #967; merged: 01:52; result: -
- lane.issuemirror1013 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #968; merged: 01:52; result: Lane work is complete and pushed.
- lane.docsfresh1012 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #964; merged: 01:35; result: Confirmed: `origin/lane/docsfresh1012` is at the same sha as local HEAD.
- lane.compatpage1012 -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #966; merged: 01:09; result: Pushed successfully.

</details>

States from units, dispatch/queue, running and hold, PR state and labels, territory.toml and nv2a_issues.toml on origin/board, logs/lane, and for the two sessions their GitHub comments. The board's free-text blocker is detail only. Timer jobs are in the Automation box (4).

## 3. What needs a person?

1. owner 2026-09-29 13:06 PDT -- WSL restart needed: sync wedged since ~07:48 PDT, 254 leaked D-state processes UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
2. owner 2026-09-29 15:55 PDT (hostops) -- 258 stuck D-state `sync` processes: root cause found, growth stopped, clearing existing ones needs an owner-scheduled WSL restart UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
3. owner 2026-09-29 20:18 PDT (hostops) OWNER HANDS, URGENT: the GitHub account jreinach-alt is suspended. UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
4. owner 10-01 10:10 PDT (hostops) tick: gh-auth still owner hands, reconfirmed 403/suspended again UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
5. owner 10-01 12:10 PDT watchdog: ops tick silent 59 min; restarted (logs/hostops/watchdog.log) UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
6. owner 10-01 16:08 PDT (hostops) tick: gh-auth still owner hands, reconfirmed 403/suspended again (`gh api user` retried once, identical "Sorry. Your account was suspended"; `git fetch origin` rc=0 via the offline-git redirect, read access unaffected). ~2629 min (~43.8h) into the outage since 09-29 ~20:18 PDT. No new lever. [gh-auth]/[lanes]/[0.5]-offpolicy-skip trio unchanged, same cascade, not re-opening (10th reconfirm). UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
7. owner 2026-10-01 21:35 PDT (hostops) PROCESS FIX, root-caused this tick: `[escalations]` violation UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
8. owner 10-02 06:53 PDT (hostops) tick: OWNER-LEVEL CALL, new -- [lane.routerca433]'s CAPA (docs/lanes/routerca433/CAPA.md, OUTBOX.md on origin/master as of this fast-forward) confirms and quantifies the exact gap the owner flagged 09-30 ([[playable-needs-frame-review]]: "look at the frames before counting any pass") at pipeline scale, not a single title: of 9 title-verdict PASSes it could check by frame, 4 sat on a menu/name-entry screen for the whole 600 s window (incl. two Castlevania runs and Super Monkey Ball); 10 of the 11 accepted titles have no frame past their first moment of play; the screen-aware driver (drive.py/lane.snapdrive's fix) has never completed a dispatched request. This bears directly on the 0.5 gate's "50 Playable" count (#433) -- an unknown fraction of titles counted Playable may not have been seen playing. The CAPA's own ranked recommendations (C1-C9) and three explicit owner decisions (D1: what counts as "live play" -- it proposes >=90% of the window in a responsive gameplay scene, not menu/load/cutscene; D2: cold boot vs savestate start for the judged window; an API budget for a vision-model screen-reading fallback, ~$1/title estimated) read as changing the Playable-count verification bar, which is explicitly reserved to the owner (not mine to decide per the standing authority: "changing the owner's bars"). Retired [lane.routerca433]'s board row this tick (PR folded, analysis-only, unit inactive -- routine, not escalated) but am NOT acting on C1 (re-reviewing/withdrawing the 4 menu-sitting PASSes) or any of D1/D2/budget myself, since that would retroactively change what "Playable" has meant for the count reported toward #433 so far. SendMessage sent to lane-local naming this file and CAPA.md directly so it reaches the owner without waiting on gh-auth (OUTBOX.md's #433 entry is also ready to post once GitHub is back). Not a new instance of the standing gh-auth escalation -- a distinct, one-time finding. UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
9. owner 2026-10-02 09:52 PDT (hostops) OWNER, Windows side: C: has 17 GB free again (1.9 TB drive, 100% used; df /mnt/c). Same recurring issue as 09-27 07:27 PDT (WSL VHDX + pagefile both grow on C:, resolved then by freeing space in a restart window to 98 GB free) -- it has refilled since. Nothing fixable from WSL (sudo unavailable here, Linux / has 632 GB free so nothing here shrinks the VHDX). Needs a Windows-side restart-window action per the same options as before: (1) wsl --shutdown then wsl --manage Ubuntu --set-sparse true or Optimize-VHD, (2) wsl --manage Ubuntu --move D:\\WSL, (3) free space elsewhere on C:. Flagging now rather than waiting for a 3-tick persistence count since this is owner-hands by nature (Windows side) and was already escalated once before under the same shape. UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
10. owner 13:29 PDT [hostops] lane.local unreachable; three items for it UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
11. owner OPEN 10-04 13:52 PDT (hostops, jam duty) THOR DISPLAY 0 COVERED: com.odin.dualscreen.assistant's full-screen BOOT_PROGRESS window 'primaryScreenTopLayout' (pid 2894) covers display 0 on bdc158a5 and has since the Thor's boot at 08:19 PDT. Every queued Thor run is refused ("display-covered ... nothing was started"): 1-1791146962-hostops-1377534 and 1-1791147029-hostops-1421890 (the libfolders head smoke, which the fold of lane/libfolders needs). What I tried: dual_screen_display_mode=0 (already the REST value, set 13:5x; the overlay stayed), KEYCODE_WAKEUP (overlay stayed focused), back to KEYCODE_SLEEP. NOT TRIED: force-stop of com.odin.dualscreen.assistant -- an OEM system app on the owner's device, and the 10-03 entry asked the owner for "force-stop ok" with no answer on file. ASK (owner): OK to `am force-stop com.odin.dualscreen.assistant` on the Thor (it restarts itself), or the owner clears it by hand. Then hostops re-queues the libfolders head smoke and the fold proceeds. Until then libfolders stays WAITING and the Thor cannot take titles. UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
12. owner OPEN 10-04 14:09 PDT (hostops, jam duty) RELAY to lane.local: lane.vcpusleep is WAITING on host capture simp2 (the B arm, #507), which only lane.local can run. Command: `APK_REF=c2dfca18a1 PATHFIND_TREE=&lt;lane/pathfind checkout> bash docs/lanes/vcpusleep/capture_simpsons_offcpu.sh simp2`, once dispatch/builds/c2dfca18a1.apk exists. It is not built yet: the B pixel arm 1-1791146995-vcpusleep-fix-1400786 builds it, and both pixel arms are queued on the Nova behind pathfind's hold (since 13:46 PDT). Hostops did not run it: the capture needs the Nova, and the Nova is held by lane.pathfind's live screening. SendMessage to lane-local is unreachable, so this line is the channel. UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
13. owner OPEN 10-04 14:09 PDT (hostops, jam duty) RELAY to lane.local, owner-level: the #303 Thor arm (lane.fmv303c) is refused by the same display-cover on display 0 as the libfolders head smoke (com.odin.dualscreen.assistant, primaryScreenTopLayout, still present at 14:08). The lanewaker ask is "clear the AYN overlay, or let the guard accept a top-screen soak". Hostops has not force-stopped the OEM assistant: owner OK is still pending (see the 13:52 OPEN above). UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
14. owner Spikeout USA push: the waiter had died again (no process since 13:28). Restarted detached at 14:09 PDT as pid 1690435; log logs/hostops/spikeout-usa-push.log. The Nova is held by lane.pathfind, so it waits. UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
15. owner OPEN 14:52 PDT (hostops, jam duty) RELAY to lane.local, owner-level: [lanewaker] owner hangwatch (14:49): choose how the supervised Whiteout HANG confirmation runs: (1) hold.sh take nova + direct pathfind.py run, as lane.pathfind did, or (2) a pathfind mode in request.sh (toolsmith). Hostops does not answer this for the owner. Lane.hangwatch was already active (unit running at 14:52, attempt 2, not resumed by hostops); its one Whiteout run waits on this choice (docs/lanes/hangwatch/NOTES.md). UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
16. owner 2026-10-05 09:08 PDT: [hostops] owner order for lane.pmucounters needs lane.local (OPEN) UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
17. owner 09:48 PDT 2026-10-05 [hostops jam duty] Nova queue starved by lane.pathfind's back-to-back holds (OPEN, 3 ticks) UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
18. owner 10:44 PDT 2026-10-05 [hostops jam duty] sports1005 push held the nova and stopped; restart needed (lane.local, OPEN) UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
19. owner 21:48 PDT 2026-10-07 [hostops jam duty] AUTH ALARM recurrence #4: access token expiring, owner /login needed (OPEN, OWNER-LEVEL) UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
20. owner 10-08 11:10 PDT watchdog: last three ops ticks failed; see logs/hostops/digest.log UNVERIFIED: no re-check in the last 2 h (host-tools/escalations.md)
21. host lane.collapse433 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: I've found why Battlefield 2 falls short on the Nova; it is not a collapse. (territory row, no unit, no request, no PR, 10-01 23:27)
22. host lane.defecttriage433 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Matches `docs/lanes/defecttriage433/` exactly, docs-only, no emulator code, no territory/nv2a_issues edits. (territory row, no unit, no request, no PR, 09-30 10:47)
23. host lane.framereview has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: retro-tron has finished and I reviewed it: REJECT. (territory row, no unit, no request, no PR, 10-04 22:10)
24. host lane.gpuclock has no session, nothing on a device and is not parked (PR #827 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: The lane is waiting again, this time on four new Nova runs, the Simpsons host session and the profile.c grant. (territory row, no unit, no request, PR #827, 10-05 16:13)
25. host lane.holdfollow1013 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. (territory row, no unit, no request, no PR)
26. host lane.issuemirror1012 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Everything is confirmed pushed and matches. (territory row, no unit, no request, no PR, 10-12 22:51)
27. host lane.nfsroute1011 has no session, nothing on a device and is not parked (PR #929 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Comment posted. (territory row, no unit, no request, PR #929, 10-11 16:37)
28. host lane.pathfindhold1012 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. (territory row, no unit, no request, no PR)
29. host lane.playsecs1013 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. (territory row, no unit, no request, no PR)
30. host lane.routefix1002 has no session, nothing on a device and is not parked (PR #683 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: The Gunvalkyrie v5 route is ready, but it is in no live queue yet. lane.local has to change one line before Star Wars III (`1791045669`, queued now) finishes, or the Nova will run the old route instead. (territory row, no unit, no request, PR #683, 10-03 10:17)
31. host lane.selftestclean1011 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Good progress — shards 1-3 are well into their fragment lists; shard 0 is stuck on the heavy `20-arms-queue.sh` (413s and counting). (territory row, no unit, no request, no PR, 10-11 16:23)
32. host lane.selftestshard has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: `jobs selftest` now runs as four parallel jobs instead of one. (territory row, no unit, no request, no PR, 09-27 22:21)
33. host lane.toolsmith has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: I've fixed the libfolders pref problem from the 10-04 addendum, and the work is pushed to `lane/toolsmith` with `State: ready`. (territory row, no unit, no request, no PR, 10-04 16:02)
34. host lane.verdict433 has no session, nothing on a device and is not parked (PR #653 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Summary Session 19 picked up where session 18 left off (which had finished cleanly and parked with nothing outstanding — the resume was the harness's normal idle-lane pickup, not a stall). (territory row, no unit, no request, PR #653, 10-01 21:11)

Listed: the owner's open decisions (host-tools/escalations.md, issues labelled decision-needed), then the alarms no job handles: a stranded lane, a device idle with runnable work, a hold past its end, a run past twice its expected time, a stale device watchdog, a title issue open with nothing in flight and no job to pick it up, a failing gate on the candidate, CI red on master, a failed timer. Not listed: owned or in-flight work, a file wait, parked work, a queue that is long because both devices are busy.

## 4. Are the machines healthy?

**Thor** in use by lanelocal-offline: OUT OF SERVICE (owner 10-12 ~23:50 PDT; owner 10-13 ~08:05 PDT: "temporarily disabled. Maybe 2 weeks for the parts to come in", so ~10-27 at the earliest): the owner took the Thor offline until the replacement hardware (fan) arrives. Nothing runs on it, nothing is pushed to it; hakux-thor-coldconfirm, -fanwait and -suites are stopped (-suites also disabled 10-13). Titles only on the Thor count as not on hand: they are re-staged from the console for the Nova. lane.local releases this hold only when the owner says the Thor is back. Since 23:57, until no end time stated · watchdog: **absent** since 20:33 (dispatch/hold/thor.why)

last hour: 0 running, 0 hands-on, 0 waste (idle-waiting + held-idle + overdue)

**Nova** in use by lanelocal-ownerplay: owner testing untested titles tonight 10-13 from ES-DE, attach-only capture by ownerplay.py watch. Since 21:18, until no end time stated · watchdog: **resting** since 21:19 (dispatch/hold/nova.why)

last hour: 0 running, 0 hands-on, 0 waste (idle-waiting + held-idle + overdue)

**Queue:** no queue: the devices are not the constraint. 0 queued, 0 of them 0.6 work; no idle-tier sweep is queued. Estimated drain: nothing to drain.

dispatch/queue and running; durations estimated: a title run its seconds + 8 min, a suite run 5 min + 1.5 min per suite.

**Console:** plug meter ON, 66.5 W (read 0s ago). Title push: 88 of 20 titles pushed in batch-xbox-20261003.tsv, the last at 10-03 18:45.

### Automation

- arms -- last run: 10-13 23:48; next run: running now; last outcome: queue host:selftest-badkey.json: selftest #1 a=510dacff37 b=07937793af suites=[Blend surface] runs=1
- authwatch -- last run: 10-13 23:47; next run: 10-13 23:52; last outcome: -
- autoverdict -- last run: 10-13 23:48; next run: 10-14 00:03; last outcome: -
- board -- last run: 10-03 06:50; next run: no timer; last outcome: This tick cleared the one FAIL: `greensize303` is now on the board, and the fleet check no longer reports it.
- cloud -- last run: 09-29 19:54; next run: no timer; last outcome: finish: #627 moved past needs-audit-2 and carries no claimed:cloud, so an earlier finish already cleared it; this one changed nothing
- defrag -- last run: 10-13 23:50; next run: 10-13 23:52; last outcome: -
- devwatch -- last run: 10-13 23:50; next run: 10-13 23:51; last outcome: -
- driver -- last run: 10-13 23:47; next run: 10-13 23:52; last outcome: -
- dx -- last run: 10-13 09:23; next run: 10-14 09:23; last outcome: -
- failintake -- last run: 10-13 23:50; next run: 10-14 00:00; last outcome: -
- fold -- last run: 10-03 08:19; next run: no timer; last outcome: tick: repaired none; folded none; handed back none; waiting none
- foldqueue -- last run: 10-13 23:44; next run: 10-13 23:59; last outcome: -
- forge-prsync -- last run: 10-13 23:48; next run: 10-13 23:54; last outcome: -
- forge-sync -- last run: 10-13 23:50; next run: 10-13 23:51; last outcome: -
- github-gateway -- last run: 10-13 23:45; next run: 10-14 00:00; last outcome: -
- handback -- last run: 10-03 08:22; next run: no timer; last outcome: nothing handed back (needs-rebase draft-strand-arm draft-strand-runs draft-strand-idle draft-strand-quiet idle-no-pr merged-runs)
- hostops -- last run: 10-13 23:48; next run: 10-14 00:08; last outcome: Tick complete.
- hourly -- last run: 10-13 23:45; next run: running now; last outcome: -
- idlewatch -- last run: 10-13 23:50; next run: 10-14 00:00; last outcome: -
- issue-mirror -- last run: 10-13 23:47; next run: 10-13 23:57; last outcome: -
- issue-sweep -- last run: 10-02 07:41; next run: no timer; last outcome: gh returned nothing for the open issue list; this tick is blind and writes nothing
- issue-sync -- last run: 10-13 23:50; next run: 10-14 00:00; last outcome: -
- jamcheck -- last run: 10-13 23:50; next run: 10-14 00:00; last outcome: -
- lanewaker -- last run: 10-13 23:47; next run: 10-13 23:52; last outcome: -
- local-board -- last run: 10-13 23:42; next run: 10-14 00:03; last outcome: lanes: 0/10 units running; ready 2 (blocked 0, waiting 0); draft-strand 8; other 20; report ~/hakux-work/status/local-board.md
- local-issue-audit -- last run: 10-13 19:41; next run: 10-14 07:41; last outcome: -
- manifest -- last run: 10-13 23:45; next run: 10-14 00:00; last outcome: -
- nightly -- last run: 10-13 00:30; next run: 10-14 00:30; last outcome: -
- ops-shadow -- last run: 10-13 23:47; next run: 10-13 23:52; last outcome: -
- pathfix -- last run: 10-13 23:47; next run: 10-13 23:52; last outcome: -
- pr-sweep -- last run: 10-02 09:13; next run: no timer; last outcome: gh returned nothing for the open PR list; this tick is blind and repairs nothing
- prune -- last run: 10-13 17:43; next run: 10-13 23:51; last outcome: -
- stallwatch -- last run: 10-13 23:50; next run: 10-14 00:00; last outcome: -
- tmpclean -- last run: 10-13 23:37; next run: 10-14 00:37; last outcome: -
- usage-meter -- last run: 10-13 23:46; next run: 10-14 00:16; last outcome: -
- xbox-keepalive -- last run: 10-13 23:17; next run: 10-14 00:17; last outcome: -
- fold -- last run: not recorded; next run: no timer; last outcome: a standing board row; it runs when the board dispatches it
- triage -- last run: not recorded; next run: no timer; last outcome: a standing board row; it runs when the board dispatches it

details

#### Window budget (the account's five-hour and weekly windows)

- dispatching normally. Lanes and audits start as work allows; expanding is the default.
- week from 2026-10-08 21:00 PDT (73% elapsed, reserve from 2026-10-14 11:24 PDT), 157 run(s), spend 991.9 of no declared budget, 0 usage-limit hit(s) this week (0 in the reserve).
- no session has ever been refused by the account's window on this host. That is the only first-hand evidence of a closed window there is: **the remaining five-hour and weekly balance cannot be queried from here**, so the weekly reserve arms on that evidence, or on `WEEK_SPEND_BUDGET` if the owner declares one in `$WORK/limits.env`. Unknown means open, by design.

#### Lane sessions finished (last 24h)

| when (PDT) | lane | model | turns | min | result | PR | said |
|---|---|---|---|---|---|---|---|
| 10-13 00:12 | compatpage1012 | sonnet-5 | 197 | 43 | ok | #966 merged | Pushed successfully. Head sha: `6915999ce7`. |
| 10-13 00:34 | x1port1012 | opus-5-5 | 301 | 36 | MAXTURNS | #965 merged |  |
| 10-13 00:57 | issuemirror1013 | sonnet-5 | 157 | 28 | ok | #968 merged | Lane work is complete and pushed. |
| 10-13 06:20 | x1port1012 | sonnet-5 | 74 | 9 | ok | #965 merged | Both comments posted. |
| 10-13 07:26 | x1port1012 | sonnet-5 | 86 | 11 | ok | #965 merged | This session's work is done and the lane is at a genuine stopping point. |
| 10-13 09:43 | pathtele1013 | sonnet-5 | 139 | 44 | ok | #972 merged | PR #972 opened, ready (both Part A and Part B complete, selftest passes, PR.md already states `State: ready`). |
| 10-13 11:03 | forgealloc1013 | sonnet-5 | 247 | 56 | ok | #977 merged | All five tasks (#433) are now complete and pushed. |
| 10-13 11:56 | pathrules1013 | sonnet-5 | 269 | 73 | ok | #979 merged | - |
| 10-13 14:13 | holdinput1013 | sonnet-5 | 243 | 69 | ok | #981 merged | - |
| 10-13 15:24 | hangstall1013 | sonnet-5 | 77 | 15 | ok |  | Done. `lane/hangstall1013` is pushed and ready for `forge_prsync.py` to open the PR. |
| 10-13 16:53 | holdinput1013 | sonnet-5 | 190 | 155 | ok | #981 merged | Lane `holdinput1013` is done and pushed. |
| 10-13 22:20 | statuspage1013 | sonnet-5 | 301 | 116 | MAXTURNS | #985 merged |  |

_result: ok = ended on its own; MAXTURNS = cut at the turn cap, work kept; ERR = the session errored. A lane that ended without a ready PR is resumed by the board (attempts 1-3 on opus, then fable, then decision-needed)._

#### Cloud-class sessions (hourly, on the host; last 24h from their `[job.cloud]` comments)

none. cloud.sh runs hourly and claims one `needs-audit-*` PR or one `cloud` issue per tick; a tick with nothing to claim leaves no comment.

- running now:

```
09-29 17:29 cloud-audit2-622 claude-sonnet-5 turns=29 149s ok needs-audit-2 removed, fold-ready added, review posted, pass-2 audit pushed. Not
09-29 19:13 cloud-audit1-627 claude-opus-5-5 turns=12 92s ok I finished pass 1 of the audit on PR #627 and moved it to `needs-remediation`: I
09-29 19:34 cloud-remediate-627 claude-opus-5-5 turns=18 146s ok PR #627 is fixed and back in the audit queue: its label went from `needs-remedia
09-29 19:54 cloud-audit2-627 claude-sonnet-5 turns=24 125s ok Pass 2 of PR #627 (hddperm) is done: all four pass-1 findings (M1, L1, L2, L3) v
```

#### Board job (every 20 min)

```
2026-10-03 07:30:15 PDT nothing actionable (0/10 lanes, no startable issue, no unlabelled ready PR)
2026-10-03 07:50:40 PDT NOTE: ~/hakuX (the unit's ExecStart path) is 120 commit(s) behind origin/master; re-execing the trunk's copy. Run: git -C /ho
2026-10-03 07:50:43 PDT nothing actionable (0/10 lanes, no startable issue, no unlabelled ready PR)
2026-10-03 08:11:15 PDT NOTE: ~/hakuX (the unit's ExecStart path) is 129 commit(s) behind origin/master; re-execing the trunk's copy. Run: git -C /ho
2026-10-03 08:11:18 PDT nothing actionable (2/10 lanes, no startable issue, no unlabelled ready PR)
2026-10-10 06:38:08 PDT NOTE: ~/hakux-work/board-wt had 121 uncommitted path(s), which this private mirror of origin/master must never hold; somethin
```

last model ticks:

```
10-02 18:08 board claude-sonnet-5 turns=78 213s ok My commit only touched `territory.toml`, confirmed clean. The large MM/AD diff i
10-02 18:28 board claude-sonnet-5 turns=50 141s ok The FAIL line is gone — the fleet report now runs clean (apart from the gh-suspe
10-03 06:50 board claude-sonnet-5 turns=31 58s ok This tick cleared the one FAIL: `greensize303` is now on the board, and the flee
```

board branch: 6357976142 25 minutes ago -- territory: retire statuspage1013 (folded 2c06371519), claim statusfix1013

#### Handhelds and arms

- adb: ee317437(device)
- dispatcher: active, workers: 1
- queue: 0 waiting, 0 idle-tier z-\* behind them, 0 running; holds: nova thor
- dispatcher last line: `10-13 23:56:38 HELD by ~/hakux-work/dispatch/hold/nova; claiming nothing until it is removed`
- affinity: lanes serving `desktop` -- an A/B pair queued now is pinned to one of them
- arms job: 122 pair(s) queued or running and not yet judged; 118 judged; 252 skipped (see `arms.sh list`); watermark 2026-09-18 13:00 PDT (stored as `2026-09-18T20:00:00Z`: arms.sh compares that UTC string to registered_utc, so the file stays UTC and only this rendering is local)

last verdicts:

- `9715a5a775` lane/async794:docs/testing/predictions/async794-fix2-must-not-move.json: VERDICT: PASS -- all 267 registered checks hold.
- `5a9978ab62` lane/async794:docs/testing/predictions/async794-download-paths-must-not-move.json: VERDICT: PASS -- all 267 registered checks hold.
- `388ea55c4b` lane/forzadecay414-fix:docs/testing/predictions/forzadecay414-fix-pixels2.json: VERDICT: FAIL -- 37 of 3363 checks violated:
- `fbed11c3e7` lane/tcg424flip:docs/testing/predictions/tcg424flip-pgraph.json: VERDICT: FAIL -- 41 of 3379 checks violated:
- `9996bfedbb` lane/memfast:docs/testing/predictions/memfast-drop-pixels-stable.json: VERDICT: FAIL -- 36 of 3167 checks violated:

```
2026-10-12 07:14:36 PDT   skip eb30dbad227e76d2ec45886f26af3eafdb5e0d1c2de3d78fdfdd29b274062bf4: master:docs/testing/predictions/fpsbelow1012-vtxexact.json: a_r
2026-10-12 10:24:44 PDT   skip 835673a625df5d7ddb3c831c3b7a1e19ab0d8821e47f73bf3c59cdd3757699a0: lane/zetaroutes1012:docs/testing/predictions/zetaroutes1012-buf
2026-10-12 11:28:28 PDT   skip c26b9a5aedd361581fa8e5114a1d0081da2602d173c731c1ef58b27273a427c3: lane/zetaroutes1012:docs/testing/predictions/zetaroutes1012-nin
2026-10-12 12:31:29 PDT   skip a54889126de7f92e9bac06a8acd3a5f96affb43a4e2976d2e163cb266c1d3089: master:docs/testing/predictions/zetaroutes1012-doa3.json: a_ref
```

last refusals, in full (a refusal is recorded once; delete the file under `$WORK/arms/skipped/` to retry):

- `a54889126d` master:docs/testing/predictions/zetaroutes1012-doa3.json: a_ref == b_ref, nothing to compare

told=2026-10-12T19:31:29Z

- `c26b9a5aed` lane/zetaroutes1012:docs/testing/predictions/zetaroutes1012-ninja-gaiden-black.json: a_ref == b_ref, nothing to compare

told=2026-10-12T18:28:28Z

- `835673a625` lane/zetaroutes1012:docs/testing/predictions/zetaroutes1012-buffy.json: no suite with goldens in its keys or disc

told=2026-10-12T17:24:44Z

#### Fold job (every 30 min)

- fold-ready: ; needs-rebase: ; needs-remediation:
- awaiting audit: needs-audit-1 ; needs-audit-2

```
2026-10-03 06:48:21 PDT tick: repaired none; folded none; handed back none; waiting none
2026-10-03 07:18:33 PDT tick: repaired none; folded none; handed back none; waiting none
2026-10-03 07:48:38 PDT tick: repaired none; folded none; handed back none; waiting none
2026-10-03 08:19:11 PDT tick: repaired none; folded none; handed back none; waiting none
```

- master: 2c06371519 60 minutes ago -- fold: lane/statuspage1013 (offline) -- status page: track 0.6, 1.0 projection chart, drop B

#### Open lane PRs

- #987 `lane/statusfix1013` status: Playable is the ledger; chart 1 marks when 0.5's targets were met -- labels: none
- #969 (draft) `lane/x1port1012-halo` x1port1012-halo: #939 ring-world leads (triage in progress) -- labels: none
- #942 (draft) `lane/routedriver2` routedriver2 session 2: Buffy's menus made robust, the ledge gap diagnosed (#433) -- labels: none
- #929 (draft) `lane/nfsroute1011` nfsroute1011: NFS Most Wanted -- routes that check the screen, and a saved profile (#433, 0.5) -- labels: none
- #827 (draft) `lane/gpuclock` lane.gpuclock (#433): is the GPU clock-limited? GPU ms per frame against the Adreno clock, per title -- labels: none
- #824 `lane/alwaystelemetry` alwaystelemetry: perflog costs ~1.2 ms/frame of render thread (+30% CPU); design the always-on tier (#433) -- labels: folded
- #792 (draft) `lane/memfast` lane.memfast F1: guest loads through the host MMU ("fastmem"), behind HAKUX_FASTMEM, default off (#507) -- REJECTED, not for fold -- labels: none
- #683 (draft) `lane/routefix1002` routefix1002: three route checks for the overnight Nova queue (#433) -- labels: none
- #673 (draft) `lane/tronhang672` tronhang672: Tron 2.0 hangs entering the first level (Nova) -- labels: none
- #653 (draft) `lane/verdict433` lane.verdict433: measurement pass for #433 (0.5: 50 Playable) -- labels: none
- #652 (draft) `lane/titleroutes2` titleroutes2: per-title routes and surveys on the Nova, successor to lane.titleroutes (#397) -- labels: none
- #643 `lane/hddcrash` hddcrash: titles disk mode 660; a request's HAKUX_TITLES_DISK wins (#397) -- labels: folded

#### Job errors (last 24h, from the units' logs)

none seen.

#### Host

- checkout `~/hakuX` on master, 0 behind origin/master (jobs run the fetched trunk regardless)
- timers: arms next -; authwatch next 23:57:59 PDT; autoverdict next 00:04:01 PDT; defrag next 23:58:00 PDT; devwatch next 23:58:30 PDT; driver next 23:57:59 PDT; dx next 09:23:00 PDT; failintake next 00:00:45 PDT; foldqueue next 23:59:28 PDT; forge-prsync next 23:59:46 PDT; forge-sync next 23:57:57 PDT; github-gateway next 00:00:08 PDT; hostops next 00:08:00 PDT; hourly next 00:45:00 PDT; idlewatch next 00
- attempts: aasample=3 accuracy804=4 adpf=2 affinitybacklog=2 alwaystelemetry=1 armlabel=1 armpin=1 armsflake=1 armsrequeue=1 armsscope=1 armsskip=3 async413=1 async794=1 aufdispatch=1 aufire412=2 aufire412b=2 backlogstate=3 battadmit=2 belowbar1005=1 bf2push656=1 bf2stall433=1 bf2ubosize433=2 blankrule297=2 blendarm50=1 blendrace50=2 blinx2input=2 blinx372=1 blinx372b=1 blinx372c=2 blinx372d=1 blinx372e=2 blit83b=1 blit84=1 blitsafe=2 boardgate=4 boardgateenv1009=1 boardprio=3 boardpushgate=1 boardtreeheal=1 boardwt-checkout-selfheal=1 branchprune=2 brdf315=1 brdf315b=1 buildflags427=1 buildstamp=1 burnoutbrief1012=2 burnoutloop1012=2 burnoutunlock1012=1 ciskip=1 claimrace=2 cloud-audit1-181=1 cloud-audit2-163=1 cloud-audit2-308=2 cloud-issue-10=1 cloud-issue-111=1 cloud-issue-112=1 cloud-issue-13=1 cloud-issue-188=3 cloud-issue-189=1 cloud-issue-200=2 cloud-issue-271=2 cloud-issue-278=1 cloud-issue-279=1 cloud-issue-282=3 cloud-issue-283=1 cloud-issue-284=4 cloud-issue-286=1 cloud-issue-297=1 cloud-issue-34=1 cloud-issue-527=1 cloud190=1 cloudclaim=1 cloudlaneguard=2 cloudtail=1 cloudterritory=1 clrpad164=2 clrsurf91=3 clrvk184=1 clrwb91=4 clrwin88=1 coldstart1010=1 collapse433=1 compatpage1012=1 crashattr=2 cull13=1 cullnf276=2 dash432=2 defecttriage433=1 desktopchannel=2 diagdump77=2 diagsoak77=1 dirtytlb=3 dispatchgate1006=2 dispatchguard=1 displayguard=3 dispsuper=1 dmasurf277=1 doa413=1 doa413b=3 doa413c=1 docsfresh1012=1 dpforce345=2 draftstrand=3 drain474=2 drawrec1010=4 drvab77=1 energymap507=2 escalationparse=1 escitems=1 failgate=3 fanduty507=4 fastpaths1010=1 fgrace1010=1 fgunknown=1 fix311=1 flatlm13=1 fleetabsent=1 fleetflush1010=1 fleetreg=2 fleetstanding=1 flicker801=1 flip474=4 flushstall787=2 fmv303=1 fmv303b=2 fmv303c=1 focusanr=1 fog278=1 foldcancel=1 foldci=3 foldflow=2 foldindex=1 foldregress=2 forgealloc1013=1 forza414=2 forzaclock=1 forzadecay414=2 forzasurf1010=4 fps20786=1 fps382=1 fpsbelow1012=1 fpsshare=1 fpstelemetry1008=4 fpstelemetry1008b=3 framereview=1 frametrace=2 fulldisc50=1 g8b8285=1 gamecheck=1 ghoul311=4 glchannel=1 glerr86=1 gmem474=1 goldencorr287=1 goldens782=1 goldovr287=1 gpl569=3 gpuclock=3 gpunonrender=2 gpupass1010=2 greensize303=1 gta482=4 gtaroutes1011=4 gtasagpu1011=1 gtawedge1012=1 handback=3 handbackbranch=1 handbacklane=1 handbackmerged=1 handbackpark=1 handbackresolved=1 handbackstrand=1 handbackwaiter=1 hangstall1013=1 hangwatch=3 harnessfix1006=3 hddcrash=4 hddperm=3 hddsplit=1 hilodot10=1 hitchcause=1 hitchwatch=1 holdfollow1013=1 holdinput1013=2 holdlease=2 holdtake=1 holdwait=1 ibcache=2 idlehalt=3 idlehaltdefault=3 idlehaltspin=1 indexcheck=1 indexloc=2 inflightpark=1 isoroots=1 issuemirror1012=1 issuemirror1013=1 issuerecon=1 issuesweep=1 jcache425=1 kabukistall=2 lanenobg1010=2 lanepath1009=2 laneshape=1 libfolders=2 linecap13=2 litcompile569=2 localforge=4 localjobs=1 localtime=1 lockwake1011=1 measured05=1 memfast=1 meterfit1010=2 modelpolicy1010=2 nanattr281=1 nanfix281=1 near30=4 nfs30plan1010=2 nfsaudio1011=3 nfsdefault1011=4 nfsframe1010=3 nfsroute1011=2 nightlynotes=3 nightlynotes1009=3 nightlytrunk=1 nightlywrap1010=1 notespath=1 notify488=3 opsrebuild=1 pacing=1 pathclass=1 pathfind=2 pathfindhold1012=1 pathknow=1 pathrules1013=1 pathtele1013=1 perdraw1009=4 perfarch=2 perfbase=1 perfregimen=2 pfifowait1009=3 pilotgate=3 pipeline413=2 playsecs1013=1 pmc188=3 pmucounters=1 postput1010=2 pri432=2 primpv13=4 profileconv1011=3 profileddefault1008=4 profilegate1011=3 pshaniso284=2 pshqueue=3 rankrule=1 regs200=1 relnote=1 relprio432=1 remotechannel=1 rendermode474=1 reportasync1010=1 reqprio=1 restoreleak1009=3 restoreprio1011=4 retreason425=1 ring53=1 ring53impl=3 routedriver=4 routedriver2=3 routefix1002=4 routeprep=1 routerca433=1 savestate1011=4 savestate433=4 scoresplit=1 selfdeps=4 selftest86=1 selftestclean1011=1 selftestshard=2 selftestsplit=2 shade224=1 shadeflat224=4 shaderfb569=2 shaderplan569=1 shaderprebuild569=4 shadetie224=1 shadetie224b=2 slowdown462=3 slowtier2=3 snapdrive=1 snapshot1011=2 soakflake=1 soakvideo1011=2 sphere273fix=1 spheremap273=1 stalecheck=2 stallmeasure569=1 statusdash=1 statusfresh=1 statusguard=1 statuspage=1 statuspage1013=1 statuswindow=1 stopmarker=1 stuckdetect1007=1 suffixpr=1 surfdl1008=3 surfgpu1009=3 surfgpudefault1009=3 surfwatch382=1 sustain507=2 swatchorder50=1 sweepclock=1 sweepcover=2 sweepremote=1 sweeps=1 swizzle87=1 tbchurn424=1 tbflip424=1 tbsize429=1 tcg424flip=4 tcgchurn=2 texscan1010=2 texvol283=1 thermal507=2 thorbottom800=2 thorheat=1 tie282c=1 tiecode282=2 titleplay=1 titleroutes=4 titleroutes2=2 titlerun=3 titles05=3 titlestate=1 tokentier=1 toolsmith=2 tronhang672=1 turncap=1 turnipcost569=1 turnipfork=2 uberdefault569=1 uberspike569=2 usage24h1009=1 usagemode=1 usagerule1010=1 usbdialog=1 vblank65=1 vcpu60=2 vcpuplan=1 vcpuprime428=2 vcpusleep=3 vcpuwait433=4 verdict10min=1 verdict433=2 visual404=1 vklayer34=1 vkpointsize34=4 vol283r=1 vshconst=3 vshcpu345=1 vshnobegin242=2 vshr12280=1 vshsubneg255=1 vtxarr262=1 waitread1006=1 wbuf31fix=3 wbuf31sel=1 wbufclip=2 wbufdepth24=1 windowbudget=2 wparam223=1 wparamclip223=2 wparamcode223=1 wparamff223=1 wparamgeom223=1 x1a7271=1 x1port1012=3 y16bump10=2 yuv10=1 zclamp276=1 zdepth272=1 zetaroutes1012=4 zetaswap275=1 zrtz272=4

_Written by `docs/testing/jobs/status.sh` on the host every job tick and every 30 min; republished when the content changes (at most every 10 min) and at least every 30 min. Every time here is PDT. Next tick due by 2026-10-14 00:20 PDT._

---

The per-title detail and the original layout: [index.svg](https://github.com/jreinach-alt/hakuX/blob/status/index.svg) opens as the full page; [IN-FLIGHT.md](https://github.com/jreinach-alt/hakuX/blob/status/IN-FLIGHT.md) lists the work in progress and recent folds.
