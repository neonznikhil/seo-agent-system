@echo off
pushd "%~dp0"
if exist venv\Scripts\python.exe (
    start "SEO Agent Backend" venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000 --host 0.0.0.0 --reload
) else (
    start "SEO Agent Backend" python -m uvicorn backend.main:app --port 8000 --host 0.0.0.0 --reload
)
popd
echo Backend running at http://localhost:8000