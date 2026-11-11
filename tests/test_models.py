"""Python vs C++ INT8 GEMM agreement, vector format, golden, wrap, order."""
import os
import random
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "model", "python"))
from gen_vectors import directed, load_vector_file, write_file  # noqa: E402
from ref import gemm_int8, wrap32  # noqa: E402

CPP = os.path.join(ROOT, "model", "cpp", "ref")
CPP_BROKEN = os.path.join(ROOT, "model", "cpp", "ref_broken")
VEC = os.path.join(ROOT, "model", "vectors", "directed.vec")


def flatten(M):
    return [x for row in M for x in row]


def cpp_batch(cases):
    """cases: list of (A, B, R, C, K) -> list of C matrices from the C++ model."""
    lines = []
    for A, B, R, C, K in cases:
        lines.append("GEMM %d %d %d" % (R, C, K))
        lines.append(" ".join(str(x) for x in flatten(A)))
        lines.append(" ".join(str(x) for x in flatten(B)))
    proc = subprocess.run(
        [CPP, "--batch"],
        input="\n".join(lines) + "\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise AssertionError("cpp batch failed: " + proc.stderr)
    out = []
    bodies = [ln for ln in proc.stdout.splitlines() if ln.startswith("C ")]
    if len(bodies) != len(cases):
        raise AssertionError("cpp rows %d != %d" % (len(bodies), len(cases)))
    for (A, B, R, C, K), line in zip(cases, bodies):
        nums = [int(x) for x in line.split()[1:]]
        if len(nums) != R * C:
            raise AssertionError("shape")
        out.append([nums[i * C : (i + 1) * C] for i in range(R)])
    return out


def test_python_hand_predictions():
    assert gemm_int8([[-128] * 64], [[-128] for _ in range(64)], 1, 1, 64) == [[1048576]]
    assert gemm_int8([[1, 2, 3], [4, 5, 6]], [[1, 0], [0, 1], [1, 1]], 2, 2, 3) == [
        [4, 5],
        [10, 11],
    ]
    assert gemm_int8([[-1]], [[1]], 1, 1, 1) == [[-1]]
    assert gemm_int8([[0, 0], [0, 0]], [[0, 0], [0, 0]], 2, 2, 2) == [[0, 0], [0, 0]]
    assert gemm_int8([[127]], [[127]], 1, 1, 1) == [[16129]]
    A = [[-128] * 131072]
    B = [[-128] for _ in range(131072)]
    assert gemm_int8(A, B, 1, 1, 131072) == [[-2147483648]]


def test_cpp_matches_python_hand():
    cases = [
        ([[-128] * 64], [[-128] for _ in range(64)], 1, 1, 64),
        ([[1, 2, 3], [4, 5, 6]], [[1, 0], [0, 1], [1, 1]], 2, 2, 3),
        ([[-1]], [[1]], 1, 1, 1),
        ([[0, 0], [0, 0]], [[0, 0], [0, 0]], 2, 2, 2),
        ([[127]], [[127]], 1, 1, 1),
    ]
    py = [gemm_int8(A, B, R, C, K) for A, B, R, C, K in cases]
    cc = cpp_batch(cases)
    assert py == cc


def test_golden_both_models():
    A = [[1, 2, 3], [4, 5, 6]]
    B = [[1, 0], [0, 1], [1, 1]]
    assert gemm_int8(A, B, 2, 2, 3) == [[4, 5], [10, 11]]
    assert cpp_batch([(A, B, 2, 2, 3)])[0] == [[4, 5], [10, 11]]


def test_directed_vectors_match_models():
    write_file(VEC, directed())
    recs = load_vector_file(VEC)
    names = {r["name"] for r in recs}
    for need in (
        "all_zeros",
        "all_m128_k64",
        "all_127",
        "alt_signs",
        "identity_like",
        "single_nonzero",
        "k1",
        "k_kmax",
        "nonsquare",
        "r1",
        "c1",
        "rand_1",
        "rand_99",
        "golden_2x2_k3",
    ):
        assert need in names
    proc = subprocess.run([CPP, "--compare", VEC], capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    for r in recs:
        got = gemm_int8(r["A"], r["B"], r["R"], r["C"], r["K"])
        assert got == r["expect"], r["name"]
    m128 = [r for r in recs if r["name"] == "all_m128_k64"][0]
    assert m128["expect"][0][0] == 64 * 16384


def test_malformed_vector_rejected():
    bad = os.path.join(ROOT, "model", "vectors", "bad.vec")
    os.makedirs(os.path.dirname(bad), exist_ok=True)
    with open(bad, "w") as f:
        f.write("TEST nope\nEND\n")
    with pytest.raises(ValueError):
        load_vector_file(bad)


def test_exhaustive_int8_pairs():
    cases = []
    py = []
    for a in range(-128, 128):
        for b in range(-128, 128):
            cases.append(([[a]], [[b]], 1, 1, 1))
            py.append([[wrap32(a * b)]])
    cc = cpp_batch(cases)
    assert cc == py
    assert len(py) == 65536


def test_random_100k():
    rng = random.Random(2026)
    cases = []
    py = []
    for _ in range(100000):
        R = rng.randint(1, 3)
        C = rng.randint(1, 3)
        K = rng.randint(1, 64)
        A = [[rng.randint(-128, 127) for _ in range(K)] for _ in range(R)]
        B = [[rng.randint(-128, 127) for _ in range(C)] for _ in range(K)]
        cases.append((A, B, R, C, K))
        py.append(gemm_int8(A, B, R, C, K))
    cc = cpp_batch(cases)
    assert cc == py


def test_high_k_and_wrap():
    rng = random.Random(7)
    cases = []
    py = []
    for n in range(996):
        K = rng.randint(65, 256)
        av = rng.choice([-128, -127, 127])
        bv = rng.choice([-128, -127, 127])
        A = [[av] * K]
        B = [[bv] for _ in range(K)]
        cases.append((A, B, 1, 1, K))
        py.append(gemm_int8(A, B, 1, 1, K))
    for av, bv in [(-128, -128), (127, 127), (-128, 127)]:
        K = 131071
        A = [[av] * K]
        B = [[bv] for _ in range(K)]
        cases.append((A, B, 1, 1, K))
        py.append(gemm_int8(A, B, 1, 1, K))
    # Real INT32 overflow: K=131072, all -128 → 2^31 → wrap to -2^31.
    A = [[-128] * 131072]
    B = [[-128] for _ in range(131072)]
    cases.append((A, B, 1, 1, 131072))
    py.append([[-2147483648]])
    assert gemm_int8(A, B, 1, 1, 131072) == [[-2147483648]]
    cc = cpp_batch(cases)
    assert cc == py
    assert cc[-1] == [[-2147483648]]
    assert len(cases) == 1000


def test_summation_order_1000():
    rng = random.Random(11)
    for n in range(1000):
        R, C, K = 2, 2, rng.randint(2, 16)
        A = [[rng.randint(-128, 127) for _ in range(K)] for _ in range(R)]
        B = [[rng.randint(-128, 127) for _ in range(C)] for _ in range(K)]
        order = list(range(K))
        rng.shuffle(order)
        As = [[A[i][k] for k in order] for i in range(R)]
        Bs = [B[k] for k in order]
        assert gemm_int8(A, B, R, C, K) == gemm_int8(As, Bs, R, C, K)


def test_broken_cpp_missing_sign_extend():
    subprocess.check_call(["make", "-C", os.path.join(ROOT, "model", "cpp"), "broken"])
    proc = subprocess.run(
        [CPP_BROKEN],
        input="GEMM 1 1 1\n-1\n1\n",
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    got = int(proc.stdout.split()[1])
    exp = gemm_int8([[-1]], [[1]], 1, 1, 1)[0][0]
    assert exp == -1
    assert got != exp
    assert got == 255
