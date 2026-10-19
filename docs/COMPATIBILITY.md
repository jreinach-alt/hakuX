# Compatibility

_Last updated 2026-10-18, for version 0.5.0._

This lists Xbox titles tried on this project's test devices, split into three groups: titles that clear the **Playable** bar, titles that run but fall short of 30 fps, and titles that do not yet play. It is not a full compatibility list: plenty of other titles have simply not been tried yet. See [`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) and the [issue tracker](https://github.com/jreinach-alt/hakuX/issues) for what is tracked about titles not on this page.

97 Playable · 20 run below 30 fps · 11 not playable

## What "Playable" means

A title is rated Playable when a held run reaches real gameplay and stays
there for at least 10 minutes (longer for a handful of titles known to
develop problems slowly) with no crash, hang or unexpected exit; spends at
least 90% of that time in actual play rather than menus, loading screens or
cutscenes (its **play share**); holds at least 28.5 fps (the 30 fps bar,
times a 0.95 tolerance) for at least 90% of the time it is playing (the
**fps bar**); plays its audio with no more than a tiny share of starved
callbacks; and shows no hitches or flicker -- checked by reviewing the
captured frames themselves, not just the frame-rate counter (**frame
review**). The rating is tied to the handheld it was measured on, an AYN
Thor or a Retroid Pocket Nova.

A few titles were rated by a person playing them rather than by the timed
run alone, where the timed run cannot hold a representative scene. Need for
Speed: Most Wanted, for one, is rated on a full race played by hand; its
automated run covers race starts only.

Titles below run the same checks but fall short of the fps bar while
everything else about the run is clean. Titles that do not yet play either
crash, hang, or never reach gameplay in the emulator.

A rating here is not a claim that a title is free of bugs, and a title's
absence from this page is not a claim that it fails to run -- titles with
an inconclusive test run are left off rather than guessed at.

## What it was tested on

Both handhelds have a Snapdragon 8 Gen 2 with an Adreno 740 GPU and run
Android 13. Every title on this page was tested with the same GPU driver:
**Turnip Adreno Driver T30 (@Mr_Purple_666)**, a Mesa Vulkan driver
(26.3.0-devel, build git-62ac221a33), installed in hakuX under Settings →
Graphics → GPU Driver. Results with the handheld's own Qualcomm driver, or
with another Turnip build, may differ.

## 🟢 Playable

