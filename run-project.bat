@echo off
setlocal DisableDelayedExpansion

cd /d "%~dp0"

if not exist ".env" (
    echo [ERROR] Khong tim thay file .env tai: %~dp0.env
    exit /b 1
)

set "JWT_SECRET_KEY="
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="JWT_SECRET_KEY" set "JWT_SECRET_KEY=%%B"
)

if not defined JWT_SECRET_KEY (
    echo [ERROR] JWT_SECRET_KEY chua duoc dat trong file .env.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Khong tim thay .venv\Scripts\python.exe.
    echo Hay tao virtual environment va cai requirements-backend.txt truoc.
    exit /b 1
)

echo Starting backend at http://127.0.0.1:8000 ...
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"

exit /b %EXIT_CODE%
