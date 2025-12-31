# Bug: Indirect Call After setjmp Uses Wrong Stack Offset

## Summary

GCC6809 generates incorrect stack offsets for indirect function calls that occur after `setjmp` when there are 3+ parameters and struct pointer dereferences.

## Symptoms

- Program crashes with "UNKNOWN OP"
- Jumps to wrong address (typically the return address instead of function pointer)
- Only occurs when `setjmp` is involved

## Root Cause

In the generated assembly for `rawrunprotected`:

```asm
    ldd   32,s      ; Load ud ✓ correct offset
    pshs  d         ; Push ud (stack shifts by 2)
    ldx   2,s       ; Load L ✓ correctly adjusted for push
    jsr   [30,s]    ; Call f ✗ WRONG! Should be [32,s]
```

After `pshs d`, all stack offsets increase by 2:
- `f` moves from `SP+30` → `SP+32`
- But GCC still uses offset 30, which now points to the **return address**

### Trace Evidence

```
*** FOUND: jsr [30,s] at $2036 ***
SP = $FFC6
[SP+30] = $2064  <-- what jsr will use (return address!)
[SP+32] = $2000  <-- where f (test_func) actually is
```

## Why setjmp Triggers It

Without setjmp, GCC generates simpler code with correct offsets:

```asm
    ldu   6,s       ; Load ud
    stu   ,--s      ; Push ud
    jsr   [6,s]     ; Call f ✓ correct (f is at SP+6 after push)
```

The setjmp case has:
1. Large local frame (26 bytes for `jmp_buf`)
2. Complex control flow (if/else around setjmp return)
3. The compiler's stack offset tracking gets confused

## Conditions

All must be present:
- 3+ parameters to the function
- Struct pointer dereferences before setjmp
- Indirect call through function pointer parameter after setjmp

## Workaround

Copy function pointer and parameters to volatile locals before setjmp:

```c
int rawrunprotected(struct State *L, Pfunc f, void *ud) {
    volatile Pfunc f_copy = f;
    volatile void *ud_copy = ud;

    struct lua_longjmp lj;
    lj.status = 0;
    lj.previous = L->errorJmp;
    L->errorJmp = &lj;

    if (setjmp(lj.b) == 0) {
        (*f_copy)(L, ud_copy);  // Use volatile copies
    }

    L->errorJmp = lj.previous;
    return lj.status;
}
```

This forces GCC to reload from known stack locations rather than using stale offsets.

## Affected Version

- GCC 4.3.6 (gcc6809 fork)
- m6809-unknown-none target

## Related Files

- `bug_funcptr_setjmp_3param.c` - Test case that reproduces the bug

## GCC Internal Analysis

### RTL Dump Investigation

The bug occurs during GCC's global register allocation (greg) pass. Analyzing the RTL dumps reveals:

**Before register allocation (lreg pass):**
The call uses a virtual register for the function pointer:
```
(call_insn ... (call (mem:HI (reg/v/f:HI 31 [ f ])) ...))
```

**After register allocation (greg pass):**
The virtual register gets spilled to stack, but the offset is wrong:
```
(insn 56 ... (set (reg:HI 6 d)
        (mem/f/c/i:HI (plus:HI (reg/f:HI 4 s)
                (const_int 32 [0x20])) ...))  ; Load ud from SP+32 ✓

(insn 21 ... (set (mem/f/i:HI (pre_dec:HI (reg/f:HI 4 s)) ...)
        (reg:HI 6 d)) ...)                    ; Push ud (SP decreases by 2)

(insn 22 ... (set (reg:HI 1 x)
        (mem/c:HI (plus:HI (reg/f:HI 4 s)
                (const_int 2 [0x2])) ...))    ; Load L from SP+2 ✓ (adjusted!)

(call_insn 23 ... (call (mem:HI (mem/f/c/i:HI (plus:HI (reg/f:HI 4 s)
                    (const_int 30 [0x1e])) ...)) ...))  ; Call [SP+30] ✗ WRONG!
```

### The Core Bug

The reload phase correctly adjusts the offset for `insn 22` (loading L into X) from SP+0 to SP+2 after the push. However, it **fails to adjust** the memory operand inside the call instruction from SP+30 to SP+32.

This is a bug in how GCC's reload handles memory operands that are **nested inside call patterns**. Regular memory operands get adjusted for stack changes, but the doubly-indirect memory operand in the call instruction is missed.

### Technical Details

1. Virtual register 31 (f) is assigned stack slot at frame offset 30
2. Virtual register 30 (L) is assigned stack slot at frame offset 0
3. Before the push, f is at SP+30 and L is at SP+0
4. The push decrements SP by 2
5. After the push, f should be at SP+32 and L is at SP+2
6. GCC correctly adjusts L's offset (0→2) but not f's offset (30→30, should be 32)

### Possible Fix Locations

1. **GCC core (reload.c/reload1.c)**: The reload pass needs to track and adjust memory operands inside call instruction patterns, not just top-level operands.

2. **m6809 backend**: Could potentially define a different calling convention or use a different pattern that avoids this issue.

3. **Workaround at C level**: Use volatile locals to force the compiler to reload values from stable locations (documented above).

## Proposed Fix

### Option 1: Fix in m6809 Backend (Recommended)

Modify the `call` expander in `m6809.md` to force indirect call addresses into a register before the call. This ensures the function pointer is loaded before any argument pushes change the stack pointer.

**Current code:**
```
(define_expand "call"
  [(call (match_operand:HI 0 "memory_operand" "")
    (match_operand:HI 1 "general_operand" ""))]
  ""
  "")
```

**Proposed fix:**
```
(define_expand "call"
  [(call (match_operand:HI 0 "memory_operand" "")
    (match_operand:HI 1 "general_operand" ""))]
  ""
{
  /* If this is an indirect call (call target is loaded from memory),
     force the address into a register first.  This is needed because
     argument pushes will change the stack pointer offset before the
     call executes, but GCC's reload doesn't adjust memory operands
     inside call patterns.  Bug: setjmp + 3 params + indirect call.  */
  rtx addr = XEXP (operands[0], 0);
  if (MEM_P (addr))
    {
      rtx reg = gen_reg_rtx (HImode);
      emit_move_insn (reg, addr);
      operands[0] = gen_rtx_MEM (HImode, reg);
    }
})
```

This forces code generation like:
```asm
    ldx   30,s      ; Load f into X (before argument push)
    ldd   32,s      ; Load ud
    pshs  d         ; Push ud
    jsr   ,x        ; Call through X (not affected by push)
```

Instead of the buggy:
```asm
    ldd   32,s      ; Load ud
    pshs  d         ; Push ud
    jsr   [30,s]    ; Call [SP+30] - WRONG! f is now at SP+32
```

### Option 2: Fix in GCC Core (Complex)

Modify `reload1.c` to track and adjust memory operands inside call instruction patterns when stack pointer changes occur. This would be a more comprehensive fix but requires deep changes to GCC's reload infrastructure.

### Verification

After applying the fix, compile with `-da` and verify the RTL shows the function pointer being loaded into a register before any argument pushing.
