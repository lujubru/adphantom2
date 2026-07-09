import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Users, Plus, Search, Phone, MessageCircle,
  Check, X, Trash2, RefreshCw,
  DollarSign, UserCheck, AlertTriangle, AlertCircle,
  GripVertical, Eye, Settings, Smartphone,
  ArrowRight, ArrowLeft, BarChart3, Zap, Copy, User, Target,
  Megaphone, Radio, Download,
  Tag as TagIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import api from '@/utils/api';
import { useTheme } from '@/contexts/ThemeContext';

import { STATUS_CONFIG, LINE_TYPE_CONFIG, STATUS_ORDER, BADGE_COLORS, BACKEND_URL } from './leads-crm/constants';
import { formatTime } from './leads-crm/utils';
import { StatusBadge } from './leads-crm/StatusSelector';
import { ChatPanel } from './leads-crm/ChatPanel';
import { BroadcastModal } from './leads-crm/BroadcastModal';
import { ChatListItem } from './leads-crm/ChatListItem';
import { TagsManagerModal, TagChipList } from './leads-crm/LeadTags';
import { SidebarNav } from './leads-crm/SidebarNav';
import { LeadAvatar } from './leads-crm/LeadAvatar';
import { MPInboxModal, useMPInbox } from './leads-crm/MPInbox';

// ─── Funnel (admin only) ───────────────────────────────────────────

