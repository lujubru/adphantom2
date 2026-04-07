# AdPhantom - Product Requirements Document

## Original Problem Statement
Aplicacion AdPhantom - CRM de WhatsApp con tracking de conversiones para Meta Pixel.

### Cambios Requeridos (Implementados)
1. **Gestion de usuarios desde UI admin**: Admin puede crear usuarios (admin/cajero), seleccionar lineas y configurar mensajes personalizados de bienvenida/usuario
2. **Fix de eventos Meta**: Quitado el fallback a variables de entorno (META_ACCESS_TOKEN, META_PIXEL_ID), solo se usa token/pixel de cada linea
3. **Rebranding a AdPhantom**: Logo, titulo, favicon actualizados
4. **Filtros de fecha en embudo**: Diario, semanal, mensual, o fecha especifica para cajeros y admins
5. **Trackeo de anuncios (utm_content)**: Asociar leads al anuncio de origen
6. **AI Tools en menu admin**: Generador de landing pages con IA (sin generacion de imagenes)
7. **Toggle de tema claro/oscuro**: Disponible para admin y cajero
8. **Audio messages**: Reproduccion de mensajes de audio de WhatsApp en el CRM
9. **CTWA Ad Tracking**: Tracking de Click-to-WhatsApp ads via referral y extraccion de texto (AD:xxxxx)
10. **External Landing Tracking**: Landing pages externas con tracking via URL params

## Architecture
- **Frontend**: React.js + Tailwind CSS
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **External APIs**: Meta Graph API (WhatsApp Business), Meta Pixel (Conversions API), Claude AI

## User Personas
1. **Admin**: Gestiona campanias, usuarios, lineas de WhatsApp, analytics, landing pages con IA
2. **Cajero**: Atiende leads de CRM, ve embudos filtrados por fecha, usa mensajes personalizados

## Core Requirements
- [x] Multi-linea WhatsApp con tracking independiente por linea
- [x] CRM tipo Kanban con estados (nuevo, spam, consultas, valido)
- [x] Envio de eventos de conversion a Meta Pixel por linea
- [x] Landing pages dinamicas con deteccion de bots
- [x] Gestion de usuarios con roles
- [x] Mensajes personalizados por usuario (bienvenida/usuario)
- [x] Audio message playback en CRM
- [x] CTWA ad tracking
- [x] Meta CAPI Purchase events con value/currency/content_type/event_id

## Key DB Schema
- `users`: {email, role, line_ids, welcome_message, user_message}
- `crm_lines`: {name, whatsapp_number, meta_pixel_id, meta_access_token}
- `crm_leads`: {phone, name, line_id, ad_source, referral, status, charge_amount, meta_events_sent}
- `wa_clicks`: {ip, user_agent, fbp, fbc, utm_content, click_id, landing_code}

## Key API Endpoints
- `POST /api/crm/leads/{lead_id}/classify`: Classify lead + send Meta event (Purchase/LowQualityLead)
- `POST /api/crm/leads/{lead_id}/send-conversion`: Manual Purchase event to Meta
- `POST /api/wa-landings/track-wa`: Landing page WA click → Lead/Contact CAPI events
- `GET /api/crm/funnel/stats`: Funnel statistics with date filters

## Critical Technical Notes
- NO trailing slashes on endpoints (causes 307 redirect on Railway)
- CRM statuses: nuevo, spam, consultas, valido (NOT cliente_real)
- Meta CAPI: Graph API v21.0, events include event_id for deduplication
- Purchase events MUST include: value (float), currency, content_type:"product"

## What's Been Implemented

### Date: 2026-04-03
- User management (CRUD) with role-based access
- Personalized messages per cajero
- Date filters on funnel stats
- Ad performance dashboard (utm_content tracking)
- Theme toggle (dark/light)
- Rebranding to AdPhantom
- Audio message playback
- CTWA ad tracking
- External landing page tracking
- Marketing landing page

### Date: 2026-04-07
- **FIX P0**: Meta CAPI Purchase event payload restructured:
  - Added `event_id` for deduplication across all CAPI events
  - Added `content_type: "product"` to all Purchase events
  - Updated Graph API from v18.0 to v21.0
  - Explicit `float()` casting for `value` parameter
  - Detailed logging: value, currency, fbp, fbc, phone, pixel, event_id
- **FIX**: Manual conversion endpoint checked `cliente_real` instead of `valido` — corrected
- **FIX**: Old classify endpoint hardcoded `value: 0` — now uses `charge_amount`
- **FIX P1**: Verified Landing Page Lead/Contact CAPI events include fbp, fbc, client_ip, user_agent

## Prioritized Backlog
### P1 (High)
- [ ] Verificar funcionamiento completo de tema claro (light mode) en todas las paginas

### P2 (Medium)
- [ ] Notificaciones push para nuevos mensajes
- [ ] Exportacion de datos a CSV
- [ ] Refactorizacion de server.py (~5000 lineas) en routers/servicios separados

### P3 (Low)
- [ ] Configurar API key de Claude para AI Tools
- [ ] Testing completo de flujo de trackeo de anuncios E2E
