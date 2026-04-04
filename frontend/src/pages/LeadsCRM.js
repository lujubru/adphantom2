import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Users, Plus, Search, Phone, MessageCircle, Send, 
  Check, X, Trash2, RefreshCw,
  DollarSign, UserCheck, AlertTriangle,
  GripVertical, Eye, Settings, Smartphone,
  ArrowRight, BarChart3, Zap, Copy, ChevronDown, User, Target
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import api from '@/utils/api';
import { useTheme } from '@/contexts/ThemeContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// ─── Status config ─────────────────────────────────────────────────

const STATUS_CONFIG = {
  nuevo:     { label: 'Nuevo',     color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',    bgColumn: 'bg-blue-950/30',    dot: 'bg-blue-400',    icon: Users },
  spam:      { label: 'Spam',      color: 'bg-red-500/20 text-red-400 border-red-500/30',       bgColumn: 'bg-red-950/30',     dot: 'bg-red-400',     icon: Trash2 },
  consultas: { label: 'Consultas', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', bgColumn: 'bg-amber-950/30',   dot: 'bg-amber-400',   icon: MessageCircle },
  valido:    { label: 'Válido',    color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', bgColumn: 'bg-emerald-950/30', dot: 'bg-emerald-400', icon: DollarSign },
};

const LINE_TYPE_CONFIG = {
  publi:     { label: 'Publicidad', color: 'bg-blue-500/20 text-blue-400' },
  principal: { label: 'Principal',  color: 'bg-emerald-500/20 text-emerald-400' },
  spam:      { label: 'Spam',       color: 'bg-red-500/20 text-red-400' },
};

const STATUS_ORDER = ['nuevo', 'spam', 'consultas', 'valido'];

// ─── Helpers ───────────────────────────────────────────────────────

function formatTime(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;
    if (diff < 86400000) return d.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' });
    if (diff < 604800000) return d.toLocaleDateString('es', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('es', { day: '2-digit', month: 'short' });
  } catch { return ''; }
}

// ─── Status Badge ──────────────────────────────────────────────────

const StatusBadge = ({ status }) => {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.nuevo;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cfg.color}`}>
      {cfg.label}
    </span>
  );
};

// ─── Status Selector dropdown ──────────────────────────────────────

const StatusSelector = ({ currentStatus, onSelect, disabled }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const cfg = STATUS_CONFIG[currentStatus] || STATUS_CONFIG.nuevo;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => !disabled && setOpen(o => !o)}
        className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${cfg.color} ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80'}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
        {cfg.label}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 min-w-[140px] overflow-hidden">
          {Object.entries(STATUS_CONFIG).map(([key, val]) => (
            <button key={key} onClick={() => { onSelect(key); setOpen(false); }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-slate-700 transition-colors ${currentStatus === key ? 'bg-slate-700/50' : ''}`}>
              <span className={`w-2 h-2 rounded-full ${val.dot}`} />
              <span className="text-white">{val.label}</span>
              {currentStatus === key && <Check className="w-3 h-3 text-emerald-400 ml-auto" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

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
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-slate-400 flex items-center gap-2">
          <BarChart3 className="w-4 h-4" /> Embudo de Conversión
          {period && <span className="text-xs text-slate-500">({period})</span>}
        </h3>
        {onFilterChange && (
          <div className="flex items-center gap-2">
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
              <option value="semanal">Esta semana</option>
              <option value="mensual">Este mes</option>
              <option value="7">Últimos 7 días</option>
              <option value="30">Últimos 30 días</option>
              <option value="90">Últimos 90 días</option>
              <option value="custom">Fecha específica</option>
            </select>
            {showDatePicker && (
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-2 py-1"
                />
                <span className="text-slate-500 text-xs">a</span>
                <input
                  type="date"
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-2 py-1"
                />
                <Button 
                  size="sm" 
                  onClick={() => onFilterChange('custom', customStart, customEnd)}
                  className="bg-teal-600 hover:bg-teal-700 text-xs h-7"
                >
                  Aplicar
                </Button>
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
                <div className={`w-16 h-16 rounded-xl flex items-center justify-center ${idx === steps.length - 1 ? 'bg-emerald-500/20' : 'bg-slate-800'}`}>
                  <Icon className={`w-6 h-6 ${idx === steps.length - 1 ? 'text-emerald-400' : 'text-slate-400'}`} />
                </div>
                <span className="text-xl font-bold text-white mt-2">{step.value.toLocaleString()}</span>
                <span className="text-xs text-slate-400">{step.label}</span>
              </div>
              {idx < steps.length - 1 && (
                <div className="flex flex-col items-center px-2">
                  <ArrowRight className="w-5 h-5 text-slate-600" />
                  <span className="text-xs text-slate-500 mt-1">{rates[idx]}%</span>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
      {totals && (
        <div className="mt-4 pt-4 border-t border-slate-700 flex justify-between text-sm">
          <span className="text-slate-400">Total Leads: <span className="text-white font-medium">{totals.leads}</span></span>
          <span className="text-slate-400">Monto: <span className="text-emerald-400 font-medium">${(totals.monto_cargas || 0).toLocaleString()}</span></span>
          <span className="text-slate-400">Promedio: <span className="text-white font-medium">${(totals.promedio_carga || 0).toLocaleString()}</span></span>
        </div>
      )}
    </div>
  );
};

// ─── Ad Performance Dashboard ──────────────────────────────────────

const AdPerformanceDashboard = ({ lineId }) => {
  const [adStats, setAdStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    const loadAdStats = async () => {
      setLoading(true);
      try {
        const params = { days };
        if (lineId) params.line_id = lineId;
        const { data } = await api.get('/crm/funnel/by-ad', { params });
        setAdStats(data || []);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    loadAdStats();
  }, [lineId, days]);

  if (loading) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
        <div className="flex items-center justify-center h-24">
          <RefreshCw className="w-5 h-5 text-purple-400 animate-spin" />
        </div>
      </div>
    );
  }

  if (adStats.length === 0) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
        <h3 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-purple-400" /> Rendimiento por Anuncio
        </h3>
        <p className="text-slate-500 text-sm text-center py-4">Sin datos de anuncios aún. Los leads con utm_content aparecerán aquí.</p>
      </div>
    );
  }

  const totalLeads = adStats.reduce((sum, ad) => sum + ad.leads, 0);
  const totalConversiones = adStats.reduce((sum, ad) => sum + ad.conversiones, 0);
  const totalMonto = adStats.reduce((sum, ad) => sum + ad.monto_total, 0);

  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-slate-400 flex items-center gap-2">
          <Target className="w-4 h-4 text-purple-400" /> Rendimiento por Anuncio
        </h3>
        <select
          value={days}
          onChange={(e) => setDays(parseInt(e.target.value))}
          className="bg-slate-800 border border-slate-700 text-white text-xs rounded-lg px-2 py-1"
        >
          <option value="7">7 días</option>
          <option value="30">30 días</option>
          <option value="90">90 días</option>
        </select>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-white">{totalLeads}</p>
          <p className="text-xs text-slate-400">Total Leads</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-emerald-400">{totalConversiones}</p>
          <p className="text-xs text-slate-400">Conversiones</p>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-amber-400">${totalMonto.toLocaleString()}</p>
          <p className="text-xs text-slate-400">Monto Total</p>
        </div>
      </div>

      {/* Ad list */}
      <div className="space-y-2 max-h-[300px] overflow-y-auto">
        {adStats.map((ad, idx) => (
          <div key={ad.ad_source || idx} className="bg-slate-800/30 rounded-lg p-3 border border-slate-700/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-purple-400 font-mono text-xs bg-purple-500/10 px-2 py-0.5 rounded">
                  {ad.ad_source || 'Sin ID'}
                </span>
                <span className="text-white font-medium text-sm">{ad.leads} leads</span>
              </div>
              <span className={`text-xs font-medium ${ad.conversion_rate >= 10 ? 'text-emerald-400' : ad.conversion_rate >= 5 ? 'text-amber-400' : 'text-slate-400'}`}>
                {ad.conversion_rate}% conv.
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">
                <span className="text-emerald-400 font-medium">{ad.conversiones}</span> válidos
              </span>
              <span className="text-amber-400 font-medium">${ad.monto_total.toLocaleString()}</span>
            </div>
            {/* Progress bar */}
            <div className="mt-2 h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-purple-500 to-emerald-500 rounded-full transition-all"
                style={{ width: `${Math.min((ad.leads / totalLeads) * 100, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Lines Manager (admin only) ────────────────────────────────────

const LinesManager = ({ lines, onRefresh, onSelectLine, selectedLineId }) => {
  const [showCreate, setShowCreate] = useState(false);
  const [editingLine, setEditingLine] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '', line_type: 'publi', whatsapp_number: '',
    whatsapp_token: '', phone_number_id: '', verify_token: '',
    meta_access_token: '', meta_pixel_id: '', description: ''
  });

  const resetForm = () => setForm({
    name: '', line_type: 'publi', whatsapp_number: '',
    whatsapp_token: '', phone_number_id: '', verify_token: '',
    meta_access_token: '', meta_pixel_id: '', description: ''
  });

  const editLine = (line) => {
    setForm({
      name: line.name || '', line_type: line.line_type || 'publi',
      whatsapp_number: line.whatsapp_number || '',
      whatsapp_token: line.whatsapp_token || '',
      phone_number_id: line.phone_number_id || '',
      verify_token: line.verify_token || '',
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
      else { await api.post('/crm/lines/', form); toast.success('Línea creada'); }
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
            <Input placeholder="Nombre de la línea" value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="bg-slate-700 border-slate-600" />
            <select value={form.line_type} onChange={e => setForm({...form, line_type: e.target.value})} className="bg-slate-700 border border-slate-600 rounded-md px-3 text-white text-sm">
              <option value="publi">Publicidad</option>
              <option value="principal">Principal</option>
              <option value="spam">Spam</option>
            </select>
          </div>
          <div className="pt-2 border-t border-slate-600">
            <p className="text-xs text-slate-400 mb-2">📱 WhatsApp Business API</p>
            <Input placeholder="Número WhatsApp (ej: 5491155554444)" value={form.whatsapp_number} onChange={e => setForm({...form, whatsapp_number: e.target.value})} className="bg-slate-700 border-slate-600 mb-2" />
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="WhatsApp Token" value={form.whatsapp_token} onChange={e => setForm({...form, whatsapp_token: e.target.value})} className="bg-slate-700 border-slate-600 text-xs" />
              <Input placeholder="Phone Number ID" value={form.phone_number_id} onChange={e => setForm({...form, phone_number_id: e.target.value})} className="bg-slate-700 border-slate-600 text-xs" />
            </div>
            <Input placeholder="Verify Token (webhook)" value={form.verify_token} onChange={e => setForm({...form, verify_token: e.target.value})} className="bg-slate-700 border-slate-600 text-xs mt-2" />
          </div>
          <div className="pt-2 border-t border-slate-600">
            <p className="text-xs text-slate-400 mb-2">📊 Meta Pixel</p>
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="Meta Access Token" value={form.meta_access_token} onChange={e => setForm({...form, meta_access_token: e.target.value})} className="bg-slate-700 border-slate-600 text-xs" />
              <Input placeholder="Meta Pixel ID" value={form.meta_pixel_id} onChange={e => setForm({...form, meta_pixel_id: e.target.value})} className="bg-slate-700 border-slate-600 text-xs" />
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

// ─── Image Lightbox ────────────────────────────────────────────────

const ImageLightbox = ({ src, onClose }) => {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/90 z-[100] flex items-center justify-center p-4"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-full bg-slate-800/80 text-white hover:bg-slate-700 transition-colors"
      >
        <X className="w-5 h-5" />
      </button>
      <img
        src={src}
        alt="Comprobante"
        className="max-w-full max-h-[90vh] rounded-xl object-contain shadow-2xl"
        onClick={e => e.stopPropagation()}
      />
      <a
        href={src}
        download="comprobante.jpg"
        className="absolute bottom-4 right-4 px-3 py-2 rounded-lg bg-slate-800/80 text-white text-xs hover:bg-slate-700 transition-colors flex items-center gap-1.5"
        onClick={e => e.stopPropagation()}
      >
        ↓ Descargar
      </a>
    </div>
  );
};

// ─── Chat Message ──────────────────────────────────────────────────

const ChatMessage = ({ message }) => {
  const isAdmin = message.sender === 'admin';
  const [imgSrc, setImgSrc] = useState(null);
  const [loadingImg, setLoadingImg] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [docSrc, setDocSrc] = useState(null);
  const [loadingDoc, setLoadingDoc] = useState(false);

  const loadImage = useCallback(async () => {
    if (imgSrc || loadingImg) return;
    setLoadingImg(true);
    try {
      const { data } = await api.get(`/crm/messages/${message.id}/image`);
      setImgSrc(`data:${data.mime_type};base64,${data.image_base64}`);
    } catch { /* silent */ }
    finally { setLoadingImg(false); }
  }, [message.id, imgSrc, loadingImg]);

  const loadDocument = useCallback(async () => {
    if (docSrc || loadingDoc) return;
    setLoadingDoc(true);
    try {
      const { data } = await api.get(`/crm/messages/${message.id}/document`);
      const mime = data.mime_type || 'application/pdf';
      setDocSrc({ url: `data:${mime};base64,${data.image_base64}`, mime, filename: data.filename || 'documento.pdf' });
    } catch { /* silent */ }
    finally { setLoadingDoc(false); }
  }, [message.id, docSrc, loadingDoc]);

  useEffect(() => {
    if (message.message_type === 'image' && message.media_id) loadImage();
    if (message.message_type === 'document' && message.media_id) loadDocument();
  }, [message.id]);

  const handleDocDownload = () => {
    if (!docSrc) return;
    const a = document.createElement('a');
    a.href = docSrc.url;
    a.download = docSrc.filename;
    a.click();
  };

  let displayContent = message.content;
  if (typeof displayContent === 'object' && displayContent !== null) displayContent = JSON.stringify(displayContent, null, 2);
  if (!displayContent) displayContent = '[Mensaje vacío]';

  return (
    <>
      {lightboxOpen && imgSrc && (
        <ImageLightbox src={imgSrc} onClose={() => setLightboxOpen(false)} />
      )}
      <div className={`flex ${isAdmin ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[75%] px-3 py-2 rounded-2xl text-sm shadow-sm ${isAdmin ? 'bg-emerald-600 text-white rounded-br-sm' : 'bg-slate-700 text-slate-100 rounded-bl-sm'}`}>
          {message.message_type === 'image' ? (
            loadingImg ? <div className="flex items-center gap-2 text-xs opacity-70"><RefreshCw className="w-3 h-3 animate-spin" />Cargando...</div>
            : imgSrc ? (
              <div className="relative group cursor-zoom-in" onClick={() => setLightboxOpen(true)}>
                <img src={imgSrc} alt="img" className="max-w-[220px] rounded-lg" />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors rounded-lg flex items-center justify-center">
                  <span className="opacity-0 group-hover:opacity-100 transition-opacity text-white text-xs font-medium bg-black/60 px-2 py-1 rounded-full">
                    🔍 Ver comprobante
                  </span>
                </div>
              </div>
            )
            : <span className="text-xs opacity-60">[Imagen no disponible]</span>
          ) : message.message_type === 'document' ? (
            loadingDoc ? (
              <div className="flex items-center gap-2 text-xs opacity-70"><RefreshCw className="w-3 h-3 animate-spin" />Cargando documento...</div>
            ) : docSrc ? (
              <button
                onClick={handleDocDownload}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-black/20 hover:bg-black/30 transition-colors text-left w-full"
              >
                <span className="text-2xl shrink-0">📄</span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold truncate">{docSrc.filename}</p>
                  <p className="text-[10px] opacity-60 mt-0.5">PDF · Toca para descargar</p>
                </div>
                <span className="ml-auto text-lg shrink-0">⬇️</span>
              </button>
            ) : (
              <div className="flex items-center gap-2 text-xs opacity-60">
                <span>📄</span> Documento no disponible
              </div>
            )
          ) : (
            <p className="whitespace-pre-wrap break-words">{displayContent}</p>
          )}
          <p className={`text-[10px] mt-1 ${isAdmin ? 'text-emerald-200/60 text-right' : 'text-slate-400'}`}>
            {message.sender_name && <span>{message.sender_name} · </span>}
            {formatTime(message.created_at)}
          </p>
        </div>
      </div>
    </>
  );
};

// ─── Chat Panel (shared between cajero and admin modal) ────────────

const ChatPanel = ({ lead, onStatusChange, onClose, showCloseButton = false, userMessages = {} }) => {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [conversionValue, setConversionValue] = useState('');
  const [showConversionInput, setShowConversionInput] = useState(false);
  const messagesEndRef = useRef(null);

  const loadMessages = useCallback(async () => {
    try {
      const { data } = await api.get(`/crm/leads/${lead.id}/messages`);
      setMessages(data.messages || []);
    } catch { /* silent */ }
  }, [lead.id]);

  useEffect(() => {
    loadMessages();
    const interval = setInterval(loadMessages, 5000);
    return () => clearInterval(interval);
  }, [loadMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (sender = 'admin') => {
    if (!newMessage.trim()) return;
    setSending(true);
    try {
      await api.post(`/crm/leads/${lead.id}/messages`, { content: newMessage, sender });
      setNewMessage('');
      loadMessages();
    } catch { toast.error('Error enviando mensaje'); }
    finally { setSending(false); }
  };

  const handleStatusChange = async (status) => {
    if (status === 'valido') {
      setShowConversionInput(true);
      return;
    }
    await onStatusChange(lead.id, status, null);
  };

  const confirmValido = async () => {
    await onStatusChange(lead.id, 'valido', conversionValue ? parseFloat(conversionValue) : null);
    setShowConversionInput(false);
    setConversionValue('');
  };

  const sendBienvenida = async () => {
    // Use custom user message or default
    const mensaje = userMessages.welcome_message || `¡Buenas!👋 Trabajamos con las plataformas MÁS COMPLETAS del país!  
💟 ¡GANAMOS! 💟 💜 GANAMOSvip 💜 🥇 OROPURO 🥇  
ℹ MINIMOS: $2000 Acreditación // $5000 Retiro. 
🏦 Retiras tus ganancias UNA vez cada 24hs! 
⛔ No abonamos ni trabajamos con Ruletas 
🎁B0N0 ¡Beneficio de bienvenida activado! B0N0🎁  
✨¡Decime tu nombre para generar el usuario!✨`;
    try {
      await api.post(`/crm/leads/${lead.id}/messages`, { content: mensaje, sender: 'admin' });
      loadMessages();
      toast.success('Bienvenida enviada');
    } catch { toast.error('Error enviando bienvenida'); }
  };

  const sendUsuario = async () => {
    let clipboardText = '';
    try {
      clipboardText = await navigator.clipboard.readText();
    } catch {
      clipboardText = '[usuario]';
    }
    // Use custom user message or default, replace [CLIPBOARD] with clipboard content
    const defaultMsg = `¡Te dejo tus datos de acceso!:
👤Usuario: [CLIPBOARD]
🔑Contraseña: hola123
🌐Link de acceso: https://ganamosnet.org
🌐Link de acceso: https://oropuro.net
🌐Link de acceso: https://1ganamos.vip
¡Te dejo el CBU para que puedas cargar! 
Le envio nuestros datos de cuenta 👇`;
    const template = userMessages.user_message || defaultMsg;
    const mensaje = template.replace(/\[CLIPBOARD\]/g, clipboardText);
    try {
      await api.post(`/crm/leads/${lead.id}/messages`, { content: mensaje, sender: 'admin' });
      loadMessages();
      toast.success('Datos de usuario enviados');
      // Copy clipboard text to make it easier to paste
      await navigator.clipboard.writeText(clipboardText);
    } catch { toast.error('Error enviando datos de usuario'); }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700 bg-slate-900/60 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-9 h-9 rounded-full bg-slate-700 flex items-center justify-center">
              <User className="w-4 h-4 text-slate-400" />
            </div>
            <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-slate-900 ${STATUS_CONFIG[lead.status]?.dot || 'bg-blue-400'}`} />
          </div>
          <div>
            <p className="text-sm font-semibold text-white leading-tight">{lead.name || lead.phone}</p>
            <p className="text-xs text-slate-400">{lead.phone}{lead.line_name ? ` · ${lead.line_name}` : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusSelector currentStatus={lead.status} onSelect={handleStatusChange} />
          {showCloseButton && (
            <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Conversion value input (shown when selecting "válido") */}
      {showConversionInput && (
        <div className="px-4 py-3 border-b border-slate-700 bg-emerald-950/30 flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-emerald-400 shrink-0" />
          <Input
            type="number"
            placeholder="Monto de venta (ej: 1500)"
            value={conversionValue}
            onChange={e => setConversionValue(e.target.value)}
            className="bg-slate-800 border-slate-600 text-white text-sm h-8 flex-1"
            autoFocus
          />
          <Button size="sm" onClick={confirmValido} className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs">Confirmar</Button>
          <Button size="sm" variant="outline" onClick={() => { setShowConversionInput(false); setConversionValue(''); }} className="border-slate-600 h-8 text-xs">Cancelar</Button>
        </div>
      )}

      {/* Bienvenida button bar */}
      <div className="px-4 py-2 border-b border-slate-800 bg-slate-800/30 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-xs text-slate-400 flex-1">Chat en tiempo real</span>
        <Button onClick={sendBienvenida} size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3 h-7">
          👋 Bienvenida
        </Button>
        <Button onClick={sendUsuario} size="sm" className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 h-7">
          👤 Usuario
        </Button>
        <Button onClick={loadMessages} variant="ghost" size="sm" className="text-slate-400 hover:text-white h-7 w-7 p-0">
          <RefreshCw className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-slate-600">
            <MessageCircle className="w-8 h-8 mb-2 opacity-20" />
            <p className="text-xs">Sin mensajes aún</p>
          </div>
        ) : messages.map(msg => <ChatMessage key={msg.id} message={msg} />)}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-slate-800 bg-slate-900/60 shrink-0">
        <div className="flex gap-2">
          <Input
            placeholder="Escribe un mensaje..."
            value={newMessage}
            onChange={e => setNewMessage(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage('admin')}
            className="flex-1 bg-slate-800 border-slate-600 text-white text-sm"
            disabled={sending}
          />
          <Button onClick={() => sendMessage('lead')} disabled={sending || !newMessage.trim()} variant="outline" className="border-slate-600" title="Registrar como mensaje del lead">
            <Users className="w-4 h-4" />
          </Button>
          <Button onClick={() => sendMessage('admin')} disabled={sending || !newMessage.trim()} className="bg-blue-600 hover:bg-blue-700">
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

// ─── Lead Card (Kanban, admin only) ───────────────────────────────

const LeadCard = ({ lead, onClick, onDragStart }) => {
  const config = STATUS_CONFIG[lead.status] || STATUS_CONFIG.nuevo;
  const Icon = config.icon;
  const hasNewMessage = lead.has_unread_messages || lead.unread_count > 0;
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
      <div className="text-xs text-slate-400 space-y-1">
        <div className="flex items-center gap-1"><Phone className="w-3 h-3" /><span className="truncate">{lead.phone}</span></div>
        {lead.line_name && <div className="flex items-center gap-1"><Smartphone className="w-3 h-3" /><span className="truncate">{lead.line_name}</span></div>}
        {lead.ad_source && <div className="flex items-center gap-1 text-purple-400"><Target className="w-3 h-3" /><span className="truncate text-[10px]">{lead.ad_source}</span></div>}
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

// ─── Kanban Column (admin only) ───────────────────────────────────

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

const AdminLeadModal = ({ lead, lines, onClose, onUpdate }) => {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 rounded-xl w-full max-w-2xl h-[85vh] flex flex-col border border-slate-700">
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
  const [selectedLead, setSelectedLead] = useState(null);   // for chat (cajero) or modal (admin)
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [draggedLead, setDraggedLead] = useState(null);
  const [selectedLineId, setSelectedLineId] = useState(null);
  const [showFunnelModal, setShowFunnelModal] = useState(false);
  
  // Funnel filter state
  const [funnelFilter, setFunnelFilter] = useState({ type: '30', startDate: null, endDate: null });

  const isAdmin = !currentUser?.role || currentUser?.role === 'admin';

  // ── Notification sound ─────────────────────────────────────────
  const prevUnreadIds = useRef(new Set());
  const audioCtxRef = useRef(null);
  const [soundEnabled, setSoundEnabled] = useState(false);

  const getAudioCtx = useCallback(() => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioCtxRef.current;
  }, []);

  const enableSound = useCallback(() => {
    try {
      const ctx = getAudioCtx();
      // Resume context on user gesture (required by browsers)
      ctx.resume().then(() => {
        setSoundEnabled(true);
        // Play a quick test tone so user confirms it works
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = 'sine'; osc.frequency.value = 780;
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
        osc.start(); osc.stop(ctx.currentTime + 0.2);
      });
    } catch { /* silent */ }
  }, [getAudioCtx]);

  const playNotificationSound = useCallback(() => {
    if (!soundEnabled) return;
    try {
      const ctx = getAudioCtx();
      if (ctx.state === 'suspended') return;
      const play = (freq, startAt, duration, gain = 0.18) => {
        const osc = ctx.createOscillator();
        const gainNode = ctx.createGain();
        osc.connect(gainNode); gainNode.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime + startAt);
        gainNode.gain.setValueAtTime(0, ctx.currentTime + startAt);
        gainNode.gain.linearRampToValueAtTime(gain, ctx.currentTime + startAt + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + startAt + duration);
        osc.start(ctx.currentTime + startAt);
        osc.stop(ctx.currentTime + startAt + duration);
      };
      play(520, 0,    0.12);
      play(780, 0.13, 0.18);
    } catch { /* silent */ }
  }, [soundEnabled, getAudioCtx]);

  // Load current user
  useEffect(() => {
    api.get('/auth/me').then(({ data }) => setCurrentUser(data)).catch(() => {});
  }, []);

  const loadLeads = useCallback(async () => {
    try {
      const params = { limit: 200 };
      if (selectedLineId) params.line_id = selectedLineId;
      const { data } = await api.get('/crm/leads/', { params });
      let list = data.leads || [];
      list.sort((a, b) => new Date(b.last_interaction || b.created_at || '') - new Date(a.last_interaction || a.created_at || ''));
      // Detect newly unread leads and play sound
      const newUnreadIds = new Set(
        list.filter(l => l.unread_count > 0 || l.has_unread_messages).map(l => l.id)
      );
      const hasNewOnes = [...newUnreadIds].some(id => !prevUnreadIds.current.has(id));
      if (hasNewOnes && prevUnreadIds.current.size > 0) playNotificationSound();
      prevUnreadIds.current = newUnreadIds;
      setLeads(list);
    } catch { toast.error('Error cargando leads'); }
    finally { setLoading(false); }
  }, [selectedLineId, playNotificationSound]);

  const loadLines = useCallback(async () => {
    try { const { data } = await api.get('/crm/lines/'); setLines(data || []); }
    catch { /* silent */ }
  }, []);

  const loadFunnel = useCallback(async () => {
    try {
      const params = {};
      if (selectedLineId) params.line_id = selectedLineId;
      
      // Apply filter
      if (funnelFilter.type === 'custom' && funnelFilter.startDate && funnelFilter.endDate) {
        params.start_date = funnelFilter.startDate;
        params.end_date = funnelFilter.endDate;
      } else if (['diario', 'semanal', 'mensual'].includes(funnelFilter.type)) {
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
    const interval = setInterval(() => { loadLeads(); loadFunnel(); }, 10000);
    return () => clearInterval(interval);
  }, [loadLeads, loadFunnel]);

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

  // Filtered leads for cajero chat list
  const filteredLeads = leads.filter(lead => {
    const matchStatus = filterStatus === 'all' || lead.status === filterStatus;
    const matchSearch = !searchTerm ||
      (lead.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (lead.phone || '').includes(searchTerm);
    return matchStatus && matchSearch;
  });

  // ── CAJERO VIEW ────────────────────────────────────────────────
  if (currentUser && !isAdmin) {
    const bgMain = darkMode ? 'bg-slate-950' : 'bg-gray-50';
    const bgCard = darkMode ? 'bg-slate-900/80' : 'bg-white';
    const bgSidebar = darkMode ? 'bg-slate-900/50' : 'bg-white';
    const borderColor = darkMode ? 'border-slate-800' : 'border-gray-200';
    const textPrimary = darkMode ? 'text-white' : 'text-gray-900';
    const textSecondary = darkMode ? 'text-slate-400' : 'text-gray-600';
    const inputBg = darkMode ? 'bg-slate-800 border-slate-700 text-white' : 'bg-gray-50 border-gray-300 text-gray-900';
    
    return (
      <div className={`h-screen ${bgMain} flex flex-col overflow-hidden`}>
        {/* Top bar */}
        <div className={`flex items-center gap-3 px-4 py-3 border-b ${borderColor} ${bgCard} shrink-0`}>
          <div className="bg-emerald-500/20 p-2 rounded-xl border border-emerald-500/30">
            <MessageCircle className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className={`text-base font-bold leading-tight flex items-center gap-2 ${textPrimary}`}>
              WhatsApp CRM
              {(() => {
                const totalUnread = leads.filter(l => (l.unread_count > 0 || l.has_unread_messages) && selectedLead?.id !== l.id).length;
                return totalUnread > 0 ? (
                  <span className="flex items-center justify-center min-w-[20px] h-5 bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 animate-pulse">
                    {totalUnread}
                  </span>
                ) : null;
              })()}
            </h1>
            <p className={`text-xs ${textSecondary}`}>Bienvenido, {currentUser.email}</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {funnel && (
              <Button
                onClick={() => setShowFunnelModal(true)}
                size="sm"
                variant="outline"
                className={darkMode ? "border-slate-600 text-slate-300 hover:text-white text-xs gap-1.5" : "border-gray-300 text-gray-600 hover:text-gray-900 text-xs gap-1.5"}
              >
                <BarChart3 className="w-3.5 h-3.5" /> Embudo de Conversión
              </Button>
            )}
            <button
              onClick={soundEnabled ? () => setSoundEnabled(false) : enableSound}
              title={soundEnabled ? 'Silenciar notificaciones' : 'Activar sonido de notificaciones'}
              className={`p-2 rounded-lg transition-colors text-lg leading-none ${soundEnabled ? 'bg-emerald-500/20 hover:bg-emerald-500/30' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'}`}
            >
              {soundEnabled ? '🔔' : '🔕'}
            </button>
            <button onClick={loadLeads} className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Funnel modal para cajero */}
        {showFunnelModal && funnel && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowFunnelModal(false)}>
            <div className="bg-slate-900 rounded-xl border border-slate-700 w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
                <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-blue-400" /> Embudo de Conversión
                </h2>
                <button onClick={() => setShowFunnelModal(false)} className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-5 space-y-4">
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
                <AdPerformanceDashboard lineId={selectedLineId} />
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-1 overflow-hidden">
          {/* Left: conversation list */}
          <div className={`w-72 shrink-0 border-r ${borderColor} flex flex-col ${bgSidebar}`}>
            <div className={`p-3 border-b ${borderColor} space-y-2`}>
              <div className="relative">
                <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${textSecondary}`} />
                <Input placeholder="Buscar..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                  className={`pl-9 ${inputBg} text-sm h-9`} />
              </div>
              <div className="flex gap-1 flex-wrap">
                {['all', ...STATUS_ORDER].map(key => (
                  <button key={key} onClick={() => setFilterStatus(key)}
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
                <div className="mx-3 mt-2 mb-1 flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
                  <span className="flex items-center justify-center w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full animate-pulse shrink-0">{totalUnread}</span>
                  <span className="text-xs text-red-400 font-medium">{totalUnread === 1 ? 'chat sin leer' : 'chats sin leer'}</span>
                </div>
              ) : null;
            })()}

            <div className={`flex-1 overflow-y-auto divide-y ${darkMode ? 'divide-slate-800/50' : 'divide-gray-200'}`}>
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
                  <button key={lead.id} onClick={() => {
                      setSelectedLead(lead);
                      // Clear unread locally so badge disappears immediately
                      setLeads(prev => prev.map(l => l.id === lead.id ? { ...l, unread_count: 0, has_unread_messages: false } : l));
                      // Persist the read state to backend
                      api.post(`/crm/leads/${lead.id}/read`).catch(() => {});
                    }}
                    className={`w-full p-3 text-left transition-colors relative ${
                      isSelected ? (darkMode ? 'bg-slate-800' : 'bg-teal-50') : ''
                    } ${hasUnread ? (darkMode ? 'bg-red-950/20' : 'bg-red-50') : ''} ${
                      darkMode ? 'hover:bg-slate-800/60' : 'hover:bg-gray-50'
                    }`}>
                    {/* Unread left bar */}
                    {hasUnread && <span className="absolute left-0 top-0 bottom-0 w-0.5 bg-red-500 rounded-r" />}
                    <div className="flex items-start gap-3">
                      <div className="relative shrink-0">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${hasUnread ? 'bg-red-900/40 ring-2 ring-red-500/50' : 'bg-slate-700'}`}>
                          <User className={`w-5 h-5 ${hasUnread ? 'text-red-300' : 'text-slate-400'}`} />
                        </div>
                        {/* Status dot */}
                        <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-slate-900 ${cfg.dot}`} />
                        {/* Unread badge */}
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

          {/* Right: chat */}
          <div className="flex-1 overflow-hidden">
            {!selectedLead ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <MessageCircle className="w-16 h-16 mb-4 opacity-10" />
                <p className="text-sm font-medium">Seleccioná una conversación</p>
                <p className="text-xs mt-1 text-slate-600">Los mensajes de WhatsApp aparecerán aquí</p>
              </div>
            ) : (
              <ChatPanel
                lead={selectedLead}
                onStatusChange={handleStatusChange}
                showCloseButton={false}
                userMessages={{
                  welcome_message: currentUser?.welcome_message,
                  user_message: currentUser?.user_message
                }}
              />
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── ADMIN VIEW ────────────────────────────────────────────────
  const bgMain = darkMode ? 'bg-slate-950' : 'bg-gray-50';
  const textPrimary = darkMode ? 'text-white' : 'text-gray-900';
  const textSecondary = darkMode ? 'text-slate-400' : 'text-gray-600';
  const inputBg = darkMode ? 'bg-slate-900 border-slate-700' : 'bg-white border-gray-300';
  
  return (
    <div className={`min-h-screen ${bgMain} p-6`}>
      {/* Header */}
      <div className="max-w-[1800px] mx-auto mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className={`text-2xl font-bold ${textPrimary} flex items-center gap-3`}>
              <Users className="w-7 h-7 text-blue-500" /> CRM Multi-Líneas
            </h1>
            <p className={`${textSecondary} text-sm mt-1`}>Gestiona y clasifica leads de WhatsApp</p>
          </div>
          <Button onClick={() => { loadLeads(); loadLines(); loadFunnel(); }} variant="outline" className={darkMode ? "border-slate-600" : "border-gray-300"}>
            <RefreshCw className="w-4 h-4 mr-2" /> Actualizar
          </Button>
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

      {/* Main content */}
      <div className="max-w-[1800px] mx-auto flex gap-6">
        {/* Sidebar - Lines + Ad Performance */}
        <div className="w-80 flex-shrink-0 space-y-4">
          <LinesManager lines={lines} onRefresh={loadLines} onSelectLine={setSelectedLineId} selectedLineId={selectedLineId} />
          <AdPerformanceDashboard lineId={selectedLineId} />
        </div>

        {/* Kanban */}
        <div className="flex-1">
          <div className="mb-4">
            <div className="relative">
              <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${textSecondary}`} />
              <Input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Buscar por nombre o teléfono..."
                className={`pl-10 ${inputBg}`} />
            </div>
          </div>
          {loading ? (
            <div className="flex items-center justify-center h-64"><RefreshCw className="w-8 h-8 text-blue-500 animate-spin" /></div>
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

      {/* Admin modal for lead chat */}
      {selectedLead && (
        <AdminLeadModal
          lead={selectedLead}
          lines={lines}
          onClose={() => setSelectedLead(null)}
          onUpdate={() => { loadLeads(); loadFunnel(); setSelectedLead(null); }}
        />
      )}
    </div>
  );
}
