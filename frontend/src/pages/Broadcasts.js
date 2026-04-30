import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Megaphone, Upload, Users, Ban, FileText, Play, Pause, X as XIcon,
  RefreshCw, Calendar, AlertCircle, CheckCircle2, Clock, Trash2, Plus,
  Eye, Send, Filter, FilePlus,
} from 'lucide-react';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

// ── Shared helpers ─────────────────────────────────────────────────
const fmt = (iso) => iso ? new Date(iso).toLocaleString('es-AR', { hour12: false }) : '—';

const STATUS_COLORS = {
  draft:     { bg: 'bg-slate-700', text: 'text-slate-300', label: 'Borrador' },
  scheduled: { bg: 'bg-violet-500/20', text: 'text-violet-300', label: 'Programada' },
  running:   { bg: 'bg-emerald-500/20', text: 'text-emerald-300', label: 'Enviando' },
  paused:    { bg: 'bg-amber-500/20', text: 'text-amber-300', label: 'Pausada' },
  completed: { bg: 'bg-blue-500/20', text: 'text-blue-300', label: 'Completada' },
  cancelled: { bg: 'bg-red-500/20', text: 'text-red-300', label: 'Cancelada' },
  failed:    { bg: 'bg-red-500/20', text: 'text-red-300', label: 'Falló' },
};

const StatusBadge = ({ status }) => {
  const c = STATUS_COLORS[status] || STATUS_COLORS.draft;
  return <span className={`text-[10px] px-2 py-0.5 rounded ${c.bg} ${c.text} font-medium`} data-testid={`campaign-status-${status}`}>{c.label}</span>;
};

const StatPill = ({ icon: Icon, label, value, color = 'text-slate-300', testid }) => (
  <div className="flex items-center gap-1.5" data-testid={testid}>
    {Icon && <Icon className={`w-3.5 h-3.5 ${color}`} />}
    <span className="text-[11px] text-slate-500">{label}:</span>
    <span className={`text-xs font-semibold ${color}`}>{value}</span>
  </div>
);

// ── Lines selector hook ────────────────────────────────────────────
// Returns the lines the current user can actually use:
//  - admin → all lines
//  - cajero → only the lines listed in current_user.line_ids
const useLines = () => {
  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const [linesRes, meRes] = await Promise.all([
          api.get('/crm/lines'),
          api.get('/auth/me').catch(() => ({ data: null })),
        ]);
        const meData = meRes.data;
        setMe(meData);
        const allLines = linesRes.data.lines || linesRes.data || [];
        if (meData?.role === 'cajero') {
          const allowed = new Set(meData.line_ids || []);
          setLines(allLines.filter(l => allowed.has(l.id)));
        } else {
          setLines(allLines);
        }
      } catch { /* silent */ }
      finally { setLoading(false); }
    })();
  }, []);
  return { lines, loading, me };
};

// ════════════════════════════════════════════════════════════════════
// AUDIENCIAS TAB
// ════════════════════════════════════════════════════════════════════

