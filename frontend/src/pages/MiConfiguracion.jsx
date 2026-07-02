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
