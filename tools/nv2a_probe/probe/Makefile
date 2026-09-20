# NV2A hardware probe, phase one.
#
# No GEN_XISO on purpose: the probe is launched from the HDD, so the disc image
# is never built, and not building it keeps extract-xiso -- and therefore cmake
# -- off the prerequisite list entirely. See ../README.md.

XBE_TITLE = nv2a_probe
SRCS      = $(CURDIR)/main.c
NXDK_NET  = y

NXDK_DIR ?= $(HOME)/nxdk_pgraph_tests/third_party/nxdk

include $(NXDK_DIR)/Makefile
