#!/usr/bin/env python3
"""Exhaustive check of the 16-bit divide/modulo helpers in libgcc1.s.

Links the real _divhi3, _modhi3, _udivhi3, _umodhi3, _seuclid and _euclid
from libgcc.a and calls them the way GCC does (dividend in X, divisor
pushed on the stack, result in X) for every 16-bit dividend against a set
of representative divisors.  Expected results come from Python (C99
truncation toward zero; the remainder takes the dividend's sign), not
from the code under test.  Dependencies: the same Python environment as
tests/run_tests.py.  See DIVMOD.md here for the helper contract and results.

    run_divmod_review.py [--jobs N] [--divisors 1,-1,7,...] [--quick]
"""

import argparse
import multiprocessing
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness


HERE = Path(__file__).resolve().parent
HELPERS = ("_divhi3", "_modhi3", "_udivhi3", "_umodhi3", "_seuclid", "_euclid")

# Divisors for the exhaustive dividend sweeps.  0 is checked separately
# (the wrappers must abort, and _euclid must never see it).
SIGNED_DIVISORS = [1, -1, 2, -2, 3, -3, 7, -7, 10, -10, 100, -100, 255, 256,
                   257, -256, 4096, 32767, -32767, -32768]
UNSIGNED_DIVISORS = [1, 2, 3, 7, 10, 100, 255, 256, 257, 4096, 32767, 32768,
                     32769, 65535]
QUICK_SIGNED = [1, -1, 7, -10, 256, -32768]
QUICK_UNSIGNED = [1, 7, 256, 65535]

EDGE_SIGNED = [0, 1, -1, 2, -2, 127, 128, 255, 256, 257, 32767, -32767, -32768,
               -32512, 32512, -129, -128, 12345, -12345]
EDGE_UNSIGNED = [0, 1, 2, 127, 128, 255, 256, 257, 32767, 32768, 32769, 65534,
                 65535, 12345, 54321]

HALT = 0xFFFC       # BRA -2 loop, like the harness's return address
ENTRY_SP = 0xE000
MAX_OPS = 1000      # a helper call takes a few hundred instructions


def c_divmod(a, b):
    """C99 signed division: quotient toward zero, remainder has a's sign."""
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return q, a - q * b


def to_signed(word):
    return word - 0x10000 if word & 0x8000 else word


def build_probe(runner):
    """Link a jump table to the helpers; return (code, symbol addresses)."""
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        source = tmp / "probe.s"
        lines = ["\t.area .text", "\t.globl _main, _abort, " + ", ".join(HELPERS),
                 "\t.globl " + ", ".join(f"call{h}" for h in HELPERS), "_main:"]
        for helper in HELPERS:
            lines += [f"call{helper}:", f"\tjmp {helper}"]
        # Divide by zero jumps here; distinct from HALT so it can be told apart
        lines += ["_abort:", "\tbra _abort", ""]
        source.write_text("\n".join(lines))
        subprocess.run([str(runner.asm), "-g", "-o", str(source)],
                       cwd=tmp, check=True, capture_output=True, text=True)
        subprocess.run([str(runner.link), "-s", "-m", "-w", "-o",
                        str(tmp / "probe.s19"), "-b", ".text=0x2000",
                        str(tmp / "probe.rel"), "-l", runner.libgcc],
                       cwd=tmp, check=True, capture_output=True, text=True)
        code = harness.parse_s19((tmp / "probe.s19").read_text())
        symbols = {}
        for line in (tmp / "probe.map").read_text().splitlines():
            match = re.match(r"\s*([0-9A-Fa-f]{4})\s+(\S+)", line)
            if match:
                symbols[match.group(2)] = int(match.group(1), 16)
    entries = {h: symbols[f"call{h}"] for h in HELPERS}
    return code, entries, symbols["_abort"]


