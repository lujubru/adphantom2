#!/usr/bin/env python3
"""
Script para crear/recrear el usuario admin en PostgreSQL
Ejecutar desde el entorno virtual del backend
"""

import sys
import os
from pathlib import Path

# Agregar el directorio app al path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from sqlalchemy import create_engine, text
from passlib.context import CryptContext
import uuid

# Configuración
ADMIN_EMAIL = "admin@trafficguardian.com"
ADMIN_PASSWORD = "admin123"

# Contexto de password (mismo que usa la app)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_database_url():
    """Obtener DATABASE_URL desde .env o solicitar al usuario"""
    env_path = Path(__file__).parent / '.env'
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.split('=', 1)[1].strip().strip('"\'')
                    return db_url
    
    print("\n⚠️  No se encontró DATABASE_URL en .env")
    print("Introduce tu DATABASE_URL de Railway:")
    print("Formato: postgresql://user:password@host:port/database")
    db_url = input("\nDATABASE_URL: ").strip()
    return db_url

def create_admin_user(database_url):
    """Crear usuario admin en la base de datos"""
    
    print("\n" + "="*60)
    print("🔧 CREANDO USUARIO ADMIN")
    print("="*60)
    
    # Crear engine
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # 1. Eliminar usuario admin existente (si existe)
            print("\n1️⃣  Eliminando usuario admin existente (si existe)...")
            result = conn.execute(
                text("DELETE FROM users WHERE email = :email"),
                {"email": ADMIN_EMAIL}
            )
            conn.commit()
            if result.rowcount > 0:
                print(f"   ✅ Usuario existente eliminado")
            else:
                print(f"   ℹ️  No había usuario previo")
            
            # 2. Generar hash del password
            print("\n2️⃣  Generando hash de password...")
            hashed_password = pwd_context.hash(ADMIN_PASSWORD)
            print(f"   ✅ Hash generado: {hashed_password[:50]}...")
            
            # 3. Crear nuevo usuario admin
            print("\n3️⃣  Creando nuevo usuario admin...")
            admin_id = str(uuid.uuid4())
            conn.execute(
                text("""
                    INSERT INTO users (id, email, hashed_password, is_active, created_at)
                    VALUES (:id, :email, :password, TRUE, NOW())
                """),
                {
                    "id": admin_id,
                    "email": ADMIN_EMAIL,
                    "password": hashed_password
                }
            )
            conn.commit()
            print(f"   ✅ Usuario creado con ID: {admin_id}")
            
            # 4. Verificar que se creó correctamente
            print("\n4️⃣  Verificando usuario...")
            result = conn.execute(
                text("SELECT id, email, is_active FROM users WHERE email = :email"),
                {"email": ADMIN_EMAIL}
            )
            user = result.fetchone()
            
            if user:
                print(f"   ✅ Usuario verificado:")
                print(f"      Email: {user[1]}")
                print(f"      Activo: {user[2]}")
            else:
                print(f"   ❌ Error: No se pudo verificar el usuario")
                return False
            
        print("\n" + "="*60)
        print("✅ USUARIO ADMIN CREADO EXITOSAMENTE")
        print("="*60)
        print(f"\n📧 Email:    {ADMIN_EMAIL}")
        print(f"🔑 Password: {ADMIN_PASSWORD}")
        print("\n💡 Ahora puedes hacer login en tu app")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print("\nVerifica que:")
        print("  1. La tabla 'users' existe en la base de datos")
        print("  2. DATABASE_URL es correcta")
        print("  3. Tienes permisos de escritura en la base de datos")
        return False
    
    finally:
        engine.dispose()

def main():
    print("\n" + "="*60)
    print("🚀 SCRIPT DE CREACIÓN DE USUARIO ADMIN")
    print("="*60)
    
    # Obtener DATABASE_URL
    database_url = get_database_url()
    
    if not database_url:
        print("\n❌ DATABASE_URL no proporcionada")
        sys.exit(1)
    
    print(f"\n📊 Base de datos: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    
    # Confirmar
    print(f"\n⚠️  Este script va a:")
    print(f"   1. Eliminar el usuario: {ADMIN_EMAIL} (si existe)")
    print(f"   2. Crear nuevo usuario: {ADMIN_EMAIL}")
    print(f"   3. Con password: {ADMIN_PASSWORD}")
    
    response = input("\n¿Continuar? (s/n): ").strip().lower()
    
    if response != 's':
        print("\n❌ Operación cancelada")
        sys.exit(0)
    
    # Crear usuario
    success = create_admin_user(database_url)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
