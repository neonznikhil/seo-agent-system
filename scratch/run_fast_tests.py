import os
import sys
import glob
import pytest

root_dir = os.path.abspath(os.getcwd())
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

tests_dir = os.path.join(root_dir, "backend", "tests")
test_files = sorted(glob.glob(os.path.join(tests_dir, "test_*.py")))

print(f"Running unit test files (skipping slow e2e generation)...", flush=True)

passed = []
failed = []

for tf in test_files:
    fname = os.path.basename(tf)
    if fname in ["test_15point_outline_pipeline.py", "test_e2e_full_flow.py", "test_e2e_user_journey.py"]:
        print(f"[SKIP E2E] {fname}", flush=True)
        continue
    ret = pytest.main([tf, "-q", "--tb=line", "-k", "not e2e"])
    if ret == 0 or ret == 5:  # 0 = pass, 5 = no tests collected/skipped
        print(f"[PASS] {fname} (ret={ret})", flush=True)
        passed.append(fname)
    else:
        print(f"[FAIL] {fname} (ret={ret})", flush=True)
        failed.append(fname)

print(f"\n==========================================")
print(f"FAST SUITE: Passed={len(passed)}, Failed={len(failed)}")
if failed:
    print(f"Failed files: {failed}")
print(f"==========================================", flush=True)
