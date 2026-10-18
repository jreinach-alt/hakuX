# How we got here

## The story of hakuX: Community Edition

_Last updated 2026-10-17, for version 0.5.2._

*All dates are 2026; times are Pacific.*

hakuX Community Edition is an original Xbox emulator for Android handhelds. It is built on xemu and on two Android ports that came before it. This fork began on 6 September. By 17 October it had:

- shipped six releases, from 0.3.3-j1 to 0.5.2;
- had 88 titles accepted as Playable, each on a held, timed run or on the maintainer's own play.

The work is done by AI coding agents, and the harness that runs them has gone through five designs along the way.

The story is told by subject. The sections follow the order in which their subjects began, and each runs in date order. The timeline below puts the whole thing in one sequence.

| Date | Milestone |
|---|---|
| 01-29 | X1 BOX brings xemu to Android |
| 02-16 | rfandango forks X1 BOX as hakuX |
| 04-09 | hakuX 0.3.1, the last upstream release |
| 09-06 | This fork's first commit |
| 09-07 | 0.3.3-j1 fixes launching games from ES-DE |
| 09-08 | First PGRAPH sweep against real-hardware captures |
| 09-10 | 0.4.0-j1, the rendering-accuracy release |
| 09-12 | A scoreboard separates rounding errors from real ones |
| 09-18 | A real Xbox goes into service; the harness is redesigned around timed jobs and lanes |
| 09-25 | The pixel suites become a regression gate, and the 1.0 criteria are set |
| 09-26 | 0.4.1-j1; work turns to individual titles |
| 09-29 | GitHub suspends the account; by morning work runs from a local repository and fold queue |
| 10-02 | The ubershader goes on by default; a local forge takes over issues and PRs |
| 10-03 | Halo: Combat Evolved passes as Playable |
| 10-05 | GitHub is restored; the forge stays the workspace, and GitHub becomes a mirror |
| 10-10 | The harness is consolidated: the planning agent is retired, and one model table serves every job |
| 10-12 | 0.5.0: 52 Playable titles, and save states brought forward from xemu |
| 10-16 | 0.5.1: the app becomes hakuX CE |
| 10-17 | 0.5.2: Halo's opening cinematic runs at about 29 fps instead of 17 |

---

## 1. Where hakuX came from

hakuX descends from four projects:

1. **xemu**, the desktop original Xbox emulator. Judging by the merge base, the Android work branched from xemu master around 01-19.
2. **X1 BOX**, by izzy2lost. It brought xemu to Android. Its first commit on 01-29 added an Android SDL2 scaffold and a setup wizard, and by 02-06 video was working, slowly. X1 BOX kept releasing after that, through 1.2.9 on 10-03.
3. **hakuX**, by rfandango. It forked X1 BOX on 02-16 and the same day added an FPS counter, Turnip driver support and a code cache.
   - **Early March:** ARM64 floating-point inline ops arrived, then a five-phase Vulkan renderer: generation counters, a fast path, bindless descriptors, draw reordering and an async shader compile worker.
   - **Releases:** the app took the hakuX name on 03-25. v0.1.0 followed on 03-26, v0.2.0 (with a GLES renderer and an EEPROM editor) on 03-27, and 0.3.0 (per-game settings, quirks, crash detection, texture replacement) on 04-07.
   - **0.3.1** (04-09) was rfandango's last release. It added persistent log capture, NV2A performance logging, lazy surface eviction and multithreaded S3TC.
   - **Since then:** by September the repo had 308 stars and had been dormant for five months. None of its 11 forks carried real work.
4. **ItsRetroPup/hakuX.** On 08-06 it shipped v0.3.2, merging rfandango's unreleased launch-handoff fix (#7). This fork is forked from ItsRetroPup's.

## 2. Picking it up (09-06 to 09-07)

The first commit landed on 09-06 at 16:14. The first problem was practical: launching a game from the ES-DE frontend failed. The emulator lost the frontend's permission to read the disc image before it could open it, and booted to the dashboard asking for a disc.

**0.3.3-j1** shipped the next day. It fixed frontend launching and installed under its own app id, alongside any official build. The ES-DE fix also went back upstream as rfandango PR #8 the same day.

## 3. Rendering accuracy and the real Xbox (09-07 to 09-25)

PGRAPH is the graphics engine inside the Xbox's NV2A GPU. On 09-07 a test harness went in that runs abaire's `nxdk_pgraph_tests` in the emulator and compares every frame against abaire's captures from a real Xbox.

