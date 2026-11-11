"""Deliberately wrong checker: expects q==1 while the DUT is held in reset."""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


@cocotb.test()
async def test_reset_wrong_expect(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    dut.rst_n.value = 0
    dut.d.value = 0
    await ClockCycles(dut.clk, 2)
    assert int(dut.q.value) == 1, "broken checker: expected q==1 after reset"
