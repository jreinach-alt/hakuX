# snapshot1011 OUTBOX (#433)

## #433 -- 2026-10-11 14:10 PDT

The save-state engine is ported to Android with its test sequence (`HAKUX_SNAPSHOT_TEST`). `ui/xemu-snapshots.c`
is built in place of the stub; states carry a version 2 header (schema, build, title, disc, controller layout)
that is checked before the machine resets; save and load start a paused machine first; the vertex-attribute,
lighting-ring, fog and other unsaved pgraph state is saved; the APU FIFO is emptied on load. Every changed C file
passes the NDK compiler with the Android build's flags. The first Nova run of the sequence is next.
