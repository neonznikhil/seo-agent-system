#!/usr/bin/env python3
"""Wrapper to run the RankForge backend with correct import paths."""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Change to the app directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import uvicorn
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Use the module directly
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)
