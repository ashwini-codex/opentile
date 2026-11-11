"""Cycle-accurate output-stationary array model (skew inside, PE pass-through)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ref import wrap32


class ArrayModel:
    def __init__(self, R, C, skew=True):
        if R < 1 or C < 1:
            raise ValueError("R, C >= 1")
        self.R = R
        self.C = C
        self.skew = skew
        self.clear()

    def clear(self):
        R, C = self.R, self.C
        self.acc = [[0] * C for _ in range(R)]
        self.a_hold = [[0] * C for _ in range(R)]
        self.b_hold = [[0] * C for _ in range(R)]
        # row i delay line of length i; col j delay line of length j
        self.row_dly = [[0] * i for i in range(R)]
        self.col_dly = [[0] * j for j in range(C)]

    def acc_flat(self):
        return [self.acc[i][j] for i in range(self.R) for j in range(self.C)]

    def step(self, a_vec, b_vec, en=True, clr=False):
        """One rising edge. a_vec length R, b_vec length C. Returns acc snapshot after the edge."""
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
            for i in range(1, R):
                self.row_dly[i] = [a_vec[i]] + self.row_dly[i][:-1]
            for j in range(1, C):
                self.col_dly[j] = [b_vec[j]] + self.col_dly[j][:-1]
        else:
            west = list(a_vec)
            north = list(b_vec)
        a_in = [[west[i] if j == 0 else self.a_hold[i][j - 1] for j in range(C)] for i in range(R)]
        b_in = [[north[j] if i == 0 else self.b_hold[i - 1][j] for j in range(C)] for i in range(R)]
        self.acc = [
            [wrap32(self.acc[i][j] + a_in[i][j] * b_in[i][j]) for j in range(C)]
            for i in range(R)
        ]
        self.a_hold = a_in
        self.b_hold = b_in
        return self.acc_flat()

    def run(self, A, B, K, stall_pattern=None):
        """Feed unskewed columns/rows for k=0..K-1 then zeros for R+C-2 cycles.

        stall_pattern: optional list of bools. False consumes the next feed with en=1.
        True holds the last feeds and steps with en=0 (does not consume the schedule).
        Returns (final_acc_matrix, traces) where traces is a list of dicts
        {t, acc, stalled} for every issued step (t is the feed index, or -1 if stalled).
        """
        R, C = self.R, self.C
        self.clear()
        schedule = []
        for k in range(K):
            schedule.append(([A[i][k] for i in range(R)], [B[k][j] for j in range(C)]))
        z_a, z_b = [0] * R, [0] * C
        for _ in range(R + C - 2):
            schedule.append((z_a, z_b))
        if stall_pattern is None:
            stall_pattern = [False] * len(schedule)
        traces = []
        idx = 0
        held_a, held_b = z_a, z_b
        feed_t = 0
        for stall in stall_pattern:
            if stall:
                snap = self.step(held_a, held_b, en=False)
                traces.append(dict(t=-1, acc=snap, stalled=True))
            else:
                a_vec, b_vec = schedule[idx]
                idx += 1
                held_a, held_b = a_vec, b_vec
                snap = self.step(a_vec, b_vec, en=True)
                traces.append(dict(t=feed_t, acc=snap, stalled=False))
                feed_t += 1
        if idx != len(schedule):
            raise ValueError("stall_pattern consumed %d of %d feeds" % (idx, len(schedule)))
        final = [self.acc[i][:] for i in range(R)]
        return final, traces


def write_trace(path, R, C, K, traces):
    """Write the architecture trace format. `traces` is a list of acc flats, one per array cycle t=0.."""
    lines = ["# opentile-trace R=%d C=%d K=%d" % (R, C, K)]
    for t, acc in enumerate(traces):
        lines.append(str(t) + " " + " ".join(str(int(v)) for v in acc))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_trace(path):
    rows = []
    header = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                if header is None:
                    header = s
                continue
            parts = s.split()
            t = int(parts[0])
            acc = [int(x) for x in parts[1:]]
            rows.append((t, acc))
    return header, rows
