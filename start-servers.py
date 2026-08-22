#!/usr/bin/env python3
"""Cross-platform server starter for SEO Agent System.

Usage:
    python start-servers.py [--help]

Starts both backend (uvicorn) and frontend (next dev) servers.
"""

import argparse
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# ANSI color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[0;35m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color

IS_WINDOWS = platform.system() == "Windows"
HAS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def color(text, color_code):
    return f"{color_code}{text}{NC}" if HAS_COLOR else text


def find_python(base_dir):
    """Find the Python interpreter, preferring venv over system Python."""
    if IS_WINDOWS:
        venv_python = base_dir / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = base_dir / "venv" / "bin" / "python"

    if venv_python.exists():
        return str(venv_python)

    return sys.executable


def find_node():
    """Find the Node.js executable."""
    node = shutil.which("node")
    if node:
        return node

    print(color("Warning: Node.js not found in PATH. Frontend will not start.", YELLOW))
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Start SEO Agent System backend and frontend servers"
    )
    parser.add_argument(
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit",
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Port for the backend server (default: 8000)",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=3000,
        help="Port for the frontend server (default: 3000)",
    )
    args = parser.parse_args()

    # Determine base directory
    base_dir = Path(__file__).parent.resolve()

    print(color("\n" + "=" * 60, CYAN))
    print(color("  SEO Agent System - Server Launcher", MAGENTA))
    print(color("=" * 60, CYAN))
    print(f"  Platform: {platform.system()} {platform.release()}")
    print(f"  Base dir: {base_dir}")
    print(f"  Python:   {find_python(base_dir)}")
    print(f"  Node:     {find_node() or 'Not found'}")
    print(color("=" * 60, CYAN) + "\n")

    # Find executables
    python_exe = find_python(base_dir)
    node_exe = find_node()

    # Start backend
    backend_dir = base_dir / "backend"
    print(color(f"Starting backend on http://127.0.0.1:{args.backend_port}", BLUE))

    backend_proc = subprocess.Popen(
        [
            python_exe,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--port",
            str(args.backend_port),
            "--host",
            "127.0.0.1",
        ],
        cwd=base_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    print(f"  Backend PID: {backend_proc.pid}")

    # Start frontend
    frontend_dir = base_dir / "frontend-next"
    frontend_proc = None

    if node_exe:
        print(
            color(f"Starting frontend on http://localhost:{args.frontend_port}", BLUE)
        )

        frontend_cmd = [node_exe, "dev", "--port", str(args.frontend_port)]
        if IS_WINDOWS:
            next_bin = frontend_dir / "node_modules" / "next" / "dist" / "bin" / "next"
            if next_bin.exists():
                frontend_cmd = [
                    str(next_bin),
                    "dev",
                    "--port",
                    str(args.frontend_port),
                ]

        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=IS_WINDOWS,
        )

        print(f"  Frontend PID: {frontend_proc.pid}")

    print(color("\n" + "=" * 60, GREEN))
    print(color("  Servers started successfully!", GREEN))
    print(color("=" * 60, GREEN))
    print(f"  Backend:  http://127.0.0.1:{args.backend_port}")
    if frontend_proc:
        print(f"  Frontend: http://localhost:{args.frontend_port}")
    print(color("=" * 60, GREEN))
    print("  Press Ctrl+C to stop all servers\n")

    try:
        while True:
            if backend_proc.poll() is not None:
                print(
                    color(
                        f"\nBackend process exited with code {backend_proc.returncode}",
                        RED,
                    )
                )
                break
            if frontend_proc and frontend_proc.poll() is not None:
                print(
                    color(
                        f"\nFrontend process exited with code {frontend_proc.returncode}",
                        RED,
                    )
                )
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print(color("\n\nShutting down servers...", YELLOW))
    finally:
        for proc in [backend_proc, frontend_proc]:
            if proc and proc.poll() is None:
                if IS_WINDOWS:
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(
                        color(
                            f"Process {proc.pid} did not terminate gracefully, killing...",
                            RED,
                        )
                    )
                    proc.kill()

        print(color("All servers stopped.", GREEN))
        sys.exit(0)


if __name__ == "__main__":
    main()
