@echo off
setlocal

echo ============================================
echo  Chanakya RAG - Install / Setup
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH. Install Python 3.12+ and re-run.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found on PATH. Install Node 20+ and re-run.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo .venv already exists - reusing it.
)

call .venv\Scripts\activate.bat

echo.
echo Installing backend dependencies ...
python -m pip install --upgrade pip >nul
pip install -r serving\requirements.txt
if errorlevel 1 (
    echo [ERROR] Backend dependency install failed.
    pause
    exit /b 1
)

echo.
echo Installing frontend dependencies ...
pushd frontend
call npm install
if errorlevel 1 (
    echo [ERROR] Frontend dependency install failed.
    popd
    pause
    exit /b 1
)
popd

echo.
if not exist ".env" (
    echo Creating .env from .env.example ...
    copy ".env.example" ".env" >nul
) else (
    echo .env already exists - leaving it untouched.
)

if not exist "frontend\.env" (
    echo Creating frontend\.env from frontend\.env.example ...
    copy "frontend\.env.example" "frontend\.env" >nul
) else (
    echo frontend\.env already exists - leaving it untouched.
)

echo.
echo ============================================
echo  Install complete.
echo.
echo  NEXT STEP: open .env and frontend\.env and
echo  fill in the real credential values (get these
echo  from Kiran - do not commit them), then run
echo  start.bat
echo ============================================
pause
