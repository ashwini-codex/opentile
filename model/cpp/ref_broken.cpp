// Deliberately wrong: INT8 operands zero-extended (unsigned) instead of sign-extended.
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

static int32_t wrap32(int64_t x) {
    const uint64_t mod = 1ULL << 32;
    int64_t y = x % (int64_t)mod;
    if (y < 0)
        y += (int64_t)mod;
    if (y >= ((int64_t)1 << 31))
        return (int32_t)(y - (int64_t)mod);
    return (int32_t)y;
}

static void gemm_broken(const uint8_t *A, const uint8_t *B, int32_t *Cout, int R, int C, int K) {
    for (int j = 0; j < C; ++j) {
        for (int i = 0; i < R; ++i) {
            int64_t acc = 0;
            for (int k = 0; k < K; ++k) {
                acc += (int64_t)A[i * K + k] * (int64_t)B[k * C + j];
            }
            Cout[i * C + j] = wrap32(acc);
        }
    }
}

int main() {
    std::string tag;
    while (std::cin >> tag) {
        if (tag != "GEMM")
            return 1;
        int R, C, K;
        std::cin >> R >> C >> K;
        std::vector<uint8_t> A(R * K), B(K * C);
        std::vector<int32_t> Cout(R * C);
        for (int n = 0; n < R * K; ++n) {
            int v;
            std::cin >> v;
            A[n] = (uint8_t)(v & 0xFF);
        }
        for (int n = 0; n < K * C; ++n) {
            int v;
            std::cin >> v;
            B[n] = (uint8_t)(v & 0xFF);
        }
        gemm_broken(A.data(), B.data(), Cout.data(), R, C, K);
        std::cout << "C";
        for (int n = 0; n < R * C; ++n)
            std::cout << " " << Cout[n];
        std::cout << "\n";
    }
    return 0;
}
