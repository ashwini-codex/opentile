#!/usr/bin/env python3
"""Directed + seeded-random vector file generator (opentile-vectors v1)."""
import argparse
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ref import gemm_int8, wrap32  # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
K_MAX = 64
MAGIC = "# opentile-vectors v1"
MAGIC_V2 = "# opentile-vectors v2"


def i8_hex(x):
    return "{:02x}".format(x & 0xFF)


def i32_hex(x):
    return "{:08x}".format(wrap32(x) & 0xFFFFFFFF)


def encode_A(A, K):
    return " ".join(i8_hex(A[i][k]) for i in range(len(A)) for k in range(K))


def encode_B(B, C):
    return " ".join(i8_hex(B[k][j]) for k in range(len(B)) for j in range(C))


def encode_C(Cmat, C):
    return " ".join(i32_hex(Cmat[i][j]) for i in range(len(Cmat)) for j in range(C))


def parse_i8(tok):
    if not re.fullmatch(r"[0-9A-Fa-f]{2}", tok):
        raise ValueError("bad A/B token %r" % tok)
    v = int(tok, 16)
    return v - 256 if v >= 128 else v


def parse_i32(tok):
    if not re.fullmatch(r"[0-9A-Fa-f]{8}", tok):
        raise ValueError("bad C token %r" % tok)
    v = int(tok, 16)
    return v - (1 << 32) if v >= (1 << 31) else v


def parse_u8(tok):
    if not re.fullmatch(r"[0-9A-Fa-f]{2}", tok):
        raise ValueError("bad A/B token %r" % tok)
    return int(tok, 16)


def parse_u32(tok):
    if not re.fullmatch(r"[0-9A-Fa-f]{8}", tok):
        raise ValueError("bad C token %r" % tok)
    return int(tok, 16)


def _strip_comment(line):
    if "#" in line:
        return line[: line.index("#")].strip()
    return line.strip()


def load_vector_file(path):
    """Load records; raise ValueError on any malformation."""
    with open(path, encoding="utf-8") as f:
        raw = f.read().splitlines()
    lines = []
    magic_ok = False
    for i, line in enumerate(raw):
        if i == 0 or (not magic_ok and line.strip() != ""):
            st = line.strip()
            if st not in (MAGIC, MAGIC_V2):
                raise ValueError("missing magic %r" % MAGIC)
            magic_ok = True
            continue
        s = _strip_comment(line)
        if s:
            lines.append(s)
    if not magic_ok:
        raise ValueError("missing magic")
    recs = []
    names = set()
    i = 0
    while i < len(lines):
        parts = lines[i].split()
        if parts[0] != "TEST" or len(parts) != 2 or not NAME_RE.match(parts[1]):
            raise ValueError("bad TEST line %r" % lines[i])
        name = parts[1]
        if name in names:
            raise ValueError("duplicate name %s" % name)
        names.add(name)
        i += 1
        if i >= len(lines):
            raise ValueError("truncated record %s" % name)
        fmt = "INT8"
        if lines[i].split()[:1] == ["FMT"]:
            parts_f = lines[i].split()
            if len(parts_f) != 2 or parts_f[1] not in ("INT8", "E4M3"):
                raise ValueError("bad FMT line %r" % lines[i])
            fmt = parts_f[1]
            i += 1
            if i >= len(lines):
                raise ValueError("truncated record %s" % name)
        rc = lines[i].split()
        if rc[:1] != ["R"] or "C" not in rc or "K" not in rc:
            raise ValueError("bad R/C/K line %r" % lines[i])
        try:
            R = int(rc[1])
            C = int(rc[rc.index("C") + 1])
            K = int(rc[rc.index("K") + 1])
        except (ValueError, IndexError) as e:
            raise ValueError("bad R/C/K ints") from e
        if not (1 <= R <= 16 and 1 <= C <= 16 and K >= 1):
            raise ValueError("R/C/K out of range")
        i += 1

        def take(tag, ntok, parse):
            nonlocal i
            if i >= len(lines) or not lines[i].startswith(tag + " "):
                raise ValueError("missing %s in %s" % (tag, name))
            toks = lines[i].split()[1:]
            if len(toks) != ntok:
                raise ValueError("%s count in %s: %d != %d" % (tag, name, len(toks), ntok))
            vals = [parse(t) for t in toks]
            i += 1
            return vals

        if fmt == "E4M3":
            a_flat = take("A", R * K, parse_u8)
            b_flat = take("B", K * C, parse_u8)
            c_flat = take("C", R * C, parse_u32)
        else:
            a_flat = take("A", R * K, parse_i8)
            b_flat = take("B", K * C, parse_i8)
            c_flat = take("C", R * C, parse_i32)
        if i >= len(lines) or lines[i] != "END":
            raise ValueError("missing END in %s" % name)
        i += 1
        A = [a_flat[r * K : (r + 1) * K] for r in range(R)]
        B = [b_flat[k * C : (k + 1) * C] for k in range(K)]
        Cmat = [c_flat[r * C : (r + 1) * C] for r in range(R)]
        recs.append(dict(name=name, fmt=fmt, R=R, C=C, K=K, A=A, B=B, expect=Cmat))
    return recs