class Machine:
    """One emulator instance with the probe loaded."""

    def __init__(self, code, abort):
        cfg = harness.Config(harness.CFG_DICT)
        self.memory = harness.Memory64K(cfg)
        self.cpu = harness.CPU(self.memory, cfg)
        for address, byte in code.items():
            self.memory._mem[address] = byte
        self.memory._mem[HALT] = 0x20
        self.memory._mem[HALT + 1] = 0xFE
        self.abort = abort

    def word(self, address, value=None):
        mem = self.memory._mem
        if value is None:
            return (mem[address] << 8) | mem[address + 1]
        mem[address] = (value >> 8) & 0xFF
        mem[address + 1] = value & 0xFF

    def call(self, entry, x, stack_arg, d=0):
        """Call ENTRY with X and D set and STACK_ARG at 2,s; run to HALT/abort.

        Returns (stopped_at, X, D, S, Y, U, DP, ops).  Y, U and DP hold
        canaries derived from the operands so a clobber is caught.
        """
        cpu = self.cpu
        canary_y = (x ^ 0x5A5A) & 0xFFFF
        canary_u = (stack_arg ^ 0xA5A5) & 0xFFFF
        canary_dp = (x >> 8) ^ 0x3C
        self.word(ENTRY_SP, HALT)
        self.word(ENTRY_SP + 2, stack_arg & 0xFFFF)
        cpu.index_x.set(x & 0xFFFF)
        cpu.accu_d.set(d & 0xFFFF)
        cpu.index_y.set(canary_y)
        cpu.user_stack_pointer.set(canary_u)
        cpu.direct_page.set(canary_dp)
        cpu.system_stack_pointer.set(ENTRY_SP)
        cpu.set_cc(0)
        cpu.program_counter.set(entry)
        ops = 0
        while cpu.program_counter.value not in (HALT, self.abort):
            if ops >= MAX_OPS:
                break
            cpu.get_and_call_next_op()
            ops += 1
        pc = cpu.program_counter.value
        stopped = "halt" if pc == HALT else "abort" if pc == self.abort else "timeout"
        regs_ok = (cpu.index_y.value == canary_y
                   and cpu.user_stack_pointer.value == canary_u
                   and cpu.direct_page.value == canary_dp)
        return (stopped, cpu.index_x.value, cpu.accu_d.value,
                cpu.system_stack_pointer.value, regs_ok, ops)


def expected_wrapper(helper, dividend, divisor):
    """Expected X after a wrapper call, as a 16-bit word."""
    if helper in ("_divhi3", "_modhi3"):
        q, r = c_divmod(to_signed(dividend), to_signed(divisor))
        value = q if helper == "_divhi3" else r
    else:
        value = dividend // divisor if helper == "_udivhi3" else dividend % divisor
    return value & 0xFFFF


def check_wrapper(machine, entries, helper, dividend, divisor):
    """Return None if the call matched the contract, else a description."""
    stopped, x, _d, s, regs_ok, ops = machine.call(entries[helper], dividend, divisor)
    if stopped != "halt":
        return f"{stopped} after {ops} ops"
    want = expected_wrapper(helper, dividend, divisor)
    problems = []
    if x != want:
        problems.append(f"X=0x{x:04x} want 0x{want:04x}")
    if s != ENTRY_SP + 2:
        problems.append(f"S=0x{s:04x} want 0x{ENTRY_SP + 2:04x}")
    if not regs_ok:
        problems.append("Y/U/DP clobbered")
    return "; ".join(problems) or None


def sweep_job(args):
    """Worker: all 65,536 dividends for one (helper, divisor)."""
    code, entries, abort, helper, divisor = args
    machine = Machine(code, abort)
    failures = []
    for dividend in range(65536):
        problem = check_wrapper(machine, entries, helper, dividend, divisor)
        if problem:
            failures.append((dividend, problem))
    return helper, divisor, failures


def report(name, failures, total):
    for dividend, problem in failures[:5]:
        print(f"  {name} dividend=0x{dividend:04x}: {problem}")
    print(f"{name}: {total - len(failures)}/{total} passed")
    return len(failures)


