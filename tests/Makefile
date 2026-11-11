SIM ?= verilator
TOPLEVEL_LANG ?= verilog
DUT ?= $(abspath $(CURDIR)/standins/good.sv)
VERILOG_SOURCES ?= $(DUT)
TOPLEVEL ?= tile_top
MODULE ?= test_tile
PARAM_R ?= 2
PARAM_C ?= 2
K_MAX ?= 64
WAVES ?= 0
VL_COVERAGE ?= 0
SIM_BUILD ?= sim_build/$(notdir $(basename $(DUT)))_$(PARAM_R)x$(PARAM_C)
XSEED ?=

export DUT VERILOG_SOURCES PARAM_R PARAM_C K_MAX SEED SUITE BP VECTORS PYTHONPATH MODULE CFILE VL_COVERAGE

EXTRA_ARGS += --timescale 1ns/1ps --Wno-fatal
EXTRA_ARGS += -Wno-WIDTH -Wno-UNOPTFLAT -Wno-CASEINCOMPLETE -Wno-LATCH
EXTRA_ARGS += -GR=$(PARAM_R) -GC=$(PARAM_C) -GK_MAX=$(K_MAX)
ifneq ($(XSEED),)
COMPILE_ARGS += --x-initial unique
PLUSARGS += +verilator+seed+$(XSEED)
endif
ifeq ($(WAVES),1)
EXTRA_ARGS += --trace
endif
ifeq ($(VL_COVERAGE),1)
COMPILE_ARGS += --coverage
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
