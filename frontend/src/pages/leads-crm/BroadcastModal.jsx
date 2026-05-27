import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Radio, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import api from '@/utils/api';
import { STATUS_CONFIG } from './constants';

export const BroadcastModal = ({ lines, onClose, currentUser }) => {
  const allowedLines = useMemo(() => {
    if (!currentUser) return lines;
    if (currentUser.role === 'admin' || currentUser.role === 'superadmin') return lines;
    const userLineIds = currentUser.line_ids || [];
    return lines.filter(l => userLineIds.includes(l.id));
  }, [lines, currentUser]);

  const [lineId, setLineId] = useState('');
  const [message, setMessage] = useState('Hola {nombre}, te comparto info desde {linea}');
  const [imageFile, setImageFile] = useState(null);
  const [audioFile, setAudioFile] = useState(null);
  const [audioAsVoice, setAudioAsVoice] = useState(true);
  const [minDelay, setMinDelay] = useState(4);
  const [maxDelay, setMaxDelay] = useState(10);
  const [maxPerHour, setMaxPerHour] = useState(300);
  const [loading, setLoading] = useState(false);
  const [activeBC, setActiveBC] = useState(null);
  const [targetStatus, setTargetStatus] = useState(['valido']);

  // Preview URL del audio para reproducir antes de enviar
  const audioPreviewUrl = useMemo(() => {
    if (!audioFile) return null;
    try { return URL.createObjectURL(audioFile); } catch { return null; }
  }, [audioFile]);
  useEffect(() => () => { if (audioPreviewUrl) URL.revokeObjectURL(audioPreviewUrl); }, [audioPreviewUrl]);

  // El audio se renderiza como "nota de voz" (PTT) en WA solo si es ogg/opus
  const audioIsPTTCompatible = useMemo(() => {
    if (!audioFile) return false;
    const n = (audioFile.name || '').toLowerCase();
    return n.endsWith('.ogg') || n.endsWith('.opus') || (audioFile.type || '').includes('ogg');
  }, [audioFile]);

  const loadActive = useCallback(async (id) => {
    try {
      const { data } = await api.get(`/crm/broadcast/${id}`);
      setActiveBC(data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    if (!activeBC?.id) return;
    if (activeBC.status === 'running') {
      const iv = setInterval(() => loadActive(activeBC.id), 3000);
      return () => clearInterval(iv);
    }
  }, [activeBC?.id, activeBC?.status, loadActive]);

  const start = async () => {
    if (!lineId) { toast.error('Elegí línea'); return; }
    if (!message.trim() && !imageFile && !audioFile) {
      toast.error('Tenés que poner mensaje, imagen o audio');
      return;
    }
    setLoading(true);
    try {
      let imagePath = null;
      let audioPath = null;
      if (imageFile) {
        const form = new FormData();
        form.append('file', imageFile);
        const { data: up } = await api.post('/crm/broadcast/upload-image', form, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        imagePath = up.filename;
      }
      if (audioFile) {
        const form = new FormData();
        form.append('file', audioFile);
        const { data: upA } = await api.post('/crm/broadcast/upload-audio', form, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        audioPath = upA.filename;
      }
      const { data: bc } = await api.post('/crm/broadcast', {
        line_id: lineId,
        target_status: targetStatus,
        message,
        image_path: imagePath,
        audio_path: audioPath,
        audio_as_voice: audioAsVoice,
        min_delay_sec: minDelay,
        max_delay_sec: maxDelay,
        max_per_hour: maxPerHour,
      });
      setActiveBC(bc);
      toast.success(`Broadcast iniciado: ${bc.total} destinatarios`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error creando broadcast');
    } finally {
      setLoading(false);
    }
  };

  const cancel = async () => {
    if (!activeBC?.id) return;
    if (!window.confirm('¿Cancelar el envío en curso?')) return;
    try {
      await api.post(`/crm/broadcast/${activeBC.id}/cancel`);
      toast.success('Cancelado');
      loadActive(activeBC.id);
    } catch { toast.error('Error cancelando'); }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-[60] flex items-center justify-center sm:p-4">
      <div className="bg-slate-900 w-full h-full sm:rounded-xl sm:max-w-xl sm:h-auto sm:max-h-[90vh] flex flex-col border border-slate-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-purple-400" />
            <h2 className="text-white font-semibold">Envío masivo</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white" data-testid="broadcast-close-btn">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!activeBC ? (
            <>
              <div>
                <label className="text-xs text-slate-400 uppercase font-semibold">Línea</label>
                <select value={lineId} onChange={e => setLineId(e.target.value)}
                  className="w-full mt-1 bg-slate-800 border border-slate-600 text-white rounded px-3 py-2 text-sm"
                  data-testid="broadcast-line-select">
                  <option value="">— Elegir línea —</option>
                  {allowedLines.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-semibold">Destinatarios (estado)</label>
                <div className="flex gap-2 mt-1 flex-wrap">
                  {['valido', 'interesado', 'nuevo', 'consultas'].map(s => (
                    <button key={s} type="button"
                      onClick={() => setTargetStatus(p => p.includes(s) ? p.filter(x => x !== s) : [...p, s])}
                      className={`px-2.5 py-1 rounded text-xs font-medium ${targetStatus.includes(s) ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
                      {STATUS_CONFIG[s]?.label || s}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-semibold">Mensaje</label>
                <textarea value={message} onChange={e => setMessage(e.target.value)} rows={4}
                  placeholder="Usá {nombre} y {linea} para personalizar"
                  className="w-full mt-1 bg-slate-800 border border-slate-600 text-white rounded px-3 py-2 text-sm font-mono"
                  data-testid="broadcast-message-input" />
                <p className="text-[11px] text-slate-500 mt-1">
                  Tokens disponibles: <code className="text-purple-300">{'{nombre}'}</code>, <code className="text-purple-300">{'{linea}'}</code>
                </p>
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-semibold">Imagen (opcional)</label>
                <input type="file" accept="image/*" onChange={e => setImageFile(e.target.files?.[0] || null)}
                  className="w-full mt-1 text-xs text-slate-300" data-testid="broadcast-image-input" />
              </div>
              <div>
                <label className="text-xs text-slate-400 uppercase font-semibold flex items-center gap-2">
                  Audio (opcional)
                  {audioFile && (
                    <button type="button" onClick={() => setAudioFile(null)}
                      className="text-[10px] text-red-400 hover:text-red-300 normal-case font-normal"
                      data-testid="broadcast-audio-clear-btn">
                      quitar
                    </button>
                  )}
                </label>
                <input type="file" accept="audio/*,.ogg,.opus,.mp3,.m4a,.aac,.amr,.wav,.webm"
                  onChange={e => setAudioFile(e.target.files?.[0] || null)}
                  className="w-full mt-1 text-xs text-slate-300" data-testid="broadcast-audio-input" />
                {audioFile && (
                  <div className="mt-2 space-y-2">
                    <audio src={audioPreviewUrl} controls className="w-full h-9" data-testid="broadcast-audio-preview" />
                    <div className="flex items-start gap-2 bg-slate-800/60 border border-slate-700 rounded p-2">
                      <input type="checkbox" id="audio-as-voice" checked={audioAsVoice}
                        onChange={e => setAudioAsVoice(e.target.checked)}
                        className="mt-0.5 cursor-pointer" data-testid="broadcast-audio-voice-toggle" />
                      <label htmlFor="audio-as-voice" className="text-[11px] text-slate-300 cursor-pointer leading-snug">
                        Enviar como <strong>nota de voz</strong> (PTT)
                        {!audioIsPTTCompatible && (
                          <span className="block text-amber-400 mt-1">
                            ⚠ Tu archivo no es .ogg/.opus → se enviará como audio reproducible normal, no como nota de voz. Para PTT, convertí el archivo a .ogg/opus.
                          </span>
                        )}
                      </label>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-snug">
                      Si además ponés un mensaje de texto, se enviará en un mensaje aparte después del audio (WhatsApp no permite leyenda en audios).
                    </p>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 uppercase font-semibold">Min delay (s)</label>
                  <input type="number" value={minDelay} onChange={e => setMinDelay(parseInt(e.target.value) || 0)} min={1}
                    className="w-full mt-1 bg-slate-800 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 uppercase font-semibold">Max delay (s)</label>
                  <input type="number" value={maxDelay} onChange={e => setMaxDelay(parseInt(e.target.value) || 0)} min={1}
                    className="w-full mt-1 bg-slate-800 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 uppercase font-semibold">Max por hora</label>
                  <input type="number" value={maxPerHour} onChange={e => setMaxPerHour(parseInt(e.target.value) || 0)} min={1}
                    className="w-full mt-1 bg-slate-800 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
                </div>
              </div>
            </>
          ) : (
            <div className="space-y-3">
              <div className="bg-slate-800/50 border border-slate-700 rounded p-3 text-sm">
                <div className="text-[10px] text-slate-400 uppercase mb-1">Estado</div>
                <div className="text-white font-semibold capitalize">{activeBC.status}</div>
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div className="bg-slate-800 rounded p-2 text-center">
                  <div className="text-[10px] text-slate-500 uppercase">Total</div>
                  <div className="text-lg font-bold text-white">{activeBC.total}</div>
                </div>
                <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-2 text-center">
                  <div className="text-[10px] text-emerald-400 uppercase">Enviados</div>
                  <div className="text-lg font-bold text-emerald-300">{activeBC.sent}</div>
                </div>
                <div className="bg-red-500/10 border border-red-500/30 rounded p-2 text-center">
                  <div className="text-[10px] text-red-400 uppercase">Fallados</div>
                  <div className="text-lg font-bold text-red-300">{activeBC.failed}</div>
                </div>
                <div className="bg-slate-800 rounded p-2 text-center">
                  <div className="text-[10px] text-slate-500 uppercase">Pendientes</div>
                  <div className="text-lg font-bold text-slate-300">{Math.max(0, activeBC.total - activeBC.sent - activeBC.failed)}</div>
                </div>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="h-full bg-gradient-to-r from-emerald-500 to-blue-500 transition-all" style={{ width: `${activeBC.total ? (activeBC.sent + activeBC.failed) / activeBC.total * 100 : 0}%` }} />
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-800 shrink-0">
          {!activeBC ? (
            <Button onClick={start} disabled={loading || !lineId || (!message.trim() && !imageFile && !audioFile)} className="w-full bg-purple-600 hover:bg-purple-700" data-testid="broadcast-start-btn">
              {loading ? 'Iniciando...' : '🚀 Iniciar envío masivo'}
            </Button>
          ) : activeBC.status === 'running' ? (
            <Button onClick={cancel} className="w-full bg-red-600 hover:bg-red-700" data-testid="broadcast-cancel-btn">Cancelar envío</Button>
          ) : (
            <Button onClick={onClose} className="w-full bg-slate-700 hover:bg-slate-600">Cerrar</Button>
          )}
        </div>
      </div>
    </div>
  );
};
