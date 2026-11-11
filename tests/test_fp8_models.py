"""Python vs C++ E4M3 GEMM, specials, library decode, broken RNE."""
import os
import random
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
from ref_fp8 import CANON_NAN, decode_e4m3, gemm_e4m3, product_e4m3  # noqa: E402

CPP = os.path.join(ROOT, "model", "cpp", "ref_fp8")

# Hand predictions (1·1, +0·−1, 448², NaN·1, 1+(−1)).
HAND = [
    ([[0x38]], [[0x38]], 0x3F800000),
    ([[0x00]], [[0xB8]], 0x80000000),
    ([[0x7E]], [[0x7E]], 0x48440000),
    ([[0x7F]], [[0x38]], 0x7FC00000),
    ([[0x38, 0x38]], [[0x38], [0xB8]], 0x00000000),
]
TIE = ([[0x38, 0x01]], [[0x68], [0x01]], 0x42800000)


def flatten(M):
    return [x for row in M for x in row]


def cpp_batch(cases):
    lines = []
    for A, B, R, C, K in cases:
        lines.append("E4M3 %d %d %d" % (R, C, K))
        lines.append(" ".join(str(int(x) & 0xFF) for x in flatten(A)))
        lines.append(" ".join(str(int(x) & 0xFF) for x in flatten(B)))
    proc = subprocess.run(
        [CPP, "--batch"],
        input="\n".join(lines) + "\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise AssertionError("cpp fp8 batch failed: " + proc.stderr)
    out = []
    bodies = [ln for ln in proc.stdout.splitlines() if ln.startswith("C ")]
    if len(bodies) != len(cases):
        raise AssertionError("cpp rows %d != %d" % (len(bodies), len(cases)))
    for (A, B, R, C, K), line in zip(cases, bodies):
        nums = [int(x, 16) for x in line.split()[1:]]
        if len(nums) != R * C:
            raise AssertionError("shape")
        out.append([nums[i * C : (i + 1) * C] for i in range(R)])
    return out


def test_five_hand_predictions():
    for A, B, want in HAND:
        K = len(A[0])
        py = gemm_e4m3(A, B, 1, 1, K)[0][0]
        assert py == want, hex(py)
    cc = cpp_batch([(A, B, 1, 1, len(A[0])) for A, B, _ in HAND])
    for i, (_, _, want) in enumerate(HAND):
        assert cc[i][0][0] == want


def test_tie_rne_and_broken_tie_up():
    A, B, want = TIE
    py = gemm_e4m3(A, B, 1, 1, 2)[0][0]
    assert py == want
    cc = cpp_batch([(A, B, 1, 1, 2)])[0][0][0]
    assert cc == want
    up = gemm_e4m3(A, B, 1, 1, 2, tie="up")[0][0]
    assert up != want
    assert up == 0x42800001


def test_exhaustive_pairs():
    cases = [([[a]], [[b]], 1, 1, 1) for a in range(256) for b in range(256)]
    py = [gemm_e4m3(A, B, 1, 1, 1) for A, B, _, _, _ in cases]
    cc = cpp_batch(cases)
    assert cc == py
    assert len(py) == 65536


def test_random_100k():
    rng = random.Random(2026)
    cases = []
    py = []
    for _ in range(100000):
        R = rng.randint(1, 2)
        C = rng.randint(1, 2)
        K = rng.randint(1, 16)
        A = [[rng.randrange(256) for _ in range(K)] for _ in range(R)]
        B = [[rng.randrange(256) for _ in range(C)] for _ in range(K)]
        cases.append((A, B, R, C, K))
        py.append(gemm_e4m3(A, B, R, C, K))
    cc = cpp_batch(cases)
    assert cc == py


def test_specials():
    # NaN either side
    assert gemm_e4m3([[0xFF]], [[0x38]], 1, 1, 1)[0][0] == CANON_NAN
    assert gemm_e4m3([[0x08]], [[0x7F]], 1, 1, 1)[0][0] == CANON_NAN
    # all −0 products → −0
    assert gemm_e4m3([[0x80, 0x80]], [[0x38], [0x38]], 1, 1, 2)[0][0] == 0x80000000
    # mixed zeros → +0
    assert gemm_e4m3([[0x00, 0x80]], [[0x38], [0x38]], 1, 1, 2)[0][0] == 0
    # max K=64 of 448*448
    A = [[0x7E] * 64]
    B = [[0x7E] for _ in range(64)]
    got = gemm_e4m3(A, B, 1, 1, 64)[0][0]
    # 64*200704 = 12845056, exact FP32?
    import struct

    want = struct.unpack(">I", struct.pack(">f", 12845056.0))[0]
    assert got == want
    cc = cpp_batch([(A, B, 1, 1, 64)])[0][0][0]
    assert cc == want


def test_decode_vs_cpp():
    proc = subprocess.run([CPP, "--decode"], capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in proc.stdout.splitlines() if ln]
    assert len(lines) == 256
    for c, ln in enumerate(lines):
        kind, val = decode_e4m3(c)
        if kind == "nan":
            assert ln.endswith("nan")
        elif kind == "zero":
            assert ln == "%02x zero%d" % (c, val)
        else:
            mag9 = int(val * 512)
            assert ln == "%02x mag9 %d" % (c, mag9)


def test_decode_library():
    ml_dtypes = pytest.importorskip("ml_dtypes")
    import numpy as np

    dt = ml_dtypes.float8_e4m3fn
    gaps = []
    for c in range(256):
        kind, val = decode_e4m3(c)
        lib = np.array([c], dtype=np.uint8).view(dt)
        f = float(lib[0])
        if kind == "nan":
            if not np.isnan(f):
                gaps.append((c, "spec nan lib %r" % f))
        elif kind == "zero":
            if f != 0.0:
                gaps.append((c, "spec zero lib %r" % f))
            else:
                import math

                lib_neg = math.copysign(1.0, f) < 0
                if bool(val) != lib_neg:
                    gaps.append((c, "zero sign spec %d lib %s" % (val, f)))
        else:
            if np.isnan(f) or abs(f - float(val)) > 1e-12:
                gaps.append((c, "spec %s lib %r" % (val, f)))
    # Record convention; any gap fails the test so it cannot be silent.
    assert gaps == [], gaps


def test_fmt_vector_roundtrip():
    from gen_vectors import MAGIC_V2, load_vector_file

    path = os.path.join(ROOT, "model", "vectors", "e4m3_demo.vec")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    A, B, want = HAND[0]
    bits = gemm_e4m3(A, B, 1, 1, 1)[0][0]
    with open(path, "w") as f:
        f.write(MAGIC_V2 + "\n")
        f.write("TEST one\nFMT E4M3\nR 1 C 1 K 1\n")
        f.write("A 38\nB 38\nC %08x\nEND\n" % bits)
    recs = load_vector_file(path)
    assert recs[0]["fmt"] == "E4M3"
    assert recs[0]["expect"][0][0] == want
