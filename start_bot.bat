@echo off
title CatBoom Dota Analyst v2
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install Python and try again.
    pause
    exit /b 1
)

if not exist ".env" (
    echo .env not found. Create it from .env.example before starting the bot.
    pause
    exit /b 1
)

python -m app.main
pause
