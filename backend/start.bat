@echo off
echo === Traffic Guardian - Starting Backend ===
echo.

if not exist "venv" (
    echo Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Starting FastAPI server...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000