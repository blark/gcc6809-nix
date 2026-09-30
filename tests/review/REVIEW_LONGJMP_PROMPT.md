Review the `review/newlib-longjmp-zero` branch against base commit `bc0cbbc`.
This is an independent correctness review, not a request to implement or
approve the proposal. Do not trust the author's results without checking.

Scope: only the m6809 newlib `longjmp(env, 0)` fix and its evidence. Ignore
any untracked ARM64/combined-review materials in the original working tree;
prefer a clean worktree of the committed branch. No GCC change is proposed.

Start with:
- `git diff bc0cbbc..HEAD`
- `tests/review/LONGJMP.md`
- `patches/newlib-longjmp-zero.patch`
- `tests/review/longjmp_*.c`
- `tests/review/run_longjmp_review.py`
- the existing `tests/run_tests.py` harness and `flake.nix`

Then:
1. Inspect the full m6809 setjmp/longjmp implementation supplied by
   `patches/newlib-m6809.patch`, not just the candidate diff. Verify the
   default ABI, stack offsets, jump-buffer layout, assembler syntax, register
   preservation, and condition-code behavior of the proposed BNE/LDD sequence.
2. Check the C specification and test validity. In particular, verify legal
   setjmp invocation contexts, automatic-local lifetime/volatile rules, and
   that every saved context is still live when jumped to. Look for UB that
   could invalidate the reproduction.
3. Review the Python test harness critically. Verify that it links and runs
   the intended libc implementation, detects failure honestly, and that its
   synthetic saved-context test and CPU reset logic justify the claims made.
   Check for emulator artifacts, missing checks, and false positives.
4. Rebuild and reproduce before/after results using LONGJMP.md. Use build
   timeouts of at least 600 seconds, and do not update flake.lock. The baseline
   run intentionally exits 1; it must not prevent the candidate run.
   Claimed results at O0/O1/Os/O2/O3: baseline 260 C passes and 15 failures;
   candidate 275 C passes. Exhaustive check: baseline fails only val=0;
   candidate passes all 65,536 values.
5. Add temporary adversarial tests if useful. Determine whether the fix
   preserves every nonzero argument and restored state without creating new
   regressions. Distinguish default-ABI guarantees from untested/nonstandard
   calling conventions and emulator-only evidence.
6. Assess the proposed integration. The candidate is intentionally NOT wired
   into flake.nix, and the new C cases are intentionally outside tests/cases
   pending approval; do not mistake this review-only staging for an omission.

Deliver findings ordered by severity with exact file/line references,
reproduction commands and observed results, and minimal corrective changes.
Separate confirmed defects from concerns or coverage gaps. Explicitly state
what you ran, what was blocked, whether the evidence supports integration,
and any remaining limits. If no defects are found, say so without inventing
findings. Do not commit changes or enable the patch without authorization.
