"""Independent AXI-Stream protocol monitor from docs/03-interface-spec.md only.

Does not import tb.py. Attached as a cocotb coroutine; records spec violations.
"""
from cocotb.triggers import RisingEdge, Timer


def _signed(val, bits):
    v = int(val)
    if v >= (1 << (bits - 1)):
        v -= 1 << bits
    return v


class AxiMonitor:
    def __init__(self):
        self.violations = []

    def ok(self):
        return not self.violations

    async def run(self, dut):
        last_c = None
        last_a = None
        last_b = None
        await Timer(1, units="ns")

        def snap_src(v, r, d, l, bits):
            vv, rr = int(v.value), int(r.value)
            if vv:
                return (vv, rr, _signed(d.value, bits), int(l.value))
            return (vv, rr, None, None)

        while True:
            rst = int(dut.rst_n.value)
            cv = int(dut.m_axis_c_tvalid.value)
            cr = int(dut.m_axis_c_tready.value)
            cd = _signed(dut.m_axis_c_tdata.value, 32) if cv else None
            cl = int(dut.m_axis_c_tlast.value) if cv else None
            busy = int(dut.busy_o.value)
            done = int(dut.done_o.value)
            err_o = int(dut.err_o.value)
            err = int(dut.err_code_o.value)
            ar = int(dut.s_axis_a_tready.value)
            br = int(dut.s_axis_b_tready.value)
            a = snap_src(dut.s_axis_a_tvalid, dut.s_axis_a_tready, dut.s_axis_a_tdata, dut.s_axis_a_tlast, 8)
            b = snap_src(dut.s_axis_b_tvalid, dut.s_axis_b_tready, dut.s_axis_b_tdata, dut.s_axis_b_tlast, 8)

            if not rst:
                if busy or done or err or cv or ar or br:
                    self.violations.append("reset: outputs not IDLE")
                last_c = last_a = last_b = None
            else:
                if err_o != int(bool(err)):
                    self.violations.append("err_o != |err_code_o")
                if done and busy:
                    self.violations.append("done_o with busy_o=1")
                if done and cv:
                    self.violations.append("done_o while C beat pending")
                if last_c is not None:
                    pcv, pcr, pcd, pcl = last_c
                    if pcv and not pcr:
                        if not cv or cd != pcd or cl != pcl:
                            self.violations.append(
                                "C tdata/tlast/tvalid changed while tvalid && !tready"
                            )
                if last_a is not None:
                    pav, par, pad, pal = last_a
                    if pav and not par:
                        if a[0] != 1 or a[2] != pad or a[3] != pal:
                            self.violations.append("A source dropped hold while !tready")
                if last_b is not None:
                    pbv, pbr, pbd, pbl = last_b
                    if pbv and not pbr:
                        if b[0] != 1 or b[2] != pbd or b[3] != pbl:
                            self.violations.append("B source dropped hold while !tready")
                last_c = (cv, cr, cd, cl) if cv else None
                last_a = a if a[0] else None
                last_b = b if b[0] else None

            await RisingEdge(dut.clk)
            await Timer(1, units="ns")
