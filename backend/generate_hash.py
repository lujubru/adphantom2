#!/usr/bin/env python3
"""
Script SIMPLE para generar hash de password
Usa esto si solo necesitas el hash para copiar manualmente
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

print("\n" + "="*60)
print("🔐 GENERADOR DE PASSWORD HASH")
print("="*60)

password = input("\nIntroduce el password a hashear: ").strip()

if not password:
    print("❌ Password vacío")
    exit(1)

print("\nGenerando hash...")
hashed = pwd_context.hash(password)

print("\n" + "="*60)
print("✅ HASH GENERADO")
print("="*60)
print(f"\nPassword: {password}")
print(f"\nHash:\n{hashed}")
print("\n" + "="*60)
print("\n💡 Usa este hash en tu SQL INSERT:")
print(f"\nINSERT INTO users (id, email, hashed_password, is_active)")
print(f"VALUES (")
print(f"  uuid_generate_v4(),")
print(f"  'admin@trafficguardian.com',")
print(f"  '{hashed}',")
print(f"  TRUE")
print(f");")
print("\n" + "="*60 + "\n")