| Title | Region | Device | Median fps | Time at bar | Tested | Notes |
|---|---|---|---|---|---|---|
| 187: Ride or Die | ? | Nova | 37.2 | 100% | 2026-10-01 |  |
| 25 to Life | ? | Nova | 59.9 | 97% | 2026-10-13 |  |
| 50 Cent: Bulletproof | ? | Nova | 30.0 | 99% | 2026-09-30 |  |
| Alias | USA | Nova | 30.0 | 100% | 2026-10-14 |  |
| Alien Hominid | Europe | Thor | 59.9 | 100% | 2026-09-26 |  |
| AMF Bowling 2004 | USA | Nova | 59.9 | 100% | 2026-10-05 |  |
| ATV Quad Power Racing 2 | ? | Nova |  | 94% | 2026-10-13 |  |
| Avatar: The Last Airbender | USA | Nova | 59.9 | 100% | 2026-10-13 |  |
| Azurik: Rise of Perathia | USA | Nova | 30.0 | 95% | 2026-09-29 |  |
| Backyard Wrestling 2: There Goes the Neighborhood | USA | Nova | 40.8 | 99% | 2026-10-14 |  |
| Bad Boys: Miami Takedown | USA | Nova | 59.9 | 100% | 2026-10-14 |  |
| Baldur's Gate: Dark Alliance | USA | Nova | 59.9 | 100% | 2026-09-30 |  |
| Blade II | ? | Nova | 30.0 | 100% | 2026-10-07 |  |
| BloodRayne 2 | USA | Nova | 30.0 | 100% | 2026-10-13 |  |
| Blowout | USA | Nova | 30.0 | 100% | 2026-10-06 |  |
| Burnout Revenge | ? | Nova |  | 98% | 2026-10-13 |  |
| Call of Duty 3 | ? | Nova | 29.4 | 100% | 2026-10-06 |  |
| Capcom vs. SNK 2 EO | ? | Nova | 59.8 | 100% | 2026-10-07 |  |
| Castlevania: Curse of Darkness | ? | Nova | 59.9 | 100% | 2026-10-03 |  |
| Cel Damage | ? | Nova | 29.9 | 98% | 2026-10-07 |  |
| Conan (Europe) | Europe | Nova | 30.0 | 100% | 2026-10-12 |  |
| Conspiracy: Weapons of Mass Destruction | Europe | Nova | 59.9 | 100% | 2026-10-14 |  |
| Crimson Skies: High Road to Revenge | USA | Nova | 30.0 | 95% | 2026-09-30 |  |
| Dance Dance Revolution Ultramix 3 | USA | Nova | 59.9 | 95% | 2026-10-16 |  |
| Dark Summit | ? | Nova | 45.9 | 93% | 2026-10-04 |  |
| David Beckham Soccer | Europe | Nova | 59.9 | 100% | 2026-10-15 |  |
| Dead or Alive 3 | ? | Nova | 50.1 | 100% | 2026-10-12 |  |
| ESPN Major League Baseball | USA | Nova | 43.2 | 100% | 2026-10-16 |  |
| ESPN MLS ExtraTime 2002 | USA | Nova | 59.9 | 100% | 2026-10-16 |  |
| Family Guy Video Game | ? | Nova | 30.0 | 100% | 2026-10-16 |  |
| Fight Club | ? | Nova | 43.4 | 94% | 2026-10-06 |  |
| FILA World Tour Tennis | Europe | Nova | 56.8 | 100% | 2026-10-15 |  |
| Future Tactics: The Uprising | USA | Nova | 59.9 | 100% | 2026-10-07 |  |
| Genma Onimusha | ? | Nova |  | 99% | 2026-10-13 |  |
| Grabbed by the Ghoulies | USA | Nova | 30.0 | 98% | 2026-10-12 |  |
| Guilty Gear XX #Reload | USA | Nova | 59.9 | 100% | 2026-10-13 |  |
| Gunvalkyrie | ? | Nova | 59.9 | 99% | 2026-10-03 |  |
| Halo: Combat Evolved | ? | Nova | 30.0 | 99% | 2026-10-03 |  |
| Harry Potter and the Philosopher's Stone | ? | Nova | 41.5 | 95% | 2026-10-13 |  |
| Hello Kitty: Roller Rescue | Europe | Nova | 59.9 | 100% | 2026-10-14 |  |
| Indigo Prophecy | USA | Nova | 59.9 | 99% | 2026-10-07 |  |
| Jacked | Europe | Nova | 46.1 | 100% | 2026-10-14 |  |
| Jet Set Radio Future | USA | Nova | 59.9 | 100% | 2026-10-04 |  |
| Kabuki Warriors | ? | Nova | 59.9 | 100% | 2026-09-30 |  |
| Knights of the Temple II | ? | Nova | 30.0 | 100% | 2026-10-14 |  |
| Knockout Kings 2002 | USA | Nova | 59.8 | 100% | 2026-10-16 |  |
| KOF: Maximum Impact – Maniax | USA | Nova | 52.4 | 99% | 2026-09-29 |  |
| Legacy of Kain: Defiance | USA | Nova | 47.6 | 97% | 2026-10-07 |  |
| Lemony Snicket's A Series of Unfortunate Events (USA) | USA | Nova | 59.9 | 100% | 2026-10-11 |  |
| Manhunt | USA | Nova | 59.0 |  | 2026-10-14 |  |
| Marvel Nemesis: Rise of the Imperfects | ? | Nova | 30.0 | 99% | 2026-10-06 |  |
| Mat Hoffman's Pro BMX 2 | USA | Nova | 30.0 | 100% | 2026-10-14 |  |
| Max Payne | USA | Nova | 51.3 | 100% | 2026-10-14 |  |
| Max Payne 2: The Fall of Max Payne | USA | Nova | 59.9 | 100% | 2026-10-08 |  |
| Mercenaries: Playground of Destruction | USA, Europe | Nova | 53.3 | 100% | 2026-10-12 |  |
| Micro Machines (Europe) | Europe | Nova | 59.9 | 100% | 2026-10-14 |  |
| MLB SlugFest - Loaded | USA | Nova | 58.9 | 100% | 2026-10-05 |  |
| MLB SlugFest 2003 | USA | Nova | 59.9 | 100% | 2026-10-05 |  |
| MLB SlugFest 2004 | USA | Nova | 44.4 | 100% | 2026-10-05 |  |
| Mortal Kombat: Armageddon | ? | Nova | 59.2 | 100% | 2026-10-06 |  |
| Mortal Kombat: Shaolin Monks | ? | Nova | 59.9 | 99% | 2026-10-18 |  |
| MTV Celebrity Deathmatch | ? | Nova | 57.2 | 99% | 2026-10-04 |  |
| MVP Baseball 2003 | USA | Nova | 59.9 | 100% | 2026-10-16 |  |
| NBA 2K2 | USA | Nova | 57.0 | 100% | 2026-10-05 |  |
| NBA 2K3 | USA | Nova | 42.9 | 96% | 2026-10-06 |  |
| NBA Live 07 | ? | Nova | 50.8 | 99% | 2026-10-17 | Owner play session; telemetry only, no frames |
| NBA Live 2004 | USA | Nova | 35.5 | 100% | 2026-10-06 |  |
| Need for Speed: Most Wanted | ? | Nova | 29.9 | 95% | 2026-10-12 | Hand-played race; 30 fps cap |
| NFL Blitz 2002 | USA | Nova | 45.0 | 100% | 2026-10-05 |  |
| Pac-Man World 2 | ? | Nova | 59.9 | 100% | 2026-10-13 |  |
| Panzer Dragoon Orta | Europe | Nova | 54.1 | 100% | 2026-10-03 |  |
| Pro Evolution Soccer 5 (Europe) | Europe | Nova | 59.9 | 100% | 2026-10-18 |  |
| RalliSport Challenge | ? | Nova | 59.6 | 92% | 2026-10-18 | Car flicker (#804) fixed. |
| Ratatouille | USA | Nova | 52.8 | 100% | 2026-10-06 |  |
| Rayman 3 Hoodlum Havoc | ? | Nova | 59.9 | 100% | 2026-10-13 |  |
| Ricky Ponting International Cricket 2005 | Australia | Nova | 59.9 | 98% | 2026-10-15 |  |
| Rogue Trooper | ? | Nova | 58.9 | 100% | 2026-10-06 |  |
| Scooby-Doo! Mystery Mayhem (Europe) | Europe | Nova | 29.0 | 100% | 2026-10-12 |  |
| Scooby-Doo! Unmasked (Europe) | Europe | Nova | 59.9 | 99% | 2026-10-13 |  |
| Shadow of Memories (Europe) | Europe | Nova | 30.0 | 100% | 2026-10-13 |  |
| Shrek 2 | ? | Nova | 29.8 | 92% | 2026-10-13 |  |
| Slam Tennis | Europe | Nova | 35.4 | 98% | 2026-10-16 |  |
| Spikeout: Battle Street | Europe | Nova | 59.9 | 100% | 2026-10-03 |  |
| SpongeBob SquarePants: Battle for Bikini Bottom | USA | Nova | 59.9 | 100% | 2026-10-07 |  |
| The Lord of the Rings: The Fellowship of the Ring | USA | Nova | 30.0 | 100% | 2026-10-07 |  |
| The Simpsons Hit & Run | ? | Nova | 37.9 | 100% | 2026-10-04 |  |
| The Wild Rings | ? | Nova | 53.3 | 100% | 2026-10-18 |  |
| TimeSplitters 2 | ? | Nova | 59.9 | 99% | 2026-10-13 |  |
| ToeJam & Earl III: Mission to Earth | USA | Nova | 59.9 | 99% | 2026-10-02 |  |
| Tony Hawk's Pro Skater 2x | ? | Nova | 59.8 | 100% | 2026-10-01 |  |
| Tony Hawk's Pro Skater 4 | ? | Nova | 56.6 | 98% | 2026-10-13 |  |
| Tony Hawk's Underground 2 | USA, Europe | Nova | 59.7 | 100% | 2026-10-13 |  |
| Tork: Prehistoric Punk | USA | Nova | 30.0 | 100% | 2026-10-04 |  |
| TY the Tasmanian Tiger | USA | Nova | 30.0 | 100% | 2026-10-14 |  |
| World Soccer Winning Eleven 9 | ? | Nova | 59.9 | 100% | 2026-10-06 |  |
| WWE Raw 2 | ? | Nova | 59.9 | 100% | 2026-09-30 |  |
| X-Men: The Official Game (Europe) | Europe | Nova | 49.3 | 100% | 2026-10-12 |  |

## 🟡 Runs, below 30 fps

| Title | Region | Device | Median fps | Time at bar | Tested | Notes |
|---|---|---|---|---|---|---|
| Aeon Flux | ? | Nova | 30.0 | 85% | 2026-10-13 |  |
| Arctic Thunder | USA | Nova | 30.2 | 64% | 2026-09-30 |  |
| Area 51 | USA | Nova | 30.0 | 73% | 2026-10-09 |  |
| Buffy the Vampire Slayer | ? | Nova | 29.7 | 74% | 2026-10-18 |  |
| Burnout 3: Takedown | ? | Nova | 30.8 | 85% | 2026-10-14 |  |
| Grand Theft Auto III | ? | Nova |  |  | 2026-10-12 | Plays, but drops into the teens while driving in the city (below the 30 fps bar); tracked as #1049. |
| Grand Theft Auto: Vice City | ? | Nova |  |  | 2026-10-12 | Plays, but drops into the teens while driving in the city (below the 30 fps bar); tracked as #1049. |
| Half-Life 2 | ? | Nova | 29.8 | 74% | 2026-10-13 |  |
| Medal of Honor: Frontline | USA | Nova | 59.9 | 86% | 2026-10-08 |  |
| NBA 2K7 | ? | Nova | 57.2 | 75% | 2026-10-16 |  |
| NBA Inside Drive 2004 | ? | Nova | 31.1 | 70% | 2026-10-16 |  |
| NHL 2K3 | USA | Nova | 35.0 | 69% | 2026-10-06 |  |
| Panzer Elite Action: Fields of Glory | Europe | Nova | 30.4 | 90% | 2026-10-07 |  |
| Spider Man 2 | ? | Nova | 25.8 | 29% | 2026-10-06 |  |
| Star Wars: The Clone Wars | USA | Nova | 29.4 | 61% | 2026-10-08 |  |
| Stranger's Wrath | ? | Nova | 27.0 | 38% | 2026-10-13 |  |
| The Incredible Hulk: Ultimate Destruction | ? | Nova | 29.2 | 64% | 2026-10-06 |  |
| The Lord of the Rings: The Return of the King | ? | Nova | 27.7 | 33% | 2026-10-06 |  |
| Turok Evolution | USA | Nova | 29.9 | 84% | 2026-10-07 |  |
| Ty the Tasmanian Tiger: Night of the Quinkan | USA, Australia | Nova | 47.8 | 79% | 2026-10-07 |  |

## 🔴 Not playable

| Title | Title ID | Tested | Reason |
|---|---|---|---|
| AMF Xtreme Bowling | 42530014 | 2026-10-05 | Crashes about 7 minutes in |
| Bruce Lee: Quest of the Dragon | 56550016 | 2026-10-02 | Hangs about 5 minutes in |
| Capcom Classics Collection Vol 2 | 43430019 | 2026-10-01 | Crashes after about 6 minutes |
| Die Hard: Vendetta | 56560029 | 2026-10-12 | Never reaches gameplay |
| Fuzion Frenzy | 4D530002 | 2026-09-27 | Hangs about 5 minutes in |
| Midtown Madness 3 | 4D53002A | 2026-09-27 | Hangs about 4 minutes in |
| Mission Impossible: Operation Surma | 4947001F | 2026-10-12 | Hangs about 5 minutes in |
| NHL Hitz Pro | 4D57001A | 2026-10-06 | Hangs after team selection |
| Project Gotham Racing | 4D530003 | 2026-09-27 | Freezes mid-race |
| Sonic Heroes | 5345002B | 2026-10-01 | Crashes about 4 minutes in |
| Super Monkey Ball Deluxe | 53450038 | 2026-10-01 | Crashes about 4 minutes in |

A rating is not a claim of no bugs, and absence from this page is not a claim of failure -- titles with inconclusive test runs are simply not listed.
