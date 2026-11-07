QCC ?= qcc
VARIANT ?= gcc_ntox86_64
CFLAGS ?= -O2 -g
SOURCES = main.c timing.c ipc.c load.c system.c service_probe.c

pp-agent: $(SOURCES) pp.h ../examples/telemetry-service/protocol.h
	$(QCC) -V$(VARIANT) -std=c11 -D_QNX_SOURCE -Wall -Wextra -Werror $(CFLAGS) -o $@ $(SOURCES)

.PHONY: all
all: pp-agent
