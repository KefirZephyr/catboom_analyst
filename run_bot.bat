@echo off
chcp 65001 >nul
title CatBoom Dota Analyst v2

echo ========================================
echo   CatBoom Dota Analyst v2
echo ========================================
echo.

cd /d "%~dp0"

if not exist ".env" (
    echo [ERROR] File .env not found.
    echo Create .env from .env.example and fill required values.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Install Python 3.11+ and try again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found.
    echo [INFO] Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Installing/updating dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to update pip.
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [INFO] Starting bot...
python -m app.main

echo.
echo Bot stopped.
pause
