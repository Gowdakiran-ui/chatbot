@echo off
setlocal

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env not found. Run install.bat, then fill in .env with real credentials.
    pause
    exit /b 1
)

if not exist "frontend\.env" (
    echo [ERROR] frontend\.env not found. Run install.bat, then fill in frontend\.env.
    pause
    exit /b 1
)

echo Starting backend on http://localhost:8000 (new window) ...
start "Chanakya Backend" cmd /k ".venv\Scripts\activate.bat && uvicorn serving.app:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo Starting frontend on http://localhost:5173 (new window) ...
start "Chanakya Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 4 /nobreak >nul

echo Opening browser ...
start "" "http://localhost:5173"

echo.
echo ============================================
echo  Both servers are running in separate windows:
echo   - Chanakya Backend  (http://localhost:8000)
echo   - Chanakya Frontend (http://localhost:5173)
echo  Close those windows (or Ctrl+C inside them) to stop.
echo ============================================
