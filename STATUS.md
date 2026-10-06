# hakuX harness

_updated 2026-10-06 04:21 PDT_

1. 0.5: Measured 117 / 145 · Benchmarked 43 / 145 · Playable 27 / 50; gate no candidate is cut yet, so no soak is on the candidate's APK; on the newest soaks it is NOT met.
2. Now: 18 lanes: 13 stranded, 2 waiting on audit, 2 no word in 48 h, 1 waiting on device.
3. Needs a person: 31 items (18 owner decisions).
4. Machines: thor in use by lanelocal-fanwait; nova running; device-bound: 6 runs queued, both devices busy.

## 1. How close is 0.5?

Measured **117** / 145&nbsp;&nbsp;`▓▓▓▓▓▓▓▓░░`

Benchmarked **43** / 145&nbsp;&nbsp;`▓▓▓░░░░░░░`

Playable **27** / 50&nbsp;&nbsp;`▓▓▓▓▓░░░░░`

![Titles over time](chart.svg)

Measured: any gameplay fps reading (the median frame rate in the play window) on either handheld, at any build and mode. Each title is plotted at its first reading (a soak's finish, a verdict, a held run, or the pass-1 review's date). Playable: the Playable ledger, each title at its acceptance (a 600 s held run with every kept frame reviewed).

Ships when both are met. At the last 48 h rate: about 2026-10-23.

