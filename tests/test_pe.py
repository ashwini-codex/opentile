"""cocotb tests for rtl/pe.sv. SUITE=all|exhaustive|control|wrap."""
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
from ref import wrap32  # noqa: E402
from ref_fp8 import CANON_NAN, gemm_e4m3  # noqa: E402
from fp8_bins import REQUIRED as FP8_REQUIRED, dump as dump_fp8_bins, record_pairs  # noqa: E402

SUITE = os.environ.get("SUITE") or "all"
SEED = int(os.environ.get("SEED", "1"))
PARAM_FMT = os.environ.get("PARAM_FMT") or "INT8"
IS_FP8 = PARAM_FMT == "E4M3"
REPORTS = os.path.join(ROOT, "reports", "O14" if IS_FP8 else "O6")


def to_signed(val, bits):
    v = int(val)
    if v >= (1 << (bits - 1)):
        v -= 1 << bits
    return v


def i8(dut_val):
    return to_signed(dut_val, 8)


def i32(dut_val):
    return to_signed(dut_val, 32)


def u32(dut_val):
    return int(dut_val) & 0xFFFFFFFF


async def tick(dut):
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.clr.value = 1
    dut.en.value = 0
    if hasattr(dut, "valid"):
        dut.valid.value = 1
    dut.a_in.value = 0
    dut.b_in.value = 0
    for _ in range(2):
        await tick(dut)
    dut.clr.value = 0
    await tick(dut)


def drive_ab(dut, a, b):
    dut.a_in.value = a & 0xFF
    dut.b_in.value = b & 0xFF


async def mac_once(dut, a, b):
    dut.clr.value = 1
    dut.en.value = 0
    await tick(dut)
    dut.clr.value = 0
    dut.en.value = 1
    drive_ab(dut, a, b)
    await tick(dut)
    return i32(dut.acc.value)


@cocotb.test(skip=IS_FP8 or SUITE not in ("all", "exhaustive"))
async def test_exhaustive(dut):
    await start_clock(dut)
    for a in range(-128, 128):
        for b in range(-128, 128):
            got = await mac_once(dut, a, b)
            want = wrap32(a * b)
            if got != want:
                raise AssertionError(
                    "exhaustive a=%d b=%d got %d want %d" % (a, b, got, want)
                )


@cocotb.test(skip=IS_FP8 or SUITE not in ("all", "random"))
async def test_random(dut):
    await start_clock(dut)
    rng = random.Random(SEED)
    for n in range(1000):
        length = rng.randint(1, 200)
        dut.clr.value = 1
        dut.en.value = 0
        await tick(dut)
        dut.clr.value = 0
        total = 0
        for _ in range(length):
            a = rng.randint(-128, 127)
            b = rng.randint(-128, 127)
            dut.en.value = 1
            drive_ab(dut, a, b)
            await tick(dut)
            total += a * b
        dut.en.value = 0
        await tick(dut)
        got = i32(dut.acc.value)
        want = wrap32(total)
        if got != want:
            raise AssertionError("random run %d got %d want %d len %d" % (n, got, want, length))


@cocotb.test(skip=IS_FP8 or SUITE not in ("all", "wrap"))
async def test_wrap(dut):
    """131072 × ((-128)*(-128)) = 2^31 → wrap32 = -2^31. Length ≤200 cannot wrap."""
    await start_clock(dut)
    dut.clr.value = 1
    dut.en.value = 0
    await tick(dut)
    dut.clr.value = 0
    dut.en.value = 1
    drive_ab(dut, -128, -128)
    n = 131072
    for _ in range(n):
        await tick(dut)
    dut.en.value = 0
    await tick(dut)
    got = i32(dut.acc.value)
    want = wrap32(n * 16384)
    if got != want:
        raise AssertionError("wrap got %d want %d" % (got, want))
    if got != -(1 << 31):
        raise AssertionError("wrap expected -2**31, got %d" % got)


@cocotb.test(skip=IS_FP8 or SUITE not in ("all", "control"))
async def test_en_clr_passthrough(dut):
    await start_clock(dut)
    dut.clr.value = 1
    dut.en.value = 1
    drive_ab(dut, 3, 4)
    await tick(dut)
    assert i32(dut.acc.value) == 0
    assert i8(dut.a_out.value) == 0
    assert i8(dut.b_out.value) == 0

    dut.clr.value = 0
    dut.en.value = 1
    drive_ab(dut, 3, 4)
    await tick(dut)
    assert i32(dut.acc.value) == 12
    assert i8(dut.a_out.value) == 3
    assert i8(dut.b_out.value) == 4

    dut.en.value = 0
    drive_ab(dut, 9, 9)
    await tick(dut)
    assert i32(dut.acc.value) == 12
    assert i8(dut.a_out.value) == 3
    assert i8(dut.b_out.value) == 4
    await tick(dut)
    assert i32(dut.acc.value) == 12
    assert i8(dut.a_out.value) == 3
    assert i8(dut.b_out.value) == 4

    dut.clr.value = 1
    dut.en.value = 1
    drive_ab(dut, 7, 7)
    await tick(dut)
    assert i32(dut.acc.value) == 0
    assert i8(dut.a_out.value) == 0
    assert i8(dut.b_out.value) == 0