**The first sweep, 09-08.** Of 1,871 tests, 115 (6.1%) matched the hardware bit for bit. Another 257 were near misses, with no colour channel off by more than 8. The rest were wrong (1,326) or blank (173).

**0.4.0-j1, 09-10.** The rendering-accuracy release followed two days later. Every change in it was measured against those hardware captures:

- **Depth:** W-buffering went from 29.9M wrong pixels to 10.5M, and its 24 blank captures were gone.
- **Window clipping:** 54 to 92 of 92 tests passing.
- **Lighting:** 0 to 27 of 195.
- **Cube maps:** 17 to 31 of 72.
- **Fog:** 13 to 23 of 280.
- **Texture borders:** 10 to 14 of 18, with border-colour error down from 56,419 px to 16,205 px.

**Why bit-identical was the wrong yardstick.** The NV2A is a GPU from 2001 with its own arithmetic precision. hakuX reproduces it with Vulkan shaders on a modern mobile GPU, which calculates at a different precision and rounds at different points. Chasing exact matches turned up many results that were not real errors:

- **Averages hid real errors.** A mean error of 0.00 could hide 87,381 pixels each off by 8. So the harness stopped using averages and counted differing pixels and the largest difference instead.
- **Most one-step differences were rounding, not wrong rules.** A pixel one step off usually came from two nearly identical calculations landing either side of a rounding edge. Those pixels sat within 0.01 to 0.04 of a step from the hardware's value. A wrong rounding rule would have flipped about half the channels, but only 0.3% to 4% differed.
- **The rounding floor didn't depend on the GPU.** The share of one-step differences was the same, within 0.1%, on the Nova's GPU and on a software renderer on a desktop. It is a precision floor that any modern GPU would show.
- **Some references couldn't tell models apart.** Where a hardware capture was one flat colour over the area in question, it could only say pass or fail. One fog model fitted to such a capture scored 94.9% and was still wrong.

So between 09-09 and 09-14 the project built its own scoring:

- **Outcome classes** separate exact, one step off, structurally wrong and blank.
- **A shape check** sorts each capture's error by its pattern rather than its size. For example, it picks out a one-pixel band along an edge, which is interpolation precision.
- **A flag on flat references** keeps them out of any ranking.
- **A scoreboard** rolls 101 test suites into 13 areas. Each cell gives exact captures and *structural* pixels: differences that are a wrong rule rather than a rounding floor.

A capture that is off by one step everywhere is never counted as exact. So the exact count understates how close the emulator is.

**Where it landed.** The scoreboard's best column, on 09-13, compared with its first, a day earlier:

| | 09-12 | 09-13 |
|---|---|---|
| Structural error | 20.6M px | 12.1M px |
| Exact captures | 948 of 3,375 (28.1%) | 1,212 of 3,379 (35.9%) |

Between the two columns, 41% of the structural error was gone. Some areas were close to complete:

| Area | Exact captures | Structural error |
|---|---|---|
| Clipping and viewport | 174 of 183 | |
| Shadow and projective textures | 176 → 256 of 288 | |
| Blending | 5 → 126 of 154 | 5.9M → 0.3M px |
| Fog | | 1.57M → 0.15M px |
| Texture formats | | 1.18M → 0.27M px |

Most of the blending gain came from one fix, and it was on the CPU side. The emulated FRNDINT instruction now honours the rounding mode the game has set, which the test's own floor function relies on.

**The real Xbox, 09-18.** A v1.1 console went into service as the project's reference on 09-18, on a direct network link to the host. It settled two questions:

- **The references were sound.** On 09-20 it ran the same suite and reproduced the published captures on 3,374 of 3,379 (99.9%), with nothing blank and nothing one step off. On 09-25 it produced a full reference set of its own. It differed from the published captures on 13, and 8 of those 13 were tests whose published captures were already out of date.
- **The hardware isn't perfectly repeatable either.** One depth test varied by 20,141 pixels between two identical runs on the console.

The console also became the reference for frame rates. From 09-28, a title that runs slowly on a real Xbox too could pass on its native rate, with the source cited.

**Picking at the edges.** On 09-25 hakuX was compared against the console's own reference set and matched 1,240 of 3,396 captures exactly (36.5%). That was only 28 more than twelve days earlier. The evidence gathered since 09-12 said the PGRAPH tests had little left to give:

- **Most of the remaining difference was rounding.** 57.4% of all differing channels were one step off, and that floor matched across two different GPUs.
- **A large part couldn't be judged.** About a quarter of the remaining error sat on flat references that can't distinguish a right model from a wrong one.
- **Small changes couldn't be told from noise.** Of 170 captures that moved between two sweeps, the comparison tool would credit only 5 without a repeat run. The console's own runs vary too.

