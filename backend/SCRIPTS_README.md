# 🔐 SCRIPTS DE USUARIO ADMIN

## 📦 Archivos Incluidos

```
backend/
├── create_admin.py         ⭐ Script principal (recomendado)
├── generate_hash.py        🔧 Solo genera hash
└── CREATE_ADMIN_GUIDE.md   📚 Guía completa
```

---

## ⚡ USO RÁPIDO

### Script Principal (Recomendado)

```bash
cd backend
source venv/bin/activate
python create_admin.py
```

**Qué hace:**
- ✅ Elimina usuario admin existente
- ✅ Crea nuevo usuario con hash correcto
- ✅ Verifica que funciona
- ✅ Todo automático

---

## 🎯 SOLUCIÓN AL PROBLEMA "Login Failed"

**Problema:** El hash en `database.sql` puede no coincidir con "admin123"

**Solución:** Usa `create_admin.py` que genera el hash correcto

---

## 📋 MÉTODOS DISPONIBLES

### Método 1: Script Automático (Más Fácil) ⭐

```bash
cd backend
source venv/bin/activate
python create_admin.py
# Introduce DATABASE_URL si es necesario
# Confirma con 's'
# ✅ Usuario creado
```

### Método 2: Solo Generar Hash

Si prefieres hacerlo manual:

```bash
cd backend
source venv/bin/activate
python generate_hash.py

# Introduce: admin123
# Copia el hash generado
# Ejecuta en pgAdmin4:

DELETE FROM users WHERE email = 'admin@trafficguardian.com';

INSERT INTO users (id, email, hashed_password, is_active)
VALUES (
  uuid_generate_v4(),
  'admin@trafficguardian.com',
  'el-hash-que-copiaste-aqui',
  TRUE
);
```

---

## 🔧 REQUISITOS

Antes de ejecutar cualquier script:

```bash
# 1. Instala dependencias
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Asegúrate que database.sql está ejecutado
# (tabla users debe existir)

# 3. Tiene DATABASE_URL en .env o la tendrás que introducir
```

---

## ✅ VERIFICAR QUE FUNCIONA

### Test Backend (Railway)

```bash
curl -X POST https://tu-backend.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@trafficguardian.com","password":"admin123"}'
```

**Respuesta exitosa:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### Test Frontend (Vercel)

1. Abre tu app
2. Login:
   - Email: `admin@trafficguardian.com`
   - Password: `admin123`
3. ✅ Dashboard debe cargar

---

## 🐛 TROUBLESHOOTING

### "Table 'users' doesn't exist"

**Solución:** Ejecuta `database.sql` en pgAdmin4 primero

### "Could not connect to database"

**Solución:** Verifica DATABASE_URL en `.env` o introdúcela manualmente

### "Module not found"

**Solución:** Activa el entorno virtual y ejecuta `pip install -r requirements.txt`

### Login sigue fallando

**Solución:**
1. Verifica que el script se ejecutó sin errores
2. Verifica que el usuario existe:
   ```sql
   SELECT * FROM users WHERE email = 'admin@trafficguardian.com';
   ```
3. Intenta recrear el usuario de nuevo con el script

---

## 💡 CAMBIAR PASSWORD

### Para cambiar el password por defecto:

**Opción A - Editar script:**
```python
# En create_admin.py línea 15
ADMIN_PASSWORD = "TuNuevoPassword123!"
```

**Opción B - Generar hash y usar SQL:**
```bash
python generate_hash.py
# Introduce tu nuevo password
# Copia el hash

# En pgAdmin4:
UPDATE users 
SET hashed_password = 'hash-generado-aqui'
WHERE email = 'admin@trafficguardian.com';
```

---

## 🎉 RESUMEN

1. **Script principal:** `python create_admin.py` (automático)
2. **Solo hash:** `python generate_hash.py` (manual)
3. **Verifica:** Login en tu app
4. **Funciona:** ✅

**Credenciales por defecto:**
- Email: `admin@trafficguardian.com`
- Password: `admin123`

---

## 📚 Documentación Completa

Lee `CREATE_ADMIN_GUIDE.md` para más detalles.
