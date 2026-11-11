SIM ?= verilator
TOPLEVEL_LANG ?= verilog
ROOT := $(abspath $(CURDIR)/../..)
DUT ?= $(ROOT)/rtl/array.sv
PE  ?= $(ROOT)/rtl/pe.sv
VERILOG_SOURCES ?= $(DUT) $(PE)
TOPLEVEL ?= array
MODULE ?= test_array
PARAM_R ?= 4
PARAM_C ?= 4
PARAM_FMT ?= INT8
WAVES ?= 0
SIM_BUILD ?= sim_build
XSEED ?=

export DUT PE VERILOG_SOURCES PYTHONPATH SUITE SEED COCOTB_RESULTS_FILE PARAM_R PARAM_C PARAM_FMT K_MAX TRACE_GOT TRACE_WANT
export PYTHONPATH := $(ROOT)/tests:$(ROOT)/model/python:$(ROOT)/scripts:$(PYTHONPATH)

EXTRA_ARGS += --timescale 1ns/1ps
EXTRA_ARGS += -GR=$(PARAM_R) -GC=$(PARAM_C)
ifeq ($(PARAM_FMT),E4M3)
EXTRA_ARGS += -GFMT=0x45344d33
endif
ifneq ($(XSEED),)
COMPILE_ARGS += --x-initial unique
PLUSARGS += +verilator+seed+$(XSEED)
endif
ifeq ($(WAVES),1)
EXTRA_ARGS += --trace
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