const AudienceUploader = ({ lines, onUploaded }) => {
  const [open, setOpen] = useState(false);
  const [lineId, setLineId] = useState('');
  const [name, setName] = useState('');
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const close = () => { setOpen(false); setName(''); setFile(null); setLineId(''); };

  const submit = async () => {
    if (!lineId || !name || !file) {
      toast.error('Completá todos los campos y elegí un CSV');
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('line_id', lineId);
      fd.append('name', name);
      const { data } = await api.post('/broadcasts/audiences/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const a = data.audience;
      toast.success(`Audiencia "${a.name}" creada con ${a.total_contacts} contactos válidos`);
      onUploaded?.();
      close();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error subiendo CSV');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button onClick={() => setOpen(true)} className="bg-emerald-600 hover:bg-emerald-500" data-testid="audience-new-btn">
        <Plus className="w-4 h-4 mr-1" /> Nueva audiencia
      </Button>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" data-testid="audience-uploader-modal">
          <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-base font-semibold text-white">Subir audiencia desde CSV</p>
              <button onClick={close} className="p-1.5 rounded hover:bg-slate-800 text-slate-400"><XIcon className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <Label className="text-xs text-slate-400">Línea</Label>
                <select
                  value={lineId} onChange={e => setLineId(e.target.value)}
                  data-testid="audience-line-select"
                  className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-sm text-white"
                >
                  <option value="">Elegí una línea…</option>
                  {lines.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </div>
              <div>
                <Label className="text-xs text-slate-400">Nombre de la audiencia</Label>
                <Input value={name} onChange={e => setName(e.target.value)} placeholder="Ej: Compradores marzo"
                  className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1"
                  data-testid="audience-name-input" />
              </div>
              <div>
                <Label className="text-xs text-slate-400">Archivo CSV</Label>
                <div
                  onClick={() => inputRef.current?.click()}
                  className="mt-1 cursor-pointer border-2 border-dashed border-slate-600 hover:border-emerald-500/50 rounded p-4 text-center text-slate-400 text-xs"
                >
                  {file ? `${file.name} (${(file.size/1024).toFixed(1)} KB)` : 'Click para elegir CSV o arrastrá acá'}
                </div>
                <input
                  ref={inputRef} type="file" accept=".csv,text/csv" hidden
                  onChange={e => setFile(e.target.files?.[0] || null)}
                  data-testid="audience-file-input"
                />
              </div>
              <div className="rounded bg-slate-800/50 p-2 text-[11px] text-slate-400 leading-relaxed">
                <p className="font-medium text-slate-300 mb-1">Columnas requeridas/aceptadas:</p>
                <p>• <span className="font-mono text-slate-200">phone</span> (o telefono / tel / celular) — obligatorio</p>
                <p>• <span className="font-mono text-slate-200">name</span> (o nombre) — opcional</p>
                <p>• <span className="font-mono text-slate-200">var1</span>, var2, var3… — variables para la plantilla</p>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" onClick={close} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="audience-cancel-btn">Cancelar</Button>
              <Button onClick={submit} disabled={busy} className="bg-emerald-600 hover:bg-emerald-500" data-testid="audience-submit-btn">
                {busy ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />}
                Subir
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

const AudiencesTab = ({ lines, onSelect }) => {
  const [audiences, setAudiences] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/broadcasts/audiences');
      setAudiences(data.audiences || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (id) => {
    if (!window.confirm('¿Eliminar esta audiencia? Los contactos asociados se borrarán.')) return;
    try {
      await api.delete(`/broadcasts/audiences/${id}`);
      toast.success('Audiencia eliminada');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-300">{audiences.length} audiencia(s)</p>
          <p className="text-[11px] text-slate-500">Listas de contactos que podés usar para campañas masivas.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="audiences-refresh-btn">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
          <AudienceUploader lines={lines} onUploaded={load} />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32"><RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" /></div>
      ) : audiences.length === 0 ? (
        <div className="text-center py-12 text-slate-400" data-testid="audiences-empty">
          <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
          <p className="text-sm">Sin audiencias todavía. Empezá subiendo un CSV.</p>
        </div>
      ) : (
        <div className="grid gap-2" data-testid="audiences-list">
          {audiences.map(a => (
            <div key={a.id} className="rounded-lg border border-slate-700/50 bg-slate-900/50 p-3 hover:border-emerald-500/30 transition-colors" data-testid={`audience-row-${a.id}`}>
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-500/15 flex items-center justify-center shrink-0">
                  <Users className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-white truncate">{a.name}</p>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">{a.line_name}</span>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {a.total_contacts} válidos · {a.stats?.invalid || 0} inválidos · {a.stats?.duplicates || 0} dup · {a.stats?.excluded_optouts || 0} optouts excluidos · {fmt(a.created_at)}
                  </p>
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => onSelect?.(a)} className="h-7 px-2 border-emerald-700/50 text-emerald-300 hover:bg-emerald-500/10" data-testid={`audience-use-${a.id}`}>
                    <Send className="w-3 h-3 mr-1" /> Usar
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => remove(a.id)} className="h-7 px-2 border-slate-600 text-slate-400 hover:text-red-300 hover:bg-red-500/10" data-testid={`audience-delete-${a.id}`}>
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ════════════════════════════════════════════════════════════════════
// CAMPAIGNS TAB + WIZARD
// ════════════════════════════════════════════════════════════════════

const CampaignWizard = ({ lines, audiences, prefilledAudience, onClose, onCreated }) => {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [lineId, setLineId] = useState(prefilledAudience?.line_id || '');
  const [audienceId, setAudienceId] = useState(prefilledAudience?.id || '');
  const [useSegment, setUseSegment] = useState(false);
  const [segPurchaseDays, setSegPurchaseDays] = useState('');
  const [segStatuses, setSegStatuses] = useState([]);
  const [segPreview, setSegPreview] = useState(null);

  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesError, setTemplatesError] = useState('');
  const [selectedTpl, setSelectedTpl] = useState(null);
  const [varMapping, setVarMapping] = useState([]); // [{from: 'name'|'var1'|...}]
  const [scheduledAt, setScheduledAt] = useState('');
  const [resendAfterHours, setResendAfterHours] = useState('');
  const [resendTemplateName, setResendTemplateName] = useState('');
  const [busy, setBusy] = useState(false);

  const audForLine = useMemo(
    () => audiences.filter(a => a.line_id === lineId),
    [audiences, lineId]
  );

  // Load templates when line changes (and we're past step 1)
  useEffect(() => {
    if (!lineId || step < 2) return;
    setTemplatesLoading(true); setTemplatesError('');
    api.get(`/broadcasts/templates?line_id=${lineId}`)
      .then(({ data }) => {
        setTemplates(data.templates || []);
        if (data.error) setTemplatesError(data.error);
      })
      .catch(e => setTemplatesError(e?.response?.data?.detail || 'Error cargando plantillas'))
      .finally(() => setTemplatesLoading(false));
  }, [lineId, step]);

  // Update var mapping when template changes
  useEffect(() => {
    if (selectedTpl) {
      setVarMapping(Array(selectedTpl.var_count).fill('').map((_, i) => i === 0 ? 'name' : `var${i}`));
    } else {
      setVarMapping([]);
    }
  }, [selectedTpl]);

  const previewSegment = async () => {
    if (!lineId) return;
    try {
      const { data } = await api.post('/broadcasts/segments/preview', {
        line_id: lineId,
        purchase_in_last_days: segPurchaseDays ? Number(segPurchaseDays) : null,
        statuses: segStatuses.length ? segStatuses : null,
      });
      setSegPreview(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error en segmento');
    }
  };

  const submit = async () => {
    if (!name || !lineId || !selectedTpl) {
      toast.error('Completá nombre, línea y plantilla');
      return;
    }
    if (!useSegment && !audienceId) { toast.error('Elegí audiencia o segmento'); return; }

    setBusy(true);
    try {
      const body = {
        line_id: lineId,
        name,
        template_name: selectedTpl.name,
        template_language: selectedTpl.language || 'es_AR',
        template_var_mapping: varMapping,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      };
      if (resendAfterHours && resendTemplateName) {
        body.resend_after_hours = Number(resendAfterHours);
        body.resend_template_name = resendTemplateName;
      }
      if (useSegment) {
        body.segment = {
          line_id: lineId,
          purchase_in_last_days: segPurchaseDays ? Number(segPurchaseDays) : null,
          statuses: segStatuses.length ? segStatuses : null,
        };
      } else {
        body.audience_id = audienceId;
      }
      const { data } = await api.post('/broadcasts/campaigns', body);
      toast.success(`Campaña "${data.campaign.name}" creada (${data.campaign.target_count} contactos)`);
      onCreated?.(data.campaign);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error creando campaña');
    } finally { setBusy(false); }
  };

  const targetCount = useSegment ? (segPreview?.total ?? 0) : (audForLine.find(a => a.id === audienceId)?.total_contacts ?? 0);
  const estimatedHours = targetCount ? Math.ceil(targetCount * 60 / 3600) : 0;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" data-testid="campaign-wizard-modal">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-base font-semibold text-white">Nueva campaña — Paso {step} de 3</p>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-slate-800 text-slate-400" data-testid="wizard-close-btn"><XIcon className="w-4 h-4" /></button>
        </div>

        {/* Step indicator */}
        <div className="flex gap-1 mb-4">
          {[1,2,3].map(s => (
            <div key={s} className={`h-1 flex-1 rounded ${step >= s ? 'bg-emerald-500' : 'bg-slate-700'}`} />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-3">
            <div>
              <Label className="text-xs text-slate-400">Línea</Label>
              <select value={lineId} onChange={e => { setLineId(e.target.value); setAudienceId(''); }} className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-sm text-white" data-testid="wizard-line-select">
                <option value="">Elegí una línea…</option>
                {lines.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            <div>
              <Label className="text-xs text-slate-400">Nombre de la campaña</Label>
              <Input value={name} onChange={e => setName(e.target.value)} placeholder="Ej: Promo bono octubre"
                className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1" data-testid="wizard-name-input" />
            </div>

            <div className="rounded border border-slate-700 p-3">
              <div className="flex items-center gap-2 mb-2">
                <button onClick={() => setUseSegment(false)} className={`text-xs px-3 py-1 rounded ${!useSegment ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}`} data-testid="wizard-source-audience-btn">Audiencia (CSV)</button>
                <button onClick={() => setUseSegment(true)} className={`text-xs px-3 py-1 rounded ${useSegment ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}`} data-testid="wizard-source-segment-btn">Segmento (filtros)</button>
              </div>

              {!useSegment ? (
                <div>
                  <Label className="text-xs text-slate-400">Audiencia</Label>
                  <select value={audienceId} onChange={e => setAudienceId(e.target.value)} disabled={!lineId} className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-sm text-white disabled:opacity-50" data-testid="wizard-audience-select">
                    <option value="">{lineId ? 'Elegí una audiencia…' : 'Primero elegí una línea'}</option>
                    {audForLine.map(a => <option key={a.id} value={a.id}>{a.name} ({a.total_contacts})</option>)}
                  </select>
                </div>
              ) : (
                <div className="space-y-2">
                  <div>
                    <Label className="text-xs text-slate-400">Compraron en los últimos N días (opcional)</Label>
                    <Input type="number" min="1" placeholder="Ej: 30" value={segPurchaseDays} onChange={e => setSegPurchaseDays(e.target.value)}
                      className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1" data-testid="wizard-seg-purchase-days" />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-400">Estados a incluir</Label>
                    <div className="flex gap-1 mt-1 flex-wrap">
                      {['nuevo','consulta','valido','spam'].map(s => (
                        <button key={s} onClick={() => setSegStatuses(prev => prev.includes(s) ? prev.filter(x=>x!==s) : [...prev, s])}
                          className={`text-[11px] px-2 py-1 rounded border ${segStatuses.includes(s) ? 'bg-emerald-600 border-emerald-500 text-white' : 'border-slate-600 text-slate-400'}`}
                          data-testid={`wizard-seg-status-${s}`}>
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                  <Button size="sm" variant="outline" onClick={previewSegment} disabled={!lineId} className="border-emerald-700/50 text-emerald-300 hover:bg-emerald-500/10" data-testid="wizard-seg-preview-btn">
                    <Eye className="w-3.5 h-3.5 mr-1" /> Previsualizar
                  </Button>
                  {segPreview && (
                    <div className="text-xs text-slate-300" data-testid="wizard-seg-preview-result">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 inline-block mr-1" />
                      {segPreview.total} contactos cumplen el filtro
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <Button onClick={() => setStep(2)} disabled={!lineId || !name || (!useSegment && !audienceId)} className="bg-emerald-600 hover:bg-emerald-500" data-testid="wizard-step1-next">
                Siguiente
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <p className="text-sm text-slate-400">Elegí una plantilla aprobada por Meta:</p>
            {templatesLoading ? (
              <div className="flex items-center justify-center h-24"><RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" /></div>
            ) : templatesError ? (
              <div className="rounded bg-red-500/10 border border-red-500/30 p-3 text-xs text-red-300 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">{templatesError}</p>
                  <p className="text-red-300/70 mt-1">Cargá el WhatsApp Business Account ID en la línea y plantillas aprobadas en Meta Business.</p>
                </div>
              </div>
            ) : templates.length === 0 ? (
              <p className="text-sm text-slate-400 italic">Esta línea no tiene plantillas aprobadas todavía.</p>
            ) : (
              <div className="grid gap-2 max-h-72 overflow-y-auto" data-testid="wizard-templates-list">
                {templates.map(t => (
                  <button key={t.name + t.language} onClick={() => setSelectedTpl(t)}
                    className={`text-left p-3 rounded border transition-colors ${selectedTpl?.name === t.name ? 'border-emerald-500 bg-emerald-500/10' : 'border-slate-700 hover:border-slate-600'}`}
                    data-testid={`wizard-template-${t.name}`}>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-white">{t.name}</p>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">{t.language}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300">{t.category}</span>
                      {t.var_count > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">{t.var_count} vars</span>}
                    </div>
                    {t.body_text && <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{t.body_text}</p>}
                  </button>
                ))}
              </div>
            )}

            {selectedTpl && selectedTpl.var_count > 0 && (
              <div className="rounded border border-slate-700 p-3 space-y-2">
                <p className="text-xs font-medium text-slate-300">Mapear variables {`{{1}}…{{${selectedTpl.var_count}}}`}</p>
                {Array.from({ length: selectedTpl.var_count }).map((_, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400 shrink-0 w-12">{`{{${i+1}}}`}</span>
                    <select
                      value={varMapping[i] || ''}
                      onChange={e => setVarMapping(prev => { const n = [...prev]; n[i] = e.target.value; return n; })}
                      className="flex-1 bg-slate-800 border border-slate-600 rounded h-8 px-2 text-xs text-white"
                      data-testid={`wizard-var-${i}`}
                    >
                      <option value="">— sin valor —</option>
                      <option value="name">name (nombre del contacto)</option>
                      {[1,2,3,4,5].map(n => <option key={n} value={`var${n}`}>var{n}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="wizard-step2-back">Atrás</Button>
              <Button onClick={() => setStep(3)} disabled={!selectedTpl} className="bg-emerald-600 hover:bg-emerald-500" data-testid="wizard-step2-next">Siguiente</Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <div className="rounded border border-slate-700 bg-slate-800/40 p-3 space-y-1.5 text-xs">
              <p className="text-slate-400"><span className="text-slate-300 font-medium">Línea:</span> {lines.find(l => l.id === lineId)?.name}</p>
              <p className="text-slate-400"><span className="text-slate-300 font-medium">Plantilla:</span> {selectedTpl?.name}</p>
              <p className="text-slate-400"><span className="text-slate-300 font-medium">Contactos objetivo:</span> {targetCount}</p>
              <p className="text-slate-400"><span className="text-slate-300 font-medium">Tiempo estimado:</span> ~{estimatedHours}hs (envío cauta 30-90s, pausa nocturna 23-9 ART)</p>
            </div>

            <div>
              <Label className="text-xs text-slate-400">Programar envío (opcional, deja vacío para iniciar manualmente después)</Label>
              <Input type="datetime-local" value={scheduledAt} onChange={e => setScheduledAt(e.target.value)}
                className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1" data-testid="wizard-scheduled-at" />
            </div>

            <div className="rounded border border-slate-700 p-3 space-y-2" data-testid="wizard-resend-section">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
                <p className="text-xs font-medium text-slate-300">Auto re-envío (opcional)</p>
              </div>
              <p className="text-[11px] text-slate-500">
                Si lo configurás, después de N horas se re-envía con OTRA plantilla solo a los contactos que NO leyeron y NO respondieron. Los optouts se respetan.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-[11px] text-slate-400">Reintentar después de (horas)</Label>
                  <Input type="number" min="1" max="168" value={resendAfterHours}
                    onChange={e => setResendAfterHours(e.target.value)}
                    placeholder="Ej: 48"
                    className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1"
                    data-testid="wizard-resend-hours" />
                </div>
                <div>
                  <Label className="text-[11px] text-slate-400">Plantilla del re-envío</Label>
                  <select value={resendTemplateName}
                    onChange={e => setResendTemplateName(e.target.value)}
                    className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-xs text-white"
                    data-testid="wizard-resend-template">
                    <option value="">— sin re-envío —</option>
                    {templates.filter(t => t.name !== selectedTpl?.name).map(t => (
                      <option key={t.name} value={t.name}>{t.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              {resendAfterHours && !resendTemplateName && (
                <p className="text-[11px] text-amber-300">Elegí también una plantilla para el re-envío.</p>
              )}
              {!resendAfterHours && resendTemplateName && (
                <p className="text-[11px] text-amber-300">Elegí también las horas de espera.</p>
              )}
            </div>

            <div className="rounded bg-amber-500/10 border border-amber-500/30 p-2 text-[11px] text-amber-200/80 flex gap-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <p>Velocidad fija: 30-90s entre mensajes. Pausa nocturna 23:00-09:00 ART. Optouts se respetan automáticamente.</p>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="wizard-step3-back">Atrás</Button>
              <Button onClick={submit} disabled={busy} className="bg-emerald-600 hover:bg-emerald-500" data-testid="wizard-submit-btn">
                {busy ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-1" />}
                Crear campaña
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const CampaignsTab = ({ lines, audiences, prefilledAudience, onAudienceUsed }) => {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showWizard, setShowWizard] = useState(!!prefilledAudience);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/broadcasts/campaigns');
      setCampaigns(data.campaigns || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    // Auto-refresh every 5s if any campaign is running
    const hasRunning = campaigns.some(c => c.status === 'running');
    if (!hasRunning) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [campaigns, load]);

  const action = async (cid, kind) => {
    try {
      await api.post(`/broadcasts/campaigns/${cid}/${kind}`);
      toast.success(kind === 'start' ? 'Campaña iniciada' : kind === 'pause' ? 'Pausada' : 'Cancelada');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error');
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-300">{campaigns.length} campaña(s)</p>
          <p className="text-[11px] text-slate-500">Envío masivo escalonado con plantillas Meta. Velocidad cauta + pausa nocturna.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="campaigns-refresh-btn">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
          <Button onClick={() => setShowWizard(true)} className="bg-emerald-600 hover:bg-emerald-500" data-testid="campaign-new-btn">
            <Plus className="w-4 h-4 mr-1" /> Nueva campaña
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32"><RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" /></div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-12 text-slate-400" data-testid="campaigns-empty">
          <Megaphone className="w-10 h-10 mx-auto mb-2 opacity-30" />
          <p className="text-sm">Sin campañas todavía. Subí una audiencia y creá tu primera campaña.</p>
        </div>
      ) : (
        <div className="grid gap-2" data-testid="campaigns-list">
          {campaigns.map(c => {
            const total = c.target_count || 0;
            const sent = c.stats?.sent || 0;
            const failed = c.stats?.failed || 0;
            const skipped = c.stats?.skipped_optout || 0;
            const progress = total ? Math.round(((sent + failed + skipped) / total) * 100) : 0;
            return (
              <div key={c.id} className="rounded-lg border border-slate-700/50 bg-slate-900/50 p-3" data-testid={`campaign-row-${c.id}`}>
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-violet-500/15 flex items-center justify-center shrink-0">
                    <Megaphone className="w-4 h-4 text-violet-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-white truncate">{c.name}</p>
                      <StatusBadge status={c.status} />
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">{c.line_name}</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Plantilla: <span className="font-mono text-slate-400">{c.template_name}</span> · {fmt(c.created_at)}
                      {c.resend_after_hours && c.resend_template_name && (
                        <span className="ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 text-[10px]" data-testid={`campaign-${c.id}-resend-badge`}>
                          <RefreshCw className="w-2.5 h-2.5" />
                          Re-envío en {c.resend_after_hours}h
                          {c.resend_done_at && ' (hecho)'}
                        </span>
                      )}
                    </p>
                    {/* Progress bar */}
                    <div className="mt-2">
                      <div className="flex items-center gap-3 text-[11px] flex-wrap mb-1">
                        <StatPill icon={Send} label="enviados" value={`${sent}/${total}`} color="text-emerald-400" testid={`campaign-${c.id}-sent`} />
                        <StatPill icon={CheckCircle2} label="entregados" value={c.stats?.delivered || 0} color="text-blue-400" />
                        <StatPill icon={Eye} label="leídos" value={c.stats?.read || 0} color="text-violet-400" />
                        <StatPill label="respondieron" value={c.stats?.replied || 0} color="text-amber-400" />
                        {failed > 0 && <StatPill icon={AlertCircle} label="fallaron" value={failed} color="text-red-400" />}
                        {skipped > 0 && <StatPill icon={Ban} label="optouts" value={skipped} color="text-slate-500" />}
                        {(c.stats?.resent || 0) > 0 && (
                          <StatPill icon={RefreshCw} label="re-enviados" value={c.stats.resent} color="text-cyan-400" testid={`campaign-${c.id}-resent`} />
                        )}
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div className="h-full bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
                      </div>
                    </div>
                    {c.paused_reason && (
                      <p className="text-[11px] text-amber-300 mt-1">
                        <Clock className="w-3 h-3 inline-block mr-1" /> {c.paused_reason}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    {(c.status === 'draft' || c.status === 'paused') && (
                      <Button size="sm" onClick={() => action(c.id, 'start')} className="h-7 px-2 bg-emerald-600 hover:bg-emerald-500 text-white" data-testid={`campaign-start-${c.id}`}>
                        <Play className="w-3 h-3 mr-1" /> {c.status === 'paused' ? 'Reanudar' : 'Iniciar'}
                      </Button>
                    )}
                    {c.status === 'running' && (
                      <Button size="sm" variant="outline" onClick={() => action(c.id, 'pause')} className="h-7 px-2 border-amber-700/50 text-amber-300 hover:bg-amber-500/10" data-testid={`campaign-pause-${c.id}`}>
                        <Pause className="w-3 h-3 mr-1" /> Pausar
                      </Button>
                    )}
                    {!['completed','cancelled','failed'].includes(c.status) && (
                      <Button size="sm" variant="outline" onClick={() => action(c.id, 'cancel')} className="h-7 px-2 border-slate-600 text-slate-400 hover:text-red-300 hover:bg-red-500/10" data-testid={`campaign-cancel-${c.id}`}>
                        <XIcon className="w-3 h-3" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showWizard && (
        <CampaignWizard
          lines={lines}
          audiences={audiences}
          prefilledAudience={prefilledAudience}
          onClose={() => { setShowWizard(false); onAudienceUsed?.(); }}
          onCreated={load}
        />
      )}
    </div>
  );
};

// ════════════════════════════════════════════════════════════════════
// TEMPLATES TAB — create templates from the app and send to Meta for approval
// ════════════════════════════════════════════════════════════════════

const TEMPLATE_STATUS_META = {
  APPROVED: { bg: 'bg-emerald-500/20', text: 'text-emerald-300', label: 'Aprobada' },
  PENDING:  { bg: 'bg-amber-500/20', text: 'text-amber-300', label: 'Pendiente' },
  REJECTED: { bg: 'bg-red-500/20', text: 'text-red-300', label: 'Rechazada' },
  PAUSED:   { bg: 'bg-slate-500/20', text: 'text-slate-300', label: 'Pausada' },
  DISABLED: { bg: 'bg-slate-500/20', text: 'text-slate-300', label: 'Deshabilitada' },
};

const TemplateCreateModal = ({ lines, onClose, onCreated }) => {
  const [lineId, setLineId] = useState('');
  const [name, setName] = useState('');
  const [category, setCategory] = useState('MARKETING');
  const [language, setLanguage] = useState('es_AR');
  const [bodyText, setBodyText] = useState('');
  const [headerText, setHeaderText] = useState('');
  const [footerText, setFooterText] = useState('');
  const [busy, setBusy] = useState(false);

  // Detect variables in body to ask for example values (Meta requires them)
  const varCount = useMemo(() => {
    const matches = bodyText.match(/\{\{\d+\}\}/g) || [];
    return matches.length;
  }, [bodyText]);
  const [exampleVars, setExampleVars] = useState([]);
  useEffect(() => {
    setExampleVars(prev => {
      const next = [...prev];
      while (next.length < varCount) next.push('');
      return next.slice(0, varCount);
    });
  }, [varCount]);

  const submit = async () => {
    if (!lineId || !name || !bodyText) {
      toast.error('Completá línea, nombre y cuerpo del mensaje');
      return;
    }
    if (!/^[a-z0-9_]+$/.test(name)) {
      toast.error('El nombre debe ser snake_case (minúsculas, números, _)');
      return;
    }
    if (varCount && exampleVars.some(v => !v)) {
      toast.error('Meta exige un valor de ejemplo para cada variable');
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post('/broadcasts/templates/create', {
        line_id: lineId, name, category, language,
        body_text: bodyText,
        header_text: headerText || null,
        footer_text: footerText || null,
        example_body_vars: varCount ? exampleVars : null,
      });
      toast.success(`Plantilla enviada a Meta (status: ${data.status}). Aprobación llega en 1-24hs.`);
      onCreated?.();
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error creando plantilla');
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" data-testid="template-create-modal">
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-base font-semibold text-white">Crear plantilla</p>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-slate-800 text-slate-400" data-testid="template-close-btn">
            <XIcon className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-xs text-slate-400">Línea</Label>
              <select value={lineId} onChange={e => setLineId(e.target.value)}
                className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-sm text-white"
                data-testid="template-line-select">
                <option value="">Elegí…</option>
                {lines.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            <div>
              <Label className="text-xs text-slate-400">Idioma</Label>
              <select value={language} onChange={e => setLanguage(e.target.value)}
                className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-sm text-white"
                data-testid="template-lang-select">
                <option value="es_AR">Español (AR)</option>
                <option value="es">Español</option>
                <option value="es_MX">Español (MX)</option>
                <option value="pt_BR">Portugués (BR)</option>
                <option value="en">Inglés</option>
                <option value="en_US">Inglés (US)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-xs text-slate-400">Nombre (snake_case)</Label>
              <Input value={name} onChange={e => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
                placeholder="ej: betwin_promo_recarga_v1"
                className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1 font-mono"
                data-testid="template-name-input" />
            </div>
            <div>
              <Label className="text-xs text-slate-400">Categoría</Label>
              <select value={category} onChange={e => setCategory(e.target.value)}
                className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-sm text-white"
                data-testid="template-category-select">
                <option value="MARKETING">Marketing (promociones, bonos)</option>
                <option value="UTILITY">Utility (confirmaciones, updates)</option>
                <option value="AUTHENTICATION">Authentication (códigos OTP)</option>
              </select>
            </div>
          </div>

          <div>
            <Label className="text-xs text-slate-400">Encabezado de texto (opcional)</Label>
            <Input value={headerText} onChange={e => setHeaderText(e.target.value)}
              placeholder="Ej: Oferta exclusiva"
              className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1"
              data-testid="template-header-input" />
          </div>

          <div>
            <Label className="text-xs text-slate-400">
              Cuerpo del mensaje <span className="text-slate-500 font-normal">(usá {`{{1}}`}, {`{{2}}`}… para variables)</span>
            </Label>
            <textarea
              value={bodyText} onChange={e => setBodyText(e.target.value)}
              rows={5}
              placeholder="Hola {{1}}, tenemos una oferta para vos: {{2}}. Respondé este mensaje para recibir más info. Si no querés recibir más, escribí BAJA."
              className="w-full mt-1 bg-slate-800 border border-slate-600 rounded px-2 py-2 text-sm text-white resize-none font-mono"
              data-testid="template-body-textarea"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Detectadas: <span className="text-slate-300 font-semibold">{varCount}</span> variable{varCount === 1 ? '' : 's'}
            </p>
          </div>

          {varCount > 0 && (
            <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2 space-y-1.5" data-testid="template-examples-section">
              <p className="text-[11px] text-amber-200">Meta exige valores de ejemplo para aprobar. Completá uno por variable:</p>
              {Array.from({ length: varCount }).map((_, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-400 w-10">{`{{${i + 1}}}`}</span>
                  <Input
                    value={exampleVars[i] || ''}
                    onChange={e => setExampleVars(prev => { const n = [...prev]; n[i] = e.target.value; return n; })}
                    placeholder={`Ejemplo para variable ${i + 1}`}
                    className="bg-slate-800 border-slate-600 text-white text-xs h-8"
                    data-testid={`template-example-${i}`}
                  />
                </div>
              ))}
            </div>
          )}

          <div>
            <Label className="text-xs text-slate-400">Pie de página (opcional)</Label>
            <Input value={footerText} onChange={e => setFooterText(e.target.value)}
              placeholder="Ej: Respondé BAJA para dejar de recibir"
              className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1"
              data-testid="template-footer-input" />
          </div>

          <div className="rounded bg-blue-500/10 border border-blue-500/30 p-2 text-[11px] text-blue-200/80 flex gap-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Tips para que Meta apruebe:</p>
              <p>• Evitá lenguaje de gambling explícito (apuesta, cargá, ganá seguro). Usá "promoción", "oferta", "beneficio".</p>
              <p>• Incluí opt-out ("Respondé BAJA para no recibir más") — sube la tasa de aprobación.</p>
              <p>• Ejemplo de variables claros y reales, no placeholders tipo "xxx".</p>
            </div>
          </div>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="template-cancel-btn">Cancelar</Button>
          <Button onClick={submit} disabled={busy} className="bg-emerald-600 hover:bg-emerald-500" data-testid="template-submit-btn">
            {busy ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Send className="w-4 h-4 mr-1" />}
            Enviar a Meta
          </Button>
        </div>
      </div>
    </div>
  );
};

const TemplatesTab = ({ lines }) => {
  const [lineId, setLineId] = useState('');
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  // Auto-pick first line if user has one
  useEffect(() => {
    if (lines.length && !lineId) setLineId(lines[0].id);
  }, [lines, lineId]);

  const load = useCallback(async () => {
    if (!lineId) return;
    setLoading(true); setError('');
    try {
      const { data } = await api.get(`/broadcasts/templates?line_id=${lineId}&include_all=true`);
      setTemplates(data.templates || []);
      if (data.error) setError(data.error);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Error cargando plantillas');
      setTemplates([]);
    } finally { setLoading(false); }
  }, [lineId]);

  useEffect(() => { load(); }, [load]);

  const remove = async (tpl) => {
    if (!window.confirm(`¿Borrar la plantilla "${tpl.name}"?`)) return;
    try {
      await api.delete(`/broadcasts/templates?line_id=${lineId}&name=${encodeURIComponent(tpl.name)}`);
      toast.success('Plantilla borrada');
      load();
    } catch (e) {
      const detail = e?.response?.data?.detail || 'Error';
      // Long permission errors get rendered as a persistent dismissible toast with longer duration
      const isPerm = /permission|permisos|owner\/shared|whatsapp_business_management/i.test(detail);
      toast.error(detail, {
        duration: isPerm ? 15000 : 5000,
        style: { maxWidth: '520px', whiteSpace: 'pre-wrap' },
      });
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Label className="text-xs text-slate-400">Línea:</Label>
          <select value={lineId} onChange={e => setLineId(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded h-8 px-2 text-xs text-white"
            data-testid="templates-line-select">
            {lines.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
          <Button variant="outline" size="sm" onClick={load} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="templates-refresh-btn">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
        <Button onClick={() => setCreating(true)} disabled={!lineId} className="bg-emerald-600 hover:bg-emerald-500" data-testid="template-new-btn">
          <FilePlus className="w-4 h-4 mr-1" /> Nueva plantilla
        </Button>
      </div>

      {error && (
        <div className="rounded bg-red-500/10 border border-red-500/30 p-3 text-xs text-red-300 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-32"><RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" /></div>
      ) : templates.length === 0 ? (
        <div className="text-center py-12 text-slate-400" data-testid="templates-empty">
          <FileText className="w-10 h-10 mx-auto mb-2 opacity-30" />
          <p className="text-sm">Sin plantillas para esta línea. Creá la primera.</p>
        </div>
      ) : (
        <div className="grid gap-2" data-testid="templates-list">
          {templates.map(t => {
            const sm = TEMPLATE_STATUS_META[t.status] || TEMPLATE_STATUS_META.PENDING;
            return (
              <div key={t.name + t.language} className="rounded-lg border border-slate-700/50 bg-slate-900/50 p-3" data-testid={`template-row-${t.name}`}>
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-blue-500/15 flex items-center justify-center shrink-0">
                    <FileText className="w-4 h-4 text-blue-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-mono text-white truncate">{t.name}</p>
                      <span className={`text-[10px] px-2 py-0.5 rounded ${sm.bg} ${sm.text} font-medium`} data-testid={`template-status-${t.status}`}>{sm.label}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">{t.language}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300">{t.category}</span>
                      {t.var_count > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">{t.var_count} vars</span>}
                    </div>
                    {t.body_text && <p className="text-[11px] text-slate-400 mt-1 line-clamp-3 whitespace-pre-wrap">{t.body_text}</p>}
                    {t.rejected_reason && !['NONE', 'PENDING', null, ''].includes(t.rejected_reason) && (
                      <p className="text-[11px] text-red-300 mt-1">
                        <AlertCircle className="w-3 h-3 inline-block mr-1" />
                        Razón de rechazo: {t.rejected_reason}
                      </p>
                    )}
                  </div>
                  <Button size="sm" variant="outline" onClick={() => remove(t)} className="h-7 px-2 border-slate-600 text-slate-400 hover:text-red-300 hover:bg-red-500/10 shrink-0" data-testid={`template-delete-${t.name}`}>
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {creating && <TemplateCreateModal lines={lines} onClose={() => setCreating(false)} onCreated={load} />}
    </div>
  );
};

// ════════════════════════════════════════════════════════════════════
// OPTOUTS TAB
// ════════════════════════════════════════════════════════════════════

const OptoutsTab = ({ lines }) => {
  const [optouts, setOptouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newPhone, setNewPhone] = useState('');
  const [newLineId, setNewLineId] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/broadcasts/optouts');
      setOptouts(data.optouts || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (id) => {
    if (!window.confirm('¿Sacar este número de la blacklist?')) return;
    try {
      await api.delete(`/broadcasts/optouts/${id}`);
      toast.success('Eliminado de la blacklist');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
  };

  const add = async () => {
    if (!newPhone || !newLineId) { toast.error('Completá teléfono y línea'); return; }
    try {
      await api.post('/broadcasts/optouts', { line_id: newLineId, phone: newPhone, reason: 'manual' });
      toast.success('Agregado a la blacklist');
      setAdding(false); setNewPhone(''); setNewLineId('');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-300">{optouts.length} contacto(s) en blacklist</p>
          <p className="text-[11px] text-slate-500">Se agregan automáticamente cuando alguien responde "BAJA / STOP / NO / CANCELAR / BAJAR / NO QUIERO MAS / REMOVER / UNSUBSCRIBE".</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} className="border-slate-600 text-slate-300 hover:bg-slate-800" data-testid="optouts-refresh-btn">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
          <Button onClick={() => setAdding(true)} className="bg-slate-700 hover:bg-slate-600" data-testid="optout-add-btn">
            <Plus className="w-4 h-4 mr-1" /> Agregar manual
          </Button>
        </div>
      </div>

      {adding && (
        <div className="rounded border border-slate-700 bg-slate-900/50 p-3 flex items-end gap-2 flex-wrap" data-testid="optout-add-form">
          <div className="flex-1 min-w-[180px]">
            <Label className="text-xs text-slate-400">Teléfono</Label>
            <Input value={newPhone} onChange={e => setNewPhone(e.target.value)} placeholder="+54 9 11 1234-5678"
              className="bg-slate-800 border-slate-600 text-white text-sm h-9 mt-1" data-testid="optout-phone-input" />
          </div>
          <div className="min-w-[140px]">
            <Label className="text-xs text-slate-400">Línea</Label>
            <select value={newLineId} onChange={e => setNewLineId(e.target.value)} className="w-full mt-1 bg-slate-800 border border-slate-600 rounded h-9 px-2 text-sm text-white" data-testid="optout-line-select">
              <option value="">Elegí…</option>
              {lines.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </div>
          <Button onClick={add} className="bg-emerald-600 hover:bg-emerald-500" data-testid="optout-save-btn">Agregar</Button>
          <Button variant="outline" onClick={() => setAdding(false)} className="border-slate-600 text-slate-300 hover:bg-slate-800">Cancelar</Button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-32"><RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" /></div>
      ) : optouts.length === 0 ? (
        <div className="text-center py-12 text-slate-400" data-testid="optouts-empty">
          <Ban className="w-10 h-10 mx-auto mb-2 opacity-30" />
          <p className="text-sm">Nadie en la blacklist. Bien.</p>
        </div>
      ) : (
        <div className="grid gap-1 max-h-[60vh] overflow-y-auto" data-testid="optouts-list">
          {optouts.map(o => (
            <div key={o.id} className="rounded border border-slate-700/50 bg-slate-900/50 px-3 py-2 flex items-center gap-3" data-testid={`optout-row-${o.id}`}>
              <Ban className="w-3.5 h-3.5 text-slate-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-mono text-white truncate">{o.phone}</p>
                <p className="text-[11px] text-slate-500 truncate">
                  {lines.find(l => l.id === o.line_id)?.name || o.line_id} · {o.reason} · {fmt(o.created_at)}
                </p>
              </div>
              <Button size="sm" variant="outline" onClick={() => remove(o.id)} className="h-7 px-2 border-slate-600 text-slate-400 hover:text-emerald-300 hover:bg-emerald-500/10" data-testid={`optout-delete-${o.id}`}>
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ════════════════════════════════════════════════════════════════════
// PAGE
// ════════════════════════════════════════════════════════════════════

const Broadcasts = () => {
  const { lines, loading: linesLoading, me } = useLines();
  const [tab, setTab] = useState('audiences');
  const [audiences, setAudiences] = useState([]);
  const [prefilledAudience, setPrefilledAudience] = useState(null);

  const reloadAudiences = useCallback(async () => {
    try {
      const { data } = await api.get('/broadcasts/audiences');
      setAudiences(data.audiences || []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { reloadAudiences(); }, [reloadAudiences]);

  const useAudience = (a) => {
    setPrefilledAudience(a);
    setTab('campaigns');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="max-w-5xl mx-auto p-4 sm:p-6">
        <div className="mb-5 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/15 flex items-center justify-center">
            <Megaphone className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Envíos masivos</h1>
            <p className="text-xs text-slate-400">Subí audiencias por CSV, mandá plantillas Meta a tus clientes (cauta + pausa nocturna).</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-800 mb-4 overflow-x-auto">
          {[
            { k: 'audiences',  l: 'Audiencias', icon: Users },
            { k: 'campaigns',  l: 'Campañas',   icon: Megaphone },
            { k: 'templates',  l: 'Plantillas', icon: FileText },
            { k: 'optouts',    l: 'Opt-outs',   icon: Ban },
          ].map(({ k, l, icon: Icon }) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              data-testid={`tab-${k}`}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${tab === k ? 'border-emerald-500 text-white' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
            >
              <Icon className="w-3.5 h-3.5" /> {l}
            </button>
          ))}
        </div>

        {linesLoading ? (
          <div className="flex items-center justify-center h-32"><RefreshCw className="w-5 h-5 text-emerald-400 animate-spin" /></div>
        ) : lines.length === 0 ? (
          <div className="text-center py-12 text-slate-400 rounded-lg border border-amber-500/30 bg-amber-500/5" data-testid="broadcasts-no-lines">
            <AlertCircle className="w-10 h-10 text-amber-400 mx-auto mb-2 opacity-60" />
            <p className="text-sm font-medium text-amber-200">
              {me?.role === 'cajero'
                ? 'Todavía no tenés líneas asignadas a tu usuario.'
                : 'No hay líneas configuradas en el sistema.'}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              {me?.role === 'cajero'
                ? 'Pedile al admin que te asigne una o más líneas en User Management.'
                : 'Creá una línea desde la sección "Líneas WA" antes de usar Broadcasts.'}
            </p>
          </div>
        ) : (
          <>
            {tab === 'audiences' && <AudiencesTab lines={lines} onSelect={useAudience} />}
            {tab === 'campaigns' && <CampaignsTab lines={lines} audiences={audiences} prefilledAudience={prefilledAudience} onAudienceUsed={() => { setPrefilledAudience(null); reloadAudiences(); }} />}
            {tab === 'templates' && <TemplatesTab lines={lines} />}
            {tab === 'optouts' && <OptoutsTab lines={lines} />}
          </>
        )}
      </div>
    </div>
  );
};

export default Broadcasts;
