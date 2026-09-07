import sys
from pathlib import Path

# Add project root to sys.path
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import traceback

def test_backend_main_import():
    """Verify backend main app imports cleanly."""
    try:
        from main import app
        assert app is not None
    except ImportError:
        from backend.main import app
        assert app is not None
