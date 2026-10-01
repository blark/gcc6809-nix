#!/usr/bin/env python3
"""Link the actual patched libgloss crt0.c and execute its reset vector."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
import run_tests as harness


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(f'{command[0]}: {result.stdout}{result.stderr}')


def source_from_patch():
    lines = (ROOT / 'patches/newlib-m6809.patch').read_text().splitlines()
    marker = '+++ b/libgloss/m6809/crt0.c'
    start = lines.index(marker)
    hunk = lines.index('@@ -0,0 +1,218 @@', start) + 1
    body = []
    for line in lines[hunk:]:
        if line.startswith('diff --git '):
            break
        if not line.startswith('+'):
            raise RuntimeError('unexpected crt0 patch hunk')
        body.append(line[1:])
    if len(body) != 218:
        raise RuntimeError(f'crt0 source length changed: {len(body)}')
    return '\n'.join(body) + '\n'


def symbols(link_map):
    return {name: int(addr, 16) for addr, name in
            re.findall(r'^\s*([0-9A-Fa-f]+)\s+(_[A-Za-z0-9_]+)\b', link_map, re.M)}


def main():
    runner = harness.GCC6809TestRunner()
    with tempfile.TemporaryDirectory(prefix='gcc6809-crt0-') as directory:
        tmp = Path(directory)
        (tmp / 'crt0.c').write_text(source_from_patch())
        (tmp / 'probe.c').write_text('''
volatile unsigned int initialized = 0x1234;
volatile unsigned int uninitialized;
volatile unsigned int report_sp, report_data, report_bss, report_cc;
int main(void) {
    __asm__ volatile ("tfr s,d\\n\\tstd _report_sp");
    __asm__ volatile ("tfr cc,a\\n\\tsta _report_cc");
    report_data = initialized;
    report_bss = uninitialized;
    return 37;
}
''')
        for name in ('crt0', 'probe'):
            source = tmp / f'{name}.c'
            run([str(runner.gcc), '-O0', '-S', str(source), '-o', str(tmp / f'{name}.s')], tmp)
            run([str(runner.asm), '-g', '-o', str(tmp / f'{name}.s')], tmp)
        run([str(runner.link), '-s', '-m', '-w', '-o', str(tmp / 'image.s19'),
             '-b', '.text=0x2000', '-b', '.data=0x1000', '-b', '.bss=0x1100', '-b', 'vector=0xfff0',
             str(tmp / 'crt0.rel'), str(tmp / 'probe.rel'), '-l', runner.libgcc], tmp)
        image = harness.parse_s19((tmp / 'image.s19').read_text())
        addresses = symbols((tmp / 'image.map').read_text())
    cfg = harness.Config(harness.CFG_DICT)
    memory = harness.Memory64K(cfg)
    cpu = harness.CPU(memory, cfg)
    mem = memory._mem
    for address, byte in image.items():
        mem[address] = byte
    def word(address):
        return (mem[address] << 8) | mem[address + 1]
    def put(address, value):
        mem[address], mem[address + 1] = value >> 8, value & 255
    # A real image loader initialized .data; crt0 does not copy it.
    # Seed .bss nonzero to distinguish missing zeroing from an already-zero emulator RAM.
    bss = addresses['_uninitialized']
    put(bss, 0xa5a5)
    initial_data = word(addresses['_initialized'])
    if initial_data != 0x1234:
        raise RuntimeError(f'linker failed to initialize .data: {initial_data:04x}')
    put(0xe001, 0)
    cpu.system_stack_pointer.set(0xb000)
    cpu.set_cc(0x50)  # IRQ/FIRQ disabled on reset; crt0 should enable them.
    cpu.program_counter.set(word(0xfffe))
    if cpu.program_counter.value not in image:
        raise RuntimeError(f'reset vector points outside linked code: {cpu.program_counter.value:04x}')
    for _ in range(5000):
        cpu.get_and_call_next_op()
        if word(addresses['_report_sp']) and mem[0xe001] == 37:
            break
    else:
        raise RuntimeError('main did not return through simulator exit')
    sp = word(addresses['_report_sp'])
    data = word(addresses['_report_data'])
    bss_result = word(addresses['_report_bss'])
    cc = mem[addresses['_report_cc']]
    if not (0x1f00 <= sp <= 0x1ffe and data == initial_data
            and bss_result == 0xa5a5 and cc & 0x50 == 0):
        raise RuntimeError(f'SP={sp:04x} data={data:04x} BSS={bss_result:04x} CC={cc:02x}')
    # This is a memory-mapped simulator exit, not a host process exit.
    # The previous loop stopped on the actual write of the returned value.
    print(f'crt0 PASS: reset vector, stack=0x{sp:04x}, initialized data, '
          'BSS intentionally unchanged, simulator exit=37')
    return 0


if __name__ == '__main__':
    sys.exit(main())
