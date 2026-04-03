#!/bin/bash

echo "=== Traffic Guardian - Backend Setup ==="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure .env file with your DATABASE_URL and SECRET_KEY"
echo "2. Create PostgreSQL database: createdb traffic_guardian"
echo "3. Run SQL setup: psql -d traffic_guardian -f database.sql"
echo "4. Run migrations: alembic upgrade head"
echo "5. Start server: uvicorn app.main:app --reload"
echo ""