# linumeRT - rdzen natywny (C11). Biblioteka wspoldzielona dla ctypes.
#   make        - buduje build/liblrt_native.so
#   make test   - test C (build/test_zmap)
#   make clean
# -ffp-contract=off: bez FMA, zeby wyniki byly zgodne bit w bit z numpy.
CC ?= cc
CFLAGS ?= -O2
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic -Werror -ffp-contract=off -fPIC
LDLIBS += -lm
BUILD := build

.PHONY: all test clean
all: $(BUILD)/liblrt_native.so

SRC := lrt_zmap.c lrt_gcode.c lrt_sim.c
HDR := lrt_zmap.h lrt_gcode.h lrt_sim.h

$(BUILD)/liblrt_native.so: $(SRC) $(HDR)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -shared -o $@ $(SRC) $(LDLIBS)

$(BUILD)/test_zmap: tests/test_zmap.c lrt_zmap.c lrt_zmap.h
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -I. -o $@ tests/test_zmap.c lrt_zmap.c $(LDLIBS)

test: $(BUILD)/test_zmap
	./$(BUILD)/test_zmap

clean:
	rm -rf $(BUILD)
