/*
 * Standalone build of the hakuX host characterisation harness, for a device
 * that can be reached directly. In the app the same code runs from
 * tcg_target_init, selected by HAKUX_HOSTBENCH / HAKUX_TOPO; see
 * hostbench.c.inc.
 *
 *   $NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang \
 *       -O2 -o hostbench tools/bench/hostbench_main.c
 *   HAKUX_HOSTBENCH=1 ./hostbench
 */
#define _GNU_SOURCE
#define HOSTBENCH_STANDALONE 1
#include "hostbench.c.inc"

int main(void)
{
    const char *topo = getenv("HAKUX_TOPO");
    hakux_place_vcpu_once();   /* HAKUX_PLACE_VCPU pins this thread */
    hakux_hostbench_maybe_run();
    if (topo && topo[0] && strcmp(topo, "0") != 0) {
        pause();
    }
    return 0;
}