def emit_record(name, A, B):
    R, K, C = len(A), len(A[0]), len(B[0])
    Cmat = gemm_int8(A, B, R, C, K)
    return "\n".join(
        [
            "TEST " + name,
            "R %d C %d K %d" % (R, C, K),
            "A " + encode_A(A, K),
            "B " + encode_B(B, C),
            "C " + encode_C(Cmat, C),
            "END",
        ]
    )


def fill(R, C, K, fn):
    A = [[fn("A", i, k) for k in range(K)] for i in range(R)]
    B = [[fn("B", k, j) for j in range(C)] for k in range(K)]
    return A, B


def directed():
    recs = []

    def add(name, A, B):
        recs.append((name, A, B))

    add("all_zeros", *fill(2, 2, 3, lambda *a: 0))
    add("all_m128_k64", *fill(2, 2, 64, lambda *a: -128))
    add("all_127", *fill(2, 2, 4, lambda *a: 127))
    add("alt_signs", *fill(2, 3, 4, lambda w, p, q: 1 if (p + q) % 2 == 0 else -1))
    ident_A = [[1 if i == k else 0 for k in range(3)] for i in range(3)]
    ident_B = [[2, 3, 4], [5, 6, 7], [8, 9, 10]]
    add("identity_like", ident_A, ident_B)
    A = [[0] * 3 for _ in range(2)]
    B = [[0] * 2 for _ in range(3)]
    A[0][1] = -3
    B[1][1] = 7
    add("single_nonzero", A, B)
    add("k1", [[9, ], [ -4, ]], [[2, 8]])
    add("k_kmax", *fill(1, 1, K_MAX, lambda *a: -128))
    add("nonsquare", [[1, 2, 3, 4], [5, 6, 7, 8]], [[1, 0], [0, 1], [1, 1], [0, 1]])
    add("r1", [[1, -2, 3]], [[4], [5], [6]])
    add("c1", [[1], [-2], [3]], [[7, 8]])
    rng = random.Random(1)
    A = [[rng.randint(-128, 127) for _ in range(5)] for _ in range(2)]
    B = [[rng.randint(-128, 127) for _ in range(3)] for _ in range(5)]
    add("rand_1", A, B)
    rng = random.Random(99)
    A = [[rng.randint(-128, 127) for _ in range(2)] for _ in range(4)]
    B = [[rng.randint(-128, 127) for _ in range(1)] for _ in range(2)]
    add("rand_99", A, B)
    add("golden_2x2_k3", [[1, 2, 3], [4, 5, 6]], [[1, 0], [0, 1], [1, 1]])
    add("pred_m1", [[-1]], [[1]])
    add("pred_127", [[127]], [[127]])
    return recs


def write_file(path, recs):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    chunks = [MAGIC]
    for name, A, B in recs:
        if not NAME_RE.match(name):
            raise ValueError(name)
        chunks.append(emit_record(name, A, B))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(chunks) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-o", default="model/vectors/directed.vec")
    args = p.parse_args()
    write_file(args.o, directed())
    print("wrote", args.o, "records", len(directed()))


if __name__ == "__main__":
    main()
