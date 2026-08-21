import subprocess
import sys
import os

os.chdir(r"C:\Users\nikhil\Desktop\seo-agent-system")

backend_proc = subprocess.Popen(
    [r"C:\Users\nikhil\Desktop\seo-agent-system\venv\Scripts\python.exe", "-m", "uvicorn", 
      "backend.main:app", "--port", "8000", "--host", "127.0.0.1"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

print("Backend started on http://127.0.0.1:8000")
print("Backend PID:", backend_proc.pid)

os.chdir(r"C:\Users\nikhil\Desktop\seo-agent-system\frontend-next")
frontend_proc = subprocess.Popen(
    [r"C:\Program Files\nodejs\node.exe", r"node_modules\next\dist\bin\next", "dev", "--port", "3000"],
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