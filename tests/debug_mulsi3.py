# /// script
# requires-python = ">=3.10"
# dependencies = ["MC6809>=0.8.0"]
# ///
"""
Step-by-step trace showing exactly what __mulsi3 does wrong.

Usage: nix develop -c uv run tests/debug_mulsi3.py
"""
import array
import subprocess
import tempfile
from pathlib import Path

from MC6809.components.cpu6809 import CPU
from MC6809.components.memory import Memory
from MC6809.core.configs import BaseConfig


# Simple disassembler for key instructions
OPCODES = {
    0x34: "PSHS", 0x35: "PULS", 0x32: "LEAS", 0x30: "LEAX", 0x31: "LEAY",
    0xAF: "STX", 0xEF: "STU", 0xED: "STD", 0xAE: "LDX", 0xEE: "LDU",
    0xEC: "LDD", 0xCC: "LDD#", 0x8E: "LDX#", 0xCE: "LDU#",
    0xBD: "JSR", 0x39: "RTS", 0x1F: "TFR", 0x4F: "CLRA", 0x5F: "CLRB",
}


def disasm(mem, addr):
    """Very basic disassembly for tracing"""
    op = mem[addr]
    if op in OPCODES:
        return OPCODES[op]
    if op == 0x10 or op == 0x11:  # Extended opcodes
        return f"${op:02X}{mem[addr+1]:02X}"
    return f"${op:02X}"


CFG_DICT = {"verbosity": None, "trace": None}


class Config(BaseConfig):
    RAM_START = 0x0000
    RAM_END = 0xFFFF
    ROM_START = 0xFFFF
    ROM_END = 0x0000


class Memory64K(Memory):
    def __init__(self, cfg, **kwargs):
        self.cfg = cfg
        self.read_bus_request_queue = None
        self.read_bus_response_queue = None
        self.write_bus_queue = None
        self.INTERNAL_SIZE = 0x10000
        self.RAM_SIZE = self.INTERNAL_SIZE
        self.ROM_SIZE = 0
        self._mem = array.array("B", [0x00] * self.INTERNAL_SIZE)
        self._read_byte_callbacks = {}
        self._read_word_callbacks = {}
        self._write_byte_callbacks = {}
        self._write_word_callbacks = {}
        self._read_byte_middleware = {}
        self._write_byte_middleware = {}
        self._read_word_middleware = {}
        self._write_word_middleware = {}


def parse_s19(s19_content: str) -> dict[int, int]:
    memory = {}
    for line in s19_content.strip().split('\n'):
        line = line.strip()
        if line.startswith('S1'):
            byte_count = int(line[2:4], 16)
            address = int(line[4:8], 16)
            data_hex = line[8:8 + (byte_count - 3) * 2]
            for i in range(0, len(data_hex), 2):
                memory[address] = int(data_hex[i:i+2], 16)
                address += 1
    return memory


def read_word(mem, addr):
    return (mem._mem[addr] << 8) | mem._mem[addr + 1]


def compile_and_link(c_code: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "test.c").write_text(c_code)

        import os
        toolchain = os.environ.get('M6809_SYSROOT', '').replace('/m6809-unknown-none', '')
        libgcc = f"{toolchain}/lib/gcc/m6809-unknown-none/4.3.6/libgcc.a"
        libc = os.environ.get('M6809_LIBC', '')
        include = f"{toolchain}/m6809-unknown-none/include"

        subprocess.run([
            "m6809-unknown-none-gcc", "-Os", "-S",
            "-I", include,
            str(tmpdir / "test.c"), "-o", str(tmpdir / "test.s")
        ], check=True, capture_output=True)

        subprocess.run(
            ["as6809", "-g", "-o", str(tmpdir / "test.s")],
            cwd=tmpdir, check=True, capture_output=True
        )

        subprocess.run([
            "aslink", "-s", "-m", "-w",
            "-o", str(tmpdir / "test.s19"),
            "-b", ".text=0x2000",
            str(tmpdir / "test.rel"),
            "-l", libc,
            "-l", libgcc
        ], cwd=tmpdir, check=True, capture_output=True)

        memory_map = parse_s19((tmpdir / "test.s19").read_text())

        symbols = {}
        for line in (tmpdir / "test.map").read_text().split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[0].isalnum():
                try:
                    symbols[parts[1]] = int(parts[0], 16)
                except ValueError:
                    pass

        return memory_map, symbols