That day the maintainer judged that the project was picking at the edges of what the PGRAPH tests alone could show. The pixel suites became a regression gate: a change that makes any capture worse is held back. Rendering work carried on, but aimed at defects players see in games (section 4). 0.5.0 still brought wide lines from 47.82% to 99.58% matching, along with better YUV, DXT, shadow-map, clipping, fog and blit results.

## 4. From pixels to games (09-25 onward)

On 09-25, with the pixel suites now a gate, the maintainer turned the project toward the defects players actually see: specific graphical glitches already reported in games such as Galleon, and others shown in a community video review. The same day set the targets for 1.0:

- **Scope:** 90% of the 950 titles xemu rates Playable or better, so 855 titles, each actually tested, at about 145 titles per minor release.
- **Playable:** at least 30 fps at full speed, reaching gameplay and staying there through a timed soak, with no audio dropouts.
- **Perfect:** only from a human review.

On 09-26, 17 titles had been tested and none was Playable. The 0.5 target became 145 titles measured and 50 Playable. That evening the maintainer also judged that general speed-ups were reaching diminishing returns, and directed new work into per-title investigations.

**Proving a title is hard.**
- **The soak:** it began at 20 minutes and was cut to a 600-second window on 09-30. That evening the first Playable Wall went up, listing the eight titles that had passed.
- **Getting into gameplay:** scripted button routes kept failing, because a script pressing buttons on a timer can't see whether it is in a menu, a cutscene or the game. By 10-02, 49 device-hours had produced one verified 600-second window. Button mashing wasn't good enough, so the project built a screen classifier that runs on the maintainer's own GPU.
  - It looks at each frame and names what it shows: an intro, a title screen, a menu, loading, a pause screen or gameplay. The driver then knows when to press Start, when to work through a menu, and when to stop pressing and play.
  - It pairs an open image-recognition model (SigLIP 2) with a small layer trained on frames from 149 titles, labelled by a Claude model. It also reads on-screen text such as Press START and PAUSE.
  - It is strict about the answer that matters most. It calls a frame gameplay only when it is confident, and at that setting it made no false gameplay calls on its 120-frame test set.
  - The first version was built on 10-02. It has shipped with the test harness since 10-12, and 35 title routes use it.
- **Menus and cutscenes:** from 10-14, a title passes on 600 seconds of real play at the frame-rate bar, even if menus and cutscenes take up the rest of the run.

**The Playable ledger:**

| Date | Event | Playable |
|---|---|---|
| 09-30 | 600-second window; first Playable Wall | 8 |
| 10-03 | Halo: Combat Evolved (722 s at 30 fps 99.4% of the time) | 16 |
| 10-04 | Jet Set Radio Future | 21 |
| 10-06 | A daily Playable target becomes a requirement, not an aim | 36 |
| 10-07 | All title work moves to the Retroid Pocket Nova | 43 |
| 10-12 | 0.5.0: GTA III, GTA Vice City, and Grabbed by the Ghoulies after an 1,800-second soak | 52 |
| 10-13 | Tony Hawk's Pro Skater 4; Burnout Revenge on the maintainer's own play | 67 |
| 10-14 | The real-play rule above | 77 |
| 10-16 | Slam Tennis and Family Guy | 87 |
| 10-17 | Marvel Nemesis: Rise of the Imperfects | 88 |

Need for Speed: Most Wanted was accepted on 10-12 from the maintainer's own race, with a 29.9 fps median on the 0.5.0 build.

**The devices.** The Retroid Pocket Nova has been the test device from the first day. An AYN Thor joined on 09-12. Its fan died on 09-29, and it is out of service while replacement parts arrive.

**Where the titles stood on 10-17.** The title registry had 967 rows:

| State | Titles |
|---|---|
| Playable | 88 |
| Not yet screened | 681 |
| Runs, below the bar | 79 |
| The test harness couldn't drive it | 75 |
| Excluded | 28 |
| Crashes or hangs | 16 |

Marvel Nemesis: Rise of the Imperfects was the last title waiting on a ruling. Its run played for 602 seconds at a 29.97 fps median and was at full frame rate 98.9% of the time. It was held for one stall of about a second while the game loaded. The maintainer ruled that a pause for loading is loading, not a hitch, and the title was accepted on 10-17.

## 5. Performance (09-25 onward)