@cocotb.test(skip=IS_FP8 or SUITE not in ("all", "wave"))
async def test_neg128_wave(dut):
    await start_clock(dut)
    os.makedirs(REPORTS, exist_ok=True)
    lines = ["cycle clr en a_in b_in a_out b_out acc"]

    async def snap(cycle):
        lines.append(
            "%d %d %d %d %d %d %d %d"
            % (
                cycle,
                int(dut.clr.value),
                int(dut.en.value),
                i8(dut.a_in.value),
                i8(dut.b_in.value),
                i8(dut.a_out.value),
                i8(dut.b_out.value),
                i32(dut.acc.value),
            )
        )

    dut.clr.value = 1
    dut.en.value = 0
    drive_ab(dut, -128, -128)
    await tick(dut)
    await snap(0)
    dut.clr.value = 0
    dut.en.value = 1
    drive_ab(dut, -128, -128)
    await tick(dut)
    await snap(1)
    dut.en.value = 0
    await tick(dut)
    await snap(2)
    with open(os.path.join(REPORTS, "neg128.wave.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    assert i32(dut.acc.value) == 16384
    assert i8(dut.a_out.value) == -128
    assert i8(dut.b_out.value) == -128


async def mac_fp8(dut, pairs):
    """clr, then one MAC per (a,b) with valid=1. Returns final FP32 bits."""
    dut.clr.value = 1
    dut.en.value = 0
    if hasattr(dut, "valid"):
        dut.valid.value = 1
    await tick(dut)
    dut.clr.value = 0
    for a, b in pairs:
        dut.en.value = 1
        drive_ab(dut, a, b)
        await tick(dut)
    dut.en.value = 0
    await tick(dut)
    return u32(dut.acc.value)


def want_fp8(pairs):
    A = [[p[0] for p in pairs]]
    B = [[p[1]] for p in pairs]
    return gemm_e4m3(A, B, 1, 1, len(pairs))[0][0]


HAND_FP8 = [
    ([(0x38, 0x38)], 0x3F800000),
    ([(0x00, 0xB8)], 0x80000000),
    ([(0x7E, 0x7E)], 0x48440000),
    ([(0x7F, 0x38)], CANON_NAN),
    ([(0x38, 0x38), (0x38, 0xB8)], 0x00000000),
    ([(0x01, 0x01)], 0x36800000),
]


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_hand", "fp8_mut"))
async def test_fp8_hand(dut):
    await start_clock(dut)
    for pairs, want in HAND_FP8:
        got = await mac_fp8(dut, pairs)
        if got != want:
            raise AssertionError(
                "hand %s got %08x want %08x" % (pairs, got, want)
            )


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_exh"))
async def test_fp8_exhaustive(dut):
    await start_clock(dut)
    for a in range(256):
        for b in range(256):
            got = await mac_fp8(dut, [(a, b)])
            want = want_fp8([(a, b)])
            if got != want:
                raise AssertionError(
                    "exh a=%02x b=%02x got %08x want %08x" % (a, b, got, want)
                )


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_random"))
async def test_fp8_random(dut):
    await start_clock(dut)
    rng = random.Random(SEED)
    for n in range(200):
        length = rng.randint(1, 16)
        pairs = [(rng.randrange(256), rng.randrange(256)) for _ in range(length)]
        got = await mac_fp8(dut, pairs)
        want = want_fp8(pairs)
        if got != want:
            raise AssertionError("random %d got %08x want %08x" % (n, got, want))


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_nan", "fp8_mut"))
async def test_fp8_nan_sticky(dut):
    await start_clock(dut)
    got = await mac_fp8(dut, [(0x38, 0x38), (0x7F, 0x01), (0x38, 0x38)])
    if got != CANON_NAN:
        raise AssertionError("nan sticky got %08x" % got)
    got = await mac_fp8(dut, [(0xFF, 0x00)])
    if got != CANON_NAN:
        raise AssertionError("nan ff got %08x" % got)
    got = await mac_fp8(dut, [(0x01, 0x7F)])
    if got != CANON_NAN:
        raise AssertionError("nan b got %08x" % got)


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_tie", "fp8_mut"))
async def test_fp8_tie(dut):
    await start_clock(dut)
    got = await mac_fp8(dut, [(0x38, 0x68), (0x01, 0x01)])
    if got != 0x42800000:
        raise AssertionError("tie rne got %08x want 42800000" % got)


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_wave"))
async def test_fp8_waves(dut):
    await start_clock(dut)
    os.makedirs(REPORTS, exist_ok=True)

    async def dump(name, pairs):
        lines = ["cycle clr en valid a_in b_in acc"]
        dut.clr.value = 1
        dut.en.value = 0
        if hasattr(dut, "valid"):
            dut.valid.value = 1
        drive_ab(dut, 0, 0)
        await tick(dut)
        lines.append(
            "0 %d %d %d %02x %02x %08x"
            % (
                int(dut.clr.value),
                int(dut.en.value),
                int(dut.valid.value) if hasattr(dut, "valid") else 1,
                int(dut.a_in.value) & 0xFF,
                int(dut.b_in.value) & 0xFF,
                u32(dut.acc.value),
            )
        )
        dut.clr.value = 0
        cyc = 1
        for a, b in pairs:
            dut.en.value = 1
            drive_ab(dut, a, b)
            await tick(dut)
            lines.append(
                "%d %d %d %d %02x %02x %08x"
                % (
                    cyc,
                    int(dut.clr.value),
                    int(dut.en.value),
                    int(dut.valid.value) if hasattr(dut, "valid") else 1,
                    a & 0xFF,
                    b & 0xFF,
                    u32(dut.acc.value),
                )
            )
            cyc += 1
        dut.en.value = 0
        await tick(dut)
        lines.append(
            "%d %d %d %d %02x %02x %08x"
            % (
                cyc,
                int(dut.clr.value),
                int(dut.en.value),
                int(dut.valid.value) if hasattr(dut, "valid") else 1,
                int(dut.a_in.value) & 0xFF,
                int(dut.b_in.value) & 0xFF,
                u32(dut.acc.value),
            )
        )
        with open(os.path.join(REPORTS, name), "w") as f:
            f.write("\n".join(lines) + "\n")
        return u32(dut.acc.value)

    got = await dump("cancel.wave.txt", [(0x38, 0x38), (0x38, 0xB8)])
    if got != 0:
        raise AssertionError("cancel wave %08x" % got)
    got = await dump("subnormal.wave.txt", [(0x01, 0x01)])
    if got != 0x36800000:
        raise AssertionError("subnormal wave %08x" % got)


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_wide", "fp8_mut"))
async def test_fp8_k11_max(dut):
    """K=11 of 448×448: fits 43-bit, wraps 40-bit. Predicted 2207744 vs −1986560."""
    await start_clock(dut)
    pairs = [(0x7E, 0x7E)] * 11
    got = await mac_fp8(dut, pairs)
    want = want_fp8(pairs)
    if got != want:
        raise AssertionError("k11 max got %08x want %08x" % (got, want))


@cocotb.test(skip=(not IS_FP8) or SUITE not in ("all", "fp8", "fp8_cov"))
async def test_fp8_coverage(dut):
    await start_clock(dut)
    os.makedirs(REPORTS, exist_ok=True)
    bins = set()
    k1 = [
        ([(0x00, 0x38)], "zero"),
        ([(0x01, 0x01)], "subnormal"),
        ([(0x38, 0x38)], "normal"),
        ([(0x7E, 0x7E)], "max"),
        ([(0x7F, 0x38)], "nan"),
        ([(0x38, 0xB8)], "mixed_signs"),
    ]
    for pairs, _name in k1:
        got = await mac_fp8(dut, pairs)
        want = want_fp8(pairs)
        if got != want:
            raise AssertionError("cov %s got %08x want %08x" % (_name, got, want))
        bins = record_pairs(bins, pairs, got)
    o15 = os.path.join(ROOT, "reports", "O15")
    os.makedirs(o15, exist_ok=True)
    dump_fp8_bins(os.path.join(o15, "bins-k1.txt"), bins, extra="phase=k1")
    cancel = [(0x38, 0x38), (0x38, 0xB8)]
    got = await mac_fp8(dut, cancel)
    if got != 0:
        raise AssertionError("cov cancel %08x" % got)
    bins = record_pairs(bins, cancel, got)
    dump_fp8_bins(os.path.join(o15, "functional-fp8.txt"), bins, extra="phase=full")
    missing = [b for b in FP8_REQUIRED if b not in bins]
    if missing:
        raise AssertionError("missing fp8 bins %s" % missing)
