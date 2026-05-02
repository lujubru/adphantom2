import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Users, Plus, Search, Phone, MessageCircle,
  Check, X, Trash2, RefreshCw,
  DollarSign, UserCheck, AlertTriangle,
  GripVertical, Eye, Settings, Smartphone,
  ArrowRight, BarChart3, Zap, Copy, User, Target,
  Megaphone, Radio,
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
import { HamburgerMenu } from './leads-crm/HamburgerMenu';

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

const LinesManager = ({ lines, onRefresh, onSelectLine, selectedLineId }) => {
  const [showCreate, setShowCreate] = useState(false);
  const [editingLine, setEditingLine] = useState(null);
  const [saving, setSaving] = useState(false);
  const emptyForm = {
    name: '', line_type: 'publi', whatsapp_number: '',
    whatsapp_token: '', phone_number_id: '', verify_token: '',
    whatsapp_business_account_id: '',
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
      if (editingLine) { await api.put(`/crm/lines/${editingLine.id}`, form); toast.success('Línea actualizada'); }
      else { await api.post('/crm/lines', form); toast.success('Línea creada'); }
      setShowCreate(false); setEditingLine(null); resetForm(); onRefresh();
    } catch { toast.error('Error guardando línea'); }
    finally { setSaving(false); }
  };

  const deleteLine = async (id) => {
    if (!window.confirm('¿Eliminar esta línea?')) return;
    try { await api.delete(`/crm/lines/${id}`); toast.success('Línea eliminada'); onRefresh(); }
    catch { toast.error('Error eliminando línea'); }
  };

  const copyWebhook = (line) => {
    navigator.clipboard.writeText(`${BACKEND_URL}/api/crm/webhook/${line.id}`);
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
            <Input placeholder="Número WhatsApp (ej: 5491155554444)" value={form.whatsapp_number} onChange={e => setForm({ ...form, whatsapp_number: e.target.value })} className="bg-slate-700 border-slate-600 mb-2" />
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="WhatsApp Token" value={form.whatsapp_token} onChange={e => setForm({ ...form, whatsapp_token: e.target.value })} className="bg-slate-700 border-slate-600 text-xs" />
              <Input placeholder="Phone Number ID" value={form.phone_number_id} onChange={e => setForm({ ...form, phone_number_id: e.target.value })} className="bg-slate-700 border-slate-600 text-xs" />
            </div>
            <Input placeholder="Verify Token (webhook)" value={form.verify_token} onChange={e => setForm({ ...form, verify_token: e.target.value })} className="bg-slate-700 border-slate-600 text-xs mt-2" />
            <div className="mt-2">
              <Input
                data-testid="line-waba-id-input"
                placeholder="WhatsApp Business Account ID (WABA ID) — requerido para Broadcasts"
                value={form.whatsapp_business_account_id}
                onChange={e => setForm({ ...form, whatsapp_business_account_id: e.target.value })}
                className="bg-slate-700 border-slate-600 text-xs"
              />
              <p className="text-[10px] text-slate-500 mt-1 leading-snug">
                💡 Obtenelo en <a href="https://business.facebook.com/wa/manage/home/" target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">Meta Business Manager → Cuentas de WhatsApp → Configuración</a>. Aparece como "ID de la cuenta" (numérico, distinto al Phone Number ID). Necesario para enviar campañas masivas con plantillas.
              </p>
            </div>
          </div>
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
                    <span className="text-slate-400">Webhook URL:</span>
                    <button onClick={e => { e.stopPropagation(); copyWebhook(line); }} className="text-blue-400 hover:text-blue-300 flex items-center gap-1"><Copy className="w-3 h-3" /> Copiar</button>
                  </div>
                  <code className="text-slate-300 break-all">{BACKEND_URL}/api/crm/webhook/{line.id}</code>
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
        />
      </div>
    </div>
  );
};

// ─── Main Component ───────────────────────────────────────────────

