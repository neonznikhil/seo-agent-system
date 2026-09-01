#!/usr/bin/env python3
"""Wrapper to run the RankForge backend with correct import paths."""
import sys
import os

# Add the current directory to Python path so relative imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)
