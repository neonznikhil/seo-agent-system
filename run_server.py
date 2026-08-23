import sys
import uvicorn

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    print("Starting RankForge API Server on 127.0.0.1:8000...", flush=True)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, log_level="info")