def check_zero_divisor(machine, entries):
    """The wrappers must reach _abort for every zero-divisor call."""
    failures = []
    for helper in ("_divhi3", "_modhi3", "_udivhi3", "_umodhi3"):
        for dividend in range(65536):
            stopped, *_ = machine.call(entries[helper], dividend, 0)
            if stopped != "abort":
                failures.append((dividend, f"{helper}: {stopped}, want abort"))
    return report("divide by zero -> _abort", failures, 4 * 65536)


def check_euclid_direct(machine, entries):
    """Call _seuclid/_euclid as libgcc1.s does: push left, D=right.

    Both results come back at once: quotient in the pushed slot, modulus
    in D.  Checked over the edge dividends x every sweep divisor.
    """
    failures = []
    total = 0
    cases = ([("_seuclid", a, b) for a in EDGE_SIGNED for b in SIGNED_DIVISORS]
             + [("_euclid", a, b) for a in EDGE_UNSIGNED for b in UNSIGNED_DIVISORS])
    for helper, left, right in cases:
        total += 1
        if helper == "_seuclid":
            q, r = c_divmod(left, right)
        else:
            q, r = left // right, left % right
        stopped, _x, d, s, regs_ok, ops = machine.call(
            entries[helper], 0x1234, left, d=right)
        quotient = machine.word(ENTRY_SP + 2)
        problems = []
        if stopped != "halt":
            problems.append(f"{stopped} after {ops} ops")
        if quotient != q & 0xFFFF:
            problems.append(f"quotient 0x{quotient:04x} want 0x{q & 0xFFFF:04x}")
        if d != r & 0xFFFF:
            problems.append(f"modulus D=0x{d:04x} want 0x{r & 0xFFFF:04x}")
        if s != ENTRY_SP + 2:
            problems.append(f"S=0x{s:04x}")
        if not regs_ok:
            problems.append("Y/U/DP clobbered")
        if problems:
            failures.append((left & 0xFFFF, f"{helper} right={right}: " + "; ".join(problems)))
    return report("_seuclid/_euclid direct (edge dividends)", failures, total)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=int, default=multiprocessing.cpu_count())
    parser.add_argument("--divisors", help="comma-separated signed divisors "
                        "for the sweep (unsigned uses their 16-bit patterns)")
    parser.add_argument("--quick", action="store_true",
                        help="fewer divisors, for a smoke run")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # progress through a pipe

    runner = harness.GCC6809TestRunner()
    code, entries, abort = build_probe(runner)
    print(f"libgcc: {runner.libgcc}")

    if args.divisors:
        signed = [int(d, 0) for d in args.divisors.split(",")]
        unsigned = sorted({d & 0xFFFF for d in signed})
    elif args.quick:
        signed, unsigned = QUICK_SIGNED, QUICK_UNSIGNED
    else:
        signed, unsigned = SIGNED_DIVISORS, UNSIGNED_DIVISORS
    if 0 in signed or 0 in unsigned:
        raise SystemExit("divisor 0 is covered by the abort check; remove it")

    failed = 0
    machine = Machine(code, abort)
    failed += check_euclid_direct(machine, entries)
    failed += check_zero_divisor(machine, entries)

    jobs = ([(code, entries, abort, h, d & 0xFFFF)
             for h in ("_divhi3", "_modhi3") for d in signed]
            + [(code, entries, abort, h, d)
               for h in ("_udivhi3", "_umodhi3") for d in unsigned])
    print(f"sweeping {len(jobs)} (helper, divisor) pairs x 65536 dividends "
          f"on {args.jobs} processes")
    with multiprocessing.Pool(args.jobs) as pool:
        for helper, divisor, failures in pool.imap_unordered(sweep_job, jobs):
            shown = to_signed(divisor) if helper in ("_divhi3", "_modhi3") else divisor
            failed += report(f"{helper} divisor={shown}", failures, 65536)
    print(f"Exhaustive divmod: {'FAIL' if failed else 'PASS'} ({failed} failures)")
    return int(failed != 0)


if __name__ == "__main__":
    sys.exit(main())
