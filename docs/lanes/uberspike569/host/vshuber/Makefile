# Host check for #569's uber vertex stage (glsl/vsh-uber.c). Builds the real
# vertex generators (vsh.c carved by vcarve.py; vsh-ff.c, vsh-prog.c,
# vsh-uber.c as they are) against psh_differ's shim.
#
#   make && ./vshcheck.sh
#
# SRC=<dir> builds against another tree's glsl/ (the text-identity check).

REPO     := ../../../../..
BUILD    ?= build
SRC      ?= $(REPO)/hw/xbox/nv2a/pgraph/glsl
DIFFER   := $(REPO)/docs/testing/psh_differ

INCLUDES := -I$(DIFFER)/shim -I$(REPO)/include -I$(REPO) -I$(SRC)
GLIB_CFLAGS := $(shell pkg-config --cflags glib-2.0)
GLIB_LIBS   := $(shell pkg-config --libs glib-2.0)
CFLAGS  ?= -O1 -g
ALL_CFLAGS := -std=gnu11 $(CFLAGS) $(INCLUDES) $(GLIB_CFLAGS) -Wno-all

VKINC ?= /home/justin/hakux-work/wt/turnipcost569/.scratch/mesa/include

OBJS := $(BUILD)/vsh.o $(BUILD)/vsh-ff.o $(BUILD)/vsh-prog.o \
        $(BUILD)/vsh-uber.o $(BUILD)/common.o $(BUILD)/vshhost.o

.PHONY: all clean
all: $(BUILD)/vshhost $(BUILD)/vsrender

$(BUILD)/vshhost: $(OBJS)
	$(CC) -o $@ $^ $(GLIB_LIBS) -lm

$(BUILD)/vsrender: vsrender.c
	@mkdir -p $(BUILD)
	$(CC) -std=gnu11 -O1 -g -I$(VKINC) -o $@ $< -ldl

$(BUILD)/vsh.c: $(SRC)/vsh.c vcarve.py
	@mkdir -p $(BUILD)
	python3 vcarve.py $< -o $@

$(BUILD)/common.c: $(SRC)/common.c
	@mkdir -p $(BUILD)
	$(DIFFER)/carve.py $< -o $@

$(BUILD)/vsh-ff.c: $(SRC)/vsh-ff.c
	@mkdir -p $(BUILD)
	cp $< $@

$(BUILD)/vsh-prog.c: $(SRC)/vsh-prog.c
	@mkdir -p $(BUILD)
	cp $< $@

$(BUILD)/vsh-uber.c: $(SRC)/vsh-uber.c
	@mkdir -p $(BUILD)
	cp $< $@

$(BUILD)/%.o: $(BUILD)/%.c
	$(CC) $(ALL_CFLAGS) -c -o $@ $<

$(BUILD)/vshhost.o: vshhost.c
	@mkdir -p $(BUILD)
	$(CC) $(ALL_CFLAGS) -c -o $@ vshhost.c

clean:
	rm -rf $(BUILD)
