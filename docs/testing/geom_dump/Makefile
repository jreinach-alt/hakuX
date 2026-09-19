# Builds geom-dump against the real geometry-shader generator.
#
# The same trick psh_differ uses: glsl/geom.c and glsl/common.c are compiled
# straight out of the tree with the one function that reads PGRAPHState cut
# out, so no configured QEMU build is needed.  The shim headers are
# psh_differ's -- they are read-only here.
#
# Why this exists: a geometry shader that fails to COMPILE draws nothing, and
# on the Vulkan path that failure is silent (audit finding L10).  Neither CI
# job compiles the GLSL this generator emits, so `make run` printing it is the
# only offline way to look at the thing the device will be asked to build.

REPO     := ../../..
BUILD    := build
GLSL     := $(REPO)/hw/xbox/nv2a/pgraph/glsl
SHIM     := ../psh_differ/shim

INCLUDES := -I$(SHIM) -I$(REPO)/include -I$(REPO) -I$(GLSL)
GLIB_CFLAGS := $(shell pkg-config --cflags glib-2.0)
GLIB_LIBS   := $(shell pkg-config --libs glib-2.0)

CFLAGS  ?= -O1 -g
ALL_CFLAGS := -std=gnu11 $(CFLAGS) $(INCLUDES) $(GLIB_CFLAGS)
GEN_CFLAGS := $(ALL_CFLAGS) -Wno-all
OWN_CFLAGS := $(ALL_CFLAGS) -Wall -Wextra -Wno-unused-parameter

OBJS := $(BUILD)/geom.o $(BUILD)/common.o $(BUILD)/dump.o
BIN  := $(BUILD)/geom-dump

.PHONY: all run clean
all: $(BIN)

$(BIN): $(OBJS)
	$(CC) -o $@ $^ $(GLIB_LIBS) -lm

$(BUILD)/geom.c: $(GLSL)/geom.c carve.py
	@mkdir -p $(BUILD)
	./carve.py $< -o $@

$(BUILD)/common.c: $(GLSL)/common.c ../psh_differ/carve.py
	@mkdir -p $(BUILD)
	../psh_differ/carve.py $< -o $@

$(BUILD)/geom.o: $(BUILD)/geom.c
	$(CC) $(GEN_CFLAGS) -c -o $@ $<

$(BUILD)/common.o: $(BUILD)/common.c
	$(CC) $(GEN_CFLAGS) -c -o $@ $<

$(BUILD)/dump.o: dump.c
	@mkdir -p $(BUILD)
	$(CC) $(OWN_CFLAGS) -c -o $@ $<

run: $(BIN)
	$(BIN)

clean:
	rm -rf $(BUILD)
