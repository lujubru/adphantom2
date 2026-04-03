#!/usr/bin/env python3
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
import uuid
import asyncio
from datetime import datetime, timezone

CAJERO_EMAIL = "cajero@aresguardian.com"
CAJERO_PASSWORD = "TuPassword123"  # cambiá esto

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12, bcrypt__ident="2b")

def get_mongo_url():
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('MONGO_URL='):
                    return line.split('=', 1)[1].strip().strip('"\'')
    return input("MONGO_URL: ").strip()

def get_db_name():
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('DB_NAME='):
                    return line.split('=', 1)[1].strip().strip('"\'')
    return "traffic_guardian"

async def create_cajero():
    mongo_url = get_mongo_url()
    db_name = get_db_name()
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    existing = await db.users.find_one({"email": CAJERO_EMAIL})
    if existing:
        print(f"⚠️  El usuario {CAJERO_EMAIL} ya existe, actualizando rol...")
        await db.users.update_one(
            {"email": CAJERO_EMAIL},
            {"$set": {"role": "cajero"}}
        )
        print("✅ Rol actualizado a cajero")
    else:
        hashed = pwd_context.hash(CAJERO_PASSWORD)
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": CAJERO_EMAIL,
            "hashed_password": hashed,
            "role": "cajero",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"✅ Usuario creado: {CAJERO_EMAIL} / {CAJERO_PASSWORD}")
    
    client.close()

asyncio.run(create_cajero())