**The emulated CPU (09-25 to 10-03).** hakuX translates the Xbox's x86 code into ARM code as it runs. Six changes to that translator and its memory handling shipped on by default in 0.5.0. Most titles already sat at their 30 fps cap, so the gains show in the slowest frames, CPU time per frame and stalls rather than in the median:

- **Jump cache (09-26).** Discarding one block of translated code used to wipe the whole jump cache. In Crimson Skies those wipes had taken 8.6% of the emulated CPU's time; they now take none. The slowest tenth of frames went from 23 to 26 fps, with every test pixel unchanged.
- **Dirty-page tracking (09-29).** The walk that arms dirty-page tracking now visits the 2 memory modes in use instead of all 22. In Crimson Skies on the Thor:
  - the walk's cost per frame fell from 3.70 ms to 0.77 ms on the render thread;
  - frames that took three or more screen refreshes fell from 4.3% to 0.8%.
- **A dead fast path removed (10-03).** A memory fast path turned out never to engage during gameplay. Removing it cut the host instructions per translated block by 21%, and the emulated CPU's time per frame in GTA San Andreas by 4-6%.
- **Targeted flushes (10-03).** Watching or unwatching a GPU surface now drops only the affected address range, instead of flushing the whole address-translation cache. Full flushes per second fell:
  - Conker: 145 to 1;
  - Blinx 2: 40 to 1;
  - Forza: 31 to 2.
- **An ARMv8.2 build (09-26).** Native thread-local storage, inline atomics and direct calls cut that overhead from 3.42% of the emulated CPU's samples to 0.41%. The cost was raising the minimum CPU.
- **A lock-free read (10-03).** The guest now reads the GPU command queue's position without taking a lock.

The October releases added two correctness fixes:
- **0.5.1:** float-to-integer stores round the way the game asks. Halo's menu ring had 9 glitched frames and now has none.
- **0.5.2:** a control-word fix, covered under Halo below.

Several CPU ideas were built, measured and left off because they did not turn into frames:
- **An inline branch cache** cut lookup time in GTA from 24.9% of the CPU to 7.3%. The freed time became idle time rather than frames.
- **Pinning the emulated CPU to the big core** lost 21.5%, because heat pushed it onto the small cores.

An analysis on 10-04 found that no combination of translator changes would reach 60 fps.

**Rendering, pacing and audio (09-26 to 10-11).** Several games were slow because of how the emulator handed work to the GPU, not because of the GPU itself. Others wasted CPU time waiting:

| Change | Date | Result |
|---|---|---|
| Stop watching a movie surface after its first write | 09-26 | 50 Cent: Bulletproof's movies play at full speed; a 97-second teaser takes 98 s instead of 111 |
| Release the graphics lock while waiting on a frame fence | 09-27 | the CPU's lock-wait share fell from 70% to 0.4%; DOA Ultimate went from 13 to 15 fps |
| Don't re-hash a texture already checked that frame | 09-27 | Crimson Skies render-thread time 23.7 → 14.5 ms a frame; frames taking three or more refreshes 12.6% → 3.4% |
| A per-title GPU rendering mode | 09-28 | 007: Agent Under Fire 17 → 26 fps; DOA Ultimate 13 → 20 |
| The frame limiter sleeps instead of spinning | 09-28 to 09-29 | Kabuki's limiter CPU 1.35 → 0.01 ms a frame |
| GPU surface reuse | 10-10 | NBA Live 07 23 → 47 fps; NBA Live 2005 25 → 43 |
| Fast renderer paths | 10-11 | Need for Speed: Most Wanted first race 26.4 → 29.8 fps; The Simpsons free roam 47.7 → 59.2 |
| Audio paced instead of written in bursts | 10-11 | Need for Speed: Most Wanted's repeated audio 15.7% → 0 |

**The ubershader (09-28 to 10-02).** The first-play stutter on Android had one main cause. On 09-28 a lane measured it: 96% of the stall was the GPU driver compiling shaders inside pipeline creation, at about 400 ms a shader. Upstream xemu has no async or ubershader path to borrow.

By that afternoon a register-combiner ubershader was running. It is a single shader that interprets the combiner state, instead of compiling a new shader for every program, and it covered all 548 programs. A vertex ubershader and a graphics-pipeline-library ladder followed on 09-29.

- **09-30:** 1317 of 1317 test pixels were identical to the exact shaders.
- **Pipeline creation:**
  - Dead or Alive 3: 26.2 s to 2.7 s.
  - DOA3's first fight: 2.9 s to 52 ms.
  - A Kabuki Warriors fight: 133 s to 27 ms.

