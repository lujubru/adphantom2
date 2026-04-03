@echo off
echo === Traffic Guardian - Backend Setup ===
echo.

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Setup complete!
echo.
echo Next steps:
echo 1. Configure .env file with your DATABASE_URL and SECRET_KEY
echo 2. Create PostgreSQL database
echo 3. Run SQL setup: psql -d traffic_guardian -f database.sql
echo 4. Run migrations: alembic upgrade head
echo 5. Start server: uvicorn app.main:app --reload
echo.
pause