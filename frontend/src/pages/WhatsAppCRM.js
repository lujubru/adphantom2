import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageCircle, Send, User, Search, Phone, RefreshCw,
  Plus, Settings, Trash2, Check, AlertTriangle, DollarSign,
  Users, Smartphone, Copy, Zap, ChevronDown, X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import api from '@/utils/api';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

// Status config — matches CRM leads statuses
const STATUS_CONFIG = {
  nuevo:     { label: 'Nuevo',     color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',    dot: 'bg-blue-400' },
  spam:      { label: 'Spam',      color: 'bg-red-500/20 text-red-400 border-red-500/30',       dot: 'bg-red-400' },
  consultas: { label: 'Consultas', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', dot: 'bg-amber-400' },
  valido:    { label: 'Válido',    color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-400' },
};

const LINE_TYPE_CONFIG = {
  publi:     { label: 'Publicidad', color: 'bg-blue-500/20 text-blue-400' },
  principal: { label: 'Principal',  color: 'bg-emerald-500/20 text-emerald-400' },
  spam:      { label: 'Spam',       color: 'bg-red-500/20 text-red-400' },
};

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

// ─── Lines Manager (admin only) ───────────────────────────────────

function LinesManager({ lines, onRefresh }) {
  const [open, setOpen] = useState(false);
  const [showForm, setShowForm] = useState(false);
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
    setShowForm(true);
    setOpen(true);
  };

  const saveLine = async (e) => {
    e.preventDefault();
    if (!form.name || !form.whatsapp_number) {
      toast.error('Nombre y número son requeridos');
      return;
    }
    setSaving(true);
    try {
      if (editingLine) {
        await api.put(`/crm/lines/${editingLine.id}`, form);
        toast.success('Línea actualizada');
      } else {
        await api.post('/crm/lines', form);
        toast.success('Línea creada');
      }
      setShowForm(false);
      setEditingLine(null);
      resetForm();
      onRefresh();
    } catch { toast.error('Error guardando línea'); }
    finally { setSaving(false); }
  };

  const deleteLine = async (id) => {
    if (!window.confirm('¿Eliminar esta línea?')) return;
    try {
      await api.delete(`/crm/lines/${id}`);
      toast.success('Línea eliminada');
      onRefresh();
    } catch { toast.error('Error eliminando línea'); }
  };

  const copyWebhook = (line) => {
    navigator.clipboard.writeText(`${BACKEND_URL}/api/crm/webhook/${line.id}`);
    toast.success('URL copiada');
  };

  return (
    <div className="border-b border-slate-800 bg-slate-900/80">
      {/* Collapsible header */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-white">
          <Smartphone className="w-4 h-4 text-blue-400" />
          Líneas de WhatsApp
          <span className="ml-1 bg-blue-500/20 text-blue-400 text-xs px-2 py-0.5 rounded-full">{lines.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); resetForm(); setEditingLine(null); setShowForm(true); setOpen(true); }}
            className="p-1 bg-blue-600 hover:bg-blue-500 rounded text-white"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {open && (
        <div className="px-4 pb-3 space-y-2 max-h-72 overflow-y-auto">
          {/* Create/Edit Form */}
          {showForm && (
            <form onSubmit={saveLine} className="bg-slate-800/60 rounded-lg p-3 space-y-2 border border-slate-700">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-white">{editingLine ? 'Editar Línea' : 'Nueva Línea'}</span>
                <button type="button" onClick={() => { setShowForm(false); setEditingLine(null); resetForm(); }}>
                  <X className="w-4 h-4 text-slate-400 hover:text-white" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="Nombre" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                  className="bg-slate-700 border-slate-600 text-white text-xs h-8" />
                <select value={form.line_type} onChange={e => setForm({ ...form, line_type: e.target.value })}
                  className="bg-slate-700 border border-slate-600 rounded-md px-2 text-white text-xs h-8">
                  <option value="publi">Publicidad</option>
                  <option value="principal">Principal</option>
                  <option value="spam">Spam</option>
                </select>
              </div>
              <Input placeholder="Número WhatsApp (ej: 5491155554444)" value={form.whatsapp_number}
                onChange={e => setForm({ ...form, whatsapp_number: e.target.value })}
                className="bg-slate-700 border-slate-600 text-white text-xs h-8" />
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="WA Token" value={form.whatsapp_token}
                  onChange={e => setForm({ ...form, whatsapp_token: e.target.value })}
                  className="bg-slate-700 border-slate-600 text-white text-xs h-8" />
                <Input placeholder="Phone Number ID" value={form.phone_number_id}
                  onChange={e => setForm({ ...form, phone_number_id: e.target.value })}
                  className="bg-slate-700 border-slate-600 text-white text-xs h-8" />
              </div>
              <Input placeholder="Verify Token (webhook)" value={form.verify_token}
                onChange={e => setForm({ ...form, verify_token: e.target.value })}
                className="bg-slate-700 border-slate-600 text-white text-xs h-8" />
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="Meta Access Token" value={form.meta_access_token}
                  onChange={e => setForm({ ...form, meta_access_token: e.target.value })}
                  className="bg-slate-700 border-slate-600 text-white text-xs h-8" />
                <Input placeholder="Meta Pixel ID" value={form.meta_pixel_id}
                  onChange={e => setForm({ ...form, meta_pixel_id: e.target.value })}
                  className="bg-slate-700 border-slate-600 text-white text-xs h-8" />
              </div>
              <div className="flex gap-2 pt-1">
                <Button type="button" variant="outline" size="sm" onClick={() => { setShowForm(false); setEditingLine(null); resetForm(); }}
                  className="border-slate-600 text-xs h-7">Cancelar</Button>
                <Button type="submit" size="sm" disabled={saving} className="bg-emerald-600 hover:bg-emerald-700 text-xs h-7">
                  {saving ? 'Guardando...' : editingLine ? 'Actualizar' : 'Crear'}
                </Button>
              </div>
            </form>
          )}

          {/* Lines list */}
          {lines.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-2">No hay líneas. Creá una para comenzar.</p>
          ) : lines.map(line => {
            const typeConfig = LINE_TYPE_CONFIG[line.line_type] || LINE_TYPE_CONFIG.publi;
            const hasWA = line.whatsapp_token && line.phone_number_id;
            const hasPixel = line.meta_access_token && line.meta_pixel_id;
            return (
              <div key={line.id} className="bg-slate-800/50 rounded-lg p-2.5 border border-slate-700/50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${typeConfig.color}`}>{typeConfig.label}</span>
                    <span className="text-sm text-white font-medium">{line.name}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => editLine(line)} className="p-1 text-slate-400 hover:text-blue-400">
                      <Settings className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => deleteLine(line.id)} className="p-1 text-slate-400 hover:text-red-400">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Phone className="w-3 h-3" />{line.whatsapp_number}
                  </span>
                  <span className="text-xs text-slate-500">{line.leads_count || 0} leads</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {hasWA
                    ? <span className="text-[10px] text-emerald-400 flex items-center gap-0.5"><Check className="w-3 h-3" />WA</span>
                    : <span className="text-[10px] text-amber-400 flex items-center gap-0.5"><AlertTriangle className="w-3 h-3" />Sin WA</span>
                  }
                  {hasPixel
                    ? <span className="text-[10px] text-emerald-400 flex items-center gap-0.5"><Zap className="w-3 h-3" />Pixel</span>
                    : <span className="text-[10px] text-amber-400 flex items-center gap-0.5"><AlertTriangle className="w-3 h-3" />Sin Pixel</span>
                  }
                  {line.verify_token && (
                    <button onClick={() => copyWebhook(line)}
                      className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-0.5 ml-auto">
                      <Copy className="w-3 h-3" />Webhook
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.nuevo;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

// ─── Status Selector (inline dropdown) ────────────────────────────

function StatusSelector({ currentStatus, onSelect, disabled }) {
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
        <div className="absolute right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 min-w-[130px] overflow-hidden">
          {Object.entries(STATUS_CONFIG).map(([key, val]) => (
            <button
              key={key}
              onClick={() => { onSelect(key); setOpen(false); }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-slate-700 transition-colors ${
                currentStatus === key ? 'bg-slate-700/50' : ''
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${val.dot}`} />
              <span className="text-white">{val.label}</span>
              {currentStatus === key && <Check className="w-3 h-3 text-emerald-400 ml-auto" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Chat Message ─────────────────────────────────────────────────

function ChatMessage({ message }) {
  const isAdmin = message.sender === 'admin';
  const [imgSrc, setImgSrc] = useState(null);
  const [loadingImg, setLoadingImg] = useState(false);

  const loadImage = useCallback(async () => {
    if (imgSrc || loadingImg) return;
    setLoadingImg(true);
    try {
      const { data } = await api.get(`/crm/messages/${message.id}/image`);
      setImgSrc(`data:${data.mime_type};base64,${data.image_base64}`);
    } catch { /* silent */ }
    finally { setLoadingImg(false); }
  }, [message.id, imgSrc, loadingImg]);

  useEffect(() => {
    if (message.message_type === 'image' && message.media_id) loadImage();
  }, [message.id]);

  const content = typeof message.content === 'object'
    ? JSON.stringify(message.content, null, 2)
    : (message.content || '[Mensaje vacío]');

  return (
    <div className={`flex ${isAdmin ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[75%] px-3 py-2 rounded-2xl text-sm shadow-sm ${
        isAdmin
          ? 'bg-emerald-600 text-white rounded-br-sm'
          : 'bg-slate-700 text-slate-100 rounded-bl-sm'
      }`}>
        {message.message_type === 'image' ? (
          loadingImg
            ? <div className="flex items-center gap-2 text-xs opacity-70"><RefreshCw className="w-3 h-3 animate-spin" />Cargando...</div>
            : imgSrc
              ? <a href={imgSrc} target="_blank" rel="noopener noreferrer">
                  <img src={imgSrc} alt="img" className="max-w-[220px] rounded-lg" />
                </a>
              : <span className="text-xs opacity-60">[Imagen no disponible]</span>
        ) : (
          <p className="whitespace-pre-wrap break-words">{content}</p>
        )}
        <p className={`text-[10px] mt-1 ${isAdmin ? 'text-emerald-200/60 text-right' : 'text-slate-400'}`}>
          {message.sender_name && <span>{message.sender_name} · </span>}
          {formatTime(message.created_at)}
        </p>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────

export default function WhatsAppCRM() {
  const [currentUser, setCurrentUser] = useState(null);
  const [leads, setLeads] = useState([]);
  const [lines, setLines] = useState([]);
  const [selectedLead, setSelectedLead] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const messagesEndRef = useRef(null);

  const isAdmin = currentUser?.role === 'admin' || !currentUser?.role;

  // Load current user role
  useEffect(() => {
    api.get('/auth/me').then(({ data }) => setCurrentUser(data)).catch(() => {});
  }, []);

  const loadLeads = useCallback(async () => {
    try {
      const params = { limit: 200 };
      const { data } = await api.get('/crm/leads', { params });
      let list = data.leads || [];
      // Sort by last interaction descending
      list.sort((a, b) => {
        const da = a.last_interaction ? new Date(a.last_interaction).getTime() : 0;
        const db2 = b.last_interaction ? new Date(b.last_interaction).getTime() : 0;
        return db2 - da;
      });
      setLeads(list);
    } catch { toast.error('Error cargando conversaciones'); }
    finally { setLoading(false); }
  }, []);

  const loadLines = useCallback(async () => {
    try {
      const { data } = await api.get('/crm/lines');
      setLines(data || []);
    } catch { /* silent */ }
  }, []);

  const loadMessages = useCallback(async (leadId) => {
    if (!leadId) return;
    setLoadingMessages(true);
    try {
      const { data } = await api.get(`/crm/leads/${leadId}/messages`);
      setMessages(data.messages || []);
    } catch { /* silent */ }
    finally { setLoadingMessages(false); }
  }, []);

  useEffect(() => { loadLeads(); loadLines(); }, [loadLeads, loadLines]);

  useEffect(() => {
    if (selectedLead) loadMessages(selectedLead.id);
  }, [selectedLead?.id, loadMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      loadLeads();
      if (selectedLead) loadMessages(selectedLead.id);
    }, 8000);
    return () => clearInterval(interval);
  }, [loadLeads, loadMessages, selectedLead?.id]);

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedLead) return;
    setSending(true);
    try {
      await api.post(`/crm/leads/${selectedLead.id}/messages`, { content: newMessage, sender: 'admin' });
      setNewMessage('');
      loadMessages(selectedLead.id);
    } catch { toast.error('Error enviando mensaje'); }
    finally { setSending(false); }
  };

  const changeStatus = async (leadId, status) => {
    try {
      await api.post(`/crm/leads/${leadId}/classify`, {
        status,
        send_to_meta: true,
        currency: 'MXN'
      });
      toast.success(`Estado cambiado a ${STATUS_CONFIG[status]?.label}`);
      // Update local state immediately
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status } : l));
      if (selectedLead?.id === leadId) setSelectedLead(prev => ({ ...prev, status }));
      loadLeads();
    } catch { toast.error('Error cambiando estado'); }
  };

  // Filtered list
  const filteredLeads = leads.filter(lead => {
    const matchStatus = filterStatus === 'all' || lead.status === filterStatus;
    const matchSearch = !search ||
      (lead.name || '').toLowerCase().includes(search.toLowerCase()) ||
      (lead.phone || '').includes(search);
    return matchStatus && matchSearch;
  });

  return (
    <div className="h-screen bg-slate-950 flex flex-col overflow-hidden">
      {/* Top Bar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800 bg-slate-900/80 shrink-0">
        <div className="bg-emerald-500/20 p-2 rounded-xl border border-emerald-500/30">
          <MessageCircle className="w-5 h-5 text-emerald-400" />
        </div>
        <div>
          <h1 className="text-base font-bold text-white leading-tight">WhatsApp CRM</h1>
          <p className="text-xs text-slate-400">
            {isAdmin ? 'Vista Administrador' : 'Vista Cajero'}
          </p>
        </div>
        <button onClick={() => { loadLeads(); if (selectedLead) loadMessages(selectedLead.id); }}
          className="ml-auto p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Lines Manager — admin only */}
      {isAdmin && <LinesManager lines={lines} onRefresh={loadLines} />}

      {/* Main chat layout */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Left sidebar: conversation list ── */}
        <div className="w-80 shrink-0 border-r border-slate-800 flex flex-col bg-slate-900/50">
          {/* Search + filter */}
          <div className="p-3 border-b border-slate-800 space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <Input
                placeholder="Buscar por nombre o teléfono..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9 bg-slate-800 border-slate-700 text-white text-sm h-9"
              />
            </div>
            <div className="flex gap-1 flex-wrap">
              {['all', ...Object.keys(STATUS_CONFIG)].map(key => (
                <button
                  key={key}
                  onClick={() => setFilterStatus(key)}
                  className={`px-2 py-0.5 rounded text-xs font-medium transition-all ${
                    filterStatus === key
                      ? (key === 'all' ? 'bg-slate-600 text-white' : STATUS_CONFIG[key]?.color || 'bg-slate-600 text-white')
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {key === 'all' ? 'Todos' : STATUS_CONFIG[key]?.label}
                </button>
              ))}
            </div>
          </div>

          {/* Lead list */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/50">
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" />
              </div>
            ) : filteredLeads.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-slate-500 px-4 text-center">
                <MessageCircle className="w-8 h-8 mb-2 opacity-20" />
                <p className="text-xs">No hay conversaciones</p>
              </div>
            ) : filteredLeads.map(lead => {
              const isSelected = selectedLead?.id === lead.id;
              const cfg = STATUS_CONFIG[lead.status] || STATUS_CONFIG.nuevo;
              return (
                <button
                  key={lead.id}
                  onClick={() => setSelectedLead(lead)}
                  className={`w-full p-3 text-left hover:bg-slate-800/60 transition-colors ${isSelected ? 'bg-slate-800' : ''}`}
                >
                  <div className="flex items-start gap-3">
                    {/* Avatar with status dot */}
                    <div className="relative shrink-0">
                      <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center">
                        <User className="w-5 h-5 text-slate-400" />
                      </div>
                      <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-slate-900 ${cfg.dot}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-sm font-semibold text-white truncate">
                          {lead.name || lead.phone}
                        </span>
                        <span className="text-[10px] text-slate-500 shrink-0">
                          {formatTime(lead.last_interaction)}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 truncate">{lead.phone}</p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <StatusBadge status={lead.status} />
                        {lead.line_name && (
                          <span className="text-[10px] text-slate-500 truncate flex items-center gap-0.5">
                            <Smartphone className="w-2.5 h-2.5" />{lead.line_name}
                          </span>
                        )}
                        {lead.messages_count > 0 && (
                          <span className="text-[10px] text-slate-600 ml-auto">{lead.messages_count} msgs</span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Right: chat panel ── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!selectedLead ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
              <MessageCircle className="w-16 h-16 mb-4 opacity-10" />
              <p className="text-sm font-medium">Seleccioná una conversación</p>
              <p className="text-xs mt-1 text-slate-600">Los mensajes de WhatsApp aparecerán aquí</p>
            </div>
          ) : (
            <>
              {/* Chat header */}
              <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-slate-700 flex items-center justify-center">
                    <User className="w-4 h-4 text-slate-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white leading-tight">
                      {selectedLead.name || selectedLead.phone}
                    </p>
                    <p className="text-xs text-slate-400">{selectedLead.phone}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {selectedLead.line_name && (
                    <span className="text-xs text-slate-400 hidden sm:flex items-center gap-1">
                      <Smartphone className="w-3 h-3" />{selectedLead.line_name}
                    </span>
                  )}
                  <StatusSelector
                    currentStatus={selectedLead.status}
                    onSelect={(status) => changeStatus(selectedLead.id, status)}
                  />
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {loadingMessages ? (
                  <div className="flex items-center justify-center h-20">
                    <RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" />
                  </div>
                ) : messages.length === 0 ? (
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
                    placeholder="Escribir mensaje..."
                    value={newMessage}
                    onChange={e => setNewMessage(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                    className="flex-1 bg-slate-800 border-slate-700 text-white text-sm"
                    disabled={sending}
                  />
                  <Button
                    onClick={sendMessage}
                    disabled={sending || !newMessage.trim()}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white px-4"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
