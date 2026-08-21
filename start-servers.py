import subprocess
import sys
import os
from pathlib import Path

base_dir = Path(__file__).parent

backend_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000", "--host", "127.0.0.1"],
    cwd=base_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

print("Backend started on http://127.0.0.1:8000")
print("Backend PID:", backend_proc.pid)

frontend_dir = base_dir / "frontend-next"

# Try to find node executable
node_cmd = "node"
if sys.platform == "win32":
    node_cmd = str(frontend_dir / "node_modules" / "next" / "dist" / "bin" / "next")

frontend_proc = subprocess.Popen(
    [node_cmd, "dev", "--port", "3000"],
    cwd=frontend_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

print("Frontend started on http://localhost:3000")
print("Frontend PID:", frontend_proc.pid)

try:
    while True:
        if backend_proc.poll() is not None:
            print("Backend died!")
            break
        if frontend_proc.poll() is not None:
            print("Frontend died!")
            break
        import time
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down...")
    backend_proc.terminate()
    frontend_proc.terminate()
