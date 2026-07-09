import React, { useEffect, useState, useCallback } from 'react';
import { Settings, Save, RefreshCw, Plus, Trash2, Info, MessageSquare, UserCheck, Landmark, Share2, CreditCard, Link2, Unlink, CheckCircle2, AlertCircle } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';

/**
 * Mi Configuración — Auto-gestión del cajero (y admin) de los textos/botones
 * del CRM: Bienvenida, Mensaje de usuario, CBUs y Derivación.
 *
 * El admin sigue pudiendo editarlos desde /user-management. Acá cada cajero
 * edita SOLO los suyos.
 */
export default function MiConfiguracion() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [me, setMe] = useState(null);

  // Form state
  const [welcomeMessage, setWelcomeMessage] = useState('');
  const [autoWelcomeEnabled, setAutoWelcomeEnabled] = useState(true);
  const [userMessage, setUserMessage] = useState('');
  const [cbuList, setCbuList] = useState([]); // [{cbu, name}]
  const [derivationMessage, setDerivationMessage] = useState('');
  const [derivationNumbers, setDerivationNumbers] = useState([]);
  // Quick-templates: object { cargado: "variante 1\n---\nvariante 2..." }
  const [quickTemplates, setQuickTemplates] = useState({});
  // Per-cashier AI-agent config
  const [aiConfig, setAiConfig] = useState({
    enabled: false, brand_name: '', brand_tone: 'casual',
    opening_time: '09:00', closing_time: '01:00',
    off_hours_message: '¡Hola! Nuestro horario de atención es de {opening} a {closing}. En breve un cajero te va a responder. 🙌',
    min_deposit: 1000, max_deposit: 500000,
    min_withdrawal: 1000, max_withdrawal: 500000,
    context_msgs: 15, confidence_threshold: 0.55, signature: '',
    platforms: [],
  });

  // ── Mercado Pago OAuth ───────────────────────────────────────
  const [mpStatus, setMpStatus] = useState({ configured: false, connected: false, connection: null });
  const [mpLoading, setMpLoading] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const loadMpStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/mercadopago/status');
      setMpStatus(data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadMpStatus();
  }, [loadMpStatus]);

  // Toast on return from OAuth flow (redirects to /mi-configuracion?mp=connected|error)
  useEffect(() => {
    const mp = searchParams.get('mp');
    if (mp === 'connected') {
      toast.success('¡Mercado Pago conectado correctamente! 🎉');
      loadMpStatus();
      searchParams.delete('mp');
      setSearchParams(searchParams, { replace: true });
    } else if (mp === 'error') {
      const reason = searchParams.get('reason');
      toast.error(`Error conectando Mercado Pago${reason ? ': ' + reason : ''}`);
      searchParams.delete('mp');
      searchParams.delete('reason');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, loadMpStatus]);

  const connectMp = async () => {
    setMpLoading(true);
    try {
      const { data } = await api.get('/mercadopago/oauth/init');
      if (data?.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        toast.error('No se pudo iniciar la conexión con Mercado Pago');
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error conectando con Mercado Pago');
    } finally {
      setMpLoading(false);
    }
  };

  const disconnectMp = async () => {
    if (!window.confirm('¿Desconectar tu cuenta de Mercado Pago? Podés volver a conectarla cuando quieras.')) return;
    setMpLoading(true);
    try {
      await api.delete('/mercadopago/disconnect');
      toast.success('Cuenta de Mercado Pago desconectada');
      loadMpStatus();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error desconectando');
    } finally {
      setMpLoading(false);
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/auth/me');
      setMe(data);
      setWelcomeMessage(data.welcome_message || '');
      setAutoWelcomeEnabled(data.auto_welcome_enabled !== false);
      setUserMessage(data.user_message || '');
      setCbuList(Array.isArray(data.cbu_list) ? data.cbu_list : []);
      setDerivationMessage(data.derivation_message || '');
      setDerivationNumbers(Array.isArray(data.derivation_numbers) ? data.derivation_numbers : []);
      setQuickTemplates(data.quick_templates && typeof data.quick_templates === 'object' ? data.quick_templates : {});
      if (data.ai_config && typeof data.ai_config === 'object') setAiConfig(prev => ({ ...prev, ...data.ai_config }));
    } catch {
      toast.error('No pude cargar tu configuración');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        welcome_message: welcomeMessage,
        user_message: userMessage,
        auto_welcome_enabled: autoWelcomeEnabled,
        derivation_message: derivationMessage,
        derivation_numbers: derivationNumbers.map(n => (n || '').trim()).filter(Boolean),
        cbu_list: cbuList
          .map(item => ({ cbu: (item.cbu || '').trim(), name: (item.name || '').trim() }))
          .filter(item => item.cbu),
        // Only send keys that have non-empty content — keeps the doc clean.
        quick_templates: Object.fromEntries(
          Object.entries(quickTemplates).map(([k, v]) => [k, (v || '').trim()]).filter(([, v]) => v)
        ),
        ai_config: {
          ...aiConfig,
          // Strip empty/whitespace platform entries only at save time so the
          // textarea can render blank lines while the user is typing. Also
          // split any line that contains commas (e.g. "a,b,c") into separate
          // entries, so the AI shows them as distinct bullets.
          platforms: Array.isArray(aiConfig.platforms)
            ? aiConfig.platforms
                .flatMap(p => (p || '').split(','))
                .map(p => p.trim())
                .filter(Boolean)
                .slice(0, 20)
            : [],
        },
      };
      await api.put('/auth/me/messages', payload);
      toast.success('Configuración guardada');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error guardando');
    } finally {
      setSaving(false);
    }
  };

  // CBU list helpers
  const addCbu = () => setCbuList(prev => [...prev, { cbu: '', name: '' }]);
  const updateCbu = (idx, field, value) => {
    setCbuList(prev => prev.map((item, i) => i === idx ? { ...item, [field]: value } : item));
  };
  const removeCbu = (idx) => setCbuList(prev => prev.filter((_, i) => i !== idx));

  // Derivation list helpers
  const addNumber = () => setDerivationNumbers(prev => [...prev, '']);
  const updateNumber = (idx, value) => setDerivationNumbers(prev => prev.map((n, i) => i === idx ? value : n));
  const removeNumber = (idx) => setDerivationNumbers(prev => prev.filter((_, i) => i !== idx));

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <RefreshCw className="w-6 h-6 text-emerald-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white py-6 px-4" data-testid="mi-configuracion-page">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-violet-500/15 flex items-center justify-center">
            <Settings className="w-5 h-5 text-violet-400" />
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-bold">Mi configuración</h1>
            <p className="text-xs text-slate-400">
              Editá los textos que usás en el CRM. {me?.role === 'admin' ? 'Como admin, también podés editar los de otros desde "Usuarios".' : 'El admin también puede ajustarlos desde User Management.'}
            </p>
          </div>
          <Button onClick={save} disabled={saving}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
            data-testid="mi-config-save-btn">
            {saving ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
            Guardar todo
          </Button>
        </div>

        <div className="space-y-5">
          {/* Bienvenida */}
          <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4" data-testid="section-welcome">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-semibold">👋 Bienvenida</h2>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <span>Auto-enviar a leads nuevos</span>
                <Switch checked={autoWelcomeEnabled} onCheckedChange={setAutoWelcomeEnabled}
                  data-testid="auto-welcome-switch" />
              </label>
            </div>
            <Textarea value={welcomeMessage} onChange={e => setWelcomeMessage(e.target.value)}
              placeholder="Ej: ¡Hola! Bienvenid@. ¿En qué puedo ayudarte hoy?"
              className="bg-slate-800 border-slate-700 text-white text-sm min-h-[100px]"
              data-testid="welcome-textarea" />
            <p className="text-[11px] text-slate-500 mt-2 flex gap-1.5">
              <Info className="w-3 h-3 shrink-0 mt-0.5" />
              Se envía automáticamente cuando un lead nuevo escribe por primera vez (si "Auto-enviar" está activado). También se manda manualmente con el botón "👋 Bienvenida" del chat.
            </p>
          </section>

          {/* Usuario / Mensaje pre-armado */}
          <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4" data-testid="section-user-msg">
            <div className="flex items-center gap-2 mb-3">
              <UserCheck className="w-4 h-4 text-blue-400" />
              <h2 className="text-sm font-semibold">👤 Mensaje "Usuario creado"</h2>
            </div>
            <Textarea value={userMessage} onChange={e => setUserMessage(e.target.value)}
              placeholder="Ej: ¡Listo! Tu usuario es: {{usuario}} y tu contraseña: {{password}}"
              className="bg-slate-800 border-slate-700 text-white text-sm min-h-[100px]"
              data-testid="user-message-textarea" />
            <p className="text-[11px] text-slate-500 mt-2 flex gap-1.5">
              <Info className="w-3 h-3 shrink-0 mt-0.5" />
              Mensaje que se envía con el botón "Usuario" del chat al confirmar la creación del usuario del cliente.
            </p>
          </section>

          {/* ⚡ Cargado — Respuestas rápidas rotativas */}
          <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4" data-testid="section-quick-cargado">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <span className="text-lime-400 text-lg leading-none">⚡</span>
                <h2 className="text-sm font-semibold">Cargado — respuestas rotativas</h2>
              </div>
              <span className="text-[10px] text-slate-500 uppercase tracking-wide">
                {((quickTemplates.cargado || '').split(/\n\s*-{3,}\s*\n/).map(s => s.trim()).filter(Boolean).length)} variantes
              </span>
            </div>
            <Textarea
              value={quickTemplates.cargado || ''}
              onChange={e => setQuickTemplates(prev => ({ ...prev, cargado: e.target.value }))}
              placeholder={`Escribí una variante por bloque separado por --- en línea propia. Ej:\n¡Cargado! ✅\n---\nListo, papu 🎉\n---\nSe cargó ya ⚡`}
              className="bg-slate-800 border-slate-700 text-white text-sm min-h-[220px] font-mono leading-relaxed"
              data-testid="quick-cargado-textarea"
            />
            <div className="mt-2 space-y-1.5 text-[11px] text-slate-500">
              <p className="flex gap-1.5">
                <Info className="w-3 h-3 shrink-0 mt-0.5" />
                <span>
                  Cada vez que el cajero presione el botón <span className="text-lime-400">⚡ Cargado</span> del chat,
                  el sistema elige aleatoriamente una de las variantes. Meta detecta el mismo mensaje repetido a
                  muchos clientes como <em>bot</em> — rotarlo previene la caída de las líneas principales.
                </span>
              </p>
              <p className="pl-4 text-slate-600">
                💡 Separador: tres o más guiones <code className="text-slate-400">---</code> en una línea propia entre variantes.
                Recomendado: 8-10 variantes.
              </p>
            </div>
          </section>

          {/* 🤖 Asistente IA — auto-respuesta por intent */}
          <section className="rounded-lg border border-violet-800/50 bg-violet-950/20 p-4" data-testid="section-ai-agent">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <span className="text-violet-300 text-lg leading-none">🤖</span>
                <h2 className="text-sm font-semibold">Asistente IA (Claude Sonnet)</h2>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">
                  ~$0.007/msg
                </span>
              </div>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="ai-enabled-toggle">
                <input
                  type="checkbox"
                  checked={!!aiConfig.enabled}
                  onChange={e => setAiConfig(prev => ({ ...prev, enabled: e.target.checked }))}
                  className="w-4 h-4 accent-violet-500"
                />
                <span className={`text-xs font-semibold ${aiConfig.enabled ? 'text-emerald-300' : 'text-slate-500'}`}>
                  {aiConfig.enabled ? 'ACTIVO' : 'Desactivado'}
                </span>
              </label>
            </div>

            <p className="text-[11px] text-slate-400 mb-3 leading-relaxed">
              Cuando el cliente escribe, la IA clasifica su intención (carga / retiro / nuevo usuario / revisar) y
              responde automáticamente siguiendo un flujo. Ta&shy;guea el lead para que solo tengas que ejecutar la
              operación. <strong className="text-amber-300">Costo estimado</strong>: ~$0.007 USD por mensaje procesado
              (~$20 al día por cada línea con 1000 msgs/día).
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Nombre de marca</label>
                <input
                  value={aiConfig.brand_name || ''}
                  onChange={e => setAiConfig(prev => ({ ...prev, brand_name: e.target.value }))}
                  placeholder="Ej: RED X"
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                  data-testid="ai-brand-name-input"
                />
              </div>
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Tono</label>
                <select
                  value={aiConfig.brand_tone || 'casual'}
                  onChange={e => setAiConfig(prev => ({ ...prev, brand_tone: e.target.value }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                  data-testid="ai-brand-tone-select"
                >
                  <option value="formal">Formal (usted)</option>
                  <option value="casual">Casual (vos, tuteo)</option>
                  <option value="amistoso">Amistoso (con emojis, apodos)</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Horario apertura (AR)</label>
                <input
                  type="time"
                  value={aiConfig.opening_time || '09:00'}
                  onChange={e => setAiConfig(prev => ({ ...prev, opening_time: e.target.value }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                />
              </div>
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Horario cierre (AR)</label>
                <input
                  type="time"
                  value={aiConfig.closing_time || '01:00'}
                  onChange={e => setAiConfig(prev => ({ ...prev, closing_time: e.target.value }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                />
              </div>
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Carga mínima ($)</label>
                <input
                  type="number" min="0"
                  value={aiConfig.min_deposit ?? 1000}
                  onChange={e => setAiConfig(prev => ({ ...prev, min_deposit: Number(e.target.value) }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                />
              </div>
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Carga máxima ($)</label>
                <input
                  type="number" min="0"
                  value={aiConfig.max_deposit ?? 500000}
                  onChange={e => setAiConfig(prev => ({ ...prev, max_deposit: Number(e.target.value) }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                />
              </div>
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Retiro mínimo ($)</label>
                <input
                  type="number" min="0"
                  value={aiConfig.min_withdrawal ?? 1000}
                  onChange={e => setAiConfig(prev => ({ ...prev, min_withdrawal: Number(e.target.value) }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                />
              </div>
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Retiro máximo ($)</label>
                <input
                  type="number" min="0"
                  value={aiConfig.max_withdrawal ?? 500000}
                  onChange={e => setAiConfig(prev => ({ ...prev, max_withdrawal: Number(e.target.value) }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white"
                />
              </div>
            </div>

            <div className="mb-3">
              <label className="text-[11px] text-slate-400 block mb-1">
                🎰 Plataformas disponibles (una por línea)
              </label>
              <Textarea
                value={(aiConfig.platforms || []).join('\n')}
                onChange={e => setAiConfig(prev => ({
                  ...prev,
                  // Preserve empty lines while typing (Enter must work). We
                  // filter/trim only at save time in `save()` below.
                  platforms: e.target.value.split('\n').slice(0, 20)
                }))}
                placeholder={"Ej:\nNueva Vegas\n1xBet\nBetsson"}
                className="bg-slate-800 border-slate-700 text-white text-xs min-h-[80px] font-mono"
                data-testid="ai-platforms-input"
              />
              <p className="text-[10px] text-slate-500 mt-1">
                La IA le va a mostrar estas opciones al cliente cuando quiera crearse un usuario nuevo.
              </p>
            </div>

            <div className="mb-3">
              <label className="text-[11px] text-slate-400 block mb-1">Mensaje fuera de horario</label>
              <Textarea
                value={aiConfig.off_hours_message || ''}
                onChange={e => setAiConfig(prev => ({ ...prev, off_hours_message: e.target.value }))}
                placeholder="Usá {opening} y {closing} como placeholders"
                className="bg-slate-800 border-slate-700 text-white text-xs min-h-[60px]"
              />
            </div>

            <div className="p-3 rounded bg-slate-900/60 border border-slate-800 space-y-1.5 text-[11px]">
              <div className="text-violet-300 font-semibold">🎯 Etiquetas que la IA aplica automáticamente:</div>
              <div>🟢 <strong>pendiente-carga</strong> — cliente mandó comprobante o pidió CBU</div>
              <div>🟡 <strong>pendiente-retiro</strong> — cliente completó el pedido de retiro</div>
              <div>🔵 <strong>nuevo-usuario</strong> — cliente pasó todos los datos para alta</div>
              <div>🔴 <strong>revisar</strong> — la IA no está segura o el cliente pidió humano</div>
              <div className="pt-1 text-slate-500">Cuando terminás la operación, quitá el tag desde el chat.</div>
            </div>
          </section>

          {/* CBUs */}
          <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4" data-testid="section-cbu">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <Landmark className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold">💳 CBUs para cobrar</h2>
              </div>
              <Button size="sm" variant="outline" onClick={addCbu}
                className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 h-7 text-xs"
                data-testid="add-cbu-btn">
                <Plus className="w-3.5 h-3.5 mr-1" /> Agregar
              </Button>
            </div>
            {cbuList.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No tenés CBUs cargados. Agregá al menos uno para usar el botón "CBU" del chat.</p>
            ) : (
              <div className="space-y-2">
                {cbuList.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2" data-testid={`cbu-row-${idx}`}>
                    <Input value={item.cbu} onChange={e => updateCbu(idx, 'cbu', e.target.value)}
                      placeholder="CBU/CVU/Alias"
                      className="flex-1 bg-slate-800 border-slate-700 text-white text-sm h-9 font-mono"
                      data-testid={`cbu-input-${idx}`} />
                    <Input value={item.name} onChange={e => updateCbu(idx, 'name', e.target.value)}
                      placeholder="Nombre del titular"
                      className="flex-1 bg-slate-800 border-slate-700 text-white text-sm h-9"
                      data-testid={`cbu-name-${idx}`} />
                    <button onClick={() => removeCbu(idx)}
                      className="p-1.5 text-red-400 hover:bg-red-500/10 rounded"
                      data-testid={`cbu-remove-${idx}`}
                      title="Eliminar este CBU">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[11px] text-slate-500 mt-2 flex gap-1.5">
              <Info className="w-3 h-3 shrink-0 mt-0.5" />
              Si tenés varios CBUs, el botón "CBU" del chat te deja elegir cuál mandar.
            </p>
          </section>

          {/* Derivación */}
          <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4" data-testid="section-derivation">
            <div className="flex items-center gap-2 mb-3">
              <Share2 className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold">↪️ Derivación</h2>
            </div>
            <div className="space-y-3">
              <div>
                <Label className="text-xs text-slate-400">Texto que acompaña la derivación</Label>
                <Textarea value={derivationMessage} onChange={e => setDerivationMessage(e.target.value)}
                  placeholder="Ej: Te derivo con un compañero que te va a atender. Escribíle al siguiente número:"
                  className="bg-slate-800 border-slate-700 text-white text-sm min-h-[80px] mt-1"
                  data-testid="derivation-message-textarea" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <Label className="text-xs text-slate-400">Números de derivación</Label>
                  <Button size="sm" variant="outline" onClick={addNumber}
                    className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 h-7 text-xs"
                    data-testid="add-derivation-btn">
                    <Plus className="w-3.5 h-3.5 mr-1" /> Agregar
                  </Button>
                </div>
                {derivationNumbers.length === 0 ? (
                  <p className="text-xs text-slate-500 italic">No tenés números cargados.</p>
                ) : (
                  <div className="space-y-2">
                    {derivationNumbers.map((n, idx) => (
                      <div key={idx} className="flex items-center gap-2" data-testid={`derivation-row-${idx}`}>
                        <Input value={n} onChange={e => updateNumber(idx, e.target.value)}
                          placeholder="+54 9 11 1234-5678"
                          className="flex-1 bg-slate-800 border-slate-700 text-white text-sm h-9"
                          data-testid={`derivation-input-${idx}`} />
                        <button onClick={() => removeNumber(idx)}
                          className="p-1.5 text-red-400 hover:bg-red-500/10 rounded"
                          data-testid={`derivation-remove-${idx}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-2 flex gap-1.5">
              <Info className="w-3 h-3 shrink-0 mt-0.5" />
              El botón "Derivar" del chat le manda al cliente el texto + un número de esta lista.
            </p>
          </section>

          {/* Mercado Pago Connect */}
          <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-4" data-testid="section-mp">
            <div className="flex items-center gap-2 mb-3">
              <CreditCard className="w-4 h-4 text-sky-400" />
              <h2 className="text-sm font-semibold">💳 Mercado Pago</h2>
              {mpStatus.connected && (
                <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 text-[10px] font-semibold">
                  <CheckCircle2 className="w-3 h-3" /> Conectado
                </span>
              )}
            </div>

            {!mpStatus.configured ? (
              <div className="flex items-start gap-2 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-200 px-3 py-2 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>El admin todavía no configuró la app de Mercado Pago en el servidor. Contactalo para habilitar esta función.</span>
              </div>
            ) : mpStatus.connected ? (
              <>
                <div className="rounded-md bg-slate-800/60 border border-slate-700 p-3 space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Cuenta MP</span>
                    <span className="text-white font-medium" data-testid="mp-nickname">
                      {mpStatus.connection?.mp_nickname || `#${mpStatus.connection?.mp_user_id}`}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Modo</span>
                    <span className={mpStatus.connection?.live_mode ? 'text-emerald-300 font-medium' : 'text-amber-300 font-medium'}>
                      {mpStatus.connection?.live_mode ? 'Producción' : 'Sandbox'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Token expira</span>
                    <span className="text-slate-200">
                      {mpStatus.connection?.token_expires_at
                        ? new Date(mpStatus.connection.token_expires_at).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
                        : '—'}
                    </span>
                  </div>
                </div>
                <div className="flex gap-2 mt-3">
                  <Button
                    onClick={connectMp}
                    disabled={mpLoading}
                    variant="outline"
                    size="sm"
                    className="border-sky-500/40 text-sky-300 hover:bg-sky-500/10 text-xs"
                    data-testid="mp-reconnect-btn"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 mr-1 ${mpLoading ? 'animate-spin' : ''}`} />
                    Reconectar
                  </Button>
                  <Button
                    onClick={disconnectMp}
                    disabled={mpLoading}
                    variant="outline"
                    size="sm"
                    className="border-red-500/40 text-red-300 hover:bg-red-500/10 text-xs"
                    data-testid="mp-disconnect-btn"
                  >
                    <Unlink className="w-3.5 h-3.5 mr-1" />
                    Desconectar
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Conectá tu cuenta de Mercado Pago para que cuando un cliente te mande un comprobante,
                  el CRM busque automáticamente el pago en tus ingresos y lo valide.
                </p>
                <ul className="mt-2 text-[11px] text-slate-500 space-y-0.5 list-disc list-inside">
                  <li>Solo lectura: el sistema NUNCA cobra ni transfiere plata</li>
                  <li>Cada cajero conecta su propia cuenta MP</li>
                  <li>Podés desconectarla en cualquier momento</li>
                </ul>
                <Button
                  onClick={connectMp}
                  disabled={mpLoading}
                  className="mt-3 bg-sky-600 hover:bg-sky-500 text-white"
                  data-testid="mp-connect-btn"
                >
                  {mpLoading ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Link2 className="w-4 h-4 mr-2" />
                  )}
                  Conectar Mercado Pago
                </Button>
              </>
            )}
          </section>

          {/* Submit footer */}
          <div className="flex justify-end gap-2 sticky bottom-3 z-10">
            <Button onClick={save} disabled={saving}
              className="bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg"
              data-testid="mi-config-save-footer-btn">
              {saving ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
              Guardar configuración
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
