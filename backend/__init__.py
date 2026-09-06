import sys
from pathlib import Path

# Ensure backend directory and repo root are in sys.path
_backend_dir = Path(__file__).resolve().parent
_repo_root = _backend_dir.parent
for _p in [str(_backend_dir), str(_repo_root)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