Target: 0.5 ships when 145 titles are benchmarked and 50 of them are Playable on the Thor/Nova handhelds (#433).

Decided: owner, 2026-09-26 17:15 PDT ([#433 comment](https://github.com/jreinach-alt/hakuX/issues/433#issuecomment-5851419837)). Read from `release-0.5.toml`.

Pipeline: Copied, Inputs, Save, Bench. ✓ done · – not yet · n/a no profile step. The per-title detail is in index.html.

| Title and next step | Status | fps | C I S B |
|---|---|---|---|
| **Alien Hominid**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Thor · 10-01 · REST | ✓ ✓ n/a ✓ |
| **AMF Bowling 2004**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – ✓ |
| **Baldur's Gate: Dark Alliance**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 09-30 · REST | ✓ ✓ n/a ✓ |
| **Black Stone: Magic & Steel**<br>needs a gameplay route and a save | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-02 · MAX | ✓ – – – |
| **Bruce Lee: Quest of the Dragon**<br>**fix the hang**<br>**blocker: hang: 21.2 s without 60 guest flips after the mark** | 🔴 blocked | **59.9**<br>81% at 28.5+<br>Thor · 09-26 · MAX | ✓ ✓ n/a – |
| **Capcom Classics Collection Vol. 2**<br>**fix the crash**<br>**blocker: crash: guest exited after 390s** | 🔴 blocked | **59.9**<br>100% at 28.5+<br>Thor · 09-30 · MAX | ✓ ✓ n/a – |
| **Castlevania: Curse of Darkness**<br>done | 🟢 Playable | **59.9**<br>97% at 28.5+<br>Thor · 10-01 · MAX<br>Nova 59.9 | ✓ ✓ ✓ ✓ |
| **Guilty Gear XX #Reload: The Midnight Carnival**<br>needs a gameplay route and a save | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Gunvalkyrie**<br>done | 🟢 Playable | **59.9**<br>99% at 28.5+<br>Nova · 10-03 · REST | ✓ – – ✓ |
| **Kabuki Warriors**<br>done | 🟢 Playable | **59.9**<br>95% at 28.5+<br>Nova · 10-03 · REST | ✓ ✓ n/a ✓ |
| **MLB SlugFest 2003**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – ✓ |
| **Ninja Gaiden**<br>**fix the crash**<br>**blocker: reached_gameplay: unconfirmed (generic route) -- review the contact sheet, then rerun with --reviewed-gameplay yes\|no** | 🔴 blocked | **59.9**<br>64% at 28.5+<br>Thor · 09-30 · MAX, soak | ✓ – ✓ – |
| **Petit Copter**<br>needs a gameplay route | 🔵 copied | **59.9**<br>78% at 28.5+<br>Thor · 10-01 · MAX, screen: 90-240 s only | ✓ – ✓ – |
| **Phantom Crash**<br>needs a gameplay route and a save | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-04 · REST | ✓ – – – |
| **RalliSport Challenge**<br>needs a gameplay route and a save | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-04 · unrecorded | ✓ – – – |
| **Sonic Heroes**<br>**fix the crash**<br>**blocker: crash: guest exited after 247s** | 🔴 blocked | **59.9**<br>100% at 28.5+<br>Thor · 10-01 · MAX | ✓ ✓ n/a – |
| **Spikeout: Battle Street**<br>done<br>#303 open · nothing in flight | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 10-03 · unrecorded | ✓ ✓ n/a ✓ |
| **Strike Force Bowling**<br>needs a gameplay route and a save | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Whacked!**<br>**fix the crash**<br>**blocker: reached_gameplay: unconfirmed (generic route) -- review the contact sheet, then rerun with --reviewed-gameplay yes\|no** | 🔴 blocked | **59.9**<br>66% at 28.5+<br>Nova · 10-04 · REST | ✓ – – – |
| **World Soccer Winning Eleven 9**<br>needs a gameplay route and a save | 🔵 copied | **59.9**<br>100% at 28.5+<br>Nova · 10-06 · unrecorded | ✓ – – – |
| **WWE Raw 2**<br>done | 🟢 Playable | **59.9**<br>100% at 28.5+<br>Nova · 09-30 · REST, soak | ✓ ✓ n/a ✓ |
| **Deathrow**<br>needs a gameplay route | 🔵 copied | **59.9**<br>100% at 28.5+<br>Thor · 09-30 · MAX, screen: 90-240 s only | ✓ – ✓ – |
| **LEGO Star Wars: The Video Game**<br>needs a gameplay route and a save | 🔵 copied | **59.9**<br>98% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **RalliSport Challenge 2**<br>benchmark at MAX | 🟣 inputs ready | **59.9**<br>74% at 28.5+<br>Thor · 09-28 · MAX, screen: 90-240 s only<br>Nova 59.9 | ✓ ✓ n/a – |
| **Tony Hawk's Pro Skater 3**<br>**fix the crash**<br>**blocker: crash: guest exited after 205s** | 🔴 blocked | **59.9**<br>100% at 28.5+<br>Thor · 10-01 · MAX, soak | ✓ ✓ n/a – |
| **Tony Hawk's Pro Skater 2x**<br>done | 🟢 Playable | **59.8**<br>100% at 28.5+<br>Thor · 10-01 · MAX<br>Nova 59.8 | ✓ ✓ n/a ✓ |
| **MLB SlugFest: Loaded**<br>done | 🟢 Playable | **58.9**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – ✓ |
| **Rogue Trooper**<br>needs a gameplay route and a save | 🔵 copied | **58.9**<br>100% at 28.5+<br>Nova · 10-06 · unrecorded | ✓ – – – |
| **Tron 2.0 - Killer App (USA, Europe).iso**<br>needs a gameplay route and a save | 🔵 copied | **58.9**<br>88% at 28.5+<br>Nova · 10-03 · REST | ✓ – – – |
| **AMF Xtreme Bowling**<br>**fix the crash**<br>**blocker: crash: exiting due to SIG_DFL handler for signal 11, ucontext 0x6fcde81e20** | 🔴 blocked | **58.7**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **MTV Celebrity Deathmatch**<br>done | 🟢 Playable | **57.2**<br>99% at 28.5+<br>Nova · 10-04 · unrecorded | ✓ – – ✓ |
| **Crash Bandicoot: The Wrath of Cortex**<br>20-min soak | soak pending | **57.1**<br>100% at 28.5+<br>Nova · 09-30 · MAX, soak | ✓ ✓ n/a ✓ |
| **NBA 2K2**<br>done | 🟢 Playable | **57.0**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – ✓ |
| **Project Gotham Racing 2**<br>**fix the hang**<br>**blocker: void: thermal-pause: thermal-pause-F8 1/1 began after +140 s and by +172 s (device 09-29 13:22:54); still paused at the last reading, relative to the mark** | 🔴 blocked | **55.7**<br>40% at 28.5+<br>Thor · 09-29 · MAX, screen: 90-240 s only | ✓ ✓ n/a – |
| **Panzer Dragoon Orta**<br>done | 🟢 Playable | **54.1**<br>100% at 28.5+<br>Nova · 10-03 · unrecorded | ✓ – ✓ ✓ |
| **Disney/Pixar Ratatouille**<br>needs a gameplay route and a save | 🔵 copied | **52.8**<br>100% at 28.5+<br>Nova · 10-06 · unrecorded | ✓ – – – |
| **Mortal Kombat: Armageddon**<br>needs a gameplay route | 🔵 copied | **52.6**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – ✓ – |
| **KOF: Maximum Impact - Maniax**<br>re-benchmark at MAX | 🟣 inputs ready | **52.4**<br>99% at 28.5+<br>Nova · 09-29 · REST | ✓ ✓ n/a – |
| **Dead or Alive 3**<br>**fix the crash**<br>**blocker: crash: guest exited after 475s** | 🔴 blocked | **52.2**<br>60% at 28.5+<br>Thor · 09-30 · MAX<br>Nova 30.0 | ✓ ✓ n/a – |
| **Super Monkey Ball Deluxe**<br>**fix the crash**<br>**blocker: crash: guest exited after 250s** | 🔴 blocked | **48.1**<br>100% at 28.5+<br>Thor · 10-01 · MAX | ✓ ✓ n/a – |
| **Dark Summit**<br>done | 🟢 Playable | **45.9**<br>93% at 28.5+<br>Nova · 10-04 · unrecorded | ✓ – – ✓ |
| **NFL Blitz 2002**<br>done | 🟢 Playable | **45.0**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – ✓ |
| **MLB SlugFest 2004**<br>done | 🟢 Playable | **44.4**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – ✓ |
| **ToeJam & Earl III: Mission to Earth**<br>done | 🟢 Playable | **42.1**<br>73% at 28.5+<br>Nova · 10-03 · unrecorded | ✓ – ✓ ✓ |
| **NBA 2K3**<br>needs a gameplay route and a save | 🔵 copied | **41.8**<br>92% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Mortal Kombat: Shaolin Monks**<br>needs a gameplay route and a save | 🔵 copied | **39.9**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Ninja Gaiden Black**<br>needs a gameplay route<br>running 1-1791284834-lane.gpunonrender-3228352 on the nova; queued 1-1791284845-lane.gpunonrender-3230278 #1 | 🔵 copied | **39.4**<br>75% at 28.5+<br>Nova · 10-02 · MAX | ✓ – ✓ – |
| **The Simpsons: Hit & Run**<br>done<br>queued 1-1791285173-lane.gpunonrender-3251320 #3; queued 1-1791285177-lane.gpunonrender-3251434 #4 | 🟢 Playable | **37.9**<br>100% at 28.5+<br>Nova · 10-04 · unrecorded | ✓ – – ✓ |
| **NHL Hitz Pro**<br>needs a gameplay route and a save | 🔵 copied | **37.4**<br>75% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Blood Wake**<br>**fix the hang**<br>**blocker: hang: 10.6 s without 60 guest flips after the mark** | 🔴 blocked | **37.4**<br>30% at 28.5+<br>Thor · 09-27 · MAX<br>Nova 59.9 | ✓ ✓ n/a – |
| **187: Ride or Die**<br>done | 🟢 Playable | **37.2**<br>100% at 28.5+<br>Nova · 10-01 · REST | ✓ ✓ n/a ✓ |
| **Tron 2.0 - Killer App**<br>needs a gameplay route and a save | 🔵 copied | **37.2**<br>98% at 28.5+<br>Nova · 10-04 · unrecorded | ✓ – – – |
| **Top Spin**<br>needs a gameplay route and a save | 🔵 copied | **36.1**<br>96% at 28.5+<br>Nova · 10-04 · MAX, soak | ✓ – – – |
| **25 to Life**<br>needs a gameplay route | 🔵 copied | **35.7**<br>54% at 30+<br>Thor · 09-26 · unrecorded, hand-reviewed | ✓ – ✓ – |
| **007: Nightfire**<br>20-min soak | soak pending | **35.3**<br>94% at 28.5+<br>Nova · 10-05 · MAX, soak<br>Thor **24.2** | ✓ ✓ n/a ✓ |
| **NHL 2K3**<br>needs a gameplay route and a save | 🔵 copied | **35.0**<br>69% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Bistro Cupid**<br>needs a gameplay route | 🔵 copied | **34.4**<br>87% at 28.5+<br>Thor · 09-30 · MAX, soak | ✓ – ✓ – |
| **Dungeons & Dragons Heroes**<br>re-benchmark at MAX<br>queued 1791272941-hostops-2039487-c3a0 #5 | 🟣 inputs ready | **33.8**<br>46% at 28.5+<br>Nova · 10-01 · REST | ✓ ✓ n/a – |
| **Burnout Revenge**<br>re-benchmark at MAX | 🟣 inputs ready | **31.7**<br>72% at 28.5+<br>Nova · 10-01 · REST | ✓ ✓ n/a – |
| **Aliens Versus Predator: Extinction**<br>needs a gameplay route and a save | 🔵 copied | **31.0**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Fuzion Frenzy**<br>**fix the hang**<br>**blocker: hang: 13.4 s without 60 guest flips after the mark** | 🔴 blocked | **30.6**<br>54% at 28.5+<br>Nova · 09-27 · MAX | ✓ ✓ n/a – |
| **Crimson Skies: High Road to Revenge**<br>done | 🟢 Playable | **30.0**<br>95% at 28.5+<br>Nova · 09-30 · REST<br>Thor **23.4** | ✓ ✓ n/a ✓ |
| **50 Cent: Bulletproof**<br>done<br>#382 open · nothing in flight | 🟢 Playable | **30.0**<br>99% at 28.5+<br>Nova · 09-30 · REST, soak | ✓ ✓ n/a ✓ |
| **Azurik: Rise of Perathia**<br>done | 🟢 Playable | **30.0**<br>95% at 28.5+<br>Nova · 09-29 · REST<br>Thor 30.0 | ✓ ✓ n/a ✓ |
| **Blowout**<br>needs a gameplay route and a save | 🔵 copied | **30.0**<br>100% at 28.5+<br>Nova · 10-06 · unrecorded | ✓ – – – |
| **Buffy the Vampire Slayer**<br>20-min soak<br>queued 1791283282-hostops-restore-c3a0 #6 | soak pending | **30.0**<br>96% at 28.5+<br>Nova · 10-02 · MAX | ✓ ✓ n/a ✓ |
| **Family Guy: Video Game!**<br>20-min soak | soak pending | **30.0**<br>98% at 28.5+<br>Thor · 10-01 · MAX | ✓ ✓ n/a ✓ |
| **GoldenEye: Rogue Agent**<br>**reach gameplay**<br>**blocker: reached_gameplay: no `mark gameplay` in logcat** | 🔴 blocked | **30.0**<br>94% at 28.5+<br>Nova · 09-27 · MAX, screen: 90-240 s only | ✓ ✓ ✓ – |
| **Halo 2**<br>needs a gameplay route | 🔵 copied | **30.0**<br>96% at 28.5+<br>Nova · 10-03 · REST | ✓ – ✓ – |
| **Halo: Combat Evolved**<br>done | 🟢 Playable | **30.0**<br>99% at 28.5+<br>Nova · 10-03 · REST | ✓ – ✓ ✓ |
| **Marvel Nemesis: Rise of the Imperfects**<br>needs a gameplay route and a save | 🔵 copied | **30.0**<br>99% at 28.5+<br>Nova · 10-06 · unrecorded | ✓ – – – |
| **Star Wars: Episode III: Revenge of the Sith**<br>needs a gameplay route and a save | 🔵 copied | **30.0**<br>65% at 28.5+<br>Nova · 10-03 · REST | ✓ – – – |
| **Grabbed by the Ghoulies**<br>raise fps (59% at 28.5+)<br>#311 closed | below 30 | **30.0**<br>59% at 28.5+<br>Thor · 09-27 · MAX | ✓ ✓ n/a ✓ |
| **Shin Megami Tensei: NINE**<br>20-min soak | soak pending | **30.0**<br>97% at 28.5+<br>Thor · 09-30 · MAX | ✓ ✓ n/a ✓ |
| **Tork: Prehistoric Punk**<br>done | 🟢 Playable | **30.0**<br>59% at 28.5+<br>Thor · 09-30 · MAX<br>Nova 30.0 | ✓ ✓ n/a ✓ |
| **Mortal Kombat: Deadly Alliance**<br>needs a gameplay route and a save | 🔵 copied | **29.9**<br>100% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Battlefield 2: Modern Combat**<br>re-benchmark at MAX | 🟣 inputs ready | **29.9**<br>67% at 28.5+<br>Nova · 10-01 · REST | ✓ ✓ n/a – |
| **Grand Theft Auto: San Andreas**<br>re-benchmark at MAX | 🟣 inputs ready | **29.8**<br>85% at 28.5+<br>Nova · 10-01 · REST | ✓ ✓ n/a – |
| **Call of Duty 3**<br>needs a gameplay route | 🔵 copied | **29.4**<br>93% at 28.5+<br>Nova · 09-26 · MAX, soak | ✓ – ✓ – |
| **Phantom Dust**<br>needs a gameplay route | 🔵 copied | **29.4**<br>74% at 28.5+<br>Thor · 09-30 · MAX, screen: 90-240 s only | ✓ – ✓ – |
| **Blinx 2: Battle of Time & Space ~ Blinx 2: Masters of Time & Space**<br>needs a gameplay route | 🔵 copied | **29.3**<br>57% at 28.5+<br>Nova · 09-27 · MAX<br>Thor **21.7** | ✓ – ✓ – |
| **The Incredible Hulk: Ultimate Destruction**<br>needs a gameplay route and a save | 🔵 copied | **29.2**<br>64% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Forza Motorsport**<br>needs a gameplay route<br>#414 open · nothing in flight | 🔵 copied | **29.0**<br>45% at 28.5+<br>Nova · 09-30 · REST<br>Thor **16.7** | ✓ – ✓ – |
| **Amped 2**<br>needs a gameplay route | 🔵 copied | **28.4**<br>44% at 28.5+<br>Nova · 10-04 · unrecorded | ✓ – ✓ – |
| **Otogi: Myth of Demons**<br>re-benchmark at MAX | 🟣 inputs ready | **28.1**<br>35% at 28.5+<br>Thor · 09-30 · REST | ✓ ✓ n/a – |
| **The Lord of the Rings: The Return of the King**<br>needs a gameplay route and a save | 🔵 copied | **27.7**<br>33% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Dino Crisis 3**<br>**fix the hang**<br>**blocker: hang: 17.3 s without 60 guest flips after the mark** | 🔴 blocked | **27.2**<br>16% at 28.5+<br>Nova · 10-02 · MAX | ✓ ✓ n/a – |
| **Counter-Strike**<br>needs a gameplay route and a save | 🔵 copied | **25.9**<br>0% at 28.5+<br>Nova · 10-03 · MAX, soak | ✓ – – – |
| **Spider-Man 2**<br>needs a gameplay route and a save<br>queued 1-1791284850-lane.gpunonrender-3230633 #2 | 🔵 copied | **25.8**<br>29% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **Need for Speed: Most Wanted**<br>needs a gameplay route and a save | 🔵 copied | **25.8**<br>19% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **BloodRayne**<br>raise fps (8% at 28.5+) | below 30 | **25.6**<br>8% at 28.5+<br>Thor · 09-28 · MAX, soak | ✓ ✓ n/a ✓ |
| **Midnight Club 3: DUB Edition**<br>raise fps (1% at 28.5+) | below 30 | **25.4**<br>1% at 28.5+<br>Nova · 10-03 · MAX, soak | ✓ ✓ ✓ ✓ |
| **Galleon**<br>raise fps (10% at 28.5+) | below 30 | **24.7**<br>10% at 28.5+<br>Thor · 09-30 · MAX | ✓ ✓ n/a ✓ |
| **JSRF: Jet Set Radio Future**<br>raise fps (11% at 28.5+) | below 30 | **24.2**<br>11% at 28.5+<br>Thor · 09-27 · MAX<br>Nova 59.9 | ✓ ✓ n/a ✓ |
| **MechAssault 2: Lone Wolf**<br>benchmark at MAX | 🟣 inputs ready | **24.1**<br>12% at 28.5+<br>Thor · 09-28 · REST, soak | ✓ ✓ n/a – |
| **Midnight Club II**<br>needs a gameplay route and a save | 🔵 copied | **23.1**<br>0% at 28.5+<br>Nova · 10-05 · unrecorded | ✓ – – – |
| **007: Agent Under Fire**<br>needs a gameplay route<br>#412 open · nothing in flight | 🔵 copied | **22.1**<br>0% at 28.5+<br>Nova · 09-30 · REST | ✓ – ✓ – |
| **Burnout 3: Takedown**<br>benchmark at MAX | 🟣 inputs ready | **22.0**<br>0% at 28.5+<br>Thor · 09-28 · MAX, soak | ✓ ✓ ✓ – |
| **Psychonauts**<br>needs a gameplay route | 🔵 copied | **22.0**<br>0% at 28.5+<br>Thor · 09-30 · MAX, screen: 90-240 s only | ✓ – ✓ – |
| **Arctic Thunder**<br>raise fps (9% at 28.5+) | below 30 | **21.4**<br>9% at 28.5+<br>Thor · 09-27 · MAX<br>Nova 30.2 | ✓ ✓ n/a ✓ |
| **Amped: Freestyle Snowboarding**<br>needs a gameplay route | 🔵 copied | **20.6**<br>9% at 28.5+<br>Nova · 10-04 · unrecorded | ✓ – ✓ – |
| **Alias**<br>raise fps (0% at 28.5+) | below 30 | **20.4**<br>0% at 28.5+<br>Thor · 09-28 · MAX, soak | ✓ ✓ n/a ✓ |
| **Dead or Alive Xtreme Beach Volleyball**<br>benchmark at MAX | 🟣 inputs ready | **20.0**<br>12% at 28.5+<br>Nova · 09-27 · MAX, screen: 90-240 s only | ✓ ✓ n/a – |
| **NBA Live 2005**<br>needs a gameplay route and a save | 🔵 copied | **20.0**<br>0% at 28.5+<br>Nova · 10-03 · unrecorded | ✓ – – – |
| **Conker: Live & Reloaded**<br>needs a gameplay route | 🔵 copied | **15.8**<br>16% at 28.5+<br>Nova · 10-03 · MAX, screen: 90-240 s only | ✓ – ✓ – |
| **Crash Twinsanity**<br>raise fps (0% at 28.5+) | below 30 | **15.7**<br>0% at 28.5+<br>Thor · 09-27 · MAX | ✓ ✓ n/a ✓ |
| **Blinx: The Time Sweeper**<br>needs a gameplay route<br>#372 open · nothing in flight | 🔵 copied | **14.8**<br>0% at 30+<br>Thor · 09-26 · unrecorded, hand-reviewed | ✓ – ✓ – |
| **Project Gotham Racing**<br>**fix the hang**<br>**blocker: hang: 11.6 s without 60 guest flips after the mark** | 🔴 blocked | **14.3**<br>0% at 28.5+<br>Thor · 09-26 · MAX | ✓ ✓ ✓ – |
| **Gauntlet: Dark Legacy**<br>benchmark at MAX | 🟣 inputs ready | **14.2**<br>0% at 28.5+<br>Thor · 09-30 · MAX, screen: 90-240 s only | ✓ ✓ n/a – |
| **Brute Force**<br>raise fps (0% at 28.5+) | below 30 | **13.2**<br>0% at 28.5+<br>Thor · 09-27 · MAX | ✓ ✓ n/a ✓ |
| **Dead or Alive 1 Ultimate**<br>needs a gameplay route<br>#413 open · nothing in flight | 🔵 copied | **12.6**<br>0% at 30+<br>Nova · 09-26 · unrecorded, hand-reviewed | ✓ – ✓ – |
| **Burnout**<br>raise fps (7% at 28.5+) | below 30 | **10.8**<br>7% at 28.5+<br>Thor · 09-27 · MAX | ✓ ✓ n/a ✓ |
| **Bloody Roar: Extreme**<br>needs a gameplay route | 🔵 copied | **9.8**<br>0% at 28.5+<br>Nova · 10-02 · MAX | ✓ – ✓ – |
| **Black**<br>raise fps (0% at 28.5+) | below 30 | **7.5**<br>0% at 28.5+<br>Thor · 09-26 · MAX | ✓ ✓ ✓ ✓ |
| **Midtown Madness 3**<br>**fix the hang**<br>**blocker: hang: 12.0 s without 60 guest flips after the mark** | 🔴 blocked | **3.1**<br>0% at 28.5+<br>Thor · 09-27 · MAX | ✓ ✓ n/a – |
| **SSX Tricky**<br>**fix the hang**<br>**blocker: reached_gameplay: unconfirmed (generic route) -- review the contact sheet, then rerun with --reviewed-gameplay yes\|no** | 🔴 blocked |  | ✓ – ✓ – |
| **Jet Set Radio Future**<br>done | 🟢 Playable |  | – – – ✓ |
| **KOF: Maximum Impact: Maniax**<br>done | 🟢 Playable |  | – ✓ n/a ✓ |
| **Dungeons & Dragons: Heroes**<br>benchmark at MAX | 🟣 inputs ready |  | ✓ ✓ n/a – |
| **Shin Megami Tensei: Nine**<br>benchmark at MAX | 🟣 inputs ready |  | ✓ ✓ n/a – |
| **Antz Extreme Racing**<br>needs a gameplay route and a save | 🔵 copied |  | ✓ – – – |
| **Aoi Namida**<br>needs a gameplay route and a save | 🔵 copied |  | ✓ – – – |
| **Area 51**<br>needs a gameplay route and a save | 🔵 copied |  | ✓ – – – |
| **Auto Modellista**<br>needs a gameplay route and a save | 🔵 copied |  | ✓ – – – |
| **Batman: Dark Tomorrow**<br>needs a gameplay route and a save | 🔵 copied |  | ✓ – – – |
| **MechAssault**<br>needs a gameplay route and a save | 🔵 copied |  | ✓ – – – |
| **Plus Plumb 2**<br>needs a gameplay route | 🔵 copied |  | ✓ – ✓ – |
| **4x4 Evo 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Aeon Flux**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **AFL Live 2003**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **AFL Live 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **AFL Live Premiership Edition**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **AFL Premiership 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Aggressive Inline**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **All-Star Baseball 2003 featuring Derek Jeter**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **All-Star Baseball 2004 featuring Derek Jeter**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **All-Star Baseball 2005 featuring Derek Jeter**<br>copy to a handheld | ⚪ not copied |  | – – – – |

<details><summary>391 more not copied</summary>

| Title and next step | Status | fps | C I S B |
|---|---|---|---|
| **Alter Echo**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **America's Army: Rise of a Soldier**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **American Chopper**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **American Chopper 2: Full Throttle**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **American McGee Presents Scrapland**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **AND 1 Streetball**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Angelic Concert**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Animaniacs: The Great Edgar Hunt**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Aquaman: Battle for Atlantis**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Arena Football**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Armed and Dangerous**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Army Men: Major Malfunction**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Army Men: Sarge's War**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Arx Fatalis**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Atari Anthology**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ATV: Quad Power Racing 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Backyard Wrestling 2: There Goes the Neighborhood**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Backyard Wrestling: Don't Try This at Home**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Bad Boys: Miami Takedown**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Baldur's Gate: Dark Alliance II**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Barbarian**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Barbie Horse Adventures: Wild Horse Rescue**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Bass Pro Shops: Trophy Bass 2007**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Bass Pro Shops: Trophy Hunter 2007**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Batman Begins**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Batman: Rise of Sin Tzu**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Batman: Vengeance**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Battle Engine Aquila**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Battlestar Galactica**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Beat Down: Fists of Vengeance**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Beyond Good & Evil**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Bicycle Casino Includes: Texas Hold'em**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Big Bumpin'**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Big Mutha Truckers**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Big Mutha Truckers 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Bionicle**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Bistro Cupid 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Blade II**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Blazing Angels: Squadrons of WWII**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Blitz: The League**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Blood Omen 2: The Legacy of Kain Series**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **BloodRayne 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **BMX XXX**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Braveknight: Lieveland Eiyuuden**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Breakdown**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Breeders' Cup: World Thoroughbred Championships**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Brian Lara International Cricket 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Broken Sword: The Sleeping Dragon**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Buffy the Vampire Slayer: Chaos Bleeds**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Burnout 2: Point of Impact**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **C.A.T: Cyber Attack Team**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cabela's Big Game Hunter 2005 Adventures**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cabela's Dangerous Hunts**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cabela's Dangerous Hunts 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cabela's Deer Hunt: 2004 Season**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cabela's Deer Hunt: 2005 Season**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cabela's Outdoor Adventures**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Call of Cthulhu: Dark Corners of the Earth**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Call of Duty 2: Big Red One**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Capcom Classics Collection Vol. 1**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Capcom Fighting Evolution ~ Capcom Fighting Jam**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Capcom vs. SNK 2 EO**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Carmen Sandiego: The Secret of the Stolen Drums**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Catwoman**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **CDS II**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cel Damage**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Championship Bowling**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Championship Manager 2006**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Championship Manager 5**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Championship Manager: Season 01/02**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Championship Manager: Season 02/03**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Charlie and the Chocolate Factory**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Chase: Hollywood Stunt Driver**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Chessmaster**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Chicago Enforcer**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Circus Maximus: Chariot Wars**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Classified: The Sentinel Crisis**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Close Combat: First to Fight: United States Marines**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Club Football**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Club Football 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Codename: Kids Next Door: Operation: V.I.D.E.O.G.A.M.E.**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cold Fear**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cold War**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Colin McRae Rally 04**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Colin McRae Rally 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Colin McRae Rally 3**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **College Hoops 2K6**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **College Hoops 2K7**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Combat Elite: WWII Paratroopers**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Commandos 2: Men of Courage**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Commandos: Strike Force**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Conan**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Conflict: Desert Storm**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Conflict: Global Storm**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Conflict: Vietnam**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Conspiracy: Weapons of Mass Destruction**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Constantine**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Corvette**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Crash 'n' Burn**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Crash Tag Team Racing**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **CRAZY TAXI 3 High Roller**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Cricket 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Crime Life: Gang Wars**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Crouching Tiger, Hidden Dragon**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Crusty Demons**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **CSI: Crime Scene Investigation**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Curious George**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Curse: The Eye of Isis**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Daisenryaku VII**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dakar 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dance Dance Revolution Ultramix**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dance Dance Revolution Ultramix 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dance Dance Revolution Ultramix 3**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dance Dance Revolution Ultramix 4**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dance:UK**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Darkwatch**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dave Mirra Freestyle BMX 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **David Beckham Soccer**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dead Man's Hand**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dead to Rights**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dead to Rights II**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Defender**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Delta Force: Black Hawk Down**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dennou Taisen: DroneZ**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Destroy All Humans!**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Destroy All Humans! 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Deus Ex: Invisible War**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Die Hard: Vendetta**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Digimon Battle Chronicle**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Digimon World X**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dinotopia: The Sunstone Odyssey**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Disney's Chicken Little**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Disney's Extreme Skate Adventure**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Disney's The Haunted Mansion**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Disney/Pixar Cars**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Disney/Pixar Finding Nemo**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Disney/Pixar The Incredibles**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Disney/Pixar The Incredibles: Rise of the Underminer**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Doom 3**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Doom 3: Resurrection of Evil**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dr. Seuss' The Cat in the Hat**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dragon Ball Z: Sagas**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dragon's Lair 3D: Return to the Lair**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Drake of the 99 Dragons**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dreamfall: The Longest Journey**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **DreamWorks Madagascar**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **DreamWorks Shark Tale**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **DreamWorks Shrek: SuperSlam**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Drihoo**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Driver: Parallel Lines**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dynasty Warriors 4**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Dynasty Warriors 5**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ed, Edd n Eddy: The Mis-Edventures**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Eggo Mania**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Enclave**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **England International Football: 2004 Edition**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Enter the Matrix**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Eragon**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN College Hoops**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN College Hoops 2K5**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN International Winter Sports 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN Major League Baseball**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN MLS ExtraTime 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN NBA 2K5**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN NBA Basketball**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN NFL 2K5**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN NFL PrimeTime 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN NHL 2K5**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN NHL Hockey**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **ESPN Winter X Games Snowboarding 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Evil Dead: A Fistful of Boomstick**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Evil Dead: Regeneration**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ex-Chaser**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Exaskeleton**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **F1 2001**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **F1 Career Challenge**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fable: The Lost Chapters**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fallout: Brotherhood of Steel**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fantastic 4**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Far Cry Instincts**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Far Cry Instincts: Evolution**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fatal Frame**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA 07**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA Football 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA Soccer 06**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA Soccer 2003**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA Soccer 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA Street**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA Street 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FIFA World Cup Germany 2006**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fight Club**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fight Night 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fight Night Round 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Fight Night Round 3**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FILA World Tour Tennis**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Final Fight: Streetwise**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FlatOut**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **FlatOut 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Flight Academy**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ford Mustang: The Legend Lives**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ford Racing 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ford Racing 3**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ford Street Racing**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Forgotten Realms: Demon Stone**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Frankie Dettori Racing**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Freaky Flyers**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Freedom Fighters**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Freestyle Metal X**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Frogger Beyond**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Frogger: Ancient Shadow**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Full Spectrum Warrior**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Full Spectrum Warrior: Ten Hammers**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Furious Karting**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Futurama**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Future Tactics: The Uprising**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gauntlet: Seven Sorrows**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gene Troopers**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Genma Onimusha**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ghost Master: The Gravenville Chronicles**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gladiator: Sword of Vengeance**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gladius**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Goblin Commander: Unleash the Horde**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Godzilla: Destroy All Monsters Melee**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Godzilla: Save the Earth**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gotcha!**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Grand Theft Auto III**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Grand Theft Auto: Vice City**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gravity Games Bike: Street. Vert. Dirt.**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Greg Hastings' Tournament Paintball**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Greg Hastings' Tournament Paintball Max'd**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Grooverider: Slot Car Thunder**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Group S Challenge**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Guilty Gear Isuka**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gun**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gun Metal**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Gungriffon: Allied Strike**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Half-Life 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Halo 2 Multiplayer Map Pack**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Harry Potter and the Chamber of Secrets**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Harry Potter and the Goblet of Fire**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Harry Potter and the Philosopher's Stone**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Harry Potter and the Prisoner of Azkaban**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Harry Potter: Quidditch World Cup**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Headhunter: Redemption**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Hello Kitty: Roller Rescue**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Heroes of the Pacific**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **High Heat Major League Baseball 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **High Rollers Casino**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Hitman 2: Silent Assassin**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Hot Wheels: Stunt Track Challenge**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Hulk**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Hummer Badlands**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Hunter: The Reckoning**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Hyper Sports 2002 Winter**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **I-Ninja**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ice Age 2: The Meltdown**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **IHRA Drag Racing 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **IHRA Drag Racing: Sportsman Edition**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **IHRA Professional Drag Racing 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Indiana Jones and the Emperor's Tomb**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **IndyCar Series**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **IndyCar Series 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Innocent Tears**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Inside Pitch 2003**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Intellivision Lives!**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **International Superstar Soccer 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Iron Phoenix**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Jacked**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Jade Empire**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **James Cameron's Dark Angel**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Jaws Unleashed**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Jikkyou World Soccer 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Judge Dredd: Dredd vs. Death**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Juiced**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Jurassic Park: Operation Genesis**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Just Cause**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Justice League Heroes**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Knight's Apprentice: Memorick's Adventures**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Knights of the Temple II**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Knockout Kings 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Kung Fu Chaos**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Largo Winch: Empire Under Threat**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Legacy of Kain: Defiance**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Legends of Wrestling**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Legends of Wrestling II**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Lemony Snicket's A Series of Unfortunate Events**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **LMA Manager 2003**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Loons: The Fight for Fame**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Mace Griffin: Bounty Hunter**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Madden NFL 07**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Madden NFL 08**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Madden NFL 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Magi Death Fight!**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Manhunt**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Mashed: Drive to Survive**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Max Payne**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Max Payne 2: The Fall of Max Payne**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Maximum Chase**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Medal of Honor: European Assault**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Medal of Honor: Frontline**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Mercenaries**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Metal Dungeon**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Metal Gear Solid 2: Substance**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Micro Machines**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Midway Arcade Treasures**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Midway Arcade Treasures 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Mission: Impossible: Operation Surma**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Monopoly Party**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Monster Garage**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Motor Trend Presents Lotus Challenge**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **MVP Baseball 2003**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Namco Museum**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **NBA 2K6**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **NBA 2K7**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **NBA Inside Drive 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **NBA Live 06**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **NBA Live 07**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **NBA Live 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Need for Speed: Hot Pursuit 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Neighbours from Hell**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Psyvariar 2: Extend Edition**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **RAW**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ricky Ponting International Cricket 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **RLH: Run Like Hell**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Robotech: Invasion**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **RollerCoaster Tycoon**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Rugby League 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Scooby-Doo! Mystery Mayhem**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Scooby-Doo! Unmasked**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Sega GT 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Sega GT 2002 + JSRF: Jet Set Radio Future**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Shadow of Memories**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Shadow The Hedgehog**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Shrek**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ski Racing 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Slam Tennis**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Splat Magazine Renegade Paintball**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Stake**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Star Wars: Battlefront**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Star Wars: Battlefront II**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Star Wars: Knights of the Old Republic II: The Sith Lords**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Star Wars: Starfighter Special Edition**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Star Wars: The Clone Wars**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Still Life**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Super Bubble Pop**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Superman Returns**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Takahashi Junko no Mahjong Seminar**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tecmo Classic Arcade**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tetris Worlds**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Bard's Tale**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Baseball 2002: Battle Ball Park Sengen**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Bible Game**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Hustle: Detroit Streets**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The King of Fighters 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Lord of the Rings: The Third Age**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Matrix: Path of Neo**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Simpsons: Road Rage**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Urbz: Sims in the City**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **The Wild Rings**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tiger Woods PGA Tour 06**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tiger Woods PGA Tour 07**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tiger Woods PGA Tour 2003**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tiger Woods PGA Tour 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tiger Woods PGA Tour 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **TimeSplitters: Future Perfect**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tom Clancy's Splinter Cell: Double Agent**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Tony Hawk's Underground 2**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Torino 2006**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Total Club Manager 2004**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Triangle Again**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Triple Play 2002**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Trivial Pursuit: Unhinged**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Turok: Evolution**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **TY the Tasmanian Tiger**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **UEFA Champions League 2004-2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ultimate Pro Pinball**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Ultimate Spider-Man**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Umezawa Yukari no Igo Seminar**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Unreal Championship**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Virtual Pool: Tournament Edition**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Whiteout**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **World Series Baseball**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **World Snooker Championship 2005**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **World Soccer Winning Eleven 8: International**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **World War II Combat: Road to Berlin**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **X-Men: The Official Game**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Xbox Live Arcade**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Xiaolin Showdown**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **XIII**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Yetisports Arctic Adventures**<br>copy to a handheld | ⚪ not copied |  | – – – – |
| **Yonenaga Kunio no Shougi Seminar**<br>copy to a handheld | ⚪ not copied |  | – – – – |

</details>

528 titles: 17 blocked, 27 Playable, 5 soak pending, 11 below 30, 13 inputs ready, 54 copied, 401 not copied. Benchmarked = below 30 + soak pending + Playable. Measured = any gameplay fps reading, on either handheld, any build or mode. Pipeline: Copied to a handheld; Inputs, the title's own route (profile setup and gameplay); Save, the profile save extracted (n/a when the route has no profile step); Bench, fps measured at MAX. fps: the gameplay median (at the bar green, 25 to the bar amber, under 25 red), the share of play at the bar it names (title_verdict.py's playable_fps x fps_tolerance, which a soak is scored at too), then the handheld, date and performance mode; the build is in the title's detail. Sources: titles/already-on-handhelds.json, logs/titlepipe/batch-\*.tsv, targets.toml, the xiso manifest, pathfind held runs, the Playable ledger, pass1-backfill.json, dispatch results/\*/verdict.json, soaks (results/\*/logcat, 60-flip windows 90-240 s); registry: docs/testing/titles/targets.toml, routes/ and titlestate.py's registry.

Hand-reviewed rows: pass 1 of #397 ([[lane.titleplay], 2026-09-26 12:09 PDT](https://github.com/jreinach-alt/hakuX/issues/397#issuecomment-5849041338)), performance mode unrecorded.

**Gate:** Ghoulies median >= 25 gfps over 90-240 s on the candidate APK, both handhelds: **no candidate is cut yet, so no soak is on the candidate's APK; on the newest soaks it is NOT met**; thor **17.5** gfps (n=46, 03:22 (216h 58m ago), ref 6bfce4a685); nova **27** gfps (n=65, 20:00 (176h 21m ago), ref 3a5d79e3ea).

| lever | owner lane | measured effect |
|---|---|---|
| #424 stop the translation cache's code-write invalidation and dirty re-arm churn | none | not measured yet: no lane holds it (IN FLIGHT (hostops 2026-09-29T05:35Z): lane.tcg424flip flips HAKUX_TCG424_RANGE to default ON -- the three valid Thor tbflip424-blinx2 pairs pass every leg (issuecomment-5884276103); it runs the Arctic Thunder A/B and the pgraph must-not-move arm before PR-ready.) |
| #425 fewer jump-cache flushes and an inline indirect-branch probe | none | not measured yet: no lane holds it (UPDATED hostops 2026-09-28T02:40Z: lane.flip474 retired (PRs #475/#485/#516 folded; Turnip sysmem measured AUF 16 -> 24, DOA 13 -> 21 gfps on the Nova); the #474 remedies are lane.rendermode474 (PR #530: per-title Turnip sysmem default for DOA and AUF; DOA A/B 1790559549/-550 and arms 1-1790561511 in the queue), lane.drain474 (PR #517 FOLDED 2026-09-28T03:43Z as 9cfa11b64f, row retired: AUF bind_textures 4.55 -> 0.10 ms/flip, fps +1.7%, J/frame -9.5% on one pair) and lane.forza414 (PR #518: the display pre-download deferral; DOA and AUF A/B soaks 1-1790561463..-468 in the Nova queue).) |
| #426 split renderer command capture from Vulkan translation | lane.remote | not measured yet: no arm or device run registered |
| #427 build with native TLS, inline LSE atomics and no intra-library PLT calls | none | BOARD job.board 2026-09-26T21:55Z: not dispatchable, a lane owns it (draft PR #435, handback resumes). |
| #428 run the emulated CPU thread on the prime core | none | CLOSED (hostops 2026-09-26T23:20Z) as refuted by lane.vcpuprime428 (PR #437): six 480 s Crimson Skies runs on the Thor, one binary; pinned to the prime core 20.56 fps mean vs 26.20 unpinned (-21.5%). |
| #429 smaller translation blocks on often-rewritten pages | none | CLOSED 2026-09-27 (hostops) as refuted in gameplay: lane.tbsize429 (PR #459, docs only) read the always-on hakuX-pages counters -- stores touching translated code (ov) are 0 in every gameplay window (Crimson A/B, Blinx survey, blinx372 runs); real codegen is ~1 block/frame at ~5.6 insns; the 19% tb_gen_code share is whole-page-invalidation recycles, which #424's range test removes (PRs #434/#456), not block size. |

## 2. What is happening right now?

13 stranded; 2 waiting on audit; 2 no word in 48 h; 1 waiting on device.

- **lane.collapse433** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-01 23:27; latest result: I've found why Battlefield 2 falls short on the Nova; it is not a collapse.
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.defecttriage433** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 09-30 10:47; latest result: Matches `docs/lanes/defecttriage433/` exactly, docs-only, no emulator code, no territory/nv2a_issues edits.
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.dispatchguard** -- kind: local lane; issue: (harness work, no tracker issue); state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 09-29 17:22; latest result: The guard is in and PR #624 is marked ready.
- **lane.framereview** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-04 22:10; latest result: retro-tron has finished and I reviewed it: REJECT.
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.gpuclock** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #827 is a draft; since: 10-05 16:13; latest result: The lane is waiting again, this time on four new Nova runs, the Simpsons host session and the profile.c grant. (PR #827)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.holdwait** -- kind: local lane; issue: (harness work, no tracker issue); state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-01 22:41; latest result: I added `hold.sh wait-idle`, and the branch `lane/holdwait` is pushed and marked ready.
- **lane.pathclass** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #646 is a draft; since: -; latest result: - (PR #646)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.pmucounters** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #828 is a draft; since: 10-05 22:35; latest result: R0 is not yet answered. (PR #828)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.routefix1002** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #683 is a draft; since: 10-03 10:17; latest result: The Gunvalkyrie v5 route is ready, but it is in no live queue yet. lane.local has to change one line before Star Wars III (`1791045669`, queued now) finishes, or the Nova will run the old route instead. (PR #683)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.selfdeps** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #695 is a draft; since: 10-03 09:51; latest result: Attempt 2 is paused on WAITING: the build-side work is done and pushed, but two script changes are outside the territory my board row grants. (PR #695)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.selftestshard** -- kind: local lane; issue: (harness work, no tracker issue); state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 09-27 22:21; latest result: `jobs selftest` now runs as four parallel jobs instead of one.
- **lane.toolsmith** -- kind: local lane; issue: #94 request.sh silently drops all but the last --only-tests/--skip-tests/--tests/--suites, and it nearly published a bracket that excluded the true answer; #95 The prediction schema has no composition field, so the comparability rule cannot be enforced -- and disc_id conflates composition with the skip list; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; no PR; since: 10-04 16:02; latest result: I've fixed the libfolders pref problem from the 10-04 addendum, and the work is pushed to `lane/toolsmith` with `State: ready`.
  - board note NOT BLOCKED. docs/testing/ab_compare.py and docs/testing/request.sh are both held by the instruments standing lane, per the owner's division of labour on dispatch scripts. Needs no device and no build. Note the ordering constraint if it lands while arms are live: adding a field is backward-compatible, but step (2)'s refusal is NOT -- it would invalidate every prediction registered without the field, which is 106 of 107, so (2) needs a grandfathering rule decided BEFORE it ships.
- **lane.verdict433** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: **stranded**; waiting on: no session, nothing queued or running on a device, not parked; PR #653 is a draft; since: 10-01 21:11; latest result: Summary Session 19 picked up where session 18 left off (which had finished cleanly and parked with nothing outstanding — the resume was the harness's normal idle-lane pickup, not a stall). (PR #653)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.gpunonrender** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: waiting on device; waiting on: running on the nova: #433 gpunonrender X0: NG Black outer vs in-pass render-pass stamps (is gpu_nonrender_ms render-pass work behind Turnip's per-tile stamp?); expected results in docs/lanes/gpunonrender/NOTES.md; 4 runs queued, first at position 1, estimated start 04:28; since: 10-06 04:07; latest result: I read the four Nova runs from last night, and the main finding is that the brief's starting point is probably wrong. (PR #836)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.alwaystelemetry** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: waiting on audit; waiting on: PR #824: an audit label (the PR is ready and unlabelled); since: 10-05 07:50; latest result: Part 1 of #433 was already finished before this session: the perflog overhead is measured and the two-tier design is posted. (PR #824)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.pathfind** -- kind: local lane; issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; state: waiting on audit; waiting on: PR #822: an audit label (the PR is ready and unlabelled); since: 10-05 22:50; latest result: Attempt 2 is closed out at 22:55 PDT with no device time. (PR #822)
  - board note Not actionable as work: the 0.5 tracking issue. Its workstreams are separate issues, each dispatched on its own.
- **lane.remote** -- kind: cloud session; issue: #461 Performance: Crimson Skies re-hashes unchanged textures (6.5 ms/frame) and Blinx's texture uploads cost 3.4 ms/frame; #557 Thermal adaptation: step quality down before the 78 C thermal pause (opt-in governor); state: no word in 48 h; waiting on: -; since: -; latest result: -
- **lane.xbox** -- kind: console session; issue: #112 xbox-hardware: the experiments that need real silicon, in the order they pay; #110 PVIDEO overlay: no size cap and no pitch handling (pvideo.c is 77 lines of register stubs); state: no word in 48 h; waiting on: -; since: -; latest result: -

### Finished today (1)

- lane.frametrace -- issue: #433 0.5 release: 145 titles benchmarked and 50 Playable on the Thor/Nova handhelds; PR: #847; merged: 00:10; result: Preflight: every branch gate passes.

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
19. host lane.collapse433 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: I've found why Battlefield 2 falls short on the Nova; it is not a collapse. (territory row, no unit, no request, no PR, 10-01 23:27)
20. host lane.defecttriage433 has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Matches `docs/lanes/defecttriage433/` exactly, docs-only, no emulator code, no territory/nv2a_issues edits. (territory row, no unit, no request, no PR, 09-30 10:47)
21. host lane.dispatchguard has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: The guard is in and PR #624 is marked ready. (territory row, no unit, no request, no PR, 09-29 17:22)
22. host lane.framereview has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: retro-tron has finished and I reviewed it: REJECT. (territory row, no unit, no request, no PR, 10-04 22:10)
23. host lane.gpuclock has no session, nothing on a device and is not parked (PR #827 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: The lane is waiting again, this time on four new Nova runs, the Simpsons host session and the profile.c grant. (territory row, no unit, no request, PR #827, 10-05 16:13)
24. host lane.holdwait has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: I added `hold.sh wait-idle`, and the branch `lane/holdwait` is pushed and marked ready. (territory row, no unit, no request, no PR, 10-01 22:41)
25. host lane.pathclass has no session, nothing on a device and is not parked (PR #646 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. (territory row, no unit, no request, PR #646)
26. host lane.pmucounters has no session, nothing on a device and is not parked (PR #828 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: R0 is not yet answered. (territory row, no unit, no request, PR #828, 10-05 22:35)
27. host lane.routefix1002 has no session, nothing on a device and is not parked (PR #683 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: The Gunvalkyrie v5 route is ready, but it is in no live queue yet. lane.local has to change one line before Star Wars III (`1791045669`, queued now) finishes, or the Nova will run the old route instead. (territory row, no unit, no request, PR #683, 10-03 10:17)
28. host lane.selfdeps has no session, nothing on a device and is not parked (PR #695 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Attempt 2 is paused on WAITING: the build-side work is done and pushed, but two script changes are outside the territory my board row grants. (territory row, no unit, no request, PR #695, 10-03 09:51)
29. host lane.selftestshard has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: `jobs selftest` now runs as four parallel jobs instead of one. (territory row, no unit, no request, no PR, 09-27 22:21)
30. host lane.toolsmith has no session, nothing on a device and is not parked (PR none none); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: I've fixed the libfolders pref problem from the 10-04 addendum, and the work is pushed to `lane/toolsmith` with `State: ready`. (territory row, no unit, no request, no PR, 10-04 16:02)
31. host lane.verdict433 has no session, nothing on a device and is not parked (PR #653 draft); nothing will wake it. Give it what it waits for and resume it, or retire its row. Its last word: Summary Session 19 picked up where session 18 left off (which had finished cleanly and parked with nothing outstanding — the resume was the harness's normal idle-lane pickup, not a stall). (territory row, no unit, no request, PR #653, 10-01 21:11)

Listed: the owner's open decisions (host-tools/escalations.md, issues labelled decision-needed), then the alarms no job handles: a stranded lane, a device idle with runnable work, a hold past its end, a run past twice its expected time, a stale device watchdog, a title issue open with nothing in flight and no job to pick it up, a failing gate on the candidate, CI red on master, a failed timer. Not listed: owned or in-flight work, a file wait, parked work, a queue that is long because both devices are busy.

## 4. Are the machines healthy?

**Thor** in use by lanelocal-fanwait: the Thor's fan is dead (owner 09-29; AYN is shipping a fan and a top screen). The dispatcher is kept off it, BUT queued Thor requests of &lt;= 480 s ARE allowed (owner 09-30 ~12:30 PDT: the Thor screening program): lane.local's runner hakux-thor-coldconfirm gives each a cold slot and stops it at xo 70 C. Staged new titles push under this hold (push-under-hold flags). Since 22:53, until no end time stated · watchdog: **resting** since 22:53 (dispatch/hold/thor.why)

last hour: 0 running, 0 hands-on, 0 waste (idle-waiting + held-idle + overdue)

**Nova** running #433 gpunonrender X0: NG Black outer vs in-pass render-pass stamps (is gpu_nonrender_ms render-pass work behind Turnip's per-tile stamp?); expected results in docs/lanes/gpunonrender/NOTES.md, for lane.gpunonrender, since 04:12 (8m ago) · watchdog: **running** since 03:41 (dispatch/running/1-1791284834-lane.gpunonrender-3228352.req)

last hour: 46 running, 15 hands-on, 0 waste (idle-waiting + held-idle + overdue)

**Queue:** device-bound: 6 runs queued, both devices busy. 6 queued, 4 of them 0.5 work; the oldest 0.5 run has waited 14 min; no idle-tier sweep is queued. Estimated drain: 1 h 32 min.

dispatch/queue and running; durations estimated: a title run its seconds + 8 min, a suite run 5 min + 1.5 min per suite.

**Console:** plug meter ON, 1.2 W (read 0s ago). Title push: 88 of 20 titles pushed in batch-xbox-20261003.tsv, the last at 10-03 18:45.

### Automation

- arms -- last run: 10-06 04:20; next run: running now; last outcome: WARNING: gh pr list did not answer; using the last tick's PR map (12 branches) and the lane/\* glob
- authwatch -- last run: 10-06 04:17; next run: 10-06 04:22; last outcome: -
- autoverdict -- last run: 10-06 04:18; next run: 10-06 04:33; last outcome: -
- board -- last run: 10-03 06:50; next run: no timer; last outcome: This tick cleared the one FAIL: `greensize303` is now on the board, and the fleet check no longer reports it.
- cloud -- last run: 09-29 19:54; next run: no timer; last outcome: finish: #627 moved past needs-audit-2 and carries no claimed:cloud, so an earlier finish already cleared it; this one changed nothing
- defrag -- last run: 10-06 04:20; next run: 10-06 04:22; last outcome: -
- devwatch -- last run: 10-06 04:20; next run: 10-06 04:21; last outcome: -
- driver -- last run: 10-06 04:17; next run: 10-06 04:22; last outcome: -
- dx -- last run: 10-05 09:23; next run: 10-06 09:23; last outcome: -
- failintake -- last run: 10-06 04:13; next run: 10-06 04:23; last outcome: -
- fold -- last run: 10-03 08:19; next run: no timer; last outcome: tick: repaired none; folded none; handed back none; waiting none
- foldqueue -- last run: 10-06 04:20; next run: 10-06 04:35; last outcome: -
- forge-prsync -- last run: 10-06 04:18; next run: 10-06 04:23; last outcome: -
- forge-sync -- last run: 10-06 04:20; next run: 10-06 04:21; last outcome: -
- github-gateway -- last run: 10-06 04:11; next run: 10-06 04:26; last outcome: -
- handback -- last run: 10-03 08:22; next run: no timer; last outcome: nothing handed back (needs-rebase draft-strand-arm draft-strand-runs draft-strand-idle draft-strand-quiet idle-no-pr merged-runs)
- hostops -- last run: 10-06 04:08; next run: 10-06 04:28; last outcome: Pathfind's void NFL Blitz Pro run: the run was on `gpunonrender`'s APK `5eef1dacd9` with `HAKUX_SURFSPLICE=1` still in `dispatch/.env_pref.nova`, so the result cannot count.
- hourly -- last run: 10-06 03:45; next run: 10-06 04:45; last outcome: -
- idlewatch -- last run: 10-06 04:19; next run: 10-06 04:29; last outcome: -
- issue-sweep -- last run: 10-02 07:41; next run: no timer; last outcome: gh returned nothing for the open issue list; this tick is blind and writes nothing
- issue-sync -- last run: 10-06 04:19; next run: 10-06 04:29; last outcome: -
- jamcheck -- last run: 10-06 04:20; next run: 10-06 04:30; last outcome: -
- lanewaker -- last run: 10-06 04:17; next run: 10-06 04:22; last outcome: -
- local-board -- last run: 10-06 04:11; next run: 10-06 04:32; last outcome: lanes: 1/10 units running; ready 0 (blocked 0, waiting 0); draft-strand 8; other 21; report ~/hakux-work/status/local-board.md
- local-issue-audit -- last run: 10-05 19:41; next run: 10-06 07:41; last outcome: -
- manifest -- last run: 10-06 04:15; next run: 10-06 04:30; last outcome: -
- nightly -- last run: 10-06 00:30; next run: 10-07 00:30; last outcome: -
- ops-shadow -- last run: 10-06 04:17; next run: 10-06 04:22; last outcome: -
- pm-evening -- last run: 10-05 17:30; next run: 10-06 17:30; last outcome: -
- pm-midday -- last run: 10-05 12:00; next run: 10-06 12:00; last outcome: -
- pm-morning -- last run: 10-05 05:00; next run: 10-06 05:00; last outcome: -
- pm-overnight -- last run: 10-06 03:30; next run: 10-07 00:30; last outcome: -
- pm-weekend -- last run: 10-04 06:00; next run: 10-10 06:00; last outcome: -
- pm-weekend-day -- last run: 10-04 17:30; next run: 10-10 12:00; last outcome: -
- pr-sweep -- last run: 10-02 09:13; next run: no timer; last outcome: gh returned nothing for the open PR list; this tick is blind and repairs nothing
- stallwatch -- last run: 10-06 04:19; next run: 10-06 04:29; last outcome: -
- tmpclean -- last run: 10-06 03:37; next run: 10-06 04:37; last outcome: -
- usage-meter -- last run: 10-06 03:50; next run: 10-06 04:21; last outcome: -
- fold -- last run: not recorded; next run: no timer; last outcome: a standing board row; it runs when the board dispatches it
- triage -- last run: not recorded; next run: no timer; last outcome: a standing board row; it runs when the board dispatches it

details

#### Window budget (the account's five-hour and weekly windows)

- dispatching normally. Lanes and audits start as work allows; expanding is the default.
- week from 2026-10-01 21:00 PDT (62% elapsed, reserve from 2026-10-07 11:24 PDT), 171 run(s), spend 830.4 of no declared budget, 0 usage-limit hit(s) this week (0 in the reserve).
- no session has ever been refused by the account's window on this host. That is the only first-hand evidence of a closed window there is: **the remaining five-hour and weekly balance cannot be queried from here**, so the weekly reserve arms on that evidence, or on `WEEK_SPEND_BUDGET` if the owner declares one in `$WORK/limits.env`. Unknown means open, by design.

#### Lane sessions finished (last 24h)

| when (PDT) | lane | model | turns | min | result | PR | said |
|---|---|---|---|---|---|---|---|
| 10-05 18:06 | frametrace | opus-5-5 | 101 | 11 | ok | #847 merged | - |
| 10-05 21:51 | pmucounters | sonnet-5 | 25 | 0 | ok | #828 draft | R0 did not run. |
| 10-05 21:52 | gpunonrender | sonnet-5 | 37 | 2 | ok | #836 draft | The C16 control reads cleanly, but the baseline half is still open. |
| 10-05 22:10 | pmucounters | sonnet-5 | 49 | 2 | ok | #828 draft | Attempt 3 is committed (`4f9da299cd`, local only; offline protocol, so nothing pushed). |
| 10-05 22:29 | frametrace | opus-5-5 | 153 | 21 | ok | #847 merged | I've named the PFIFO thread's wait from the code and queued three Nova captures to measure it. |
| 10-05 22:35 | pmucounters | sonnet-5 | 28 | 3 | ok | #828 draft | R0 is not yet answered. |
| 10-05 22:46 | pathfind | sonnet-5 | 230 | 289 | ok | #822 open | - |
| 10-05 22:50 | pathfind | sonnet-5 | 14 | 0 | ok | #822 open | Attempt 2 is closed out at 22:55 PDT with no device time. |
| 10-05 22:53 | gpunonrender | sonnet-5 | 26 | 2 | ok | #836 draft | The C0 control baseline is read and the control passes on every criterion. |
| 10-05 23:26 | frametrace | opus-5-5 | 107 | 10 | ok | #847 merged | Preflight: every branch gate passes. Only `coverage` fails, on board issues #838–#846 having no lane row. |
| 10-06 01:10 | gpunonrender | opus-5-5 | 110 | 19 | ok | #836 draft | I've built the Forza fix (scope A), switched off by default. |
| 10-06 04:14 | gpunonrender | opus-5-5 | 152 | 17 | ok | #836 draft | I read the four Nova runs from last night, and the main finding is that the brief's starting point is probably wrong. |

_result: ok = ended on its own; MAXTURNS = cut at the turn cap, work kept; ERR = the session errored. A lane that ended without a ready PR is resumed by the board (attempts 1-3 on claude-opus-5-5, then claude-opus-5-5, then decision-needed)._

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
2026-10-03 07:30:12 PDT NOTE: ~/hakuX (the unit's ExecStart path) is 120 commit(s) behind origin/master; re-execing the trunk's copy. Run: git -C /ho
2026-10-03 07:30:15 PDT nothing actionable (0/10 lanes, no startable issue, no unlabelled ready PR)
2026-10-03 07:50:40 PDT NOTE: ~/hakuX (the unit's ExecStart path) is 120 commit(s) behind origin/master; re-execing the trunk's copy. Run: git -C /ho
2026-10-03 07:50:43 PDT nothing actionable (0/10 lanes, no startable issue, no unlabelled ready PR)
2026-10-03 08:11:15 PDT NOTE: ~/hakuX (the unit's ExecStart path) is 129 commit(s) behind origin/master; re-execing the trunk's copy. Run: git -C /ho
2026-10-03 08:11:18 PDT nothing actionable (2/10 lanes, no startable issue, no unlabelled ready PR)
```

last model ticks:

```
10-02 18:08 board claude-sonnet-5 turns=78 213s ok My commit only touched `territory.toml`, confirmed clean. The large MM/AD diff i
10-02 18:28 board claude-sonnet-5 turns=50 141s ok The FAIL line is gone — the fleet report now runs clean (apart from the gh-suspe
10-03 06:50 board claude-sonnet-5 turns=31 58s ok This tick cleared the one FAIL: `greensize303` is now on the board, and the flee
```

board branch: 806b48451c 41 minutes ago -- board: PM 03:33 -- grant reports.c and pfifo.c to lane.gpunonrender from folded lanes accur

#### Handhelds and arms

- adb: bdc158a5(device) ee317437(device)
- dispatcher: active, workers: 2
- queue: 6 waiting, 0 idle-tier z-\* behind them, 1 running; holds: thor
- running: lane.gpunonrender d946e1ba44 -- #433 gpunonrender X1: NG Black with HAKUX_GPUTS_INRP=0 (cost of the in-pass BOTTOM_OF_PIPE
- dispatcher last line: `10-06 04:21:26 hddPath -> /storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box/titles.qcow2 (sha256 b83cd6a14930, 1887436`
- affinity: lanes serving `desktop nova` -- an A/B pair queued now is pinned to one of them
- arms job: 122 pair(s) queued or running and not yet judged; 118 judged; 176 skipped (see `arms.sh list`); watermark 2026-09-18 13:00 PDT (stored as `2026-09-18T20:00:00Z`: arms.sh compares that UTC string to registered_utc, so the file stays UTC and only this rendering is local)

last verdicts:

- `9715a5a775` lane/async794:docs/testing/predictions/async794-fix2-must-not-move.json: VERDICT: PASS -- all 267 registered checks hold.
- `5a9978ab62` lane/async794:docs/testing/predictions/async794-download-paths-must-not-move.json: VERDICT: PASS -- all 267 registered checks hold.
- `388ea55c4b` lane/forzadecay414-fix:docs/testing/predictions/forzadecay414-fix-pixels2.json: VERDICT: FAIL -- 37 of 3363 checks violated:
- `fbed11c3e7` lane/tcg424flip:docs/testing/predictions/tcg424flip-pgraph.json: VERDICT: FAIL -- 41 of 3379 checks violated:
- `9996bfedbb` lane/memfast:docs/testing/predictions/memfast-drop-pixels-stable.json: VERDICT: FAIL -- 36 of 3167 checks violated:

```
2026-10-04 18:46:56 PDT WARNING: gh pr list did not answer; using the last tick's PR map (12 branches) and the lane/* glob
2026-10-04 19:46:55 PDT WARNING: gh pr list did not answer; using the last tick's PR map (13 branches) and the lane/* glob
2026-10-04 20:46:41 PDT WARNING: gh pr list did not answer; using the last tick's PR map (13 branches) and the lane/* glob
2026-10-04 21:46:51 PDT WARNING: gh pr list did not answer; using the last tick's PR map (12 branches) and the lane/* glob
```

last refusals, in full (a refusal is recorded once; delete the file under `$WORK/arms/skipped/` to retry):

- `3ca87cf99e` lane/fmv303c:docs/testing/predictions/fmv303c-wb-probe.json: a_ref == b_ref, nothing to compare

told=2026-10-04T22:16:31Z

- `92394bb4c3` lane/vcpusleep:docs/testing/predictions/vcpusleep-simpsons.json: no suite with goldens in its keys or disc

told=2026-10-04T21:12:52Z

- `6b933f6193` lane/fmv303c:docs/testing/predictions/fmv303c-wb-probe.json: a_ref == b_ref, nothing to compare

told=2026-10-04T21:12:51Z

#### Fold job (every 30 min)

- fold-ready: ; needs-rebase: ; needs-remediation:
- awaiting audit: needs-audit-1 ; needs-audit-2

```
2026-10-03 06:48:21 PDT tick: repaired none; folded none; handed back none; waiting none
2026-10-03 07:18:33 PDT tick: repaired none; folded none; handed back none; waiting none
2026-10-03 07:48:38 PDT tick: repaired none; folded none; handed back none; waiting none
2026-10-03 08:19:11 PDT tick: repaired none; folded none; handed back none; waiting none
```

- master: c3a0c70ace 4 hours ago -- fold: lane/frametrace (offline) -- frametrace: the PFIFO thread's GPU waits named per title (d

#### Open lane PRs

- #836 (draft) `lane/gpunonrender` lane/gpunonrender -- labels: none
- #828 (draft) `lane/pmucounters` lane/pmucounters -- labels: none
- #827 (draft) `lane/gpuclock` lane.gpuclock (#433): is the GPU clock-limited? GPU ms per frame against the Adreno clock, per title -- labels: none
- #824 `lane/alwaystelemetry` alwaystelemetry: perflog costs ~1.2 ms/frame of render thread (+30% CPU); design the always-on tier (#433) -- labels: none
- #822 `lane/pathfind` pathfind: a screen-reading agent that drives a title from boot into gameplay -- labels: none
- #792 (draft) `lane/memfast` lane.memfast F1: guest loads through the host MMU ("fastmem"), behind HAKUX_FASTMEM, default off (#507) -- REJECTED, not for fold -- labels: none
- #695 (draft) `lane/selfdeps` selfdeps: builds fetch nothing from GitHub (#433) -- labels: none
- #683 (draft) `lane/routefix1002` routefix1002: three route checks for the overnight Nova queue (#433) -- labels: none
- #673 (draft) `lane/tronhang672` tronhang672: Tron 2.0 hangs entering the first level (Nova) -- labels: none
- #653 (draft) `lane/verdict433` lane.verdict433: measurement pass for #433 (0.5: 50 Playable) -- labels: none
- #652 (draft) `lane/titleroutes2` titleroutes2: per-title routes and surveys on the Nova, successor to lane.titleroutes (#397) -- labels: none
- #649 `lane/routedriver2` routedriver2 session 2: Buffy's menus made robust, the ledge gap diagnosed (#433) -- labels: none
- #646 (draft) `lane/pathclass` pathclass: a local GPU screen-state classifier for pathfind (#433) -- labels: none
- #643 `lane/hddcrash` hddcrash: titles disk mode 660; a request's HAKUX_TITLES_DISK wins (#397) -- labels: none

#### Job errors (last 24h, from the units' logs)

none seen.

#### Host

- checkout `~/hakuX` on master, 393 behind origin/master (jobs run the fetched trunk regardless)
- timers: arms next -; authwatch next 04:27:56 PDT; autoverdict next 04:33:40 PDT; defrag next 04:24:00 PDT; devwatch next 04:23:30 PDT; driver next 04:27:56 PDT; dx next 09:23:00 PDT; failintake next 04:23:55 PDT; foldqueue next 04:36:00 PDT; forge-prsync next 04:23:47 PDT; forge-sync next 04:23:44 PDT; github-gateway next 04:27:14 PDT; hostops next 04:28:00 PDT; hourly next 04:45:00 PDT; idlewatch next 04
- attempts: aasample=3 accuracy804=4 adpf=2 affinitybacklog=2 alwaystelemetry=1 armlabel=1 armpin=1 armsflake=1 armsrequeue=1 armsscope=1 armsskip=3 async413=1 async794=1 aufdispatch=1 aufire412=2 aufire412b=2 backlogstate=3 battadmit=2 belowbar1005=1 bf2push656=1 bf2stall433=1 bf2ubosize433=2 blankrule297=2 blendarm50=1 blendrace50=2 blinx2input=2 blinx372=1 blinx372b=1 blinx372c=2 blinx372d=1 blinx372e=2 blit83b=1 blit84=1 blitsafe=2 boardgate=4 boardprio=3 boardpushgate=1 boardtreeheal=1 boardwt-checkout-selfheal=1 branchprune=2 brdf315=1 brdf315b=1 buildflags427=1 buildstamp=1 ciskip=1 claimrace=2 cloud-audit1-181=1 cloud-audit2-163=1 cloud-audit2-308=2 cloud-issue-10=1 cloud-issue-111=1 cloud-issue-112=1 cloud-issue-13=1 cloud-issue-188=3 cloud-issue-189=1 cloud-issue-200=2 cloud-issue-271=2 cloud-issue-278=1 cloud-issue-279=1 cloud-issue-282=3 cloud-issue-283=1 cloud-issue-284=4 cloud-issue-286=1 cloud-issue-297=1 cloud-issue-34=1 cloud-issue-527=1 cloud190=1 cloudclaim=1 cloudlaneguard=2 cloudtail=1 cloudterritory=1 clrpad164=2 clrsurf91=3 clrvk184=1 clrwb91=4 clrwin88=1 collapse433=1 crashattr=2 cull13=1 cullnf276=2 dash432=2 defecttriage433=1 desktopchannel=2 diagdump77=2 diagsoak77=1 dirtytlb=3 dispatchguard=1 displayguard=3 dispsuper=1 dmasurf277=1 doa413=1 doa413b=3 doa413c=1 dpforce345=2 draftstrand=3 drain474=2 drvab77=1 energymap507=2 escalationparse=1 escitems=1 failgate=3 fanduty507=4 fgunknown=1 fix311=1 flatlm13=1 fleetabsent=1 fleetreg=2 fleetstanding=1 flicker801=1 flip474=4 flushstall787=2 fmv303=1 fmv303b=2 fmv303c=1 focusanr=1 fog278=1 foldcancel=1 foldci=3 foldflow=2 foldindex=1 foldregress=2 forza414=2 forzaclock=1 forzadecay414=2 fps20786=1 fps382=1 fpsshare=1 framereview=1 frametrace=2 fulldisc50=1 g8b8285=1 gamecheck=1 ghoul311=4 glchannel=1 glerr86=1 gmem474=1 goldencorr287=1 goldens782=1 goldovr287=1 gpl569=3 gpuclock=3 gpunonrender=3 greensize303=1 gta482=4 handback=3 handbackbranch=1 handbacklane=1 handbackmerged=1 handbackpark=1 handbackresolved=1 handbackstrand=1 handbackwaiter=1 hangwatch=3 hddcrash=4 hddperm=3 hddsplit=1 hilodot10=1 hitchcause=1 hitchwatch=1 holdlease=2 holdtake=1 holdwait=1 ibcache=2 idlehalt=3 idlehaltdefault=3 idlehaltspin=1 indexcheck=1 indexloc=2 inflightpark=1 isoroots=1 issuerecon=1 issuesweep=1 jcache425=1 kabukistall=2 laneshape=1 libfolders=2 linecap13=2 litcompile569=2 localforge=4 localjobs=1 localtime=1 measured05=1 memfast=1 nanattr281=1 nanfix281=1 near30=4 nightlynotes=3 nightlytrunk=1 notespath=1 notify488=3 opsrebuild=1 pacing=1 pathclass=1 pathfind=3 pathknow=1 perfarch=2 perfbase=1 perfregimen=2 pilotgate=3 pipeline413=2 pmc188=3 pmucounters=1 pri432=2 primpv13=4 pshaniso284=2 pshqueue=3 rankrule=1 regs200=1 relnote=1 relprio432=1 remotechannel=1 rendermode474=1 reqprio=1 retreason425=1 ring53=1 ring53impl=3 routedriver=4 routedriver2=3 routefix1002=4 routeprep=1 routerca433=1 savestate433=4 scoresplit=1 selfdeps=2 selftest86=1 selftestshard=2 selftestsplit=2 shade224=1 shadeflat224=4 shaderfb569=2 shaderplan569=1 shaderprebuild569=4 shadetie224=1 shadetie224b=2 slowdown462=3 slowtier2=3 snapdrive=1 soakflake=1 sphere273fix=1 spheremap273=1 stalecheck=2 stallmeasure569=1 statusdash=1 statusfresh=1 statusguard=1 statuspage=1 statuswindow=1 stopmarker=1 suffixpr=1 surfwatch382=1 sustain507=2 swatchorder50=1 sweepclock=1 sweepcover=2 sweepremote=1 sweeps=1 swizzle87=1 tbchurn424=1 tbflip424=1 tbsize429=1 tcg424flip=4 tcgchurn=2 texvol283=1 thermal507=2 thorbottom800=2 thorheat=1 tie282c=1 tiecode282=2 titleplay=1 titleroutes=4 titleroutes2=2 titlerun=3 titles05=3 titlestate=1 tokentier=1 toolsmith=2 tronhang672=1 turncap=1 turnipcost569=1 turnipfork=2 uberdefault569=1 uberspike569=2 usagemode=1 usbdialog=1 vblank65=1 vcpu60=2 vcpuplan=1 vcpuprime428=2 vcpusleep=3 vcpuwait433=4 verdict10min=1 verdict433=2 visual404=1 vklayer34=1 vkpointsize34=4 vol283r=1 vshconst=3 vshcpu345=1 vshnobegin242=2 vshr12280=1 vshsubneg255=1 vtxarr262=1 wbuf31fix=3 wbuf31sel=1 wbufclip=2 wbufdepth24=1 windowbudget=2 wparam223=1 wparamclip223=2 wparamcode223=1 wparamff223=1 wparamgeom223=1 x1a7271=1 y16bump10=2 yuv10=1 zclamp276=1 zdepth272=1 zetaswap275=1 zrtz272=4

_Written by `docs/testing/jobs/status.sh` on the host every job tick and every 30 min; republished when the content changes (at most every 10 min) and at least every 30 min. Every time here is PDT. Next tick due by 2026-10-06 04:51 PDT._

---

The per-title detail and the original layout: [index.svg](index.svg) opens as the full page; [IN-FLIGHT.md](IN-FLIGHT.md) lists the work in progress and recent folds.
