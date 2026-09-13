# Round-trips the MCPX ACI migration field list on the host, with no
# configured QEMU build and no device. `make run` is the whole gate.
#
# The field list and the struct it describes are carved out of the tree by
# carve.py, so this tests the real aci.c and the real ac97_int.h rather than a
# copy that can drift. Everything QEMU-shaped they reach comes from shim/ --
# and only the real migration/vmstate.h and hw/audio/ac97_int.h are used
# unshimmed, because those two are the subject.

REPO     := ../../..
BUILD    := build

INCLUDES := -I. -I$(BUILD) -Ishim -I$(REPO)/include -I$(REPO)
CFLAGS   ?= -O1 -g
ALL_CFLAGS := -std=gnu11 $(CFLAGS) $(INCLUDES) -Wall -Wextra \
              -Wno-unused-parameter

GEN := $(BUILD)/carved.c $(BUILD)/members.c.inc
BIN := $(BUILD)/aci-vmstate

.PHONY: all run clean
all: $(BIN)

$(GEN): carve.py $(REPO)/hw/xbox/mcpx/aci.c $(REPO)/hw/audio/ac97_int.h
	@mkdir -p $(BUILD)
	./carve.py --repo $(REPO) --outdir $(BUILD)

$(BIN): $(GEN) harness.h body.c.inc
	$(CC) $(ALL_CFLAGS) -o $@ $(BUILD)/carved.c

run: $(BIN)
	$(BIN)

clean:
	rm -rf $(BUILD)
