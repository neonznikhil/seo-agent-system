import sys
from pathlib import Path

# Add project root to sys.path
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import traceback

print("Testing backend.main import...")
try:
    from backend.main import app
    print("SUCCESS: backend.main app imported cleanly:", app)
except Exception as e:
    print("FAILED TO IMPORT backend.main:")
    traceback.print_exc()
