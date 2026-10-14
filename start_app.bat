@echo off
title Climate Hazard Trend Analyzer Launcher
echo ==========================================================
echo Starting Climate Hazard Trend Analyzer (Full Stack)
echo ==========================================================

echo [1/2] Launching Backend on http://localhost:8000 ...
start "FastAPI Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo [2/2] Launching Frontend on http://localhost:5173 ...
start "React Vite Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Waiting for servers to initialize...
timeout /t 3 >nul

echo Opening application in your browser...
start http://localhost:5173

echo.
echo Both servers are now running in separate windows.
echo To stop them, simply close the respective command prompt windows.
echo ==========================================================
