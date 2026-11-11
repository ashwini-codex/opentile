#!/usr/bin/env python3
"""Good stand-in must pass; each broken stand-in must fail."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
REPORTS = os.path.join(ROOT, "reports", "O5")
os.makedirs(REPORTS, exist_ok=True)

MAKE = ["make", "-C", TESTS]


def tests_ok(xml_path):
    """Verilator+cocotb exits 0 even on test fail; results.xml is the verdict."""
    if not os.path.isfile(xml_path):
        return False
    txt = open(xml_path, encoding="utf-8").read()
    if "<failure" in txt or "<error" in txt:
        return False
    return "<testcase" in txt


def run(label, env, log_name, expect_pass):
    e = os.environ.copy()
    e.update(env)
    e["PYTHONPATH"] = TESTS + os.pathsep + os.path.join(ROOT, "model", "python") + (
        os.pathsep + e["PYTHONPATH"] if e.get("PYTHONPATH") else ""
    )
    e.setdefault("COCOTB_LOG_LEVEL", "INFO")
    e.setdefault("SIM", "verilator")
    xml_name = log_name.replace(".log", ".xml")
    xmlp = os.path.join(REPORTS, xml_name)
    e["COCOTB_RESULTS_FILE"] = xmlp
    logp = os.path.join(REPORTS, log_name)
    print("RUN", label, "expect", "PASS" if expect_pass else "FAIL")
    with open(logp, "w") as log:
        log.write("label=%s expect_pass=%s\n" % (label, expect_pass))
        log.flush()
        p = subprocess.run(MAKE, env=e, cwd=TESTS, stdout=log, stderr=subprocess.STDOUT)
    ok = (p.returncode == 0) and tests_ok(xmlp)
    line = "  -> %s make_rc %s xml %s log %s" % (
        "PASS" if ok else "FAIL",
        p.returncode,
        xmlp,
        logp,
    )
    print(line)
    with open(os.path.join(REPORTS, "make-sim.log"), "a") as f:
        f.write("RUN %s expect %s\n%s\n" % (label, "PASS" if expect_pass else "FAIL", line))
    if expect_pass and not ok:
        print("ERROR: %s should have passed" % label)
        return 1
    if (not expect_pass) and ok:
        print("ERROR: %s should have failed" % label)
        return 1
    return 0


def main():
    ver = os.path.join(REPORTS, "versions.txt")
    with open(ver, "w") as f:
        subprocess.run(
            ["bash", "-lc", "date -u; verilator --version; python3 -c 'import cocotb; print(\"cocotb\", cocotb.__version__)'"],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    with open(os.path.join(REPORTS, "make-sim.log"), "w") as f:
        f.write(open(ver).read())
        f.write("\n")
    rc = 0
    # Unique (R,C) from directed generator
    shapes = [(2, 2), (2, 3), (3, 3), (1, 1), (3, 2), (4, 1)]
    for R, C in shapes:
        rc |= run(
            "good directed %dx%d" % (R, C),
            dict(
                DUT=os.path.join(TESTS, "standins/good.sv"),
                PARAM_R=str(R),
                PARAM_C=str(C),
                K_MAX="64",
                SUITE="directed",
                BP="always",
                SEED="1",
                SIM_BUILD="sim_build/good_%dx%d" % (R, C),
            ),
            "good-directed-%dx%d.log" % (R, C),
            True,
        )
    rc |= run(
        "good random 2x2",
        dict(
            DUT=os.path.join(TESTS, "standins/good.sv"),
            PARAM_R="2",
            PARAM_C="2",
            K_MAX="64",
            SUITE="random",
            BP="always",
            SEED="1",
                SIM_BUILD="sim_build/good_2x2",
        ),
        "good-random.log",
        True,
    )
    for bp in ("always", "random", "long", "every_other"):
        rc |= run(
            "good bp " + bp,
            dict(
                DUT=os.path.join(TESTS, "standins/good.sv"),
                PARAM_R="2",
                PARAM_C="2",
                K_MAX="64",
                SUITE="bp",
                BP=bp,
                SEED="2",
                SIM_BUILD="sim_build/good_2x2",
            ),
            "good-bp-%s.log" % bp,
            True,
        )
    rc |= run(
        "good err/busy",
        dict(
            DUT=os.path.join(TESTS, "standins/good.sv"),
            PARAM_R="2",
            PARAM_C="2",
            K_MAX="64",
            SUITE="err",
            BP="always",
            SEED="1",
            SIM_BUILD="sim_build/good_2x2",
        ),
        "good-err.log",
        True,
    )
    broken = [
        ("broken_sign", "always"),
        ("broken_k_offbyone", "always"),
        ("broken_drop_last", "always"),
        ("broken_rows_swapped", "always"),
        ("broken_bpress", "stall3"),
    ]
    for name, bp in broken:
        rc |= run(
            name,
            dict(
                DUT=os.path.join(TESTS, "standins", name + ".sv"),
                PARAM_R="2",
                PARAM_C="2",
                K_MAX="64",
                SUITE="catch",
                BP=bp,
                SEED="1",
                SIM_BUILD="sim_build/" + name,
            ),
            name + ".log",
            False,
        )
    summary = os.path.join(REPORTS, "make-sim.log")
    with open(summary, "a") as f:
        f.write("exit_rc=%d\n" % rc)
        if rc == 0:
            f.write("SIM OK: good passed, five broken failed\n")
        else:
            f.write("SIM FAIL\n")
    if rc != 0:
        print("SIM FAIL: stand-in phase")
        return rc
    print("SIM OK: good passed, five broken failed")
    # Same tile testbench plus extra RTL tests against real tile_top
    rtl = os.path.join(ROOT, "tests", "run_tile_rtl.py")
    p = subprocess.run([sys.executable, rtl])
    if p.returncode != 0:
        print("SIM FAIL: real tile_top phase")
        return p.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
