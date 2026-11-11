#!/usr/bin/env python3
"""Good PE must pass; unsigned variant must fail exhaustive."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PE = os.path.join(ROOT, "tests", "pe")
REPORTS = os.path.join(ROOT, "reports", "O6")
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
            ["make", "-C", PE], env=e, cwd=PE, stdout=log, stderr=subprocess.STDOUT
        )
    ok = (p.returncode == 0) and tests_ok(xmlp)
    print("  ->", "PASS" if ok else "FAIL", "make_rc", p.returncode, "log", logp)
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
            [
                "bash",
                "-lc",
                "date -u; verilator --version; yosys -V | head -1; sby --version 2>/dev/null | head -1; "
                "python3 -c 'import cocotb; print(\"cocotb\", cocotb.__version__)'",
            ],
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    summary = os.path.join(REPORTS, "pe-test.log")
    with open(summary, "w") as f:
        f.write(open(ver).read() + "\n")
    rc = 0
    rc |= run(
        "good pe all",
        dict(
            DUT=os.path.join(ROOT, "rtl", "pe.sv"),
            SUITE="all",
            SEED="1",
            SIM_BUILD="sim_build/pe_good",
            WAVES="0",
        ),
        "good-pe.log",
        True,
    )
    rc |= run(
        "unsigned exhaustive",
        dict(
            DUT=os.path.join(ROOT, "rtl", "variants", "pe_unsigned.sv"),
            SUITE="exhaustive",
            SEED="1",
            SIM_BUILD="sim_build/pe_unsigned",
            WAVES="0",
        ),
        "unsigned-caught.log",
        False,
    )
    with open(summary, "a") as f:
        f.write("exit_rc=%d\n" % rc)
        f.write("PE-TEST OK\n" if rc == 0 else "PE-TEST FAIL\n")
    if rc == 0:
        print("PE-TEST OK: good passed, unsigned failed")
    return rc


if __name__ == "__main__":
    sys.exit(main())
