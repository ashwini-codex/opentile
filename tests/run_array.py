#!/usr/bin/env python3
"""Good array must pass; broken-skew must fail trace compare."""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARRAY = os.path.join(ROOT, "tests", "array")
REPORTS = os.path.join(ROOT, "reports", "O7")
os.makedirs(REPORTS, exist_ok=True)


def tests_ok(xml_path):
    if not os.path.isfile(xml_path):
        return False
    txt = open(xml_path, encoding="utf-8").read()
    if "<failure" in txt or "<error" in txt:
        return False
    return "<testcase" in txt


def run(label, env, log_name, expect_pass):
    e = os.environ.copy()
    e.update(env)
    e.setdefault("SIM", "verilator")
    xmlp = os.path.join(REPORTS, log_name.replace(".log", ".xml"))
    e["COCOTB_RESULTS_FILE"] = xmlp
    logp = os.path.join(REPORTS, log_name)
    print("RUN", label, "expect", "PASS" if expect_pass else "FAIL")
    with open(logp, "w") as log:
        log.write("label=%s expect_pass=%s\n" % (label, expect_pass))
        log.flush()
        p = subprocess.run(
            ["make", "-C", ARRAY], env=e, cwd=ARRAY, stdout=log, stderr=subprocess.STDOUT
        )
    ok = (p.returncode == 0) and tests_ok(xmlp)
    print("  ->", "PASS" if ok else "FAIL", "make_rc", p.returncode, "log", logp)
    with open(os.path.join(REPORTS, "array-test.log"), "a") as f:
        f.write("RUN %s expect %s -> %s\n" % (label, "PASS" if expect_pass else "FAIL", "PASS" if ok else "FAIL"))
    if expect_pass and not ok:
        print("ERROR: %s should have passed" % label)
        return 1
    if (not expect_pass) and ok:
        print("ERROR: %s should have failed" % label)
        return 1
    return 0


def good(R, C, suite, seed, sim_build, log, extra=None):
    env = dict(
        DUT=os.path.join(ROOT, "rtl", "array.sv"),
        PARAM_R=str(R),
        PARAM_C=str(C),
        SUITE=suite,
        SEED=str(seed),
        K_MAX="64",
        SIM_BUILD=sim_build,
        WAVES="0",
    )
    if extra:
        env.update(extra)
    return run("good %dx%d %s" % (R, C, suite), env, log, True)


def main():
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            [
                "bash",
                "-lc",
                "date -u; verilator --version; python3 -c 'import cocotb; print(\"cocotb\", cocotb.__version__)'",
            ],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    with open(os.path.join(REPORTS, "array-test.log"), "w") as f:
        f.write(open(ver).read() + "\n")
    rc = 0
    # CI sizes: 4x4 and two others (2x3, 1x4)
    rc |= good(4, 4, "traces", 8, "sim_build/a4x4", "good-4x4-traces.log")
    rc |= good(4, 4, "random", 7, "sim_build/a4x4", "good-4x4-random.log")
    rc |= good(4, 4, "stall", 9, "sim_build/a4x4", "good-4x4-stall.log")
    rc |= good(4, 4, "wavefront", 1, "sim_build/a4x4", "good-4x4-wavefront.log")
    rc |= good(2, 3, "shapes", 2, "sim_build/a2x3", "good-2x3-shapes.log")
    rc |= good(1, 4, "shapes", 3, "sim_build/a1x4", "good-1x4-shapes.log")
    rc |= good(4, 2, "shapes", 4, "sim_build/a4x2", "good-4x2-shapes.log")
    rc |= good(3, 1, "shapes", 5, "sim_build/a3x1", "good-3x1-shapes.log")
    rc |= good(2, 2, "golden", 1, "sim_build/a2x2", "good-2x2-golden.log")
    for R, C, seed in ((1, 1, 11), (8, 1, 12), (1, 8, 13), (8, 8, 14), (2, 2, 15), (4, 4, 16)):
        rc |= good(R, C, "formula", seed, "sim_build/a%dx%d" % (R, C), "good-%dx%d-formula.log" % (R, C))
    xtraces = []
    for seed in (1, 2, 3):
        log = "good-2x2-xinit-%d.log" % seed
        rc |= good(
            2,
            2,
            "golden",
            1,
            "sim_build/a2x2_x%d" % seed,
            log,
            extra={"XSEED": str(seed * 17 + 3)},
        )
        src = os.path.join(REPORTS, "golden-2x2-k3.dut.trace")
        dst = os.path.join(REPORTS, "xinit-%d.dut.trace" % seed)
        if os.path.isfile(src):
            shutil.copy(src, dst)
            xtraces.append(open(dst).read())
    if len(set(xtraces)) != 1:
        print("ERROR: x-initial traces differ across seeds")
        rc |= 1
    rc |= run(
        "broken row-1 skew 2x2",
        dict(
            DUT=os.path.join(ROOT, "rtl", "variants", "array_nonskew_row.sv"),
            PARAM_R="2",
            PARAM_C="2",
            SUITE="catch",
            SEED="1",
            SIM_BUILD="sim_build/a2x2_nonskew",
            WAVES="0",
            TRACE_GOT=os.path.join(REPORTS, "nonskew.dut.trace"),
            TRACE_WANT=os.path.join(REPORTS, "nonskew.model.trace"),
        ),
        "nonskew-caught.log",
        True,  # the cocotb test PASSES because it asserts the comparator fails
    )
    with open(os.path.join(REPORTS, "array-test.log"), "a") as f:
        f.write("exit_rc=%d\n" % rc)
        f.write("ARRAY-TEST OK\n" if rc == 0 else "ARRAY-TEST FAIL\n")
    if rc == 0:
        print("ARRAY-TEST OK")
    return rc


if __name__ == "__main__":
    sys.exit(main())
