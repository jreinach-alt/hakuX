# NV2A hardware probe, phase one.
#
# No GEN_XISO on purpose: the probe is launched from the HDD, so the disc image
# is never built, and not building it keeps extract-xiso -- and therefore cmake
# -- off the prerequisite list entirely. See ../README.md.
#
# TWO BUILDS, AND THEY MUST NOT BE CONFUSABLE.
#
#   make                          -> bin/default.xbe          (safe; the console one)
#   make PROBE_ALLOW_HAZARDS=y    -> bin-hazards/default.xbe   (EMULATOR ONLY)
#
# The hazard-allowed build compiles out the probe's refusal to write
# NV_PMC_ENABLE, the PLL coefficients and the rest of the hazard list. On
# 2026-09-20 a blind 0 into NV_PMC_ENABLE stopped the console dead -- CPU
# included, so the watchdog could not help and it took a power cycle. Under the
# emulator that same write is a measurement; on the console it is the fault.
#
# So the variant is a BUILD flag and not a config key: a config key would mean
# the console binary could be talked into a hazardous write by editing a file
# next to it. But "a separate build" only buys anything if the two builds are
# actually separable, and by default they are not -- which is what the two
# mechanisms below are for:
#
#   1. SEPARATE OUTPUT. The hazard-allowed image lands in bin-hazards/ under
#      its own XBE title, never in bin/. `default.xbe` in bin/ is what the FTP
#      deploy and SITE EXEC steps in ../README.md read, and it can only ever be
#      the safe one.
#   2. THE OBJECTS ARE NOT SHARED ACROSS VARIANTS. nxdk's Makefile tracks
#      SOURCE files, not CFLAGS: build the hazard variant, drop the flag, run
#      make again, and main.obj is newer than main.c so it is not rebuilt --
#      the hazard-allowed object walks straight into what the operator believes
#      is the safe XBE. The stamp below notices the variant changed and deletes
#      the objects before anything else runs.
#
# The third mechanism is on the host: the probe announces
# "-HAZARDS-ALLOWED-EMULATOR-ONLY" in its HELLO and probe_driver.py refuses the
# session unless the caller passed allow_hazards. A build flag nobody can
# observe at runtime is a comment.

PROBE_ALLOW_HAZARDS ?= n

ifeq ($(PROBE_ALLOW_HAZARDS),y)
XBE_TITLE     = nv2a_probe_HAZARDS
OUTPUT_DIR    = bin-hazards
CFLAGS       += -DPROBE_ALLOW_HAZARDS
PROBE_VARIANT = hazards
else
XBE_TITLE     = nv2a_probe
OUTPUT_DIR    = bin
PROBE_VARIANT = safe
endif

SRCS      = $(CURDIR)/main.c
NXDK_NET  = y

# Runs at parse time, before any rule, so a variant switch cannot race a build.
# Cheap and unconditional: the only thing it ever deletes is an object built
# with the other variant's flags.
PROBE_STAMP := $(CURDIR)/.build-variant
$(shell if [ "$$(cat $(PROBE_STAMP) 2>/dev/null)" != "$(PROBE_VARIANT)" ]; then \
            rm -f $(CURDIR)/main.obj $(CURDIR)/main.c.d $(CURDIR)/main.exe \
                  $(CURDIR)/main.lib $(CURDIR)/main.exe.manifest; \
            echo $(PROBE_VARIANT) > $(PROBE_STAMP); \
        fi)

NXDK_DIR ?= $(HOME)/nxdk_pgraph_tests/third_party/nxdk

include $(NXDK_DIR)/Makefile
