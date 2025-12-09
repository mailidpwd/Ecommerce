@echo off
REM Quick start script for Windows

echo 🚀 Starting Decision Recommendation Backend...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python 3.9+
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

echo 📦 Activating virtual environment...
call venv\Scripts\activate.bat

echo 📦 Installing dependencies...
pip install -r requirements.txt -q

echo 🎭 Installing Playwright browsers...
playwright install chromium --with-deps

echo.
echo ✅ Setup complete!
echo.
echo 🌐 Starting server on http://localhost:8000
echo 📚 API docs: http://localhost:8000/docs
echo.
echo ⏱️  Performance target: ^<5 seconds per request
echo.

REM Start the server
python main.py
pause

