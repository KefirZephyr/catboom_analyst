@echo off
title CatBoom Analyst Bot
cd /d "F:\Desktop\catboom_analyst"

echo.
echo ========================================
echo   🎯 CatBoom Analyst Bot Launcher
echo ========================================
echo.

:: Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Установите Python с https://python.org
    pause
    exit /b 1
)

:: Проверяем наличие .env файла
if not exist ".env" (
    echo ❌ Файл .env не найден!
    echo 💡 Создайте файл .env с настройками бота
    echo.
    echo Пример содержимого .env:
    echo BOT_TOKEN=your_bot_token_here
    echo API_ID=your_api_id_here
    echo API_HASH=your_api_hash_here
    echo DATABASE_URL=sqlite:///catboom_analyst.db
    echo.
    pause
    exit /b 1
)

:: Проверяем наличие main.py
if not exist "main.py" (
    echo ❌ Файл main.py не найден!
    echo 💡 Убедитесь что вы находитесь в правильной папке
    pause
    exit /b 1
)

echo ✅ Проверка файлов пройдена
echo.

:: Установка зависимостей (если нужно)
if not exist "requirements.txt" (
    echo ⚠️ Файл requirements.txt не найден
) else (
    echo 📦 Проверяем зависимости...
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo ⚠️ Некоторые зависимости могли не установиться
    ) else (
        echo ✅ Зависимости актуальны
    )
)

echo.
echo 🚀 Запускаем CatBoom Analyst Bot...
echo.
echo 💡 Для остановки бота нажмите Ctrl+C
echo 📱 После запуска отправьте боту команду /start
echo.

:: Запуск бота
python main.py

echo.
echo 🛑 Бот остановлен
pause
