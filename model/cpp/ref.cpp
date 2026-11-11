// C++ INT8 GEMM reference. Independent of the Python model:
// column-major loop nest (j, i, k), int64 accumulation, then explicit wrap
// via unsigned 32-bit reduction (no signed overflow).
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
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

// A, B, Cout stored row-major. Loops walk columns of C first.
static void gemm(const int8_t *A, const int8_t *B, int32_t *Cout, int R, int C, int K) {
    for (int j = 0; j < C; ++j) {
        for (int i = 0; i < R; ++i) {
            int64_t acc = 0;
            for (int k = 0; k < K; ++k) {
                int64_t a = (int64_t)A[i * K + k];
                int64_t b = (int64_t)B[k * C + j];
                acc += a * b;
            }
            Cout[i * C + j] = wrap32(acc);
        }
    }
}

static int8_t parse_i8(const std::string &t) {
    if (t.size() != 2)
        throw std::runtime_error("bad i8 hex");
    unsigned v = (unsigned)std::stoul(t, nullptr, 16);
    return (int8_t)(uint8_t)v;
}

static int32_t parse_i32(const std::string &t) {
    if (t.size() != 8)
        throw std::runtime_error("bad i32 hex");
    unsigned long v = std::stoul(t, nullptr, 16);
    return wrap32((int64_t)(uint32_t)v);
}

static std::string hex8(int8_t x) {
    char buf[8];
    std::snprintf(buf, sizeof(buf), "%02x", (unsigned)(uint8_t)x);
    return buf;
}

static std::string hex32(int32_t x) {
    char buf[16];
    std::snprintf(buf, sizeof(buf), "%08x", (unsigned)(uint32_t)x);
    return buf;
}

static std::string strip_comment(const std::string &line) {
    auto p = line.find('#');
    std::string s = (p == std::string::npos) ? line : line.substr(0, p);
    while (!s.empty() && std::isspace((unsigned char)s.front()))
        s.erase(s.begin());
    while (!s.empty() && std::isspace((unsigned char)s.back()))
        s.pop_back();
    return s;
}

static int run_vecfile(const std::string &path, bool compare) {
    std::ifstream in(path);
    if (!in)
        throw std::runtime_error("cannot open " + path);
    std::string line;
    bool magic = false;
    while (std::getline(in, line)) {
        if (!magic) {
            if (strip_comment(line).size() == 0 && line.find_first_not_of(" \t\r") == std::string::npos)
                continue;
            if (line.size() >= 21) {
                // compare exact magic on the raw first non-blank
            }
            std::string raw = line;
            while (!raw.empty() && (raw.back() == '\r' || raw.back() == '\n'))
                raw.pop_back();
            if (raw != "# opentile-vectors v1" && raw != "# opentile-vectors v2")
                throw std::runtime_error("missing magic");
            magic = true;
            continue;
        }
        std::string s = strip_comment(line);
        if (s.empty())
            continue;
        std::istringstream is(s);
        std::string kw;
        is >> kw;
        if (kw != "TEST")
            throw std::runtime_error("expected TEST");
        std::string name;
        is >> name;
        std::string rc;
        do {
            if (!std::getline(in, line))
                throw std::runtime_error("truncated");
            rc = strip_comment(line);
        } while (rc.empty());
        int R = 0, C = 0, K = 0;
        {
            std::istringstream rs(rc);
            std::string t;
            rs >> t;
            if (t != "R")
                throw std::runtime_error("expected R");
            rs >> R >> t;
            if (t != "C")
                throw std::runtime_error("expected C");
            rs >> C >> t;
            if (t != "K")
                throw std::runtime_error("expected K");
            rs >> K;
        }
        auto read_tagged = [&](const char *tag) {
            std::string body;
            do {
                if (!std::getline(in, line))
                    throw std::runtime_error("truncated field");
                body = strip_comment(line);
            } while (body.empty());
            std::istringstream fs(body);
            std::string got;
            fs >> got;
            if (got != tag)
                throw std::runtime_error(std::string("expected ") + tag);
            std::vector<std::string> toks;
            std::string x;
            while (fs >> x)
                toks.push_back(x);
            return toks;
        };
        auto atoks = read_tagged("A");
        auto btoks = read_tagged("B");
        auto ctoks = read_tagged("C");
        std::string end;
        do {
            if (!std::getline(in, line))
                throw std::runtime_error("missing END");
            end = strip_comment(line);
        } while (end.empty());
        if (end != "END")
            throw std::runtime_error("missing END");
        if ((int)atoks.size() != R * K || (int)btoks.size() != K * C || (int)ctoks.size() != R * C)
            throw std::runtime_error("token count in " + name);
        std::vector<int8_t> A(R * K), Bv(K * C);
        std::vector<int32_t> Cexp(R * C), Cgot(R * C);
        for (int n = 0; n < R * K; ++n)
            A[n] = parse_i8(atoks[n]);
        for (int n = 0; n < K * C; ++n)
            Bv[n] = parse_i8(btoks[n]);
        for (int n = 0; n < R * C; ++n)
            Cexp[n] = parse_i32(ctoks[n]);
        gemm(A.data(), Bv.data(), Cgot.data(), R, C, K);
        if (compare) {
            for (int n = 0; n < R * C; ++n) {
                if (Cgot[n] != Cexp[n]) {
                    std::cerr << "MISMATCH " << name << " idx " << n << " got " << Cgot[n]
                              << " exp " << Cexp[n] << "\n";
                    return 1;
                }
            }
        } else {
            std::cout << "TEST " << name << "\n";
            std::cout << "R " << R << " C " << C << " K " << K << "\n";
            std::cout << "A";
            for (int n = 0; n < R * K; ++n)
                std::cout << " " << hex8(A[n]);
            std::cout << "\nB";
            for (int n = 0; n < K * C; ++n)
                std::cout << " " << hex8(Bv[n]);
            std::cout << "\nC";
            for (int n = 0; n < R * C; ++n)
                std::cout << " " << hex32(Cgot[n]);
            std::cout << "\nEND\n";
        }
    }
    if (!magic)
        throw std::runtime_error("missing magic");
    if (compare)
        std::cout << "vecfile compare ok\n";
    return 0;
}

static int run_batch() {
    std::string tag;
    while (std::cin >> tag) {
        if (tag != "GEMM") {
            std::cerr << "expected GEMM\n";
            return 1;
        }
        int R, C, K;
        std::cin >> R >> C >> K;
        std::vector<int8_t> A(R * K), B(K * C);
        std::vector<int32_t> Cout(R * C);
        for (int n = 0; n < R * K; ++n) {
            int v;
            std::cin >> v;
            A[n] = (int8_t)v;
        }
        for (int n = 0; n < K * C; ++n) {
            int v;
            std::cin >> v;
            B[n] = (int8_t)v;
        }
        gemm(A.data(), B.data(), Cout.data(), R, C, K);
        std::cout << "C";
        for (int n = 0; n < R * C; ++n)
            std::cout << " " << Cout[n];
        std::cout << "\n";
    }
    return 0;
}

int main(int argc, char **argv) {
    try {
        if (argc >= 2 && std::string(argv[1]) == "--batch")
            return run_batch();
        bool compare = false;
        std::string path;
        for (int i = 1; i < argc; ++i) {
            std::string a = argv[i];
            if (a == "--compare")
                compare = true;
            else
                path = a;
        }
        if (path.empty()) {
            std::cerr << "usage: ref [--compare] file.vec | ref --batch\n";
            return 2;
        }
        return run_vecfile(path, compare);
    } catch (const std::exception &e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
}
