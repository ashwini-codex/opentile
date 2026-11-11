SIM ?= verilator
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES ?= $(PWD)/reg1.sv
TOPLEVEL ?= reg1
MODULE ?= test_reg1
WAVES ?= 0

# Verilator 5: timing and warnings the smoke can ignore.
EXTRA_ARGS += --trace --Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
