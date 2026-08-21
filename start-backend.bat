cd /d C:\Users\nikhil\Desktop\seo-agent-system
start "RankForge Backend" venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000 --host 0.0.0.0
echo Backend running at http://localhost:8000