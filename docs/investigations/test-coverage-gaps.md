# Two suites run a fraction of their goldens, and no config can change it

`Blend tests` has 1,673 goldens and runs 105. `Depth buffer` has 784 and runs
72. Both were read as a configuration gap — the suites running a default subset
unless each test is named explicitly. **That is not the cause, and a config
naming every test changes nothing.** Measured, not assumed: a disc whose config
names all 1,673 blend tests explicitly (104,441 bytes against the usual ~920)
runs 105 of them in 207s.

## `Blend tests`: the 1,568 are interactive-only

`blend_tests.cpp` registers the individual `<sfactor>_<eqn>_<dfactor>` triples
and immediately marks each one interactive:

```c
tests_[name] = [...]() { TestDetailed(name, ...); };
interactive_only_tests_.insert(name);
```

`TestSuite::RunAll` filters on exactly that set:

```c
void TestSuite::RunAll(bool include_interactive) {
    ...
    if (include_interactive ||
        interactive_only_tests_.find(test_name) == interactive_only_tests_.end())
```

and **both call sites pass `false`** — `test_driver.cpp:132` and
`menu_item.cpp:259` — with no path from `RuntimeConfig` to either. The 1,568
are therefore unreachable from any automated run, and from the menu's own
"run all" for the suite; they run only when selected one at a time.
`clipping_precision_tests.cpp` is the only other suite using the mechanism.

The header describes the flag as covering "tests that do not save artifacts",
which is inaccurate here: `TestDetailed` ends in `FinishDraw(name)` and saves
like any other test. That description is probably why the gap went unexamined.

## `Depth buffer`: the missing tests are never created

A different cause, and a more absolute one. `depth_format_tests.cpp` registers
a hand-picked nine cutoffs per combination out of `kNumDepthTests = 48`:

```c
add_entry(0); add_entry(1); add_entry(2);
add_entry(kNumDepthTests / 4); add_entry(kNumDepthTests / 2);
add_entry(kNumDepthTests - kNumDepthTests / 4);
add_entry(kNumDepthTests - 2); add_entry(kNumDepthTests - 1);
add_entry(kNumDepthTests);
```

Four depth formats x two compression settings x nine = **72**, which is exactly
what runs. The rest are not skipped; `tests_` never contains them. The goldens
come from a build whose constructor registered the full sweep.

## What this means for numbers already quoted

Both figures stand as measurements of what we run, and neither can be widened
from this repository:

- `Blend tests`' 6,499,076 non-precision channels, and #43's signed-byte rule
  fitting 3600/3600, are drawn from the 105 `#spot_` grids. Each grid cell
  summarises fifteen destination factors, so the rule is fitted on a coarser
  oracle than the 1,568 would provide. That is a real limitation of the claim,
  and it is not one a longer run on this disc can remove.
- Every `Depth buffer` figure, and #16's conclusions, rest on nine cutoffs of
  forty-nine.

Unlocking either needs an **nxdk_pgraph_tests source change and a rebuilt
ISO**: thread `include_interactive` through from the runtime config (or drop
the insert) for blend; register all forty-nine cutoffs for depth. Blend is the
one worth doing — a fifteen-fold larger oracle, and the right test for #43 —
but it is an upstream change, not a change here.

## Two smaller things found on the way

- **`check_disc.py` fails silently on a large config.** It reports "no test
  config found" for a 104KB config that is present and correct; its outward-in
  brace scan does not cope at that size. It is the pre-flight meant to stop a
  wasted run, and it fails on the first disc big enough to need it.
- **`output_directory_path` must be a single level.** Working discs use
  `e:/blend`; a nested `e:/nxdk_pgraph_tests/blendall` extracts nothing. That
  cost one run here before the real cause was found.


## Correction: a released binary does generate them

This page concluded that unlocking the 1,568 needs an nxdk_pgraph_tests source
change and a rebuilt ISO. That is wrong for blend. The tests were **retired
upstream** when `#spot_` replaced them -- marking them interactive-only is how
that retirement was implemented -- but the **2025-03-14 release still generates
them**: the device lane ran it and got 1,568 captures in 934s, matching the
golden count exactly.

So the oracle is reachable today with an older released disc, no source change
and no rebuild. The mechanism described above is still what the current binary
does; the conclusion drawn from it was too strong.
