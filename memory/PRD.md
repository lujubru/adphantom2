# AdPhantom - Product Requirements Document

## Original Problem Statement
Aplicación AdPhantom - CRM de WhatsApp con tracking de conversiones para Meta Pixel.

### Cambios Requeridos (Implementados)
1. **Gestión de usuarios desde UI admin**: Admin puede crear usuarios (admin/cajero), seleccionar líneas y configurar mensajes personalizados de bienvenida/usuario
2. **Fix de eventos Meta**: Quitado el fallback a variables de entorno (META_ACCESS_TOKEN, META_PIXEL_ID), solo se usa token/pixel de cada línea
3. **Rebranding a AdPhantom**: Logo, título, favicon actualizados
4. **Filtros de fecha en embudo**: Diario, semanal, mensual, o fecha específica para cajeros y admins
5. **Trackeo de anuncios (utm_content)**: Asociar leads al anuncio de origen
6. **AI Tools en menú admin**: Generador de landing pages con IA (sin generación de imágenes)
7. **Toggle de tema claro/oscuro**: Disponible para admin y cajero

## Architecture
- **Frontend**: React.js + Tailwind CSS
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **External APIs**: Meta Graph API (WhatsApp Business), Meta Pixel (Conversions API), Claude AI

## User Personas
1. **Admin**: Gestiona campañas, usuarios, líneas de WhatsApp, analytics, landing pages con IA
2. **Cajero**: Atiende leads de CRM, ve embudos filtrados por fecha, usa mensajes personalizados

## Core Requirements
- [x] Multi-línea WhatsApp con tracking independiente por línea
- [x] CRM tipo Kanban con estados (nuevo, spam, consultas, válido)
- [x] Envío de eventos de conversión a Meta Pixel por línea
- [x] Landing pages dinámicas con detección de bots
- [x] Gestión de usuarios con roles
- [x] Mensajes personalizados por usuario (bienvenida/usuario)

## What's Been Implemented
### Date: 2026-04-03
- Endpoint `/api/auth/users` (GET, POST, PUT, DELETE) para gestión de usuarios
- Campos `welcome_message` y `user_message` en modelo de usuario
- Endpoint `/api/crm/funnel/stats` con parámetros `filter_type`, `start_date`, `end_date`
- Endpoint `/api/crm/funnel/by-ad` para estadísticas por anuncio
- Campo `ad_source` en leads extraído de `utm_content` via `click_id`
- Página UserManagement.js para gestión de usuarios desde UI
- Toggle de tema en Layout.js con soporte claro/oscuro
- Actualizado branding a "AdPhantom" en navbar y login
- Quitado fallback a variables de entorno en eventos Meta

## Prioritized Backlog
### P0 (Critical)
- [x] Login y autenticación funcional
- [x] Gestión de usuarios desde UI

### P1 (High)
- [x] Filtros de fecha en embudo
- [x] Trackeo de anuncios
- [ ] Verificar funcionamiento completo de tema claro (light mode)

### P2 (Medium)
- [ ] Notificaciones push para nuevos mensajes
- [ ] Exportación de datos a CSV

## Next Tasks
1. Configurar API key de Claude para AI Tools
2. Verificar funcionamiento del tema claro en todas las páginas
3. Testing completo de flujo de trackeo de anuncios
4. Agregar estadísticas de conversión por anuncio en dashboard
