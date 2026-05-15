@echo off
chcp 65001 >nul
echo ============================================
echo   МедАссистент - Медицинский Telegram Бот
echo ============================================
echo.

echo [1/2] Установка зависимостей...
pip install -r requirements.txt
echo.

echo [2/2] Запуск бота...
python -m bot.main

pause