export default function LeadsCRM() {
  const { darkMode } = useTheme();
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
        const hasUnread = count > 0 || l.has_unread_messages;
        if (hasUnread) {
          currentUnreadMap.set(l.id, count);
          const prevCount = prevUnreadMap.current.get(l.id) || 0;
          if (count > prevCount || (prevCount === 0 && hasUnread)) {
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

  useEffect(() => {
    const interval = setInterval(() => { loadLeads(); loadFunnel(); }, 5000);
    return () => clearInterval(interval);
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
    return matchStatus && matchSearch;
  });

  // Open a lead from the chat list — marks as read.
  const openLead = useCallback((lead) => {
    setSelectedLead(lead);
    setLeads(prev => prev.map(l => l.id === lead.id ? { ...l, unread_count: 0, has_unread_messages: false } : l));
    api.post(`/crm/leads/${lead.id}/read`).catch(() => {});
  }, []);

  const closeLead = useCallback(() => setSelectedLead(null), []);

  // ── CAJERO VIEW ────────────────────────────────────────────────
  if (currentUser && !isAdmin) {
    const bgMain = darkMode ? 'bg-slate-950' : 'bg-gray-50';
    const bgCard = darkMode ? 'bg-slate-900/80' : 'bg-white';
    const borderColor = darkMode ? 'border-slate-800' : 'border-gray-200';
    const textPrimary = darkMode ? 'text-white' : 'text-gray-900';
    const textSecondary = darkMode ? 'text-slate-400' : 'text-gray-600';
    const inputBg = darkMode ? 'bg-slate-800 border-slate-700 text-white' : 'bg-gray-50 border-gray-300 text-gray-900';

    // On mobile with a chat open → full-screen chat (hides sidebar list)
    const mobileChatOpen = isMobile && selectedLead;

    return (
      <div className={`${bgMain} flex flex-col`} style={{ height: 'calc(100dvh - 4rem)', minHeight: 'calc(100dvh - 4rem)' }}>
        {/* Hamburger menu — desktop only, hidden on mobile (mobile keeps top bar) */}
        {!mobileChatOpen && !isMobile && (
          <HamburgerMenu
            currentUser={currentUser}
            darkMode={darkMode}
            funnel={funnel}
            onFunnelOpen={() => setShowFunnelModal(true)}
            soundEnabled={soundEnabled}
            onSoundToggle={soundEnabled ? () => setSoundEnabled(false) : enableSound}
            notifyEnabled={notifyEnabled}
            onNotifyToggle={notifyEnabled ? disableNotify : enableNotify}
            pwaPrompt={pwaPrompt}
            pwaInstalled={pwaInstalled}
            onInstall={installPWA}
            onBroadcast={() => setBroadcastOpen(true)}
            onRefresh={loadLeads}
            onContactsExport={async () => {
              try {
                const res = await api.get('/crm/contacts/history?fmt=csv', { responseType: 'blob' });
                const url = window.URL.createObjectURL(new Blob([res.data], { type: 'text/csv;charset=utf-8' }));
                const a = document.createElement('a');
                a.href = url; a.download = `contactos-${new Date().toISOString().slice(0, 10)}.csv`;
                document.body.appendChild(a); a.click(); a.remove();
                window.URL.revokeObjectURL(url);
                toast.success('Contactos exportados');
              } catch { toast.error('Error exportando contactos'); }
            }}
            unreadCount={leads.filter(l => (l.unread_count > 0 || l.has_unread_messages) && selectedLead?.id !== l.id).length}
          />
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
                      <div className="relative shrink-0">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center ${hasUnread ? 'bg-red-900/40 ring-2 ring-red-500/50' : 'bg-slate-700'}`}>
                          <User className={`w-6 h-6 ${hasUnread ? 'text-red-300' : 'text-slate-400'}`} />
                        </div>
                        <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-slate-900 ${cfg.dot}`} />
                        {hasUnread && (
                          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1 shadow-lg shadow-red-500/40 animate-pulse">
                            {lead.unread_count > 9 ? '9+' : lead.unread_count || '!'}
                          </span>
                        )}
                      </div>
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
                userMessages={{
                  welcome_message: currentUser?.welcome_message,
                  user_message: currentUser?.user_message,
                  derivation_message: currentUser?.derivation_message,
                  derivation_numbers: currentUser?.derivation_numbers || [],
                  cbu_list: currentUser?.cbu_list || []
                }}
              />
            )}
          </div>
        </div>

        {broadcastOpen && (
          <BroadcastModal lines={lines} currentUser={currentUser} onClose={() => setBroadcastOpen(false)} />
        )}
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
    </div>
  );
}