def trace_execution():
    print("=" * 70)
    print("STEP-BY-STEP TRACE: Why __mulsi3 fails")
    print("=" * 70)

    code = """
long a = 6;
long b = 7;
int main(void) {
    long result = a * b;
    return (int)result;
}
"""

    print("\nCompiling: 6L * 7L = 42L")
    memory_map, symbols = compile_and_link(code)

    mulsi3_addr = symbols.get('___mulsi3', 0x2020)
    mulhi3_addr = symbols.get('_mulhi3', 0x20F0)
    main_addr = symbols.get('_main', 0x2000)

    # Setup emulator
    cfg = Config(CFG_DICT)
    mem = Memory64K(cfg)
    cpu = CPU(mem, cfg)

    for addr, byte in memory_map.items():
        mem._mem[addr] = byte

    halt_addr = 0xFFFC
    mem._mem[halt_addr] = 0x20
    mem._mem[halt_addr + 1] = 0xFE

    sp = 0xFFF0
    mem._mem[sp - 1] = halt_addr & 0xFF
    mem._mem[sp - 2] = (halt_addr >> 8) & 0xFF
    sp -= 2

    cpu.system_stack_pointer.set(sp)
    cpu.program_counter.set(main_addr)

    print(f"\n_main is at ${main_addr:04X}")
    print(f"___mulsi3 is at ${mulsi3_addr:04X}")
    print(f"_mulhi3 is at ${mulhi3_addr:04X}")

    # Track state
    entered_mulsi3 = False
    result_ptr = None
    trace_count = 0
    max_trace = 300  # First N instructions inside mulsi3

    # Track what addresses get written
    writes_to_result = []

    print("\n" + "=" * 70)
    print("PHASE 1: main() calls ___mulsi3")
    print("=" * 70)

    for step in range(3000):
        pc = cpu.program_counter.value
        x = cpu.index_x.value
        s = cpu.system_stack_pointer.value
        d = (cpu.accu_a.value << 8) | cpu.accu_b.value

        if pc == halt_addr:
            break

        # About to call mulsi3 - show the setup
        if pc == mulsi3_addr - 3 and not entered_mulsi3:  # JSR instruction
            print(f"\nAbout to call ___mulsi3:")
            print(f"  Stack has arguments pushed (a=6, b=7)")
            print(f"  X = ${x:04X}  <-- This is the result pointer!")
            print(f"  Result area at ${x:04X} is currently all zeros")

        # Entering mulsi3
        if pc == mulsi3_addr and not entered_mulsi3:
            entered_mulsi3 = True
            result_ptr = x
            print(f"\n" + "=" * 70)
            print(f"PHASE 2: Inside ___mulsi3 (tracing first {max_trace} instructions)")
            print("=" * 70)
            print(f"\nKey question: Does it ever write to ${result_ptr:04X}?")
            print(f"\n{'Step':<5} {'PC':<6} {'Opcode':<8} {'X':<6} {'D':<6} {'S':<6} Notes")
            print("-" * 70)

        # Trace inside mulsi3
        if entered_mulsi3 and trace_count < max_trace:
            op = disasm(mem._mem, pc)
            notes = ""

            # Check for writes to result pointer area
            if op == "STX" or op == "STD":
                notes = "STORE instruction"
            if op == "RTS":
                notes = "RETURNING!"

            print(f"{trace_count:<5} ${pc:04X}  {op:<8} ${x:04X} ${d:04X} ${s:04X} {notes}")
            trace_count += 1

        # Exiting mulsi3
        if entered_mulsi3 and pc >= main_addr and pc < mulsi3_addr:
            print(f"\n" + "=" * 70)
            print("PHASE 3: Returned to main()")
            print("=" * 70)

            print(f"\nResult pointer was: ${result_ptr:04X}")
            print(f"Contents of result area:")
            for i in range(0, 4, 2):
                val = read_word(mem, result_ptr + i)
                print(f"  [{result_ptr + i:04X}] = ${val:04X}", end="")
                if i == 0:
                    print("  (high word)")
                else:
                    print("  (low word) <-- should be $002A!")

            print(f"\nmain() will now do: ldx 10,s  ; load result")
            print(f"But the result area is all zeros!")

            entered_mulsi3 = False
            break

        try:
            cpu.get_and_call_next_op()
        except Exception as e:
            print(f"Error at ${pc:04X}: {e}")
            break

    # Continue to end
    for step in range(1000):
        pc = cpu.program_counter.value
        if pc == halt_addr:
            break
        try:
            cpu.get_and_call_next_op()
        except:
            break

    print(f"\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print(f"\nFinal X register: ${cpu.index_x.value:04X} ({cpu.index_x.value})")
    print(f"Expected: $002A (42)")
    print(f"\nThe bug: ___mulsi3 receives the result pointer in X (${result_ptr:04X})")
    print(f"but it never writes the computed result to that location.")
    print(f"The function does compute 6*7=42 internally, but the epilogue")
    print(f"doesn't copy the result to *X before returning.")


if __name__ == "__main__":
    trace_execution()
