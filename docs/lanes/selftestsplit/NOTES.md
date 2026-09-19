# lane.selftestsplit

Splitting `docs/testing/jobs/selftest.sh` into separately-ownable fragments
under `docs/testing/jobs/selftest.d/`, so two harness lanes adding checks never
touch the same path.

In progress.