const FunnelDisplay = ({ funnel, conversionRates, totals, period, onFilterChange, filterType, startDate, endDate }) => {
  const steps = [
    { key: 'visitas', label: 'Visitas',    value: funnel?.visitas || 0, icon: Eye },
    { key: 'clicks',  label: 'Clicks WA',  value: funnel?.clicks  || 0, icon: Smartphone },
    { key: 'chats',   label: 'Chats',      value: funnel?.chats   || 0, icon: MessageCircle },
    { key: 'cargas',  label: 'Válidos',    value: funnel?.cargas  || 0, icon: DollarSign },
  ];
  const rates = [
    conversionRates?.visitas_to_clicks || 0,
    conversionRates?.clicks_to_chats   || 0,
    conversionRates?.chats_to_cargas   || 0,
  ];

  const [showDatePicker, setShowDatePicker] = useState(false);
  const [customStart, setCustomStart] = useState(startDate || '');
  const [customEnd, setCustomEnd] = useState(endDate || '');

  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-sm font-medium text-slate-400 flex items-center gap-2">
          <BarChart3 className="w-4 h-4" /> Embudo de Conversión
          {period && <span className="text-xs text-slate-500">({period})</span>}
        </h3>
        {onFilterChange && (
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={filterType || '30'}
              onChange={(e) => {
                const val = e.target.value;
                if (val === 'custom') {
                  setShowDatePicker(true);
                } else {
                  setShowDatePicker(false);
                  onFilterChange(val, null, null);
                }
              }}
              className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-2 py-1"
            >
              <option value="diario">Hoy</option>
              <option value="ayer">Ayer</option>
              <option value="ultimos_10">Últimos 10 días</option>
              <option value="semanal">Esta semana</option>
              <option value="mensual">Este mes</option>
              <option value="mes_anterior">Mes anterior</option>
              <option value="7">Últimos 7 días</option>
              <option value="30">Últimos 30 días</option>
              <option value="90">Últimos 90 días</option>
              <option value="custom">Fecha específica</option>
            </select>
            {showDatePicker && (
              <div className="flex items-center gap-2">
                <input type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-2 py-1" />
                <span className="text-slate-500 text-xs">a</span>
                <input type="date" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-2 py-1" />
                <Button size="sm" onClick={() => onFilterChange('custom', customStart, customEnd)}
                  className="bg-teal-600 hover:bg-teal-700 text-xs h-7">Aplicar</Button>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="flex items-center justify-between">
        {steps.map((step, idx) => {
          const Icon = step.icon;
          return (
            <React.Fragment key={step.key}>
              <div className="flex flex-col items-center">
                <div className={`w-12 h-12 sm:w-16 sm:h-16 rounded-xl flex items-center justify-center ${idx === steps.length - 1 ? 'bg-emerald-500/20' : 'bg-slate-800'}`}>
                  <Icon className={`w-5 h-5 sm:w-6 sm:h-6 ${idx === steps.length - 1 ? 'text-emerald-400' : 'text-slate-400'}`} />
                </div>
                <span className="text-base sm:text-xl font-bold text-white mt-2">{step.value.toLocaleString()}</span>
                <span className="text-xs text-slate-400">{step.label}</span>
              </div>
              {idx < steps.length - 1 && (
                <div className="flex flex-col items-center px-1 sm:px-2">
                  <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5 text-slate-600" />
                  <span className="text-xs text-slate-500 mt-1">{rates[idx]}%</span>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
      {totals && (
        <div className="mt-4 pt-4 border-t border-slate-700 flex justify-between text-sm flex-wrap gap-2">
          <span className="text-slate-400">Total Leads: <span className="text-white font-medium">{totals.leads}</span></span>
          <span className="text-slate-400">Monto: <span className="text-emerald-400 font-medium">${(totals.monto_cargas || 0).toLocaleString()}</span></span>
          <span className="text-slate-400">Promedio: <span className="text-white font-medium">${(totals.promedio_carga || 0).toLocaleString()}</span></span>
        </div>
      )}
    </div>
  );
};

// ─── Ad Performance Dashboard ──────────────────────────────────────

// ─── Lines Manager (admin only) ────────────────────────────────────

const WaRegisterBlock = ({ lineId, phoneNumber, alreadyRegisteredAt, wabaIdFromForm, tokenFromForm }) => {
  const [busy, setBusy] = useState(false);
  const [method, setMethod] = useState('SMS');
  const [otp, setOtp] = useState('');
  const [pin, setPin] = useState('');
  const [showRegister, setShowRegister] = useState(false);
  const [subscribing, setSubscribing] = useState(false);

  const subscribeApp = async () => {
    if (!wabaIdFromForm) {
      toast.error('Pegá el WABA ID en el campo de arriba antes de suscribir', { duration: 6000 });
      return;
    }
    setSubscribing(true);
    try {
      const { data } = await api.post(`/crm/lines/${lineId}/wa-subscribe-app`, {
        waba_id: wabaIdFromForm,
        token: tokenFromForm,
      });
      const count = (data?.subscribed_apps || []).length;
      toast.success(`✅ WABA suscrita a la App. ${count} app${count === 1 ? '' : 's'} suscrita${count === 1 ? '' : 's'}. Ya deberían empezar a llegar webhooks.`, { duration: 10000, style: { maxWidth: '520px' } });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error suscribiendo WABA', { duration: 15000, style: { maxWidth: '520px' } });
    } finally { setSubscribing(false); }
  };

  const requestCode = async () => {
    setBusy(true);
    try {
      await api.post(`/crm/lines/${lineId}/wa-request-code`, { code_method: method, language: 'es' });
      toast.success(`Código ${method} enviado a ${phoneNumber}. Revisá el celular.`, { duration: 8000 });
      setShowRegister(true);
    } catch (e) {
      const detail = e?.response?.data?.detail || 'Error pidiendo código';
      toast.error(detail, { duration: 12000, style: { maxWidth: '520px' } });
      // Si Meta dijo "ya verificado", igual mostrar el register form (sin OTP)
      if (detail.includes('ya está verificado') || detail.includes('136025')) setShowRegister(true);
    } finally { setBusy(false); }
  };

  const doRegister = async () => {
    if (!/^\d{6}$/.test(pin)) { toast.error('El PIN debe ser de 6 dígitos numéricos'); return; }
    setBusy(true);
    try {
      const body = { pin };
      if (otp.trim()) body.code = otp.trim();
      await api.post(`/crm/lines/${lineId}/wa-register`, body);
      toast.success('✅ Número registrado. En 1-2 minutos pasa a "Conectado" en Meta y queda listo para recibir mensajes.', { duration: 12000, style: { maxWidth: '520px' } });
      setShowRegister(false);
      setOtp(''); setPin('');
    } catch (e) {
      const detail = e?.response?.data?.detail || 'Error registrando';
      toast.error(detail, { duration: 15000, style: { maxWidth: '520px' } });
    } finally { setBusy(false); }
  };

  return (
    <div className="pt-2 border-t border-slate-600">
      <p className="text-xs text-slate-400 mb-2">🔓 Registro del número en WhatsApp Cloud API</p>

      {/* Subscribe WABA to App — must run for webhooks to be delivered */}
      <div className="mb-3 rounded border border-purple-700/40 bg-purple-900/15 p-2">
        <p className="text-[11px] text-slate-300 leading-snug mb-2">
          🛰️ <strong>Suscribir WABA a la App de Meta</strong> — paso silencioso que Meta NO hace solo cuando agregás un número. Si los mensajes "llegan al teléfono" pero no aparecen en el CRM, casi siempre es esto.
        </p>
        <Button type="button" size="sm" onClick={subscribeApp} disabled={subscribing} className="bg-purple-600 hover:bg-purple-500 text-white text-xs h-8 w-full" data-testid="wa-subscribe-app-btn">
          {subscribing ? 'Suscribiendo...' : '🛰️ Suscribir WABA a la App (activar webhooks)'}
        </Button>
      </div>

      {alreadyRegisteredAt ? (
        <div className="text-[11px] text-emerald-400 bg-emerald-900/15 border border-emerald-700/30 rounded p-2 mb-2">
          ✅ Registrado el {new Date(alreadyRegisteredAt).toLocaleDateString('es-AR')}. Si Meta lo muestra "Pendiente", podés volver a registrarlo abajo.
        </div>
      ) : (
        <p className="text-[11px] text-amber-400 bg-amber-900/15 border border-amber-700/30 rounded p-2 mb-2">
          ⚠️ Si en Meta aparece "Pendiente" pese a haber verificado el número, usá los botones de abajo.
        </p>
      )}

      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <select value={method} onChange={e => setMethod(e.target.value)} className="bg-slate-700 border border-slate-600 rounded h-8 px-2 text-xs text-white">
          <option value="SMS">📩 SMS</option>
          <option value="VOICE">📞 Llamada</option>
        </select>
        <Button type="button" size="sm" onClick={requestCode} disabled={busy} className="bg-blue-600 hover:bg-blue-500 text-white text-xs h-8" data-testid="wa-request-code-btn">
          1. Pedir código a {phoneNumber}
        </Button>
        <Button type="button" size="sm" onClick={() => setShowRegister(true)} disabled={busy} variant="outline" className="border-slate-600 text-slate-300 text-xs h-8" data-testid="wa-skip-otp-btn">
          Ya verificado → Registrar
        </Button>
      </div>

      {showRegister && (
        <div className="rounded border border-blue-700/40 bg-blue-900/15 p-2 space-y-2" data-testid="wa-register-form">
          <div className="grid grid-cols-2 gap-2">
            <Input
              placeholder="OTP (6 dígitos del SMS)"
              value={otp}
              onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              className="bg-slate-700 border-slate-600 text-xs font-mono"
              data-testid="wa-otp-input"
            />
            <Input
              placeholder="PIN nuevo (6 dígitos, inventalo)"
              value={pin}
              onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              className="bg-slate-700 border-slate-600 text-xs font-mono"
              data-testid="wa-pin-input"
            />
          </div>
          <p className="text-[10px] text-slate-400 leading-snug">
            ⚠️ Anotate el PIN — Meta te lo va a pedir si después querés mover el número. Si el número estaba en API y conoces el PIN viejo, usá ese y dejá el OTP vacío.
          </p>
          <Button type="button" size="sm" onClick={doRegister} disabled={busy || !pin} className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-8 w-full" data-testid="wa-register-btn">
            2. Registrar número en API
          </Button>
        </div>
      )}
    </div>
  );
};

const LinesManager = ({ lines, onRefresh, onSelectLine, selectedLineId }) => {
  const [showCreate, setShowCreate] = useState(false);
  const [editingLine, setEditingLine] = useState(null);
  const [saving, setSaving] = useState(false);
  const [numberPicker, setNumberPicker] = useState({ open: false, numbers: [] });
  const emptyForm = {
    name: '', line_type: 'publi', whatsapp_number: '',
    whatsapp_token: '', phone_number_id: '', verify_token: '',
    whatsapp_business_account_id: '',
    webhook_parent_line_id: '',
    meta_access_token: '', meta_pixel_id: '', description: ''
  };
  const [form, setForm] = useState(emptyForm);

  const resetForm = () => setForm(emptyForm);

  const editLine = (line) => {
    setForm({
      name: line.name || '', line_type: line.line_type || 'publi',
      whatsapp_number: line.whatsapp_number || '',
      whatsapp_token: line.whatsapp_token || '',
      phone_number_id: line.phone_number_id || '',
      verify_token: line.verify_token || '',
      whatsapp_business_account_id: line.whatsapp_business_account_id || '',
      webhook_parent_line_id: line.webhook_parent_line_id || '',
      meta_access_token: line.meta_access_token || '',
      meta_pixel_id: line.meta_pixel_id || '',
      description: line.description || '',
    });
    setEditingLine(line);
    setShowCreate(true);
  };

  const saveLine = async (e) => {
    e.preventDefault();
    if (!form.name || !form.whatsapp_number) { toast.error('Nombre y número son requeridos'); return; }
    setSaving(true);
    try {
      // Normalize: empty parent id → null (so backend doesn't try to lookup '')
      const payload = {
        ...form,
        webhook_parent_line_id: form.webhook_parent_line_id || null,
      };
      if (editingLine) { await api.put(`/crm/lines/${editingLine.id}`, payload); toast.success('Línea actualizada'); }
      else { await api.post('/crm/lines', payload); toast.success('Línea creada'); }
      setShowCreate(false); setEditingLine(null); resetForm(); onRefresh();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Error desconocido';
      toast.error(`Error guardando línea: ${detail}`, { duration: 8000, style: { maxWidth: '480px' } });
      console.error('saveLine error', err);
    }
    finally { setSaving(false); }
  };

  const deleteLine = async (id) => {
    if (!window.confirm('¿Eliminar esta línea?')) return;
    try { await api.delete(`/crm/lines/${id}`); toast.success('Línea eliminada'); onRefresh(); }
    catch { toast.error('Error eliminando línea'); }
  };

  // Returns the webhook URL the user must paste in Meta for a given line.
  // If the line shares webhook with a parent, returns the parent's URL.
  const webhookUrlFor = (line) => {
    const ownerId = line?.webhook_parent_line_id || line?.id;
    return `${BACKEND_URL}/api/crm/webhook/${ownerId}`;
  };

  const copyWebhook = (line) => {
    navigator.clipboard.writeText(webhookUrlFor(line));
    toast.success('URL copiada');
  };

  return (
    <div className="bg-slate-900/50 rounded-xl border border-slate-800 overflow-hidden">
      <div className="p-4 border-b border-slate-700 flex items-center justify-between">
        <h3 className="font-medium text-white flex items-center gap-2">
          <Smartphone className="w-4 h-4 text-blue-400" /> Líneas de WhatsApp
        </h3>
        <Button size="sm" onClick={() => { resetForm(); setEditingLine(null); setShowCreate(!showCreate); }} className="bg-blue-600 hover:bg-blue-700">
          <Plus className="w-4 h-4" />
        </Button>
      </div>

      {showCreate && (
        <form onSubmit={saveLine} className="p-4 border-b border-slate-700 bg-slate-800/50 space-y-3">
          <h4 className="text-sm font-medium text-white mb-2">{editingLine ? 'Editar Línea' : 'Nueva Línea'}</h4>
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="Nombre de la línea" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="bg-slate-700 border-slate-600" />
            <select value={form.line_type} onChange={e => setForm({ ...form, line_type: e.target.value })} className="bg-slate-700 border border-slate-600 rounded-md px-3 text-white text-sm">
              <option value="publi">Publicidad</option>
              <option value="principal">Principal</option>
              <option value="spam">Spam</option>
            </select>
          </div>
          <div className="pt-2 border-t border-slate-600">
            <p className="text-xs text-slate-400 mb-2">📱 WhatsApp Business API</p>

            {/* Webhook sharing — multi-line con UNA sola Meta App */}
            {(() => {
              const eligibleParents = lines.filter(l => l.id !== editingLine?.id && l.verify_token && l.phone_number_id);
              const parent = form.webhook_parent_line_id ? lines.find(l => l.id === form.webhook_parent_line_id) : null;
              const apiBase = process.env.REACT_APP_BACKEND_URL || '';
              const webhookOwnerId = parent?.id || editingLine?.id;
              const webhookUrl = webhookOwnerId ? `${apiBase}/api/crm/webhook/${webhookOwnerId}` : '';
              return (
                <div className="mb-3 rounded border border-blue-700/40 bg-blue-900/15 p-2">
                  <label className="text-[11px] text-slate-300 font-medium block mb-1">
                    🔗 Compartir webhook con otra línea (opcional)
                  </label>
                  <select
                    value={form.webhook_parent_line_id || ''}
                    onChange={e => setForm({ ...form, webhook_parent_line_id: e.target.value })}
                    className="w-full bg-slate-700 border border-slate-600 rounded h-8 px-2 text-xs text-white"
                    data-testid="line-webhook-parent-select"
                  >
                    <option value="">— Webhook propio (línea nueva en Meta) —</option>
                    {eligibleParents.map(l => (
                      <option key={l.id} value={l.id}>Usar webhook de: {l.name}</option>
                    ))}
                  </select>
                  {parent && (
                    <div className="mt-2 space-y-1 text-[11px] text-slate-400 leading-snug">
                      <p>✅ Esta línea va a heredar el <strong>Verify Token</strong>, el <strong>WhatsApp Token</strong> y el <strong>WABA ID</strong> de <span className="text-blue-300">{parent.name}</span>.</p>
                      <p>📌 En Meta Business Manager, agregá este número al mismo <strong>App</strong> que tiene <span className="text-blue-300">{parent.name}</span> y pegá su <strong>Phone Number ID</strong> abajo.</p>
                      <div className="mt-1.5 flex items-center gap-1">
                        <span className="text-slate-500 shrink-0">Webhook URL:</span>
                        <code className="flex-1 px-1.5 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[10px] truncate">{webhookUrl}</code>
                        <button
                          type="button"
                          onClick={() => { navigator.clipboard?.writeText(webhookUrl); toast.success('URL copiada'); }}
                          className="text-blue-400 hover:text-blue-300 px-1"
                          title="Copiar URL"
                          data-testid="copy-webhook-url-btn"
                        >📋</button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            <Input placeholder="Número WhatsApp (ej: 5491155554444)" value={form.whatsapp_number} onChange={e => setForm({ ...form, whatsapp_number: e.target.value })} className="bg-slate-700 border-slate-600 mb-2" />
            <div className="grid grid-cols-2 gap-2">
              <Input
                placeholder={form.webhook_parent_line_id ? 'Heredado del padre' : 'WhatsApp Token'}
                value={form.whatsapp_token}
                onChange={e => setForm({ ...form, whatsapp_token: e.target.value })}
                className="bg-slate-700 border-slate-600 text-xs disabled:opacity-50"
                disabled={!!form.webhook_parent_line_id}
              />
              <div className="relative">
                <Input placeholder="Phone Number ID (único por número)" value={form.phone_number_id} onChange={e => setForm({ ...form, phone_number_id: e.target.value })} className="bg-slate-700 border-slate-600 text-xs pr-8" />
                {form.webhook_parent_line_id && (
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const { data } = await api.post('/crm/wa-list-numbers', { parent_line_id: form.webhook_parent_line_id });
                        const nums = data?.numbers || [];
                        if (nums.length === 0) { toast.error('La WABA no tiene números registrados'); return; }
                        setNumberPicker({ open: true, numbers: nums });
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || 'Error listando números');
                      }
                    }}
                    className="absolute right-1 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-[10px]"
                    title="Listar números de la WABA padre"
                    data-testid="line-list-numbers-btn"
                  >📞</button>
                )}
              </div>
            </div>
            <Input
              placeholder={form.webhook_parent_line_id ? 'Verify Token heredado del padre' : 'Verify Token (webhook)'}
              value={form.verify_token}
              onChange={e => setForm({ ...form, verify_token: e.target.value })}
              className="bg-slate-700 border-slate-600 text-xs mt-2 disabled:opacity-50"
              disabled={!!form.webhook_parent_line_id}
            />
            <div className="mt-2">
              <Input
                data-testid="line-waba-id-input"
                placeholder={form.webhook_parent_line_id ? 'WABA ID del nuevo número (puede ser distinto al del padre)' : 'WhatsApp Business Account ID (WABA ID) — requerido para Broadcasts'}
                value={form.whatsapp_business_account_id}
                onChange={e => setForm({ ...form, whatsapp_business_account_id: e.target.value })}
                className="bg-slate-700 border-slate-600 text-xs"
              />
              <p className="text-[10px] text-slate-500 mt-1 leading-snug">
                💡 Obtenelo en <a href="https://business.facebook.com/wa/manage/home/" target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">Meta Business Manager → Cuentas de WhatsApp → Configuración</a>. Aparece como "ID de la cuenta" (numérico, distinto al Phone Number ID). {form.webhook_parent_line_id && <span className="text-amber-400">⚠️ Si el nuevo número está en otra WABA, ponele su WABA propio acá (si dejás vacío hereda del padre).</span>}
              </p>
            </div>
          </div>

          {/* WhatsApp Cloud API — number registration */}
          {form.phone_number_id && form.whatsapp_token && (
            editingLine ? (
              <WaRegisterBlock
                lineId={editingLine.id}
                phoneNumber={form.whatsapp_number}
                alreadyRegisteredAt={editingLine.wa_registered_at}
                wabaIdFromForm={
                  form.whatsapp_business_account_id ||
                  (form.webhook_parent_line_id
                    ? (lines.find(l => l.id === form.webhook_parent_line_id)?.whatsapp_business_account_id || '')
                    : '')
                }
                tokenFromForm={form.whatsapp_token}
              />
            ) : (
              <div className="pt-2 border-t border-slate-600">
                <p className="text-xs text-slate-400 mb-2">🔓 Registro del número en WhatsApp Cloud API</p>
                <div className="rounded border border-blue-700/40 bg-blue-900/15 p-2.5">
                  <p className="text-[11px] text-blue-300 leading-snug">
                    💡 Primero <strong>guardá la línea</strong> con "Crear". Después abrila para editar y vas a ver los botones para:
                    <br />• 🛰️ Suscribir WABA a la App de Meta
                    <br />• 📩 Pedir código y registrar el número
                  </p>
                </div>
              </div>
            )
          )}
          <div className="pt-2 border-t border-slate-600">
            <p className="text-xs text-slate-400 mb-2">📊 Meta Pixel</p>
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="Meta Access Token" value={form.meta_access_token} onChange={e => setForm({ ...form, meta_access_token: e.target.value })} className="bg-slate-700 border-slate-600 text-xs" />
              <Input placeholder="Meta Pixel ID" value={form.meta_pixel_id} onChange={e => setForm({ ...form, meta_pixel_id: e.target.value })} className="bg-slate-700 border-slate-600 text-xs" />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => { setShowCreate(false); setEditingLine(null); resetForm(); }} className="border-slate-600">Cancelar</Button>
            <Button type="submit" size="sm" disabled={saving} className="bg-emerald-600 hover:bg-emerald-700">{saving ? 'Guardando...' : editingLine ? 'Actualizar' : 'Crear Línea'}</Button>
          </div>
        </form>
      )}

      {/* Number picker modal — shows phone numbers of the parent's WABA */}
      {numberPicker.open && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setNumberPicker({ open: false, numbers: [] })}>
          <div className="bg-slate-800 border border-slate-700 rounded-lg max-w-lg w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 bg-slate-800 border-b border-slate-700 p-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">📞 Elegí el número del nuevo Phone Number ID</h3>
              <button onClick={() => setNumberPicker({ open: false, numbers: [] })} className="text-slate-400 hover:text-white"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-2 space-y-1">
              {numberPicker.numbers.map(n => {
                const verified = n.code_verification_status === 'VERIFIED';
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => {
                      setForm({
                        ...form,
                        phone_number_id: n.id,
                        whatsapp_number: form.whatsapp_number || (n.display_phone_number || '').replace(/\D/g, ''),
                      });
                      setNumberPicker({ open: false, numbers: [] });
                      toast.success(`Seleccionado: ${n.display_phone_number}`);
                    }}
                    className="w-full text-left p-2.5 rounded hover:bg-blue-500/10 border border-transparent hover:border-blue-700/40"
                    data-testid={`number-picker-option-${n.id}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-white truncate">{n.display_phone_number || '(sin número)'}</p>
                        <p className="text-[10px] text-slate-500 font-mono truncate">ID: {n.id}</p>
                        {n.verified_name && <p className="text-[10px] text-slate-400 truncate">{n.verified_name}</p>}
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${verified ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'}`}>
                          {verified ? '✅ Verificado' : '⏳ Pendiente'}
                        </span>
                        {n.quality_rating && <span className="text-[10px] text-slate-500">Q: {n.quality_rating}</span>}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="divide-y divide-slate-700 max-h-[400px] overflow-y-auto">
        <button onClick={() => onSelectLine(null)} className={`w-full p-3 text-left hover:bg-slate-800/50 transition-colors ${!selectedLineId ? 'bg-slate-800' : ''}`}>
          <span className="text-sm text-white">Todas las líneas</span>
        </button>
        {lines.map(line => {
          const typeConfig = LINE_TYPE_CONFIG[line.line_type] || LINE_TYPE_CONFIG.publi;
          const hasConfig = line.whatsapp_token && line.phone_number_id;
          const hasPixel = line.meta_access_token && line.meta_pixel_id;
          const hasWaba = !!line.whatsapp_business_account_id;
          return (
            <div key={line.id} className={`p-3 hover:bg-slate-800/50 transition-colors ${selectedLineId === line.id ? 'bg-slate-800' : ''}`}>
              <div className="flex items-center justify-between cursor-pointer" onClick={() => onSelectLine(line.id)}>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${typeConfig.color}`}>{typeConfig.label}</span>
                  <span className="text-sm text-white font-medium">{line.name}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={e => { e.stopPropagation(); editLine(line); }} className="p-1 text-slate-400 hover:text-blue-400"><Settings className="w-4 h-4" /></button>
                  <button onClick={e => { e.stopPropagation(); deleteLine(line.id); }} className="p-1 text-slate-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{line.whatsapp_number}</span>
                <span>{line.leads_count || 0} leads</span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                {hasConfig ? <span className="text-xs text-emerald-400 flex items-center gap-1"><Check className="w-3 h-3" />WA Config</span> : <span className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />Sin WA</span>}
                {hasPixel ? <span className="text-xs text-emerald-400 flex items-center gap-1"><Zap className="w-3 h-3" />Pixel</span> : <span className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />Sin Pixel</span>}
                {hasWaba ? <span data-testid={`line-waba-ok-${line.id}`} className="text-xs text-emerald-400 flex items-center gap-1"><Check className="w-3 h-3" />WABA</span> : <span data-testid={`line-waba-missing-${line.id}`} className="text-xs text-amber-400 flex items-center gap-1" title="Falta el WhatsApp Business Account ID — necesario para Broadcasts"><AlertTriangle className="w-3 h-3" />Sin WABA</span>}
              </div>
              {line.verify_token && (
                <div className="mt-2 p-2 bg-slate-700/50 rounded text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-400">
                      Webhook URL{line.webhook_parent_line_id ? ' (compartido)' : ''}:
                    </span>
                    <button onClick={e => { e.stopPropagation(); copyWebhook(line); }} className="text-blue-400 hover:text-blue-300 flex items-center gap-1"><Copy className="w-3 h-3" /> Copiar</button>
                  </div>
                  <code className="text-slate-300 break-all">{webhookUrlFor(line)}</code>
                  {line.webhook_parent_line_id && (() => {
                    const parent = lines.find(l => l.id === line.webhook_parent_line_id);
                    return (
                      <p className="text-[10px] text-blue-400 mt-1">
                        🔗 Hereda de <strong>{parent?.name || line.webhook_parent_line_id}</strong>
                      </p>
                    );
                  })()}
                  <p className="text-slate-500 mt-1">Verify Token: <code className="text-slate-300">{line.verify_token}</code></p>
                </div>
              )}
            </div>
          );
        })}
        {lines.length === 0 && <div className="p-4 text-center text-slate-500 text-sm">No hay líneas creadas</div>}
      </div>
    </div>
  );
};

// ─── Kanban (admin only) ───────────────────────────────────────────

const LeadCard = ({ lead, onClick, onDragStart }) => {
  const config = STATUS_CONFIG[lead.status] || STATUS_CONFIG.nuevo;
  const Icon = config.icon;
  const hasNewMessage = lead.has_unread_messages || lead.unread_count > 0;
  const adBadge = lead.ad_badge;
  const adColor = adBadge ? (BADGE_COLORS[adBadge.color] || BADGE_COLORS.blue) : null;
  return (
    <div draggable onDragStart={e => onDragStart(e, lead)} onClick={() => onClick(lead)}
      className={`flex-shrink-0 w-[200px] p-3 rounded-lg border ${config.color} cursor-pointer hover:scale-[1.02] transition-all group relative`}>
      {hasNewMessage && (
        <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center shadow-lg shadow-red-500/30 z-10">!</span>
      )}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <GripVertical className="w-4 h-4 opacity-50 group-hover:opacity-100 cursor-grab" />
          <span className="font-medium text-white truncate max-w-[110px]">{lead.name}</span>
        </div>
        <Icon className="w-4 h-4 opacity-70" />
      </div>
      {adBadge && (
        <div className={`mb-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded border ${adColor.border} ${adColor.bg} max-w-full`}
          data-testid={`lead-card-ad-badge-${lead.id}`} title={adBadge.label}>
          <Megaphone className={`w-2.5 h-2.5 shrink-0 ${adColor.icon}`} />
          <span className={`text-[9px] font-semibold truncate ${adColor.text}`}>{adBadge.label}</span>
        </div>
      )}
      <div className="text-xs text-slate-400 space-y-1">
        <div className="flex items-center gap-1"><Phone className="w-3 h-3" /><span className="truncate">{lead.phone}</span></div>
        {lead.line_name && <div className="flex items-center gap-1"><Smartphone className="w-3 h-3" /><span className="truncate">{lead.line_name}</span></div>}
        {lead.ad_source && !adBadge && <div className="flex items-center gap-1 text-purple-400"><Target className="w-3 h-3" /><span className="truncate text-[10px]">{lead.ad_source}</span></div>}
        {lead.charge_amount > 0 && <div className="flex items-center gap-1 text-emerald-400"><DollarSign className="w-3 h-3" />${lead.charge_amount.toLocaleString()}</div>}
        {lead.messages_count > 0 && (
          <div className={`flex items-center gap-1 ${hasNewMessage ? 'text-red-400 font-medium' : ''}`}>
            <MessageCircle className="w-3 h-3" />{lead.messages_count} msgs
            {hasNewMessage && <span className="text-red-400">● nuevo</span>}
          </div>
        )}
        {Array.isArray(lead.tag_details) && lead.tag_details.length > 0 && (
          <div className="pt-0.5"><TagChipList tags={lead.tag_details} max={3} size="xs" /></div>
        )}
      </div>
    </div>
  );
};

const KanbanColumn = ({ status, leads, onLeadClick, onDragStart, onDrop, onDragOver }) => {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;
  const columnLeads = leads
    .filter(l => l.status === status)
    .sort((a, b) => new Date(b.last_interaction || b.created_at || '') - new Date(a.last_interaction || a.created_at || ''));
  return (
    <div className={`rounded-xl ${config.bgColumn} border border-slate-700/50`} onDragOver={onDragOver} onDrop={e => onDrop(e, status)}>
      <div className="px-4 py-2.5 border-b border-slate-700/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${config.color.split(' ')[1]}`} />
          <span className="font-medium text-white text-sm">{config.label}</span>
        </div>
        <span className="text-xs text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">{columnLeads.length}</span>
      </div>
      <div className="p-3 flex gap-3 overflow-x-auto min-h-[120px] items-start">
        {columnLeads.map(lead => <LeadCard key={lead.id} lead={lead} onClick={onLeadClick} onDragStart={onDragStart} />)}
        {columnLeads.length === 0 && <div className="flex-1 text-center text-slate-500 text-xs py-8">Sin leads</div>}
      </div>
    </div>
  );
};

// ─── Admin Lead Modal (Kanban click → chat) ───────────────────────

const AdminLeadModal = ({ lead, onClose, onUpdate }) => {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center sm:p-4">
      <div className="bg-slate-900 w-full h-full sm:rounded-xl sm:max-w-2xl sm:h-[85vh] flex flex-col sm:border sm:border-slate-700 overflow-hidden">
        <ChatPanel
          lead={lead}
          onStatusChange={async (leadId, status, conversionValue) => {
            try {
              await api.post(`/crm/leads/${leadId}/classify`, {
                status, send_to_meta: true,
                conversion_value: conversionValue,
                currency: 'USD'
              });
              toast.success(`✅ ${STATUS_CONFIG[status]?.label}`);
              onUpdate();
              onClose();
            } catch { toast.error('Error clasificando lead'); }
          }}
          onClose={onClose}
          showCloseButton={true}
          onLeadDeleted={() => { onUpdate(); onClose(); }}
        />
      </div>
    </div>
  );
};

// ─── Export Contacts Modal ────────────────────────────────────────

const ContactsExportModal = ({ onClose }) => {
  const [statusFilter, setStatusFilter] = useState('all');
  const [downloading, setDownloading] = useState(false);

  const OPTIONS = [
    { value: 'all',       label: 'Todos los contactos',         hint: 'Toda la base sin filtrar' },
    { value: 'valido',    label: 'Solo Válidos',                hint: 'Los que ya cargaron alguna vez' },
    { value: 'consultas', label: 'Solo Consultas',              hint: 'Preguntaron pero no cargaron — ideal para reactivación' },
    { value: 'nuevo',     label: 'Solo Nuevos (sin clasificar)', hint: 'Leads sin estado todavía' },
  ];

  const download = async () => {
    setDownloading(true);
    try {
      const url = `/crm/contacts/history?fmt=csv&status=${encodeURIComponent(statusFilter)}`;
      const res = await api.get(url, { responseType: 'blob' });
      const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: 'text/csv;charset=utf-8' }));
      const a = document.createElement('a');
      const suffix = statusFilter === 'all' ? 'todos' : statusFilter;
      a.href = blobUrl;
      a.download = `contactos-${suffix}-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(blobUrl);
      toast.success('Contactos exportados');
      onClose();
    } catch {
      toast.error('Error exportando contactos');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose} data-testid="contacts-export-modal-backdrop">
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5"
        onClick={e => e.stopPropagation()} data-testid="contacts-export-modal">
        <div className="flex items-center justify-between mb-1">
          <p className="text-base font-semibold text-white">Descargar contactos</p>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-slate-800 text-slate-400"
            data-testid="contacts-export-close-btn">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-slate-400 mb-4">Elegí qué segmento querés bajar como CSV.</p>

        <div className="space-y-2">
          {OPTIONS.map(opt => (
            <label key={opt.value}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                statusFilter === opt.value
                  ? 'border-emerald-500/50 bg-emerald-500/10'
                  : 'border-slate-700 bg-slate-800/40 hover:bg-slate-800/80'
              }`}
              data-testid={`contacts-export-opt-${opt.value}`}>
              <input
                type="radio"
                name="contacts-export-status"
                value={opt.value}
                checked={statusFilter === opt.value}
                onChange={e => setStatusFilter(e.target.value)}
                className="mt-0.5 accent-emerald-500"
                data-testid={`contacts-export-radio-${opt.value}`}
              />
              <div className="min-w-0">
                <p className="text-sm font-medium text-white">{opt.label}</p>
                <p className="text-[11px] text-slate-400">{opt.hint}</p>
              </div>
            </label>
          ))}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}
            className="border-slate-600 text-slate-300 hover:bg-slate-800"
            data-testid="contacts-export-cancel-btn">
            Cancelar
          </Button>
          <Button onClick={download} disabled={downloading}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
            data-testid="contacts-export-download-btn">
            {downloading ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Download className="w-4 h-4 mr-1" />}
            Descargar CSV
          </Button>
        </div>
      </div>
    </div>
  );
};

// ─── Admin Lines Panel ────────────────────────────────────────────
// Vista limpia para admin: cards de líneas con mini-stats + botón "Ver
// como cajero". Cada línea muestra cuántos leads tiene en cada estado
// para que el admin pueda priorizar dónde meterse.

const LineNotesField = ({ line, onSaved }) => {
  const [value, setValue] = useState(line?.notes || '');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const debounceRef = useRef(null);
  const initialRef = useRef(line?.notes || '');

  // Si el padre refresca y la nota cambió por afuera, re-sincronizamos
  useEffect(() => {
    if ((line?.notes || '') !== initialRef.current) {
      initialRef.current = line?.notes || '';
      setValue(line?.notes || '');
    }
  }, [line?.notes]);

  const onChange = (e) => {
    const next = e.target.value;
    setValue(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      if (next === initialRef.current) return;
      setSaving(true);
      try {
        await api.put(`/crm/lines/${line.id}`, { notes: next });
        initialRef.current = next;
        setSavedAt(Date.now());
        onSaved?.();
      } catch {
        toast.error('No se guardaron las observaciones');
      } finally {
        setSaving(false);
      }
    }, 900);
  };

  // Indicador visual: "Guardando..." mientras tipea, "Guardado ✓" 2s después
  const showSavedBadge = savedAt && Date.now() - savedAt < 2500;

  return (
    <div className="mt-2.5" data-testid={`line-notes-${line.id}`}>
      <div className="flex items-center justify-between mb-1">
        <label className="text-[10px] uppercase tracking-wide text-slate-500">
          Observaciones
        </label>
        {saving ? (
          <span className="text-[10px] text-slate-500 italic">guardando…</span>
        ) : showSavedBadge ? (
          <span className="text-[10px] text-emerald-400">guardado ✓</span>
        ) : null}
      </div>
      <textarea
        value={value}
        onChange={onChange}
        rows={2}
        placeholder="Ej: número de Naranjax, asignada a Juan, usa CBU del banco X..."
        className="w-full text-xs bg-slate-800/60 border border-slate-700 rounded px-2 py-1.5 text-slate-200 placeholder:text-slate-600 resize-none focus:outline-none focus:border-blue-500/60"
        data-testid={`line-notes-input-${line.id}`}
      />
    </div>
  );
};


const ReceiptOCRToggle = ({ line, onSaved }) => {
  const [enabled, setEnabled] = React.useState(!!line.receipt_ocr_enabled);
  const [saving, setSaving] = React.useState(false);
  React.useEffect(() => { setEnabled(!!line.receipt_ocr_enabled); }, [line.receipt_ocr_enabled]);

  const toggle = async () => {
    const next = !enabled;
    setEnabled(next);
    setSaving(true);
    try {
      await api.put(`/crm/lines/${line.id}`, { receipt_ocr_enabled: next });
      toast.success(next ? 'OCR de comprobantes activado 🤖' : 'OCR desactivado');
      onSaved?.();
    } catch (err) {
      setEnabled(!next);
      toast.error(err?.response?.data?.detail || 'Error guardando');
    } finally { setSaving(false); }
  };

  return (
    <div className="mt-2.5" data-testid={`line-ocr-${line.id}`}>
      <label className="flex items-start gap-2 cursor-pointer group">
        <input
          type="checkbox"
          checked={enabled}
          disabled={saving}
          onChange={toggle}
          className="mt-0.5 accent-emerald-500"
          data-testid={`line-ocr-toggle-${line.id}`}
        />
        <span className="text-[11px] leading-tight">
          <span className={`font-semibold ${enabled ? 'text-emerald-300' : 'text-slate-300'}`}>
            🤖 OCR de comprobantes {enabled && '(activo)'}
          </span>
          <span className="block text-[10px] text-slate-500">
            Claude lee las imágenes que envían los clientes y las cruza con MP
          </span>
        </span>
      </label>
    </div>
  );
};


const AdminLinesPanel = ({ lines, leads, onSelectLine, onRefresh, onBroadcast }) => {
  const [showLinesManager, setShowLinesManager] = useState(false);
  // Computamos stats por línea sobre los leads ya cargados (los mismos que
  // usa el CRM cuando admin entra normal).
  const statsByLine = React.useMemo(() => {
    const map = {};
    for (const l of leads) {
      const lid = l.line_id;
      if (!lid) continue;
      if (!map[lid]) map[lid] = { total: 0, nuevo: 0, consultas: 0, valido: 0, no_responde: 0, unread: 0, today: 0 };
      map[lid].total += 1;
      const status = l.status || 'nuevo';
      if (map[lid][status] !== undefined) map[lid][status] += 1;
      if (l.unread_count > 0 || l.has_unread_messages) map[lid].unread += 1;
      const ci = l.created_at;
      if (ci && new Date(ci).toDateString() === new Date().toDateString()) {
        map[lid].today += 1;
      }
    }
    return map;
  }, [leads]);

  return (
    <div className="min-h-screen bg-slate-950 text-white" data-testid="admin-lines-panel">
      <div className="max-w-6xl mx-auto p-4 sm:p-6">
        {/* Header */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
              <Users className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Administración de líneas</h1>
              <p className="text-xs text-slate-400">Vista admin · entrá a cualquier línea para operarla como cajero</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={() => setShowLinesManager(v => !v)} variant="outline"
              className={`border-emerald-500/40 ${showLinesManager ? 'bg-emerald-500/20 text-emerald-200' : 'text-emerald-300 bg-emerald-500/10'} hover:bg-emerald-500/20`}
              data-testid="admin-panel-toggle-lines-manager">
              <Settings className="w-4 h-4 mr-2" /> {showLinesManager ? 'Ocultar gestor' : 'Gestionar líneas'}
            </Button>
            <Button onClick={onBroadcast} variant="outline"
              className="border-purple-500/40 text-purple-300 bg-purple-500/10 hover:bg-purple-500/20"
              data-testid="admin-panel-broadcast-btn">
              <Radio className="w-4 h-4 mr-2" /> Envío masivo
            </Button>
            <Button onClick={onRefresh} variant="outline" className="border-slate-600"
              data-testid="admin-panel-refresh-btn">
              <RefreshCw className="w-4 h-4 mr-2" /> Actualizar
            </Button>
          </div>
        </div>

        {/* Gestor de líneas plegable: crear/editar/eliminar líneas */}
        {showLinesManager && (
          <div className="mb-5">
            <LinesManager lines={lines} onRefresh={onRefresh} onSelectLine={() => {}} selectedLineId={null} />
          </div>
        )}

        {/* Líneas en grid */}
        {lines.length === 0 ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-8 text-center">
            <AlertCircle className="w-8 h-8 text-amber-400 mx-auto mb-2 opacity-60" />
            <p className="text-sm font-medium text-amber-200">No hay líneas configuradas</p>
            <p className="text-xs text-slate-400 mt-1">Configurá líneas WhatsApp desde el gestor de líneas para empezar.</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {lines.map(line => {
              const s = statsByLine[line.id] || { total: 0, nuevo: 0, consultas: 0, valido: 0, no_responde: 0, unread: 0, today: 0 };
              return (
                <div key={line.id}
                  className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 hover:border-slate-700 transition-colors"
                  data-testid={`admin-line-card-${line.id}`}>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate">{line.name}</p>
                      <p className="text-[11px] text-slate-500 font-mono truncate">{line.whatsapp_number}</p>
                    </div>
                    {s.unread > 0 && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 shrink-0"
                        title="Conversaciones con mensajes sin leer">
                        {s.unread} sin leer
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-2 mb-3 text-center">
                    <div className="rounded bg-slate-800/50 p-2">
                      <p className="text-[10px] text-slate-500 uppercase">Hoy</p>
                      <p className="text-lg font-bold text-emerald-300">{s.today}</p>
                    </div>
                    <div className="rounded bg-slate-800/50 p-2">
                      <p className="text-[10px] text-slate-500 uppercase">Nuevos</p>
                      <p className="text-lg font-bold text-blue-300">{s.nuevo}</p>
                    </div>
                    <div className="rounded bg-slate-800/50 p-2">
                      <p className="text-[10px] text-slate-500 uppercase">Total</p>
                      <p className="text-lg font-bold text-white">{s.total}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-3">
                    {s.consultas > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">Consultas: {s.consultas}</span>}
                    {s.valido > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">Válidos: {s.valido}</span>}
                    {s.no_responde > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-300">No responde: {s.no_responde}</span>}
                  </div>
                  <Button onClick={() => onSelectLine(line.id)} size="sm"
                    className="w-full bg-blue-600 hover:bg-blue-500 text-white"
                    data-testid={`admin-view-as-cajero-${line.id}`}>
                    Ver como cajero →
                  </Button>

                  <ReceiptOCRToggle line={line} onSaved={onRefresh} />
                  <LineNotesField line={line} onSaved={onRefresh} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};


// ─── Main Component ───────────────────────────────────────────────

export default function LeadsCRM() {
  const { darkMode, toggleTheme } = useTheme();
  const [currentUser, setCurrentUser] = useState(null);
  const [leads, setLeads] = useState([]);
  const [lines, setLines] = useState([]);
  const [funnel, setFunnel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedLead, setSelectedLead] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [draggedLead, setDraggedLead] = useState(null);
  const [selectedLineId, setSelectedLineId] = useState(null);
  const [showFunnelModal, setShowFunnelModal] = useState(false);
  const [funnelFilter, setFunnelFilter] = useState({ type: '30', startDate: null, endDate: null });

  const isAdmin = !currentUser?.role || currentUser?.role === 'admin';

  // Modo "Ver como cajero": cuando admin elige una línea desde el panel
  // limpio, entra al CRM normal pero filtrando los leads de esa línea
  // (operando como si fuera el cajero de la línea, con permisos plenos).
  const [adminViewAsLineId, setAdminViewAsLineId] = useState(null);

  // ── PWA install prompt ─────────────────────────────────────────
  const [pwaPrompt, setPwaPrompt] = useState(null);
  const [pwaInstalled, setPwaInstalled] = useState(false);
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  // ── Tags (Etiquetas) ──────────────────────────────────────────
  const [tagsModalOpen, setTagsModalOpen] = useState(false);
  const [tagFilter, setTagFilter] = useState('all'); // tag_id or 'all'
  const [tagFilterOptions, setTagFilterOptions] = useState([]);

  // ── Mercado Pago inbox ────────────────────────────────────────
  const [mpInboxOpen, setMpInboxOpen] = useState(false);
  const mpInbox = useMPInbox({ enabled: !!currentUser });

  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
    const check = () => setPwaInstalled(
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true
    );
    check();
    const listener = (e) => {
      e.preventDefault();
      setPwaPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', listener);
    window.addEventListener('appinstalled', () => { setPwaPrompt(null); setPwaInstalled(true); });
    return () => window.removeEventListener('beforeinstallprompt', listener);
  }, []);

  const installPWA = useCallback(async () => {
    if (!pwaPrompt) return;
    pwaPrompt.prompt();
    const choice = await pwaPrompt.userChoice;
    if (choice.outcome === 'accepted') setPwaInstalled(true);
    setPwaPrompt(null);
  }, [pwaPrompt]);

  // ── Notification sound ─────────────────────────────────────────
  const prevUnreadMap = useRef(new Map());
  const firstLoadDone = useRef(false);
  const audioCtxRef = useRef(null);
  const [soundEnabled, setSoundEnabled] = useState(() => {
    try { return localStorage.getItem('crm_sound_enabled') === '1'; } catch { return false; }
  });
  const [notifyEnabled, setNotifyEnabled] = useState(() => {
    try {
      return localStorage.getItem('crm_notify_enabled') === '1'
        && typeof Notification !== 'undefined'
        && Notification.permission === 'granted';
    } catch { return false; }
  });
  const leadsRef = useRef([]);

  useEffect(() => {
    try { localStorage.setItem('crm_sound_enabled', soundEnabled ? '1' : '0'); } catch { /* silent */ }
  }, [soundEnabled]);
  useEffect(() => {
    try { localStorage.setItem('crm_notify_enabled', notifyEnabled ? '1' : '0'); } catch { /* silent */ }
  }, [notifyEnabled]);

  const getAudioCtx = useCallback(() => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioCtxRef.current;
  }, []);

  const playChime = (ctx) => {
    const now = ctx.currentTime;
    const master = ctx.createGain();
    master.gain.value = 0.22;
    master.connect(ctx.destination);
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 4500;
    filter.Q.value = 0.8;
    filter.connect(master);
    const tones = [
      { freq: 523.25, gain: 0.55, decay: 1.4 },
      { freq: 783.99, gain: 0.28, decay: 1.2 },
      { freq: 1046.5, gain: 0.35, decay: 1.0 },
    ];
    tones.forEach(({ freq, gain, decay }) => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      osc.connect(g);
      g.connect(filter);
      g.gain.setValueAtTime(0, now);
      g.gain.linearRampToValueAtTime(gain, now + 0.008);
      g.gain.exponentialRampToValueAtTime(0.0001, now + decay);
      osc.start(now);
      osc.stop(now + decay + 0.05);
    });
  };

  const enableSound = useCallback(() => {
    try {
      const ctx = getAudioCtx();
      ctx.resume().then(() => {
        setSoundEnabled(true);
        playChime(ctx);
      });
    } catch { /* silent */ }
  }, [getAudioCtx]);

  const playNotificationSound = useCallback(() => {
    if (!soundEnabled) return;
    try {
      const ctx = getAudioCtx();
      if (ctx.state === 'suspended') {
        ctx.resume().then(() => playChime(ctx)).catch(() => {});
      } else {
        playChime(ctx);
      }
    } catch { /* silent */ }
  }, [soundEnabled, getAudioCtx]);

  // ── Browser push notifications ────────────────────────────────
  const urlBase64ToUint8Array = (base64String) => {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = window.atob(base64);
    const output = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) output[i] = raw.charCodeAt(i);
    return output;
  };

  const registerServiceWorkerAndSubscribe = useCallback(async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      throw new Error('Tu navegador no soporta Web Push');
    }
    // 1. Register SW at root scope
    let reg;
    try {
      reg = await navigator.serviceWorker.register('/sw.js');
    } catch (e) {
      throw new Error(`No se pudo registrar el Service Worker: ${e.message}`);
    }
    await navigator.serviceWorker.ready;
    // 2. Get VAPID key from backend
    let vk;
    try {
      const res = await api.get('/push/vapid-public-key');
      vk = res.data;
    } catch (e) {
      throw new Error(`No se pudo obtener la VAPID public key del backend: ${e?.response?.status || e.message}`);
    }
    if (!vk?.public_key) throw new Error('Backend no devolvió VAPID public_key');
    const appServerKey = urlBase64ToUint8Array(vk.public_key);
    // 3. Subscribe (or get existing subscription)
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      try {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: appServerKey,
        });
      } catch (e) {
        // Android Chrome most common cause: Google Play Services not signed in
        throw new Error(`PushManager.subscribe falló: ${e.message}. Asegurate de estar logueado en Google (Ajustes → Cuentas).`);
      }
    }
    // 4. Send subscription to backend
    const subJson = sub.toJSON();
    try {
      await api.post('/push/subscribe', {
        endpoint: subJson.endpoint,
        keys: subJson.keys,
        user_agent: navigator.userAgent,
      });
    } catch (e) {
      throw new Error(`Backend rechazó la suscripción: ${e?.response?.status || e.message}`);
    }
    return sub;
  }, []);

  const enableNotify = useCallback(async () => {
    try {
      if (typeof Notification === 'undefined') {
        toast.error('Tu navegador no soporta notificaciones');
        return;
      }
      if (!('serviceWorker' in navigator)) {
        toast.error('Tu navegador no soporta Service Workers (requerido en mobile)');
        return;
      }
      if (!window.isSecureContext) {
        toast.error('Las notificaciones requieren HTTPS. Abrí la app con https://');
        return;
      }
      if (Notification.permission === 'denied') {
        toast.error('Permiso denegado. Activalo en Ajustes de Android → App → Notificaciones.');
        return;
      }
      if (Notification.permission !== 'granted') {
        const res = await Notification.requestPermission();
        if (res !== 'granted') {
          toast.error(`Permiso no otorgado: ${res}`);
          return;
        }
      }
      // Register SW + subscribe to Web Push so notifications keep working
      // even if Chrome window is closed/minimized.
      try {
        await registerServiceWorkerAndSubscribe();
      } catch (e) {
        // Surface the REAL error so the cajero can see what's wrong (VAPID,
        // SW registration, backend endpoint, etc.)
        const msg = e?.message || String(e);
        console.error('Web Push subscribe failed:', e);
        toast.error(`Push Web falló: ${msg}. Te dejé las notificaciones básicas activas.`);
      }
      setNotifyEnabled(true);
      // On Android Chrome, `new Notification(...)` fired from the page is
      // rejected — you MUST call registration.showNotification. Use the SW.
      try {
        const reg = await navigator.serviceWorker.getRegistration('/sw.js');
        if (reg) {
          await reg.showNotification('CRM Leads', {
            body: 'Notificaciones activadas ✨',
            icon: '/logo.png',
            badge: '/logo.png',
            silent: true,
            tag: 'welcome',
          });
        }
      } catch (e) {
        console.warn('Preview notification failed (non-fatal):', e);
      }
    } catch (e) {
      console.error('enableNotify error:', e);
      toast.error(`Error activando notificaciones: ${e?.message || e}`);
    }
  }, [registerServiceWorkerAndSubscribe]);

  const disableNotify = useCallback(async () => {
    setNotifyEnabled(false);
    try {
      if ('serviceWorker' in navigator) {
        const reg = await navigator.serviceWorker.getRegistration('/sw.js');
        const sub = await reg?.pushManager?.getSubscription();
        if (sub) {
          const subJson = sub.toJSON();
          await api.post('/push/unsubscribe', {
            endpoint: subJson.endpoint,
            keys: subJson.keys,
          }).catch(() => {});
          await sub.unsubscribe().catch(() => {});
        }
      }
    } catch { /* silent */ }
  }, []);

  const showLeadNotification = useCallback((lead) => {
    try {
      if (!notifyEnabled || typeof Notification === 'undefined') return;
      if (Notification.permission !== 'granted') return;
      if (document.visibilityState === 'visible' && document.hasFocus()) return;
      const title = lead.name || lead.phone || 'Nuevo mensaje';
      const bodyParts = [];
      if (lead.line_name) bodyParts.push(`📱 ${lead.line_name}`);
      if (lead.unread_count > 1) bodyParts.push(`${lead.unread_count} mensajes sin leer`);
      else bodyParts.push('Nuevo mensaje');
      if (lead.ad_badge?.label) bodyParts.push(`📢 ${lead.ad_badge.label}`);
      const n = new Notification(title, {
        body: bodyParts.join(' · '),
        icon: '/logo.png',
        badge: '/logo.png',
        tag: `lead-${lead.id}`,
        renotify: true,
        silent: true,
      });
      n.onclick = () => {
        try {
          window.focus();
          const fresh = leadsRef.current.find(l => l.id === lead.id) || lead;
          setSelectedLead(fresh);
          n.close();
        } catch { /* silent */ }
      };
      setTimeout(() => { try { n.close(); } catch {} }, 10000);
    } catch { /* silent */ }
  }, [notifyEnabled]);

  useEffect(() => {
    api.get('/auth/me').then(({ data }) => setCurrentUser(data)).catch(() => {});
  }, []);

  const loadLeads = useCallback(async () => {
    try {
      const params = { limit: 500 };
      if (selectedLineId) params.line_id = selectedLineId;
      const { data } = await api.get('/crm/leads', { params });
      let list = data.leads || [];
      list.sort((a, b) => new Date(b.last_interaction || b.created_at || '') - new Date(a.last_interaction || a.created_at || ''));
      const currentUnreadMap = new Map();
      const triggeredLeads = [];
      list.forEach(l => {
        const count = Number(l.unread_count || 0);
        // Sólo consideramos "unread" cuando hay count real > 0. Antes usábamos
        // also `has_unread_messages` como respaldo, pero generaba notificaciones
        // fantasma cuando el backend devolvía count=0 con el flag aún true
        // (race-condition entre marcar como leído y refresco del flag).
        if (count > 0) {
          currentUnreadMap.set(l.id, count);
          const wasInMap = prevUnreadMap.current.has(l.id);
          const prevCount = prevUnreadMap.current.get(l.id) || 0;
          // Disparar SOLO cuando:
          // - El lead no estaba en el map previo (nuevo unread), o
          // - El contador subió (llegó un mensaje nuevo encima de los previos).
          if (!wasInMap || count > prevCount) {
            triggeredLeads.push(l);
          }
        }
      });
      if (triggeredLeads.length > 0 && firstLoadDone.current) {
        playNotificationSound();
        triggeredLeads.slice(0, 3).forEach(lead => showLeadNotification(lead));
      }
      prevUnreadMap.current = currentUnreadMap;
      firstLoadDone.current = true;
      leadsRef.current = list;
      try {
        const totalUnread = list.reduce((acc, l) => acc + (l.unread_count || 0), 0);
        document.title = totalUnread > 0 ? `(${totalUnread}) CRM Leads` : 'CRM Leads';
      } catch { /* silent */ }
      setLeads(list);
    } catch { toast.error('Error cargando leads'); }
    finally { setLoading(false); }
  }, [selectedLineId, playNotificationSound, showLeadNotification]);

  const loadLines = useCallback(async () => {
    try { const { data } = await api.get('/crm/lines'); setLines(data || []); }
    catch { /* silent */ }
  }, []);

  const loadFunnel = useCallback(async () => {
    try {
      const params = {};
      if (selectedLineId) params.line_id = selectedLineId;
      if (funnelFilter.type === 'custom' && funnelFilter.startDate && funnelFilter.endDate) {
        params.start_date = funnelFilter.startDate;
        params.end_date = funnelFilter.endDate;
      } else if (['diario', 'ayer', 'ultimos_10', 'semanal', 'mensual', 'mes_anterior'].includes(funnelFilter.type)) {
        params.filter_type = funnelFilter.type;
      } else {
        params.days = parseInt(funnelFilter.type) || 30;
      }
      const { data } = await api.get('/crm/funnel/stats', { params });
      setFunnel(data);
    } catch { /* silent */ }
  }, [selectedLineId, funnelFilter]);

  const handleFunnelFilterChange = (type, startDate, endDate) => {
    setFunnelFilter({ type, startDate, endDate });
  };

  useEffect(() => { loadLeads(); loadLines(); loadFunnel(); }, [loadLeads, loadLines, loadFunnel]);

  // Load available tags for current line/view context (filter dropdown)
  useEffect(() => {
    const scope = selectedLineId || adminViewAsLineId || null;
    const load = async () => {
      try {
        const params = {};
        if (scope) params.line_id = scope;
        const { data } = await api.get('/crm/tags', { params });
        setTagFilterOptions(data || []);
      } catch { /* silent */ }
    };
    load();
    // Reset filter when scope changes
    setTagFilter('all');
  }, [selectedLineId, adminViewAsLineId]);

  // Reset del tracking de unread al cambiar de línea: el set de leads visibles
  // cambia, así que prevUnreadMap quedaría obsoleto y dispararía sonidos
  // fantasma al "redescubrir" leads de otra línea.
  useEffect(() => {
    prevUnreadMap.current = new Map();
    firstLoadDone.current = false;
  }, [selectedLineId]);

  useEffect(() => {
    // Polling de leads/funnel: pausa cuando la pestaña está oculta para
    // ahorrar egress (Railway). Cuando la pestaña vuelve a foco, refresca al
    // toque. Intervalo 10s (antes 5s) — sigue siendo casi-real-time para CRM.
    let interval = null;
    let lastTickAt = Date.now();
    const POLL_MS = 10000;
    // Si el navegador pausa setInterval (background tabs en Chrome/Safari),
    // al volver al foreground forzamos catch-up si pasó más que el intervalo.
    const STALE_MS = 8000;

    const tick = () => { lastTickAt = Date.now(); loadLeads(); loadFunnel(); };
    const start = () => {
      if (interval) return;
      interval = setInterval(tick, POLL_MS);
    };
    const stop = () => {
      if (interval) { clearInterval(interval); interval = null; }
    };

    if (document.visibilityState === 'visible') start();

    // Catch-up unificado: dispara fetch inmediato si pasó suficiente tiempo
    // desde el último tick. Se invoca desde visibilitychange + focus +
    // pageshow porque algunos navegadores (Safari iOS, Chrome Android) no
    // disparan visibilitychange de forma confiable al volver de background.
    const catchUp = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastTickAt >= STALE_MS) {
        tick();
      }
      start();
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        catchUp();
      } else {
        stop();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('focus', catchUp);
    window.addEventListener('pageshow', catchUp);
    window.addEventListener('online', catchUp);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('focus', catchUp);
      window.removeEventListener('pageshow', catchUp);
      window.removeEventListener('online', catchUp);
    };
  }, [loadLeads, loadFunnel]);

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    const handler = (evt) => {
      if (evt.data?.type === 'OPEN_LEAD' && evt.data.leadId) {
        const fresh = leadsRef.current.find(l => l.id === evt.data.leadId);
        if (fresh) setSelectedLead(fresh);
        else {
          loadLeads().then(() => {
            const after = leadsRef.current.find(l => l.id === evt.data.leadId);
            if (after) setSelectedLead(after);
          });
        }
      }
    };
    navigator.serviceWorker.addEventListener('message', handler);
    try {
      const params = new URLSearchParams(window.location.search);
      const pendingId = params.get('openLead');
      if (pendingId) {
        const found = leadsRef.current.find(l => l.id === pendingId);
        if (found) setSelectedLead(found);
        window.history.replaceState({}, '', window.location.pathname);
      }
    } catch { /* silent */ }
    return () => navigator.serviceWorker.removeEventListener('message', handler);
  }, [loadLeads]);

  const handleStatusChange = async (leadId, status, conversionValue) => {
    try {
      await api.post(`/crm/leads/${leadId}/classify`, {
        status, send_to_meta: true,
        conversion_value: conversionValue,
        currency: 'USD'
      });
      toast.success(`✅ ${STATUS_CONFIG[status]?.label}`);
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status } : l));
      if (selectedLead?.id === leadId) setSelectedLead(prev => ({ ...prev, status }));
      loadLeads(); loadFunnel();
    } catch { toast.error('Error cambiando estado'); }
  };

  // Kanban drag
  const handleDragStart = (e, lead) => { setDraggedLead(lead); e.dataTransfer.effectAllowed = 'move'; };
  const handleDragOver = (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; };
  const handleDrop = async (e, newStatus) => {
    e.preventDefault();
    if (!draggedLead || draggedLead.status === newStatus) { setDraggedLead(null); return; }
    try {
      await api.post(`/crm/leads/${draggedLead.id}/move?new_status=${newStatus}`);
      loadLeads(); loadFunnel();
      toast.success(`Lead movido a ${STATUS_CONFIG[newStatus]?.label}`);
    } catch { toast.error('Error moviendo lead'); }
    finally { setDraggedLead(null); }
  };

  const filteredLeads = leads.filter(lead => {
    const matchStatus = filterStatus === 'all' || lead.status === filterStatus;
    const matchSearch = !searchTerm ||
      (lead.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (lead.phone || '').includes(searchTerm);
    // Si admin está en modo "Ver como cajero" filtramos solo los leads de
    // esa línea (todos los cajeros que la operan).
    const matchAdminView = !adminViewAsLineId || lead.line_id === adminViewAsLineId;
    const matchTag = tagFilter === 'all' || (Array.isArray(lead.tags) && lead.tags.includes(tagFilter));
    return matchStatus && matchSearch && matchAdminView && matchTag;
  });

  // Open a lead from the chat list — marks as read.
  const openLead = useCallback((lead) => {
    setSelectedLead(lead);
    setLeads(prev => prev.map(l => l.id === lead.id ? { ...l, unread_count: 0, has_unread_messages: false } : l));
    api.post(`/crm/leads/${lead.id}/read`).catch(() => {});
  }, []);

  const closeLead = useCallback(() => setSelectedLead(null), []);

  // Atajo global: ESC cierra el chat abierto y vuelve a la lista de chats.
  // Ignoramos el ESC si el foco está en un input/textarea/contenteditable
  // (para no interrumpir a los cajeros cuando escriben y usan ESC para
  // cerrar un dropdown, un modal, o borrar el texto). También ignoramos si
  // hay algún modal shadcn abierto (que gestiona su propio ESC).
  useEffect(() => {
    const isTypingInField = (el) => {
      if (!el) return false;
      const tag = (el.tagName || '').toUpperCase();
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
      if (el.isContentEditable) return true;
      return false;
    };
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      // Si hay un dialog radix/shadcn abierto, dejar que él maneje su propio ESC
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      // Si el usuario está tipeando, no interceptamos
      if (isTypingInField(e.target)) return;
      // Solo actúa si hay un chat abierto
      if (!selectedLead) return;
      e.preventDefault();
      setSelectedLead(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedLead]);

  // ── ADMIN PANEL (vista limpia con cards de líneas) ─────────────
  // Si admin entra sin haber elegido línea, mostramos el panel limpio.
  // Si elige una línea, cae a la vista normal (filtrada por esa línea con
  // el botón "Volver a líneas" arriba).
  if (isAdmin && !adminViewAsLineId) {
    return (
      <>
        <AdminLinesPanel
          lines={lines}
          leads={leads}
          onSelectLine={(lid) => setAdminViewAsLineId(lid)}
          onRefresh={() => { loadLeads(); loadLines(); loadFunnel(); }}
          onBroadcast={() => setBroadcastOpen(true)}
        />
        {broadcastOpen && (
          <BroadcastModal lines={lines} currentUser={currentUser} onClose={() => setBroadcastOpen(false)} />
        )}
      </>
    );
  }

  // ── CAJERO VIEW (also used by admin when drilled into a line) ────
  if (currentUser && (!isAdmin || adminViewAsLineId)) {
    const bgMain = darkMode ? 'bg-slate-950' : 'bg-gray-50';
    const bgCard = darkMode ? 'bg-slate-900/80' : 'bg-white';
    const borderColor = darkMode ? 'border-slate-800' : 'border-gray-200';
    const textPrimary = darkMode ? 'text-white' : 'text-gray-900';
    const textSecondary = darkMode ? 'text-slate-400' : 'text-gray-600';
    const inputBg = darkMode ? 'bg-slate-800 border-slate-700 text-white' : 'bg-gray-50 border-gray-300 text-gray-900';

    // On mobile with a chat open → full-screen chat (hides sidebar list)
    const mobileChatOpen = isMobile && selectedLead;

    return (
      <div className={`${bgMain} flex`} style={{ height: 'calc(100dvh - 4rem)', minHeight: 'calc(100dvh - 4rem)' }}>
        {/* Kommo-style vertical sidebar — desktop only */}
        {!mobileChatOpen && !isMobile && (
          <SidebarNav
            currentUser={currentUser}
            darkMode={darkMode}
            onThemeToggle={toggleTheme}
            onFunnelOpen={() => setShowFunnelModal(true)}
            soundEnabled={soundEnabled}
            onSoundToggle={soundEnabled ? () => setSoundEnabled(false) : enableSound}
            notifyEnabled={notifyEnabled}
            onNotifyToggle={notifyEnabled ? disableNotify : enableNotify}
            pwaPrompt={pwaPrompt}
            pwaInstalled={pwaInstalled}
            onInstall={installPWA}
            onBroadcast={() => setBroadcastOpen(true)}
            onTagsOpen={() => setTagsModalOpen(true)}
            onMPInboxOpen={() => setMpInboxOpen(true)}
            mpInboxUnread={mpInbox.data?.unread || 0}
            mpInboxTotalPending={mpInbox.data?.total_pending || 0}
            onRefresh={loadLeads}
            onContactsExport={isAdmin ? () => setExportModalOpen(true) : undefined}
            unreadCount={leads.filter(l => (l.unread_count > 0 || l.has_unread_messages) && selectedLead?.id !== l.id).length}
            showBackToLines={isAdmin && !!adminViewAsLineId}
            onBackToLines={() => { setAdminViewAsLineId(null); setSelectedLead(null); }}
          />
        )}

        <div className="flex flex-col flex-1 min-w-0">
        {/* Admin drill-down breadcrumb (desktop) */}
        {isAdmin && adminViewAsLineId && !isMobile && (
          <div className={`flex items-center gap-2 px-4 py-2 border-b ${borderColor} ${bgCard} shrink-0`}>
            <button
              onClick={() => { setAdminViewAsLineId(null); setSelectedLead(null); }}
              data-testid="admin-drill-back-btn"
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Volver a líneas
            </button>
            <span className="text-slate-600 text-xs">·</span>
            <span className="text-xs font-medium text-slate-200">
              Operando como cajero de: {lines.find(l => l.id === adminViewAsLineId)?.name || 'Línea'}
            </span>
          </div>
        )}

        {/* Mobile top bar (preserved as-is) */}
        {!mobileChatOpen && isMobile && (
          <div className={`flex items-center gap-2 px-3 py-2.5 border-b ${borderColor} ${bgCard} shrink-0 sticky top-0 z-10`}>
            <div className="bg-emerald-500/20 p-2 rounded-xl border border-emerald-500/30 shrink-0">
              <MessageCircle className="w-5 h-5 text-emerald-400" />
            </div>
            <div className="min-w-0 flex-1">
              <h1 className={`text-base font-bold leading-tight flex items-center gap-2 ${textPrimary}`}>
                {(() => {
                  const totalUnread = leads.filter(l => (l.unread_count > 0 || l.has_unread_messages) && selectedLead?.id !== l.id).length;
                  return totalUnread > 0 ? (
                    <span className="flex items-center justify-center min-w-[20px] h-5 bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 animate-pulse">
                      {totalUnread}
                    </span>
                  ) : null;
                })()}
              </h1>
              <p className={`text-xs ${textSecondary} truncate`}>Hola, {currentUser.email}</p>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {funnel && (
                <Button
                  onClick={() => setShowFunnelModal(true)}
                  size="sm"
                  variant="outline"
                  className={darkMode ? "border-slate-600 text-slate-300 hover:text-white text-xs gap-1.5 h-8 px-2" : "border-gray-300 text-gray-600 hover:text-gray-900 text-xs gap-1.5 h-8 px-2"}
                  data-testid="funnel-open-btn"
                >
                  <BarChart3 className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Embudo</span>
                </Button>
              )}
              <button
                onClick={soundEnabled ? () => setSoundEnabled(false) : enableSound}
                title={soundEnabled ? 'Silenciar' : 'Activar sonido'}
                data-testid="toggle-sound-btn"
                className={`p-2 rounded-lg transition-colors text-base leading-none ${soundEnabled ? 'bg-emerald-500/20' : 'text-slate-500 hover:bg-slate-800'}`}
              >
                {soundEnabled ? '🔔' : '🔕'}
              </button>
              <button
                onClick={notifyEnabled ? disableNotify : enableNotify}
                title={notifyEnabled ? 'Desactivar notificaciones' : 'Activar notificaciones'}
                data-testid="toggle-notify-btn"
                className={`p-2 rounded-lg transition-colors text-base leading-none ${notifyEnabled ? 'bg-blue-500/20' : 'text-slate-500 hover:bg-slate-800'}`}
              >
                {notifyEnabled ? '💬' : '🔇'}
              </button>
              {pwaPrompt && !pwaInstalled && (
                <button
                  onClick={installPWA}
                  title="Instalar app"
                  data-testid="install-pwa-btn"
                  className="flex items-center gap-1 px-2 h-8 rounded-lg text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/25"
                >
                  ⬇️<span className="hidden sm:inline">Instalar</span>
                </button>
              )}
              {(currentUser?.role === 'admin' || (currentUser?.line_ids && currentUser.line_ids.length > 0)) && (
                <button
                  onClick={() => setBroadcastOpen(true)}
                  title="Envío masivo"
                  data-testid="broadcast-open-btn"
                  className="flex items-center gap-1 px-2 h-8 rounded-lg text-xs font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/40 hover:bg-purple-500/25"
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Masivo</span>
                </button>
              )}
              {(currentUser?.role === 'admin' || (currentUser?.line_ids && currentUser.line_ids.length > 0)) && (
                <button
                  onClick={() => setTagsModalOpen(true)}
                  title="Gestionar etiquetas"
                  data-testid="tags-manager-open-btn"
                  className="flex items-center gap-1 px-2 h-8 rounded-lg text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/25"
                >
                  <TagIcon className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Etiquetas</span>
                </button>
              )}
              <button onClick={loadLeads} className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors" data-testid="refresh-leads-btn">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Funnel modal */}
        {showFunnelModal && funnel && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-2 sm:p-4" onClick={() => setShowFunnelModal(false)}>
            <div className="bg-slate-900 rounded-xl border border-slate-700 w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
                <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-blue-400" /> Embudo de Conversión
                </h2>
                <button onClick={() => setShowFunnelModal(false)} className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-3 sm:p-5 space-y-4">
                <FunnelDisplay
                  funnel={funnel.funnel}
                  conversionRates={funnel.conversion_rates}
                  totals={funnel.totals}
                  period={funnel.period}
                  onFilterChange={handleFunnelFilterChange}
                  filterType={funnelFilter.type}
                  startDate={funnelFilter.startDate}
                  endDate={funnelFilter.endDate}
                />
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Left: conversation list (hidden on mobile when chat is open) */}
          <div
            className={`
              ${mobileChatOpen ? 'hidden' : 'flex'}
              md:flex w-full md:w-80 md:shrink-0 border-r ${borderColor} flex-col ${bgCard}
            `}
            data-testid="chat-list-container"
          >
            <div className={`p-3 border-b ${borderColor} space-y-2 shrink-0`}>
              <div className="relative md:ml-10" data-testid="chat-list-search-wrap">
                <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${textSecondary}`} />
                <Input placeholder="Buscar..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                  className={`pl-9 ${inputBg} text-sm h-9`} data-testid="chat-list-search" />
              </div>
              <div className="flex gap-1 flex-wrap">
                {['all', ...STATUS_ORDER].map(key => (
                  <button key={key} onClick={() => setFilterStatus(key)}
                    data-testid={`filter-${key}`}
                    className={`px-2 py-0.5 rounded text-xs font-medium transition-all ${filterStatus === key
                      ? (key === 'all' ? 'bg-slate-600 text-white' : STATUS_CONFIG[key]?.color)
                      : 'text-slate-500 hover:text-slate-300'}`}>
                    {key === 'all' ? 'Todos' : STATUS_CONFIG[key]?.label}
                  </button>
                ))}
              </div>
              {tagFilterOptions.length > 0 && (
                <div className="flex gap-1 flex-wrap items-center" data-testid="tag-filter-bar">
                  <button
                    onClick={() => setTagFilter('all')}
                    data-testid="tag-filter-all"
                    className={`px-2 py-0.5 rounded-full text-[10px] font-medium border transition-all ${tagFilter === 'all' ? 'bg-slate-600 text-white border-slate-500' : 'text-slate-400 border-slate-700 hover:text-slate-200'}`}
                  >
                    Sin filtro
                  </button>
                  {tagFilterOptions.map(t => {
                    const active = tagFilter === t.id;
                    return (
                      <button
                        key={t.id}
                        onClick={() => setTagFilter(active ? 'all' : t.id)}
                        data-testid={`tag-filter-${t.id}`}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border transition-all ${active ? 'text-white' : 'text-slate-300 hover:brightness-125'}`}
                        style={{
                          backgroundColor: active ? t.color : 'transparent',
                          borderColor: t.color,
                        }}
                        title={t.name}
                      >
                        <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: t.color }} />
                        <span className="truncate max-w-[80px]">{t.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Unread summary banner */}
            {(() => {
              const totalUnread = filteredLeads.filter(l => (l.unread_count > 0 || l.has_unread_messages) && selectedLead?.id !== l.id).length;
              return totalUnread > 0 ? (
                <div className="mx-3 mt-2 mb-1 flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 shrink-0">
                  <span className="flex items-center justify-center w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full animate-pulse shrink-0">{totalUnread}</span>
                  <span className="text-xs text-red-400 font-medium">{totalUnread === 1 ? 'chat sin leer' : 'chats sin leer'}</span>
                </div>
              ) : null;
            })()}

            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center h-32"><RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" /></div>
              ) : filteredLeads.length === 0 ? (
                <div className={`flex flex-col items-center justify-center h-32 ${textSecondary} text-center px-4`}>
                  <MessageCircle className="w-8 h-8 mb-2 opacity-20" />
                  <p className="text-xs">No hay conversaciones</p>
                </div>
              ) : [...filteredLeads].sort((a, b) => {
                const aUnread = (a.unread_count > 0 || a.has_unread_messages) ? 1 : 0;
                const bUnread = (b.unread_count > 0 || b.has_unread_messages) ? 1 : 0;
                return bUnread - aUnread;
              }).map(lead => {
                const isSelected = selectedLead?.id === lead.id;
                const cfg = STATUS_CONFIG[lead.status] || STATUS_CONFIG.nuevo;
                const hasUnread = (lead.unread_count > 0 || lead.has_unread_messages) && !isSelected;
                return (
                  <button key={lead.id} onClick={() => openLead(lead)}
                    data-testid={`chat-list-item-${lead.id}`}
                    className={`w-full p-3 text-left transition-colors relative border-b ${borderColor} ${
                      isSelected ? (darkMode ? 'bg-slate-800' : 'bg-teal-50') : ''
                    } ${hasUnread ? (darkMode ? 'bg-red-950/20' : 'bg-red-50') : ''} ${
                      darkMode ? 'hover:bg-slate-800/60 active:bg-slate-800' : 'hover:bg-gray-50 active:bg-gray-100'
                    }`}>
                    {hasUnread && <span className="absolute left-0 top-0 bottom-0 w-0.5 bg-red-500 rounded-r" />}
                    <div className="flex items-start gap-3">
                      <LeadAvatar
                        lead={lead}
                        size="sm"
                        ring={hasUnread}
                        statusClass={cfg.dot}
                      />
                      {hasUnread && (
                        <span className="absolute top-2 left-14 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1 shadow-lg shadow-red-500/40 animate-pulse pointer-events-none">
                          {lead.unread_count > 9 ? '9+' : lead.unread_count || '!'}
                        </span>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <span className={`text-sm truncate ${hasUnread ? 'font-bold text-red-100' : 'font-semibold text-white'}`}>
                            {lead.name || lead.phone}
                          </span>
                          <span className={`text-[10px] shrink-0 ${hasUnread ? 'text-red-400 font-medium' : 'text-slate-500'}`}>
                            {formatTime(lead.last_interaction)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 truncate">{lead.phone}</p>
                        <div className="flex items-center gap-1.5 mt-1">
                          <StatusBadge status={lead.status} />
                          {lead.line_name && (
                            <span className="text-[10px] text-slate-500 flex items-center gap-0.5 truncate">
                              <Smartphone className="w-2.5 h-2.5 shrink-0" />{lead.line_name}
                            </span>
                          )}
                          {hasUnread && (
                            <span className="ml-auto text-[10px] text-red-400 font-bold flex items-center gap-0.5 animate-pulse">
                              ● nuevo mensaje
                            </span>
                          )}
                        </div>
                        {Array.isArray(lead.tag_details) && lead.tag_details.length > 0 && (
                          <div className="mt-1">
                            <TagChipList tags={lead.tag_details} max={3} size="xs" />
                          </div>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: chat panel */}
          <div
            className={`
              ${mobileChatOpen ? 'flex' : 'hidden'}
              md:flex flex-1 overflow-hidden min-h-0
            `}
            data-testid="chat-panel-container"
          >
            {!selectedLead ? (
              <div className="hidden md:flex flex-col items-center justify-center h-full w-full text-slate-500">
                <MessageCircle className="w-16 h-16 mb-4 opacity-10" />
                <p className="text-sm font-medium">Seleccioná una conversación</p>
                <p className="text-xs mt-1 text-slate-600">Los mensajes de WhatsApp aparecerán aquí</p>
              </div>
            ) : (
              <ChatPanel
                lead={selectedLead}
                onStatusChange={handleStatusChange}
                showCloseButton={false}
                showBackButton={isMobile}
                onBack={closeLead}
                onLeadUpdated={(updated) => {
                  setSelectedLead(prev => prev && prev.id === updated.id ? { ...prev, ...updated } : prev);
                  setLeads(prev => prev.map(l => l.id === updated.id ? { ...l, ...updated } : l));
                }}
                onLeadDeleted={(deletedId) => {
                  setLeads(prev => prev.filter(l => l.id !== deletedId));
                  setSelectedLead(null);
                }}
                userMessages={{
                  welcome_message: currentUser?.welcome_message,
                  user_message: currentUser?.user_message,
                  derivation_message: currentUser?.derivation_message,
                  derivation_numbers: currentUser?.derivation_numbers || [],
                  cbu_list: currentUser?.cbu_list || [],
                  quick_templates: currentUser?.quick_templates || {}
                }}
              />
            )}
          </div>
        </div>

        {broadcastOpen && (
          <BroadcastModal lines={lines} currentUser={currentUser} onClose={() => setBroadcastOpen(false)} />
        )}

        {exportModalOpen && (
          <ContactsExportModal onClose={() => setExportModalOpen(false)} />
        )}
        <TagsManagerModal
          open={tagsModalOpen}
          onClose={() => setTagsModalOpen(false)}
          lines={
            currentUser?.role === 'admin'
              ? lines
              : lines.filter(l => (currentUser?.line_ids || []).includes(l.id))
          }
          defaultLineId={selectedLineId || adminViewAsLineId}
        />
        <MPInboxModal
          open={mpInboxOpen}
          onClose={() => setMpInboxOpen(false)}
          currentLead={selectedLead}
          onAssigned={() => { mpInbox.refresh(); }}
        />
        </div>
      </div>
    );
  }

  // ── ADMIN VIEW ────────────────────────────────────────────────
  const bgMain = darkMode ? 'bg-slate-950' : 'bg-gray-50';
  const textPrimary = darkMode ? 'text-white' : 'text-gray-900';
  const textSecondary = darkMode ? 'text-slate-400' : 'text-gray-600';
  const inputBg = darkMode ? 'bg-slate-900 border-slate-700' : 'bg-white border-gray-300';
  const cardBg = darkMode ? 'bg-slate-900/50 border border-slate-800' : 'bg-white border border-gray-200';

  return (
    <div className={`min-h-screen ${bgMain} p-3 sm:p-6`}>
      <div className="max-w-[1800px] mx-auto mb-6">
        {/* Breadcrumb "Volver a líneas" cuando admin entró desde el panel */}
        {adminViewAsLineId && (
          <button
            onClick={() => { setAdminViewAsLineId(null); setSelectedLead(null); }}
            className="mb-3 inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition-colors"
            data-testid="admin-back-to-lines-btn"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Volver a líneas
            <span className="text-slate-600 mx-1">·</span>
            <span className="text-slate-300 font-medium">
              {lines.find(l => l.id === adminViewAsLineId)?.name || 'Línea'}
            </span>
          </button>
        )}
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <h1 className={`text-xl sm:text-2xl font-bold ${textPrimary} flex items-center gap-3`}>
              <Users className="w-6 h-6 sm:w-7 sm:h-7 text-blue-500" /> CRM Multi-Líneas
            </h1>
            <p className={`${textSecondary} text-sm mt-1`}>Gestiona y clasifica leads de WhatsApp</p>
          </div>
          <div className="flex items-center gap-2">
            {(currentUser?.role === 'admin' || currentUser?.role === 'superadmin') && (
              <Button
                onClick={() => setBroadcastOpen(true)}
                variant="outline"
                className="border-purple-500/40 text-purple-300 bg-purple-500/10 hover:bg-purple-500/20"
                data-testid="admin-broadcast-btn"
              >
                <Radio className="w-4 h-4 mr-2" /> Envío masivo
              </Button>
            )}
            {(currentUser?.role === 'admin' || currentUser?.role === 'superadmin') && (
              <Button
                onClick={() => setTagsModalOpen(true)}
                variant="outline"
                className="border-emerald-500/40 text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20"
                data-testid="admin-tags-btn"
              >
                <TagIcon className="w-4 h-4 mr-2" /> Etiquetas
              </Button>
            )}
            <Button onClick={() => { loadLeads(); loadLines(); loadFunnel(); }} variant="outline" className={darkMode ? "border-slate-600" : "border-gray-300"}>
              <RefreshCw className="w-4 h-4 mr-2" /> Actualizar
            </Button>
          </div>
        </div>
        {funnel && (
          <FunnelDisplay
            funnel={funnel.funnel}
            conversionRates={funnel.conversion_rates}
            totals={funnel.totals}
            period={funnel.period}
            onFilterChange={handleFunnelFilterChange}
            filterType={funnelFilter.type}
            startDate={funnelFilter.startDate}
            endDate={funnelFilter.endDate}
          />
        )}
      </div>

      <div className="max-w-[1800px] mx-auto flex flex-col lg:flex-row gap-6">
        <div className="w-full lg:w-80 lg:flex-shrink-0 space-y-4">
          <LinesManager lines={lines} onRefresh={loadLines} onSelectLine={setSelectedLineId} selectedLineId={selectedLineId} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="mb-4">
            <div className="relative">
              <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${textSecondary}`} />
              <Input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Buscar por nombre o teléfono..."
                className={`pl-10 ${inputBg}`} />
            </div>
          </div>
          {loading ? (
            <div className="flex items-center justify-center h-64"><RefreshCw className="w-8 h-8 text-blue-500 animate-spin" /></div>
          ) : isMobile ? (
            /* WhatsApp-style chat list — mobile */
            <div className={`${cardBg} rounded-lg overflow-hidden`}>
              {filteredLeads.length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-sm">No hay leads</div>
              ) : (
                filteredLeads.map(lead => (
                  <ChatListItem key={lead.id} lead={lead} onClick={setSelectedLead} />
                ))
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {STATUS_ORDER.map(status => (
                <KanbanColumn key={status} status={status} leads={filteredLeads} onLeadClick={setSelectedLead}
                  onDragStart={handleDragStart} onDragOver={handleDragOver} onDrop={handleDrop} />
              ))}
            </div>
          )}
        </div>
      </div>

      {selectedLead && (
        <AdminLeadModal
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
          onUpdate={() => { loadLeads(); loadFunnel(); setSelectedLead(null); }}
        />
      )}
      {broadcastOpen && (
        <BroadcastModal lines={lines} currentUser={currentUser} onClose={() => setBroadcastOpen(false)} />
      )}
      {exportModalOpen && (
        <ContactsExportModal onClose={() => setExportModalOpen(false)} />
      )}
      <TagsManagerModal
        open={tagsModalOpen}
        onClose={() => setTagsModalOpen(false)}
        lines={lines}
        defaultLineId={selectedLineId || adminViewAsLineId}
      />
      <MPInboxModal
        open={mpInboxOpen}
        onClose={() => setMpInboxOpen(false)}
        currentLead={selectedLead}
        onAssigned={() => { mpInbox.refresh(); }}
      />
    </div>
  );
}
