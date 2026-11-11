"""Python INT8 GEMM reference. Row-major i,j,k; wrap the full sum once."""

INT32_MOD = 1 << 32
INT32_HALF = 1 << 31


def wrap32(x):
    """Map an unbounded int to signed INT32: ((x + 2^31) mod 2^32) - 2^31."""
    return ((int(x) + INT32_HALF) % INT32_MOD) - INT32_HALF


def gemm_int8(A, B, R, C, K):
    """C = wrap32(A @ B) with A[R][K], B[K][C] signed INT8 values as Python ints."""
    if R < 1 or C < 1 or K < 1:
        raise ValueError("R, C, K must be >= 1")
    if len(A) != R or any(len(row) != K for row in A):
        raise ValueError("A shape")
    if len(B) != K or any(len(row) != C for row in B):
        raise ValueError("B shape")
    out = []
    for i in range(R):
        row = []
        for j in range(C):
            total = 0
            for k in range(K):
                total += A[i][k] * B[k][j]
            row.append(wrap32(total))
        out.append(row)
    return out
