"""AXI-Stream driver, C monitor, scoreboard, coverage for tile_top stand-ins."""
import os
import random
import sys

import cocotb
from cocotb.triggers import RisingEdge, Timer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
from ref import gemm_int8, wrap32  # noqa: E402


def to_signed(val, bits):
    v = int(val)
    if v >= (1 << (bits - 1)):
        v -= 1 << bits
    return v


class Coverage:
    def __init__(self):
        self.bins = set()

    def record(self, A, B, K, K_MAX, bp, R, C, err, expect=None):
        flat = [x for row in A for x in row] + [x for row in B for x in row]
        ops = []
        if all(x == 0 for x in flat):
            ops.append("op_zero")
        if any(abs(x) == 1 for x in flat):
            ops.append("op_pm1")
        if any(x in (-128, 127) for x in flat):
            ops.append("op_extreme")
        if any(x > 0 for x in flat) and any(x < 0 for x in flat):
            ops.append("op_mixed")
        for op in ops:
            self.bins.add(op)
        if any(x < 0 for x in flat):
            self.bins.add("sign_neg")
            sgn = "neg"
        else:
            self.bins.add("sign_pos")
            sgn = "pos"
        for op in ops:
            self.bins.add("cross_%s_%s" % (op, sgn))
        if K == 1:
            self.bins.add("K1")
        elif K == 2:
            self.bins.add("K2")
        elif K == K_MAX:
            self.bins.add("KMAX")
        else:
            self.bins.add("Ktyp")
        self.bins.add("bp_" + bp)
        self.bins.add("size_%dx%d" % (R, C))
        if err & 1:
            self.bins.add("err_k")
        if err & 2:
            self.bins.add("err_atlast")
        if err & 4:
            self.bins.add("err_btlast")
        if expect is not None:
            flatc = [x for row in expect for x in row]
            if any(c == 0 for c in flatc):
                self.bins.add("acc_zero")
            if any(abs(c) < 256 for c in flatc):
                self.bins.add("acc_small")
            if any(256 <= abs(c) < 16384 for c in flatc):
                self.bins.add("acc_med")
            if any(abs(c) >= 16384 for c in flatc):
                self.bins.add("acc_large")
            if any(c < 0 for c in flatc):
                self.bins.add("acc_neg")
            if any(c > 0 for c in flatc):
                self.bins.add("acc_pos")

    def dump(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write("coverage bins %d\n" % len(self.bins))
            for b in sorted(self.bins):
                f.write(b + "\n")


COV = Coverage()


class Scoreboard:
    def __init__(self):
        self.beats = []
        self.tlasts = []
        self.errors = []

    def push(self, data, tlast):
        self.beats.append(int(data))
        self.tlasts.append(int(tlast))

    def check(self, expect, name):
        exp_flat = [expect[i][j] for i in range(len(expect)) for j in range(len(expect[0]))]
        if len(self.beats) != len(exp_flat):
            self.errors.append(
                "%s beat count got %d want %d" % (name, len(self.beats), len(exp_flat))
            )
            return False
        for n, (g, e) in enumerate(zip(self.beats, exp_flat)):
            if g != e:
                self.errors.append("%s C[%d] got %d want %d" % (name, n, g, e))
                return False
        if self.tlasts and not self.tlasts[-1]:
            self.errors.append("%s TLAST missing on last C beat" % name)
            return False
        if any(self.tlasts[:-1]):
            self.errors.append("%s TLAST early on C" % name)
            return False
        return True


async def reset(dut, cycles=4):
    dut.rst_n.value = 0
    dut.start_i.value = 0
    dut.cfg_k_i.value = 1
    dut.s_axis_a_tvalid.value = 0
    dut.s_axis_a_tlast.value = 0
    dut.s_axis_a_tdata.value = 0
    dut.s_axis_b_tvalid.value = 0
    dut.s_axis_b_tlast.value = 0
    dut.s_axis_b_tdata.value = 0
    dut.m_axis_c_tready.value = 1
    for _ in range(cycles):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


def ready_gen(mode, rng):
    stall_left = 0

    def next_ready():
        nonlocal stall_left
        if mode == "always":
            return 1
        if mode == "every_other":
            next_ready.n = getattr(next_ready, "n", 0) + 1
            return next_ready.n % 2
        if mode == "random":
            return int(rng.random() < 0.5)
        if mode == "long":
            if stall_left > 0:
                stall_left -= 1
                return 0
            if rng.random() < 0.15:
                stall_left = rng.randint(50, 200)
                return 0
            return 1
        if mode == "stall3":
            # 40 cycles of C not-ready so STORE is stalled for consecutive cycles.
            next_ready.n = getattr(next_ready, "n", 0) + 1
            return 0 if next_ready.n <= 40 else 1
        return 1

    return next_ready


async def run_txn(dut, A, B, R, C, K, bp="always", seed=1, name="txn", start_busy_probe=False):
    rng = random.Random(seed)
    nxt_ready = ready_gen(bp, rng)
    a_beats = [A[i][k] for i in range(R) for k in range(K)]
    b_beats = [B[k][j] for k in range(K) for j in range(C)]
    expect = gemm_int8(A, B, R, C, K)
    sb = Scoreboard()
    a_i = b_i = 0
    dut.cfg_k_i.value = K
    dut.start_i.value = 1
    await RisingEdge(dut.clk)
    dut.start_i.value = 0
    timeout = 0
    last_hold = None
    saw_busy = False

    def drive_ab():
        if a_i < len(a_beats):
            dut.s_axis_a_tdata.value = a_beats[a_i] & 0xFF
            dut.s_axis_a_tlast.value = int(a_i == len(a_beats) - 1)
            dut.s_axis_a_tvalid.value = 1
        else:
            dut.s_axis_a_tvalid.value = 0
            dut.s_axis_a_tlast.value = 0
        if b_i < len(b_beats):
            dut.s_axis_b_tdata.value = b_beats[b_i] & 0xFF
            dut.s_axis_b_tlast.value = int(b_i == len(b_beats) - 1)
            dut.s_axis_b_tvalid.value = 1
        else:
            dut.s_axis_b_tvalid.value = 0
            dut.s_axis_b_tlast.value = 0

    def snap():
        return dict(
            av=int(dut.s_axis_a_tvalid.value),
            ar=int(dut.s_axis_a_tready.value),
            bv=int(dut.s_axis_b_tvalid.value),
            br=int(dut.s_axis_b_tready.value),
            cv=int(dut.m_axis_c_tvalid.value),
            cr=int(dut.m_axis_c_tready.value),
            cd=to_signed(dut.m_axis_c_tdata.value, 32) if int(dut.m_axis_c_tvalid.value) else 0,
            cl=int(dut.m_axis_c_tlast.value) if int(dut.m_axis_c_tvalid.value) else 0,
            busy=int(dut.busy_o.value),
        )

    drive_ab()
    dut.m_axis_c_tready.value = nxt_ready()
    await Timer(1, units="ns")
    s = snap()
    while True:
        timeout += 1
        if timeout > 200000:
            sb.errors.append("%s timeout" % name)
            break
        await RisingEdge(dut.clk)
        if s["cv"]:
            if last_hold is not None:
                prev_d, prev_l, prev_r = last_hold
                if not prev_r:
                    if s["cd"] != prev_d or s["cl"] != prev_l:
                        sb.errors.append(
                            "%s back-pressure ignored: tdata/tlast changed while !tready"
                            % name
                        )
                        break
            last_hold = (s["cd"], s["cl"], s["cr"])
        else:
            last_hold = None
        if s["av"] and s["ar"] and a_i < len(a_beats):
            a_i += 1
        if s["bv"] and s["br"] and b_i < len(b_beats):
            b_i += 1
        if s["cv"] and s["cr"]:
            sb.push(s["cd"], s["cl"])
        if int(dut.done_o.value):
            if int(dut.busy_o.value):
                sb.errors.append("%s busy_o still 1 on done_o" % name)
            break
        if start_busy_probe and int(dut.busy_o.value):
            dut.start_i.value = 1
            saw_busy = True
        elif saw_busy:
            dut.start_i.value = 0
        drive_ab()
        dut.m_axis_c_tready.value = nxt_ready()
        await Timer(1, units="ns")
        s = snap()
    ok = sb.check(expect, name)
    err = int(dut.err_code_o.value)
    COV.record(A, B, K, int(os.environ.get("K_MAX", "64")), bp, R, C, err, expect)
    if sb.errors:
        for e in sb.errors:
            cocotb.log.error(e)
        raise AssertionError("; ".join(sb.errors))
    return ok
