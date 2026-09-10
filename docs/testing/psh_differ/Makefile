# Builds psh-differ against the real shader generator.
#
# psh.c and glsl/common.c are compiled straight out of the tree, minus the
# functions that read PGRAPHState (see carve.py). Everything QEMU-shaped they
# still reach comes from shim/. Nothing here needs a configured QEMU build --
# `make` in this directory is enough.

REPO     := ../../..
BUILD    := build
GLSL     := $(REPO)/hw/xbox/nv2a/pgraph/glsl

INCLUDES := -Ishim -I$(REPO)/include -I$(REPO) -I$(GLSL)
GLIB_CFLAGS := $(shell pkg-config --cflags glib-2.0)
GLIB_LIBS   := $(shell pkg-config --libs glib-2.0)

CFLAGS  ?= -O1 -g
ALL_CFLAGS := -std=gnu11 $(CFLAGS) $(INCLUDES) $(GLIB_CFLAGS)
# The carved sources are upstream code; do not fail this build on its warnings.
GEN_CFLAGS := $(ALL_CFLAGS) -Wno-all
OWN_CFLAGS := $(ALL_CFLAGS) -Wall -Wextra -Wno-unused-parameter

CARVED  := $(BUILD)/psh.c $(BUILD)/common.c
OBJS    := $(BUILD)/psh.o $(BUILD)/common.o $(BUILD)/differ.o
BIN     := $(BUILD)/psh-differ

.PHONY: all run clean
all: $(BIN)

$(BIN): $(OBJS)
	$(CC) -o $@ $^ $(GLIB_LIBS) -lm

$(BUILD)/%.c: $(GLSL)/%.c carve.py
	@mkdir -p $(BUILD)
	./carve.py $< -o $@

$(BUILD)/psh.o: $(BUILD)/psh.c
	$(CC) $(GEN_CFLAGS) -c -o $@ $<

$(BUILD)/common.o: $(BUILD)/common.c
	$(CC) $(GEN_CFLAGS) -c -o $@ $<

$(BUILD)/differ.o: differ.c
	@mkdir -p $(BUILD)
	$(CC) $(OWN_CFLAGS) -c -o $@ $<

run: $(BIN)
	$(BIN)

clean:
	rm -rf $(BUILD)
