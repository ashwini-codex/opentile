// C++ E4M3 GEMM. Independent of the Python Fraction model:
// decode via significand<<exp (Q9 magnitude), product as int64 ulps of 2^-18,
// clz-based RNE pack into IEEE bits.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

static const uint32_t CANON_NAN = 0x7FC00000u;

struct Dec {
    bool nan;
    int sign;   // 0 or 1
    int mag9;   // |value| / 2^{-9}
};

static Dec dec_e4m3(unsigned c) {
    c &= 0xFFu;
    int s = (int)((c >> 7) & 1);
    int e = (int)((c >> 3) & 15);
    int m = (int)(c & 7);
    Dec d;
    d.nan = false;
    d.sign = s;
    d.mag9 = 0;
    if (e == 15 && m == 7) {
        d.nan = true;
        return d;
    }
    if (e == 0)
        d.mag9 = m;
    else
        d.mag9 = (8 + m) << (e - 1);
    return d;
}

static uint32_t rne_bits(int64_t n, int all_neg0) {
    if (n == 0)
        return all_neg0 ? 0x80000000u : 0u;
    uint32_t sign = n < 0 ? 1u : 0u;
    uint64_t m = (uint64_t)(n < 0 ? -n : n);
    int e2 = 63 - __builtin_clzll(m);
    int bexp = (e2 - 18) + 127;
    if (e2 <= 23) {
        uint32_t sig24 = (uint32_t)(m << (23 - e2));
        return (sign << 31) | ((uint32_t)bexp << 23) | (sig24 & 0x7FFFFFu);
    }
    int shift = e2 - 23;
    uint64_t sig24 = m >> shift;
    uint64_t rest = m & ((1ULL << shift) - 1ULL);
    int round_bit = (int)((rest >> (shift - 1)) & 1ULL);
    int sticky = (rest & ((1ULL << (shift - 1)) - 1ULL)) != 0;
    if (round_bit && (sticky || (sig24 & 1ULL))) {
        sig24 += 1;
        if (sig24 == (1ULL << 24)) {
            sig24 = 1ULL << 23;
            bexp += 1;
        }
    }
    return (sign << 31) | ((uint32_t)bexp << 23) | ((uint32_t)sig24 & 0x7FFFFFu);
}

static uint32_t mac_dot(const uint8_t *A, const uint8_t *B, int Ccols, int K, int i, int j) {
    int64_t acc = 0;
    int nprod = 0, nneg0 = 0;
    for (int k = 0; k < K; ++k) {
        Dec a = dec_e4m3(A[i * K + k]);
        Dec b = dec_e4m3(B[k * Ccols + j]);
        nprod++;
        if (a.nan || b.nan)
            return CANON_NAN;
        int64_t mag = (int64_t)a.mag9 * (int64_t)b.mag9;
        int sg = a.sign ^ b.sign;
        if (mag == 0) {
            if (sg)
                nneg0++;
        } else if (sg)
            acc -= mag;
        else
            acc += mag;
    }
    int all_neg0 = (acc == 0 && nneg0 == nprod);
    return rne_bits(acc, all_neg0);
}

static void gemm_e4m3(const uint8_t *A, const uint8_t *B, uint32_t *Cout, int R, int C, int K) {
    for (int j = 0; j < C; ++j)
        for (int i = 0; i < R; ++i)
            Cout[i * C + j] = mac_dot(A, B, C, K, i, j);
}

static int run_batch() {
    std::string tag;
    while (std::cin >> tag) {
        if (tag != "E4M3") {
            std::cerr << "expected E4M3\n";
            return 1;
        }
        int R, C, K;
        std::cin >> R >> C >> K;
        std::vector<uint8_t> A((size_t)R * K), B((size_t)K * C);
        std::vector<uint32_t> Cout((size_t)R * C);
        for (int n = 0; n < R * K; ++n) {
            int v;
            std::cin >> v;
            A[(size_t)n] = (uint8_t)v;
        }
        for (int n = 0; n < K * C; ++n) {
            int v;
            std::cin >> v;
            B[(size_t)n] = (uint8_t)v;
        }
        gemm_e4m3(A.data(), B.data(), Cout.data(), R, C, K);
        std::cout << "C";
        for (int n = 0; n < R * C; ++n)
            std::printf(" %08x", Cout[(size_t)n]);
        std::cout << "\n";
    }
    return 0;
}

static int run_decode() {
    for (int c = 0; c < 256; ++c) {
        Dec d = dec_e4m3((unsigned)c);
        if (d.nan)
            std::printf("%02x nan\n", c);
        else if (d.mag9 == 0)
            std::printf("%02x zero%d\n", c, d.sign);
        else {
            // print signed mag9 for compare
            int s = d.sign ? -d.mag9 : d.mag9;
            std::printf("%02x mag9 %d\n", c, s);
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc >= 2 && std::string(argv[1]) == "--batch")
        return run_batch();
    if (argc >= 2 && std::string(argv[1]) == "--decode")
        return run_decode();
    std::cerr << "usage: ref_fp8 --batch | ref_fp8 --decode\n";
    return 2;
}