It went on by default on 10-02. On a cold first launch on the Nova:

| Title | Pipeline creation | Freezes | Time at full frame rate |
|---|---|---|---|
| Kabuki Warriors | 141.3 s → 2.8 s | three (22.5, 10.7, 60.9 s) → none | 72% → 93% |
| Dead or Alive 3 | 122.7 s → 2.9 s | gone | 63% → 82% |
| Tron 2.0 | 49.8 s → 3.2 s | a 226-second hang → none | 48% → 82% |

Two more steps cut the remaining compile cost:
- **Prebuilding:** pipelines from a previous play are now built ahead of time on a compile pool. This removed replay stalls: 34% fewer hitches on replay, and the worst stall 86% shorter.
- **Lit pipelines:** they compile about twice as fast, 25.8 s down to 12.0 s for the same set.

**Halo (10-16 to 10-17).** On 10-16 the maintainer played Halo: Combat Evolved and found its opening cinematic running at about 17 fps. Three changes, each measured on its own, brought it to about 29 fps by the next morning, and 0.5.2 shipped them that afternoon:

- **16-bit render targets are converted on the GPU** instead of being copied back to the CPU. Halo's cinematic went from 59.3 to 41.9 ms a frame. The same change lifted:
  - a Mortal Kombat: Shaolin Monks cutscene from 27.5-29 to 54 fps;
  - Top Spin matches from 38 to 59 fps.
- **Occlusion tests are answered as soon as they are queued,** using the test's previous count. The game had been spinning while it waited on them, for a quarter of its time; afterwards it spun 1% of the time. This took the cinematic from 42.1 to 35.9 ms a frame.
- **The translator no longer ends a block of code each time the game reloads the floating-point control word,** only when the precision actually changes. Halo reloads it constantly and never changes it: exits at that one routine fell from 36,249 to 0. On its own this took the cinematic from 42.6 to 40.5 ms a frame.

