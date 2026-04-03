import React, { useState, useEffect, useCallback } from 'react';
import { Globe, Plus, Trash2, Edit, Eye, Copy, X, ExternalLink, Phone, BarChart3, MousePointerClick, MessageCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import api from '@/utils/api';

const DEFAULT_FORM = {
  name: '', brand_name: '', logo_url: '', bg_image_url: '',
  color_primary: '#9A3ACD', color_glow: '#611589',
  title: 'ACCESO VIP', title_color: '#FFFFFF',
  subtitle: '', subtitle_color: '#FFFFFF',
  bonus_text: '', bonus_color: '#FFFFFF',
  button_text: 'Ir a WhatsApp Ahora', button_color: '#FFFFFF', button_bg: '#4AD810',
  wa_numbers: [''], wa_message: 'Hola! Quiero mi usuario.',
  show_reviews: true, show_notifications: true, is_active: true,
  pixel_id: '', pixel_events: ['PageView', 'Lead'],
  meta_access_token: '',
};

export default function WALandings() {
  const [landings, setLandings] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({ ...DEFAULT_FORM });
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState({});

  const baseUrl = (process.env.REACT_APP_BACKEND_URL || window.location.origin).replace(/\/$/, '');

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/wa-landings');
      setLandings(data);
      data.forEach(async (l) => {
        try {
          const { data: s } = await api.get(`/wa-landings/${l.id}/stats`);
          setStats(prev => ({ ...prev, [l.id]: s }));
        } catch {}
      });
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setField = (key, val) => setForm(p => ({ ...p, [key]: val }));

  const setNumber = (idx, val) => {
    const nums = [...form.wa_numbers];
    nums[idx] = val;
    setForm(p => ({ ...p, wa_numbers: nums }));
  };
  const addNumber = () => setForm(p => ({ ...p, wa_numbers: [...p.wa_numbers, ''] }));
  const removeNumber = (idx) => {
    if (form.wa_numbers.length <= 1) return;
    setForm(p => ({ ...p, wa_numbers: p.wa_numbers.filter((_, i) => i !== idx) }));
  };

  const openEdit = (landing) => {
    setEditId(landing.id);
    setForm({
      name: landing.name || '', brand_name: landing.brand_name || '',
      logo_url: landing.logo_url || '', bg_image_url: landing.bg_image_url || '',
      color_primary: landing.color_primary || '#9A3ACD', color_glow: landing.color_glow || '#611589',
      title: landing.title || '', title_color: landing.title_color || '#FFFFFF',
      subtitle: landing.subtitle || '', subtitle_color: landing.subtitle_color || '#FFFFFF',
      bonus_text: landing.bonus_text || '', bonus_color: landing.bonus_color || '#FFFFFF',
      button_text: landing.button_text || 'Ir a WhatsApp Ahora',
      button_color: landing.button_color || '#FFFFFF', button_bg: landing.button_bg || '#4AD810',
      wa_numbers: landing.wa_numbers?.length ? landing.wa_numbers : [''],
      wa_message: landing.wa_message || '',
      show_reviews: landing.show_reviews ?? true, show_notifications: landing.show_notifications ?? true,
      is_active: landing.is_active ?? true,
      pixel_id: landing.pixel_id || '',
      pixel_events: landing.pixel_events?.length ? landing.pixel_events : ['PageView', 'Lead'],
      meta_access_token: landing.meta_access_token || '',
    });
    setShowForm(true);
  };

  const openNew = () => {
    setEditId(null);
    setForm({ ...DEFAULT_FORM, wa_numbers: [''] });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.name) return toast.error('Nombre requerido');
    const nums = form.wa_numbers.filter(n => n.trim());
    if (nums.length === 0) return toast.error('Al menos un numero de WhatsApp');
    setSaving(true);
    try {
      const payload = { ...form, wa_numbers: nums };
      if (editId) {
        await api.put(`/wa-landings/${editId}`, payload);
        toast.success('Landing actualizada');
      } else {
        await api.post('/wa-landings', payload);
        toast.success('Landing creada');
      }
      setShowForm(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error guardando');
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    if (!window.confirm('Eliminar esta landing?')) return;
    try {
      await api.delete(`/wa-landings/${id}`);
      toast.success('Eliminada');
      load();
    } catch { toast.error('Error eliminando'); }
  };

  const copyUrl = (code) => {
    navigator.clipboard.writeText(`${baseUrl}/l/${code}`);
    toast.success('URL copiada');
  };

  return (
    <div data-testid="wa-landings-page" className="min-h-screen bg-slate-950 p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="bg-purple-500/20 p-2.5 rounded-xl border border-purple-500/30">
              <Globe className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Landings WhatsApp</h1>
              <p className="text-sm text-slate-400">Crea landing pages con redireccion a WhatsApp</p>
            </div>
          </div>
          <Button data-testid="create-landing-btn" onClick={openNew} className="bg-purple-600 hover:bg-purple-500 text-white">
            <Plus className="w-4 h-4 mr-2" /> Nueva Landing
          </Button>
        </div>

        {/* Landing List */}
        {!showForm && (
          <div className="grid gap-4">
            {landings.length === 0 ? (
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-12 text-center">
                <Globe className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400">No hay landings creadas</p>
                <p className="text-slate-500 text-sm mt-1">Crea tu primera landing page con boton de WhatsApp</p>
              </div>
            ) : landings.map(l => {
              const s = stats[l.id] || {};
              return (
                <div key={l.id} data-testid={`landing-${l.code}`}
                  className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-white font-semibold truncate">{l.name}</h3>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full border ${l.is_active ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}`}>
                        {l.is_active ? 'Activa' : 'Inactiva'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                      <code className="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">/l/{l.code}</code>
                      <button onClick={() => copyUrl(l.code)} className="text-slate-500 hover:text-white transition-colors">
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span className="flex items-center gap-1"><Phone className="w-3 h-3" /> {l.wa_numbers?.length || 0} numeros</span>
                      <span className="flex items-center gap-1"><MousePointerClick className="w-3 h-3" /> {s.total_clicks ?? l.total_clicks ?? 0} visitas</span>
                      <span className="flex items-center gap-1"><MessageCircle className="w-3 h-3" /> {s.wa_clicks ?? l.total_wa_clicks ?? 0} WA clicks</span>
                      <span className="flex items-center gap-1"><BarChart3 className="w-3 h-3" /> {s.clicks_today ?? 0} hoy</span>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <a href={`${baseUrl}/l/${l.code}`} target="_blank" rel="noopener noreferrer"
                      className="p-2 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:border-slate-500 transition-all">
                      <Eye className="w-4 h-4" />
                    </a>
                    <button data-testid={`edit-${l.code}`} onClick={() => openEdit(l)}
                      className="p-2 rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:border-slate-500 transition-all">
                      <Edit className="w-4 h-4" />
                    </button>
                    <button data-testid={`delete-${l.code}`} onClick={() => remove(l.id)}
                      className="p-2 rounded-lg border border-red-800/50 text-red-400/60 hover:text-red-400 hover:border-red-500/50 transition-all">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Create/Edit Form */}
        {showForm && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-white font-semibold text-lg">{editId ? 'Editar Landing' : 'Nueva Landing'}</h2>
              <button onClick={() => setShowForm(false)} className="text-slate-500 hover:text-white"><X className="w-5 h-5" /></button>
            </div>

            {/* Basic */}
            <Section title="General">
              <Field label="Nombre interno" testId="form-name">
                <Input value={form.name} onChange={e => setField('name', e.target.value)} placeholder="Ej: Casino Truco" className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <Field label="Nombre de marca (se muestra en la landing)" testId="form-brand">
                <Input value={form.brand_name} onChange={e => setField('brand_name', e.target.value)} placeholder="Ej: RED OFICIAL" className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <div className="flex items-center gap-3">
                <input type="checkbox" checked={form.is_active} onChange={e => setField('is_active', e.target.checked)} className="w-4 h-4 rounded" />
                <span className="text-sm text-slate-300">Landing activa</span>
              </div>
            </Section>

            {/* Visual */}
            <Section title="Apariencia">
              <Field label="URL del logo (opcional)" testId="form-logo">
                <Input value={form.logo_url} onChange={e => setField('logo_url', e.target.value)} placeholder="https://..." className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <Field label="URL imagen de fondo (opcional)" testId="form-bg">
                <Input value={form.bg_image_url} onChange={e => setField('bg_image_url', e.target.value)} placeholder="https://..." className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <ColorField label="Color principal" value={form.color_primary} onChange={v => setField('color_primary', v)} />
                <ColorField label="Color brillo" value={form.color_glow} onChange={v => setField('color_glow', v)} />
              </div>
            </Section>

            {/* Content */}
            <Section title="Contenido">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Field label="Titulo principal" testId="form-title">
                  <Input value={form.title} onChange={e => setField('title', e.target.value)} className="bg-slate-800 border-slate-700 text-white" />
                </Field>
                <ColorField label="Color titulo" value={form.title_color} onChange={v => setField('title_color', v)} />
              </div>
              <Field label="Subtitulo" testId="form-subtitle">
                <Input value={form.subtitle} onChange={e => setField('subtitle', e.target.value)} placeholder="Ej: TE DAMOS UN 100% EXTRA" className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <Field label="Texto de bono" testId="form-bonus">
                <Input value={form.bonus_text} onChange={e => setField('bonus_text', e.target.value)} placeholder="Ej: BONO ACTIVO AL 100%" className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                  <input type="checkbox" checked={form.show_reviews} onChange={e => setField('show_reviews', e.target.checked)} className="w-4 h-4 rounded" />
                  Mostrar reviews falsos
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                  <input type="checkbox" checked={form.show_notifications} onChange={e => setField('show_notifications', e.target.checked)} className="w-4 h-4 rounded" />
                  Mostrar notificaciones de retiros
                </label>
              </div>
            </Section>

            {/* WhatsApp */}
            <Section title="WhatsApp">
              <div className="space-y-2">
                <label className="text-sm text-slate-400">Numeros de WhatsApp (rotacion automatica)</label>
                {form.wa_numbers.map((num, i) => (
                  <div key={i} className="flex gap-2">
                    <Input data-testid={`form-wa-number-${i}`} value={num} onChange={e => setNumber(i, e.target.value)}
                      placeholder="Ej: 5491150036293" className="bg-slate-800 border-slate-700 text-white" />
                    {form.wa_numbers.length > 1 && (
                      <button onClick={() => removeNumber(i)} className="text-red-400/60 hover:text-red-400 p-2"><Trash2 className="w-4 h-4" /></button>
                    )}
                  </div>
                ))}
                <Button variant="ghost" size="sm" onClick={addNumber} className="text-purple-400 hover:text-purple-300">
                  <Plus className="w-3 h-3 mr-1" /> Agregar numero
                </Button>
              </div>
              <Field label="Mensaje pre-armado" testId="form-wa-message">
                <Input value={form.wa_message} onChange={e => setField('wa_message', e.target.value)}
                  placeholder="Hola! Quiero mi usuario." className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <p className="text-xs text-slate-500">El click ID se agrega automaticamente al final: "Mensaje (ID: XXXXX)"</p>
            </Section>

            {/* Button */}
            <Section title="Boton">
              <Field label="Texto del boton" testId="form-btn-text">
                <Input value={form.button_text} onChange={e => setField('button_text', e.target.value)} className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <ColorField label="Color texto boton" value={form.button_color} onChange={v => setField('button_color', v)} />
                <ColorField label="Fondo boton" value={form.button_bg} onChange={v => setField('button_bg', v)} />
              </div>
            </Section>

            {/* Meta Pixel */}
            <Section title="Meta Pixel (Facebook/Instagram Ads)">
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mb-3">
                <p className="text-blue-400 text-sm font-medium mb-1">🎯 Importante para optimizar tus anuncios</p>
                <p className="text-blue-300/70 text-xs">El Pixel de Meta permite trackear conversiones y optimizar tus campañas. Sin Pixel, Meta no puede encontrar audiencias similares a quienes convierten.</p>
              </div>
              <Field label="Pixel ID" testId="form-pixel-id">
                <Input value={form.pixel_id} onChange={e => setField('pixel_id', e.target.value)} 
                  placeholder="Ej: 1234567890123456" className="bg-slate-800 border-slate-700 text-white" />
              </Field>
              <p className="text-xs text-slate-500 mb-3">Encuentra tu Pixel ID en: Meta Business Suite → Eventos → Origenes de datos → Tu Pixel</p>
              
              <Field label="Access Token (para Conversions API)" testId="form-access-token">
                <Input value={form.meta_access_token} onChange={e => setField('meta_access_token', e.target.value)} 
                  placeholder="EAAxxxxxx..." className="bg-slate-800 border-slate-700 text-white font-mono text-xs" />
              </Field>
              <p className="text-xs text-slate-500 mb-3">Opcional pero recomendado. Permite enviar eventos desde el servidor para mayor precision. Generalo en: Meta Business Suite → Configuracion del pixel → Conversions API</p>
              
              <div className="space-y-2">
                <label className="text-sm text-slate-400">Eventos a trackear (Frontend - Pixel JS):</label>
                <div className="flex flex-wrap gap-3">
                  {['PageView', 'Lead', 'Contact', 'InitiateCheckout'].map(event => (
                    <label key={event} className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={form.pixel_events?.includes(event)} 
                        onChange={e => {
                          if (e.target.checked) {
                            setField('pixel_events', [...(form.pixel_events || []), event]);
                          } else {
                            setField('pixel_events', (form.pixel_events || []).filter(ev => ev !== event));
                          }
                        }} 
                        className="w-4 h-4 rounded" 
                      />
                      {event}
                    </label>
                  ))}
                </div>
                <p className="text-xs text-slate-500">
                  <strong>PageView:</strong> Al cargar la landing | 
                  <strong> Lead:</strong> Al hacer click en WhatsApp
                </p>
              </div>
              
              <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3 mt-3">
                <p className="text-emerald-400 text-sm font-medium mb-1">📡 Conversions API (Backend)</p>
                <p className="text-emerald-300/70 text-xs">Si configuras el Access Token, tambien se enviaran eventos Lead desde el servidor cuando hacen click en WhatsApp. Esto mejora la medicion porque no depende de cookies bloqueadas.</p>
              </div>
            </Section>

            <div className="flex gap-3 pt-2">
              <Button data-testid="save-landing-btn" onClick={save} disabled={saving} className="bg-purple-600 hover:bg-purple-500 text-white">
                {saving ? 'Guardando...' : editId ? 'Guardar Cambios' : 'Crear Landing'}
              </Button>
              <Button variant="ghost" onClick={() => setShowForm(false)} className="text-slate-400">Cancelar</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-1">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, testId, children }) {
  return (
    <div data-testid={testId}>
      <label className="text-sm text-slate-400 block mb-1">{label}</label>
      {children}
    </div>
  );
}

function ColorField({ label, value, onChange }) {
  return (
    <div>
      <label className="text-sm text-slate-400 block mb-1">{label}</label>
      <div className="flex gap-2 items-center">
        <input type="color" value={value} onChange={e => onChange(e.target.value)}
          className="w-8 h-8 rounded border border-slate-700 cursor-pointer bg-transparent" />
        <Input value={value} onChange={e => onChange(e.target.value)}
          className="bg-slate-800 border-slate-700 text-white text-sm w-28" />
      </div>
    </div>
  );
}
