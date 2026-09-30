# Host checks for the #569 P6 combiner ubershader. Builds the real psh.c and
# psh-uber.c the way docs/testing/psh_differ does (carved, against its shim),
# and links psh_differ's baselines by including differ.c.
#
#   make && ./build/uberhost --out build/shaders --per-baseline 200

REPO     := ../../../..
BUILD    := build
GLSL     := $(REPO)/hw/xbox/nv2a/pgraph/glsl
DIFFER   := $(REPO)/docs/testing/psh_differ

INCLUDES := -I$(DIFFER)/shim -I$(REPO)/include -I$(REPO) -I$(GLSL) -I$(DIFFER)
GLIB_CFLAGS := $(shell pkg-config --cflags glib-2.0)
GLIB_LIBS   := $(shell pkg-config --libs glib-2.0)

CFLAGS  ?= -O1 -g
ALL_CFLAGS := -std=gnu11 $(CFLAGS) $(INCLUDES) $(GLIB_CFLAGS) -Wno-all

OBJS := $(BUILD)/psh.o $(BUILD)/common.o $(BUILD)/psh-uber.o $(BUILD)/uberhost.o

.PHONY: all clean
all: $(BUILD)/uberhost $(BUILD)/render_bin

# Vulkan headers only (the loader is dlopened): Mesa's copy, as vendored by
# lane.turnipcost569's build. Override VKINC to use another.
VKINC ?= /home/justin/hakux-work/wt/turnipcost569/.scratch/mesa/include

$(BUILD)/render_bin: render.c
	@mkdir -p $(BUILD)
	$(CC) -std=gnu11 -O1 -g -I$(VKINC) -o $@ $< -ldl

$(BUILD)/uberhost: $(OBJS)
	$(CC) -o $@ $^ $(GLIB_LIBS) -lm

$(BUILD)/psh.c: $(GLSL)/psh.c
	@mkdir -p $(BUILD)
	$(DIFFER)/carve.py $< -o $@

$(BUILD)/common.c: $(GLSL)/common.c
	@mkdir -p $(BUILD)
	$(DIFFER)/carve.py $< -o $@

$(BUILD)/psh-uber.c: $(GLSL)/psh-uber.c carve_uber.py
	@mkdir -p $(BUILD)
	python3 carve_uber.py $< -o $@

$(BUILD)/%.o: $(BUILD)/%.c
	$(CC) $(ALL_CFLAGS) -c -o $@ $<

$(BUILD)/uberhost.o: uberhost.c $(DIFFER)/differ.c
	@mkdir -p $(BUILD)
	$(CC) $(ALL_CFLAGS) -c -o $@ uberhost.c

clean:
	rm -rf $(BUILD)
