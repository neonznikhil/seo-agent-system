import os
import sys
import glob
import importlib.util
import time

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
tests_dir = os.path.join(os.getcwd(), "backend", "tests")
test_files = sorted(glob.glob(os.path.join(tests_dir, "test_*.py")))

print(f"Testing import of {len(test_files)} test files...", flush=True)

for test_file in test_files:
    fname = os.path.basename(test_file)
    t0 = time.time()
    try:
        spec = importlib.util.spec_from_file_location(fname[:-3], test_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        dt = time.time() - t0
        print(f"  [OK] {fname} ({dt:.2f}s)", flush=True)
    except Exception as e:
        dt = time.time() - t0
        print(f"  [IMPORT ERROR] {fname} ({dt:.2f}s): {e}", flush=True)

print("Finished import scan.", flush=True)
