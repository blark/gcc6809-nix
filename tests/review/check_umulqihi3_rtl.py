#!/usr/bin/env python3
"""Reject unsigned byte MUL RTL with a bare QI or negative HI factor.

This checks emitted RTL, not a demonstrated C wrong-code reproducer.
Uses GCC6809_TOOLCHAIN or --gcc; no emulator dependency.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def form_at(text, start):
    depth = 0
    quoted = escaped = False
    for end in range(start, len(text)):
        char = text[end]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:end + 1]
    raise ValueError("Unbalanced RTL dump")


def children(form):
    result = []
    pos = form.index(" ") + 1
    while pos < len(form) - 1:
        if form[pos] == "(":
            child = form_at(form, pos)
            result.append(child)
            pos += len(child)
        else:
            pos += 1
    return result


def check_dump(text):
    checked = constants = 0
    errors = []
    for match in re.finditer(r"\(mult:HI\s", text):
        product = form_at(text, match.start())
        operands = children(product)
        if len(operands) != 2:
            raise ValueError("Expected two multiplication operands")
        if not operands[0].startswith("(zero_extend:HI "):
            continue  # Ordinary HI multiplication is not this native byte pattern.
        checked += 1
        factor = operands[1]
        if factor.startswith("(zero_extend:HI "):
            inner = children(factor)
            if len(inner) != 1 or not re.match(r"\([^\s():]+(?::[^\s():]+)*:QI\s", inner[0]):
                errors.append("Second extension does not contain a QI operand: " + factor)
        elif factor.startswith("(const_int "):
            constant = re.match(r"\(const_int (-?\d+)(?:\s|\))", factor)
            if constant is None:
                raise ValueError("Malformed RTL integer constant: " + factor)
            value = int(constant.group(1))
            constants += 1
            if not 0 <= value <= 255:
                errors.append("HI factor is not an unsigned byte: " + factor)
        else:
            errors.append("Unextended QI factor in HI multiplication: " + factor)
    return checked, constants, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = os.environ.get("GCC6809_TOOLCHAIN")
    parser.add_argument("--gcc", default=str(Path(default) / "bin/m6809-unknown-none-gcc")
                        if default else shutil.which("m6809-unknown-none-gcc"))
    args = parser.parse_args()
    if not args.gcc:
        parser.error("Set GCC6809_TOOLCHAIN or --gcc")
    cases = Path(__file__).resolve().parents[1] / "cases"
    levels = os.environ.get("GCC6809_OPT", "-O0 -O1 -O2 -O3 -Os").split()
    if not levels:
        parser.error("GCC6809_OPT must contain at least one level")
    total = constants = failures = 0
    for opt in levels:
        for name in ("mulqi3_narrow.c", "umulqihi3_factors.c"):
            with tempfile.TemporaryDirectory(prefix="gcc6809-umul-rtl-") as directory:
                tmp = Path(directory)
                subprocess.run([args.gcc, opt, "-std=c99", "-S", "-fdump-rtl-expand",
                                str(cases / name), "-o", str(tmp / "probe.s")],
                               cwd=tmp, check=True)
                dumps = list(tmp.glob("*.expand"))
                if len(dumps) != 1:
                    raise RuntimeError("Expected one expand dump")
                count, immediate, errors = check_dump(dumps[0].read_text())
                if name == "mulqi3_narrow.c" and not count:
                    errors.append("Missing native byte-product coverage")
                total += count
                constants += immediate
                failures += len(errors)
                print(f"{opt} {name}: {count} byte products, {immediate} constants, "
                      f"{len(errors)} RTL errors")
                for error in errors[:3]:
                    print("  " + error)
    if not total or not constants:
        print("FAIL: missing native byte-product or immediate-factor coverage")
        failures += 1
    print(f"RTL: {total} products, {constants} constants, {failures} errors")
    return int(failures != 0)


if __name__ == "__main__":
    raise SystemExit(main())
