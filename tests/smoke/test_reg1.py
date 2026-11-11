"""cocotb smoke: 1-bit register follows d one cycle after reset is released."""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles


@cocotb.test()
async def test_reset_then_toggle(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.d.value = 0
    await ClockCycles(dut.clk, 2)
    assert int(dut.q.value) == 0, f"reset did not clear q, got {dut.q.value}"

    dut.d.value = 1
    await ClockCycles(dut.clk, 1)
    assert int(dut.q.value) == 0, f"q changed while still in reset, got {dut.q.value}"

    dut.rst_n.value = 1
    await RisingEdge(dut.clk)  # samples d=1 with rst_n=1
    await RisingEdge(dut.clk)  # q visible
    assert int(dut.q.value) == 1, f"q did not follow d=1, got {dut.q.value}"

    dut.d.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    assert int(dut.q.value) == 0, f"q did not follow d=0, got {dut.q.value}"