Together they took the cinematic from 58.9 ms a frame to 35.0 (17.0 fps to 28.6). When the maintainer played the release build that afternoon, it held 29 fps in 91.6% of readings. One cutscene still dipped to 19-23 fps ([#1018](https://github.com/jreinach-alt/hakuX/issues/1018)).

## 6. Save states (10-11 to 10-12)

hakuX's save states are xemu's work, brought forward. The desktop xemu has had working snapshots all along, and X1 BOX brought save states to its own Android app on 02-28. hakuX, though, had forked X1 BOX twelve days earlier, from an early port where save states were stubbed out: the Android app was built against a stand-in file whose save and load functions did nothing.

Every hakuX release before 0.5.0 carried that stub. That covers rfandango's 0.3.1 and this fork's 0.3.3-j1, 0.4.0-j1 and 0.4.1-j1, and the source of each one confirms it.

0.5.0 pulled xemu's snapshot code forward into hakuX on Android, made it reliable there, and built the handheld features on top:

- **10-11:** xemu's own snapshot code replaced the stub in the Android app. On the Nova a state was about 59 MB. It took about 300 ms to save and about 100 ms to load, and passed 40 of 40 save-and-load cycles.
- **10-11 to 10-12, the full feature:**
  - **Slots:** ten per game plus an auto slot, with undo for the last save and the last load.
  - **Disk rewind:** loading a state also rewinds the virtual hard disk, via a disk-only snapshot that takes 18-29 ms.
  - **Compression:** on by default, it shrinks a state from 41.6 MB to 10.1 MB, for a 76 ms pause against 67 ms uncompressed.
  - **Testing:** 160 saves and 160 loads, all clean.
- **Safety:** a load is refused if the state doesn't match the running game, disc, controller layout or save format, so a state can't load into the wrong game.

Save states shipped in 0.5.0 on 10-12.

## 7. How the work gets done: the harness

The code is written by AI coding agents running Claude Code. A *lane* is one agent session briefed on one issue and working in its own copy of the repo. When it finishes, its work is *folded*: merged into the trunk after checks. The harness is everything around the lanes: the device queue, the board that says what to work on, the checks, and the jobs that keep it all moving without colliding.

The harness has had five designs. Each one fixed the main flaw of the one before:

| Design | Dates | Shape | Main flaw |
|---|---|---|---|
| 1. One session | 09-06 to 09-11 | One interactive session does everything | One device and one pair of hands; work done twice; tracker drift |
| 2. Orchestrator and sub-agents | 09-12 to 09-18 | The session dispatches agents into their own copies | Everything stops when the session does; agents start from stale code |
| 3. Timed jobs on GitHub | 09-19 to 09-29 | Stateless jobs every 20 minutes; GitHub holds the board | Folds deadlock unseen; GitHub is a single point of failure |
| 4. Offline trunk and local forge | 09-30 to 10-09 | A local repo, a fold queue, a forge and model-free watchers | Jobs left running against GitHub; landed fixes not reaching the runner |
| 5. Consolidation | 10-10 onward | Fewer moving parts, a gate before every device run | The GitHub mirror and the forge's issue state lag |

**1. One session (09-06 to 09-11).** One interactive session held the working branch, built the app, drove the one handheld and committed directly. It dispatched only four sub-agents in five days. A review on 09-12 listed the flaws:
- **Duplicated and retracted work.** Two agents produced the same fix independently, and five claims about causes had to be withdrawn.
- **Tracker drift.** The issue tracker listed six closed issues as open and had silently lost three entries.
- **Mismatched comparisons.** A working fix was reverted after numbers from two different test discs were compared.
- **Hand-kept builds.** Five APKs were in flight and kept straight by hand.
- **The device was the bottleneck,** at about 10-30 measurements an hour.

The fix was a device dispatcher (09-12) that owns the device and records which build and disc every measurement used. Alongside it came a territory table of the files each agent may change (09-13) and a registry of running agents.

**2. Orchestrator and sub-agents (09-12 to 09-18).** The session became an orchestrator. It dispatched 54 sub-agents on 09-12 and 128 by 09-18. Commits rose from about 50 a day to about 190. The flaws:
- **Everything depended on one conversation.** When its turn ended, nothing was dispatched, folded or read. On 09-18 alone there were two fleet-wide stalls, and three finished experiments sat unqueued with both devices idle.
- **Agents started from stale code.** Their copies were based on the trunk, which had fallen 1,275 commits behind the working branch, and some agents redid work that had already landed.
- **One shared build tree.** The device queue built from it and refused it whenever it was dirty: 251 requeues in a day.
- **Coordination files were rolled back.** They lived in the tree, so cherry-picks silently reverted them.
- **Permission waits.** 77 commits waited hours for permission to touch a file that was already marked free.

On 09-18 the harness was redesigned around five rules:
1. No long-lived orchestrator: a stateless job runs every 20 minutes.
2. The board lives on GitHub and on a branch of its own.
3. No shared trees: every lane gets its own copy and builds privately.
4. Master is the trunk, and folds are merges.
5. CI is used freely.

It was built that evening. 09-19 brought the first nightly build on a moving trunk.

**3. Timed jobs on GitHub (09-19 to 09-29).** Each lane was a headless agent session on one issue with one pull request. A fold job merged it once an audit and CI passed, and cloud jobs audited every PR twice. This was the busiest stretch. In the week of 09-21, after the move to Opus 5.5 on 09-24, there were 397 lane sessions, 266 cloud runs and 262 folds, 114 of them on 09-25 alone. GitHub's issue and PR numbers went from #200 to #629 in nine days. The flaws:
- **The monitor followed a checklist.** Every jam of 09-25 and 09-26 was invisible to it:
  - folds deadlocked;
  - lanes stranded when their background tasks died;
  - ready PRs nobody marked;
  - a device queue 94 commits behind the trunk;
  - 31 issues ready to dispatch while 4 lanes ran.
- **An index that conflicted on every fold.** The code index stored line numbers, so a four-line insert rewrote 125 entries. Every open PR then conflicted, GitHub ran no CI on a conflicting PR, and the fold job waited indefinitely.
- **Decisions sat for days** waiting for a human. The maintainer ruled that the harness makes those calls itself.
- **GitHub was a single point of failure.** It held the board, CI, the fold gate and the channel to the cloud jobs.

Fixes landed inside the design on 09-25 and 09-26:
- The host monitor moved onto a timer, with a watchdog.
- A health check measured outcomes, such as lanes running and folds landing, instead of ticking off steps.
- The index anchored on content rather than line numbers.
- A lane's files were released as soon as its PR was ready.

On the evening of 09-29 GitHub suspended the account. It gave no reason. At the time one account was producing about 330 PRs and 2,500 Actions runs a week.

**4. Offline trunk and local forge (09-30 to 10-09).** The first hour and a half after the suspension went on protecting the source:
- a backup bundle of every branch and tag (885 refs), on a second drive;
- a local bare repository;
- URL rewrites so that every tool pointed at the local repository.

Then the harness was rebuilt around it:
- **A fold queue (09-30).** Every 15 minutes it merges each ready lane in a scratch tree. A lane folds only if:
  - its selftest passes;
  - a device run was made from the exact code, whenever emulator code changed;
  - it touched only files in its territory;
  - it has exactly one PR description.
  
  The first offline fold landed at 00:21 on 09-30.
- **A local forge (10-02).** Forgejo took over issues and PRs. The GitHub-era issues had no public archive, so a lane rebuilt them from the agents' own transcripts: 629 numbers recovered, 336 of them in full.
- **Model-free watchers (10-03).** Single-purpose jobs watch for an idle device, waiting lanes, stalls and failures, and act without calling a model.
- **GitHub's return (10-05).** The forge stayed the place of work by choice. A gateway mirrors it to GitHub one way every 15 minutes, and Actions stay off.

The flaws:
- **Jobs still bound to GitHub kept running against nothing.** The host monitor kept calling GitHub for three days, and four GitHub-only timers kept firing.
- **A jam handler was cut before its replacement acted.** A fold failed late on 10-02, and the Nova sat idle until morning.
- **A fold isn't live until the running tree moves.** The tree that builds device runs sat 417 commits behind for three days, so a landed fix never ran.
- **Four wrong dispatches in one day** (10-06). The maintainer ruled that nothing reaches a device unless a gate has checked it.
- **A three-day mirror stall nobody noticed** (10-06 to 10-09), caused by a deadlocked pipe.
- **Two issue numberings drifted apart,** GitHub's and the forge's.

The fold queue itself refused 72 folds in this design and the next. 45 of those were lanes touching files outside their territory, which is the check doing its job. The fixes:
- **10-06:** the queue starts the device run for the new trunk and updates the running tree after every fold.
- **10-09:** the mirror was reworked and re-arms itself.

**5. Consolidation (10-10 onward).**
- **10-10:** the planning agent was retired, and operational calls moved to the maintainer's session and to model-free jobs. One model table now serves every job.
- **10-11:** every device request is checked against the title's state before it runs.
- **10-12:** issue and PR numbers come from one space. GitHub allocates them, and a mirror keeps both sides in step.
- **10-16:** each fold runs the selftest fragments its PR names, instead of the whole 146-fragment suite, which took 30-60 minutes.
- **10-16:** every title defect becomes an issue and a tracker row in the same session.
- **10-17:** every brief starts with a committed table of what has already been tried.

Open flaws:
- **A second runner tree** for the pathfinder sat 136 commits behind for a day, so two landed fixes didn't reach the device until 10-13.
- **The GitHub mirror skipped** any push that changed workflow files and reported it only as a skip. GitHub's master was stale from 10-13 to 10-16, and an alarm was added on 10-16.
- **Forge issue state isn't kept up as work lands.** 209 of the 215 issues filed on the forge still show as open, so the open count overstates the backlog.

**Activity by week**, on master:

| Week | Commits | Merges | Folds | Lane sessions |
|---|---|---|---|---|
| 09-06 to 09-13 | 1,228 | 40 | 117 | |
| 09-14 to 09-20 | 786 | 174 | 208 | 97 |
| 09-21 to 09-27 | 1,509 | 540 | 262 | 397 |
| 09-28 to 10-04 | 916 | 302 | 158 | 339 |
| 10-05 to 10-11 | 610 | 153 | 65 | 178 |
| 10-12 to 10-17 | 354 | 120 | 79 | 85 |
| **Total** | **5,403** | **1,329** | **889** | **1,096** |

About the columns:
- **Commits** excludes merges.
- **Folds** counts every landing on the trunk: manual landings and cherry-picks to 09-18, 399 GitHub PR folds from 09-18 to 09-29, and 234 offline folds since.
- **Lane sessions** are counted from 09-18, when the lane log began. Before that the orchestrator dispatched 128 sub-agents.

**Issues and PRs to 10-17.** Issues and PRs share one number space, and #1 to #1049 are in use:

| | On GitHub, to 09-29 | On the forge, from 10-02 | Total |
|---|---|---|---|
| Issues filed | 193 | 215 | 408 |
| Issues marked closed | 133 | 6 (see the open flaws above) | 139 |
| PRs | 432 (399 folded) | 194 (175 merged) | 626 |

## 8. The releases

**0.3.3-j1 (09-07): launching from a frontend.**
- **New:** installs alongside an official build under its own app id; exports the EEPROM beside the HDD image.
- **Fixed:** launching a game from ES-DE or another frontend, which had not worked in any released build; a crash when a ROM link could not be passed on; exiting a frontend-launched game now returns to the frontend; diagnostic log tags that the log capture had been dropping.
- **Smaller:** the APK went from 30.3 MiB to 23.4 MiB by shipping the Vulkan validation layer in debug builds only.

**0.4.0-j1 (09-10): rendering accuracy.**
- **Rendering:** every change was measured against framebuffers captured from a real Xbox. It covers texture borders and border colour, wrap modes, cylinder wrap, texture perspective, signed texture channels, textures the CPU rewrites in place, cube maps, more texture formats, render targets, depth, fog and fixed-function lighting.
- **Fixed:** several emulator aborts and Vulkan resource-lifetime bugs, and a clean exit when the guest powers off.

**0.4.1-j1 (09-26): fixing our own regression.** This one was our fault, not something inherited from earlier hakuX builds.
- **The cause:** on 09-08, a PGRAPH accuracy fix stopped the renderer from writing old render-target pixels over memory the game had since reused. It took the bump-map tests from 2 of 40 passing to 38, and it shipped in 0.4.0-j1.
- **What it broke:** the fix kept a memory watch on each retired render target. When the slot was reused, that watch was dropped without being released. Every guest memory lookup walked the growing list, so Grabbed by the Ghoulies, RalliSport Challenge 2 and Conker slowed to 1-3 fps after a few minutes of play.
- **The fix:** release the watch before the slot is reused. 0.4.1-j1 shipped that one change on its own, and Grabbed by the Ghoulies held 29 fps again on both devices.

**0.5.0 (10-12): rated by play.**
- **Playable:** the first release rated by play rather than by pixel counts: 52 titles Playable, and frame rates measured on 175.
- **New:** save states, using xemu's snapshot code in place of the stub hakuX had carried since the fork; several games folders; the ubershader; pipelines prebuilt from a previous play; fast renderer paths; GPU surface reuse; and full-screen output on the Thor's small bottom screen.
- **Game fixes:**
  - Need for Speed: Most Wanted no longer stutters or repeats audio, and its first race starts at 29.8 fps instead of 26.4.
  - GTA San Andreas loses its hard-edged white sky polygons.
  - RalliSport Challenge's rival cars no longer vanish on alternate frames.
  - Forza Motorsport no longer slows over a race.
  - 50 Cent: Bulletproof's movies play at full speed.
  - 007: Agent Under Fire goes from 17 to 26 fps.
  - NBA Live 07 goes from a 23 to a 47 fps median.
- **Timing:** games that set their clock from VBLANK no longer run slow (Galleon went from 56.6 Hz to 59.8 Hz), and 720p and 1080i games are no longer timed as PAL.
- **Crashes and hangs fixed:**
  - a translation-cache race with disc DMA;
  - a crash when the texture cache filled;
  - an overflow on very large inline draws;
  - an assertion when a vertex program wrote its own constants.
- **Rendering:**
  - wide lines now match the hardware 99.58% of the time, up from 47.82%;
  - YUV textures are exact;
  - DXT decoding is closer to the hardware;
  - shadow-map comparisons, clipping, fog, blits and smaller corrections all improved.
- **Requirements:** Android 10 and an ARMv8.2 CPU. Box art lookup became opt-in.

**0.5.1 (10-16): hakuX CE.**
- **New:** the app is renamed hakuX CE (Community Edition), with a new adaptive icon.
- **Fixed:**
  - Halo's menu ring no longer jumps back in bursts, because float-to-integer stores now round the way the Xbox does;
  - bad audio data, a missing audio device, a texture outside video memory or a corrupt pipeline cache no longer crashes the emulator;
  - the setup wizard rejects a BIOS file of the wrong size.
- **Published:** on GitHub on 10-16 at 23:00.

**0.5.2 (10-17): Halo and Shaolin Monks.**
- **Halo: Combat Evolved:** the opening cinematic goes from 17 fps to about 29. Occlusion tests are answered as soon as they are queued, the cinematic's colour surfaces skip a slow texture path, and the CPU translator stops recompiling around one floating-point instruction. Some stretches still run under 30 fps ([#1018](https://github.com/jreinach-alt/hakuX/issues/1018)).
- **Mortal Kombat: Shaolin Monks:** the Goro's Lair cutscene goes from 27.5-29 fps to about 54. 16-bit render targets that a game samples as textures are now converted on the GPU, for every title.
- **Published:** on GitHub on 10-17.

---

*A note on counts:* the Playable figures here come from the project's acceptance ledger. The public compatibility list is refreshed in batches, so it can show a lower number for a few days.
