SIM ?= verilator
TOPLEVEL_LANG ?= verilog
ROOT := $(abspath $(CURDIR)/../..)
DUT ?= $(ROOT)/rtl/pe.sv
VERILOG_SOURCES ?= $(DUT)
TOPLEVEL ?= pe
MODULE ?= test_pe
WAVES ?= 0
SIM_BUILD ?= sim_build
PARAM_FMT ?= INT8
TIE_UP ?= 0

export DUT VERILOG_SOURCES PYTHONPATH SUITE SEED COCOTB_RESULTS_FILE PARAM_FMT TIE_UP
export PYTHONPATH := $(ROOT)/tests:$(ROOT)/model/python:$(PYTHONPATH)

EXTRA_ARGS += --timescale 1ns/1ps
ifeq ($(PARAM_FMT),E4M3)
EXTRA_ARGS += -GFMT=0x45344d33
endif
ifneq ($(TIE_UP),0)
EXTRA_ARGS += -GTIE_UP=1
endif
ifeq ($(WAVES),1)
EXTRA_ARGS += --trace
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
