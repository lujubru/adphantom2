# 🔐 CREAR USUARIO ADMIN - Script Python

## 📝 Descripción

Script para crear/recrear el usuario admin correctamente en PostgreSQL usando el mismo hash de bcrypt que usa la aplicación.

**Problema resuelto:** El hash en el SQL puede no coincidir, este script genera el hash correcto.

---

## 🚀 USO DEL SCRIPT

### Opción 1: Con .env Configurado (Recomendado)

Si ya tienes `backend/.env` con `DATABASE_URL`:

```bash
# 1. Activa entorno virtual
cd backend
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# 2. Ejecuta el script
python create_admin.py
```

### Opción 2: Sin .env (Manual)

Si no tienes `.env` o quieres usar otra base de datos:

```bash
# 1. Activa entorno virtual
cd backend
source venv/bin/activate

# 2. Ejecuta el script
python create_admin.py

# 3. El script te pedirá DATABASE_URL
# Pega la URL de Railway:
postgresql://postgres:PASSWORD@HOST:PORT/railway
```

---

## 📋 EJEMPLO DE USO

```bash
$ cd backend
$ source venv/bin/activate
$ python create_admin.py

============================================================
🚀 SCRIPT DE CREACIÓN DE USUARIO ADMIN
============================================================

📊 Base de datos: monorail.proxy.rlwy.net:12345/railway

⚠️  Este script va a:
   1. Eliminar el usuario: admin@trafficguardian.com (si existe)
   2. Crear nuevo usuario: admin@trafficguardian.com
   3. Con password: admin123

¿Continuar? (s/n): s

============================================================
🔧 CREANDO USUARIO ADMIN
============================================================

1️⃣  Eliminando usuario admin existente (si existe)...
   ✅ Usuario existente eliminado

2️⃣  Generando hash de password...
   ✅ Hash generado: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8...

3️⃣  Creando nuevo usuario admin...
   ✅ Usuario creado con ID: f47ac10b-58cc-4372-a567-0e02b2c3d479

4️⃣  Verificando usuario...
   ✅ Usuario verificado:
      Email: admin@trafficguardian.com
      Activo: True

============================================================
✅ USUARIO ADMIN CREADO EXITOSAMENTE
============================================================

📧 Email:    admin@trafficguardian.com
🔑 Password: admin123

💡 Ahora puedes hacer login en tu app
============================================================
```

---

## 🎯 CREDENCIALES POR DEFECTO

```
Email:    admin@trafficguardian.com
Password: admin123
```

### Cambiar Credenciales

Edita el archivo `create_admin.py`:

```python
# Líneas 14-15
ADMIN_EMAIL = "tu-email@ejemplo.com"
ADMIN_PASSWORD = "tu-password-seguro"
```

---

## 🔧 REQUISITOS

El script necesita:
- ✅ Python 3.11+
- ✅ Entorno virtual activado
- ✅ Dependencias instaladas (`pip install -r requirements.txt`)
- ✅ Acceso a base de datos PostgreSQL
- ✅ Tabla `users` creada (ejecuta `database.sql` primero)

---

## 📊 QUÉ HACE EL SCRIPT

1. **Conecta** a PostgreSQL usando DATABASE_URL
2. **Elimina** usuario admin existente (si existe)
3. **Genera** hash bcrypt del password (mismo algoritmo que la app)
4. **Crea** nuevo usuario admin con hash correcto
5. **Verifica** que el usuario se creó correctamente

---

## 🐛 TROUBLESHOOTING

### Error: "No such table: users"

**Causa:** No ejecutaste `database.sql`

**Solución:**
```bash
# En pgAdmin4
# Ejecuta database.sql completo
```

### Error: "Could not connect to database"

**Causa:** DATABASE_URL incorrecta

**Solución:**
1. Copia DATABASE_URL desde Railway
2. Verifica formato: `postgresql://user:pass@host:port/db`
3. Asegúrate que PostgreSQL está activo en Railway

### Error: "Module 'passlib' not found"

**Causa:** Dependencias no instaladas

**Solución:**
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### Error: "Permission denied"

**Causa:** No tienes permisos de escritura en DB

**Solución:**
- Verifica que el usuario de DATABASE_URL tiene permisos
- En Railway, el usuario automático tiene todos los permisos

---

## 💡 CUÁNDO USAR ESTE SCRIPT

**Úsalo cuando:**
- ✅ El login da "Incorrect email or password"
- ✅ Acabas de ejecutar `database.sql` por primera vez
- ✅ Quieres cambiar el password del admin
- ✅ Recreaste la base de datos
- ✅ Migraste a nuevo servidor

**NO lo uses si:**
- ❌ Ya tienes un admin funcionando
- ❌ Solo quieres crear usuarios adicionales (usa la API)

---

## 🔐 SEGURIDAD

- ✅ Usa bcrypt para hash (mismo que la app)
- ✅ Hash diferente cada vez (salt aleatorio)
- ✅ Compatible con el sistema de auth de FastAPI
- ✅ Password no se guarda en texto plano

**IMPORTANTE:** Cambia el password después del primer login en producción.

---

## 📝 EJEMPLO: Crear Admin con Email Personalizado

```python
# Edita create_admin.py
ADMIN_EMAIL = "miempresa@ejemplo.com"
ADMIN_PASSWORD = "MiPasswordSeguro123!"

# Ejecuta
python create_admin.py
```

---

## ✅ VERIFICAR QUE FUNCIONA

Después de ejecutar el script:

### Test Backend
```bash
curl -X POST https://guardian-production-c153.up.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@trafficguardian.com","password":"admin123"}'

# Debe responder con token:
{"access_token":"eyJ...","token_type":"bearer"}
```

### Test Frontend
1. Abre tu app en Vercel
2. Login con las credenciales
3. ✅ Debe entrar al dashboard

---

## 🎉 RESUMEN

```bash
# Pasos rápidos
cd backend
source venv/bin/activate
python create_admin.py
# Confirmar con 's'
# ✅ Usuario creado

# Test
# Login en tu app con admin@trafficguardian.com / admin123
```

**¡Listo! Usuario admin creado correctamente con hash válido** ✅
