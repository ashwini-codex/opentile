"""Cycle-accurate E4M3 array model: same skew as INT8, MAC only on valid."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ref_fp8 import CANON_NAN, _rne_bits, product_e4m3


class ArrayModelE4M3:
    def __init__(self, R, C, skew=True):
        if R < 1 or C < 1:
            raise ValueError("R, C >= 1")
        self.R = R
        self.C = C
        self.skew = skew
        self.clear()

    def clear(self):
        R, C = self.R, self.C
        self.acc_fx = [[0] * C for _ in range(R)]
        self.poison = [[False] * C for _ in range(R)]
        self.all_neg0 = [[False] * C for _ in range(R)]
        self.seen = [[False] * C for _ in range(R)]
        self.a_hold = [[0] * C for _ in range(R)]
        self.b_hold = [[0] * C for _ in range(R)]
        self.v_hold = [[False] * C for _ in range(R)]
        self.row_dly = [[0] * i for i in range(R)]
        self.col_dly = [[0] * j for j in range(C)]
        self.vrow_dly = [[False] * i for i in range(R)]

    def _fp32(self, i, j):
        if self.poison[i][j]:
            return CANON_NAN
        return _rne_bits(self.acc_fx[i][j], self.all_neg0[i][j])

    def acc_flat(self):
        return [self._fp32(i, j) for i in range(self.R) for j in range(self.C)]

    def _mac(self, i, j, a, b):
        p = product_e4m3(a & 0xFF, b & 0xFF)
        if p[0] == "nan":
            self.poison[i][j] = True
            self.seen[i][j] = True
            return
        if p[0] == "zero":
            sign = p[1]
            if not self.seen[i][j]:
                self.all_neg0[i][j] = bool(sign)
            else:
                self.all_neg0[i][j] = self.all_neg0[i][j] and bool(sign)
            self.seen[i][j] = True
            return
        self.seen[i][j] = True
        self.all_neg0[i][j] = False
        ulp = int(p[1] * (1 << 18))
        self.acc_fx[i][j] += ulp

    def step(self, a_vec, b_vec, en=True, clr=False, valid=True):
        if clr:
            self.clear()
            return self.acc_flat()
        if not en:
            return self.acc_flat()
        R, C = self.R, self.C
        a_vec = list(a_vec)
        b_vec = list(b_vec)
        if self.skew:
            west = [a_vec[0]] + [self.row_dly[i][-1] for i in range(1, R)]
            north = [b_vec[0]] + [self.col_dly[j][-1] for j in range(1, C)]
            vwest = [bool(valid)] + [self.vrow_dly[i][-1] for i in range(1, R)]
            for i in range(1, R):
                self.row_dly[i] = [a_vec[i]] + self.row_dly[i][:-1]
                self.vrow_dly[i] = [bool(valid)] + self.vrow_dly[i][:-1]
            for j in range(1, C):
                self.col_dly[j] = [b_vec[j]] + self.col_dly[j][:-1]
        else:
            west = list(a_vec)
            north = list(b_vec)
            vwest = [bool(valid)] * R
        a_in = [[west[i] if j == 0 else self.a_hold[i][j - 1] for j in range(C)] for i in range(R)]
        b_in = [[north[j] if i == 0 else self.b_hold[i - 1][j] for j in range(C)] for i in range(R)]
        v_in = [[vwest[i] if j == 0 else self.v_hold[i][j - 1] for j in range(C)] for i in range(R)]
        for i in range(R):
            for j in range(C):
                if v_in[i][j]:
                    self._mac(i, j, a_in[i][j], b_in[i][j])
        self.a_hold = a_in
        self.b_hold = b_in
        self.v_hold = v_in
        return self.acc_flat()

    def run(self, A, B, K, stall_pattern=None):
        R, C = self.R, self.C
        self.clear()
        schedule = []
        for k in range(K):
            schedule.append(([A[i][k] for i in range(R)], [B[k][j] for j in range(C)], True))
        z_a, z_b = [0] * R, [0] * C
        for _ in range(R + C - 2):
            schedule.append((z_a, z_b, False))
        if stall_pattern is None:
            stall_pattern = [False] * len(schedule)
        traces = []
        idx = 0
        held_a, held_b, held_v = z_a, z_b, False
        feed_t = 0
        for stall in stall_pattern:
            if stall:
                snap = self.step(held_a, held_b, en=False, valid=held_v)
                traces.append(dict(t=-1, acc=snap, stalled=True))
            else:
                a_vec, b_vec, v = schedule[idx]
                idx += 1
                held_a, held_b, held_v = a_vec, b_vec, v
                snap = self.step(a_vec, b_vec, en=True, valid=v)
                traces.append(dict(t=feed_t, acc=snap, stalled=False))
                feed_t += 1
        if idx != len(schedule):
            raise ValueError("stall_pattern consumed %d of %d feeds" % (idx, len(schedule)))
        final = [[self._fp32(i, j) for j in range(C)] for i in range(R)]
        return final, traces
