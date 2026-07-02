import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageCircle, RefreshCw, Send, X, Image as ImageIcon, Mic, DollarSign,
  User, Users, ArrowLeft, ArrowDown, Share2, Phone, Landmark, Pencil, Check as CheckIcon,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import api from '@/utils/api';
import { STATUS_CONFIG } from './constants';
import { StatusSelector } from './StatusSelector';
import { ChatMessage } from './ChatMessage';
import { AdPreviewCard } from './AdPreviewCard';
import { LeadTagsBar } from './LeadTags';
import { LeadAvatar } from './LeadAvatar';

export const ChatPanel = ({
  lead,
  onStatusChange,
  onClose,
  showCloseButton = false,
  onBack,
  showBackButton = false,
  userMessages = {},
  onLeadUpdated,
  onLeadDeleted,
}) => {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [conversionValue, setConversionValue] = useState('');
  const [showConversionInput, setShowConversionInput] = useState(false);
  const [adPreview, setAdPreview] = useState(null);
  const [adCollapsed, setAdCollapsed] = useState(false);
  const [showDerivarMenu, setShowDerivarMenu] = useState(false);
  const derivarRef = useRef(null);
  const [showCbuMenu, setShowCbuMenu] = useState(false);
  const cbuRef = useRef(null);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [savingName, setSavingName] = useState(false);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  // Smart auto-scroll: only auto-scroll if cajero is near bottom. Otherwise
  // show a floating "↓ N nuevos" pill so they don't lose their place while
  // reading historical messages.
  const [isNearBottom, setIsNearBottom] = useState(true);
  const isNearBottomRef = useRef(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const lastSeenMsgIdRef = useRef(null);
  const previousLeadIdRef = useRef(lead.id);

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    const el = messagesContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior });
    }
    setUnreadCount(0);
    setIsNearBottom(true);
    isNearBottomRef.current = true;
  }, []);

  const handleScroll = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const near = distanceFromBottom < 120;
    isNearBottomRef.current = near;
    setIsNearBottom(near);
    if (near) setUnreadCount(0);
  }, []);

  const loadMessages = useCallback(async () => {
    try {
      const { data } = await api.get(`/crm/leads/${lead.id}/messages`);
      setMessages(data.messages || []);
    } catch { /* silent */ }
  }, [lead.id]);

  const loadAdPreview = useCallback(async () => {
    try {
      const { data } = await api.get(`/crm/leads/${lead.id}/ad-preview`);
      setAdPreview(data);
    } catch { setAdPreview(null); }
  }, [lead.id]);

  useEffect(() => {
    loadMessages();
    loadAdPreview();
    setAdCollapsed(true); // contraído por default — el cajero lo despliega si quiere

    // Polling de mensajes: pausa cuando la pestaña está oculta (ahorra egress
    // Railway). Catch-up inmediato al volver al foco. Intervalo 10s (antes 5s).
    let interval = null;
    let lastTickAt = Date.now();
    const POLL_MS = 10000;
    const STALE_MS = 8000;
    const tick = () => { lastTickAt = Date.now(); loadMessages(); };
    const start = () => {
      if (interval) return;
      interval = setInterval(tick, POLL_MS);
    };
    const stop = () => {
      if (interval) { clearInterval(interval); interval = null; }
    };

    if (document.visibilityState === 'visible') start();

    // visibilitychange no es 100% confiable en Safari iOS / Chrome Android.
    // Reforzamos con focus / pageshow / online para garantizar catch-up.
    const catchUp = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastTickAt >= STALE_MS) tick();
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
  }, [loadMessages, loadAdPreview]);

  useEffect(() => {
    // When switching to a different lead, force-jump to bottom.
    if (previousLeadIdRef.current !== lead.id) {
      previousLeadIdRef.current = lead.id;
      lastSeenMsgIdRef.current = null;
      setUnreadCount(0);
      isNearBottomRef.current = true;
      setIsNearBottom(true);
      // Defer to next frame so the DOM has the new messages painted.
      requestAnimationFrame(() => scrollToBottom('auto'));
      return;
    }
    if (messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];
    const lastId = lastMsg?.id;
    const prevSeen = lastSeenMsgIdRef.current;
    const hasNew = lastId && lastId !== prevSeen;

    if (isNearBottomRef.current) {
      // Cajero is at the bottom — keep them pinned to the latest message.
      scrollToBottom('smooth');
      lastSeenMsgIdRef.current = lastId;
    } else if (hasNew && prevSeen) {
      // Cajero is reading older messages — count incoming new ones from the lead.
      // Only count messages that arrived AFTER the last seen one.
      const prevIdx = messages.findIndex(m => m.id === prevSeen);
      const newOnes = prevIdx >= 0 ? messages.slice(prevIdx + 1) : messages;
      // Only count incoming (not admin) messages as unread, otherwise the
      // pill would also fire when the cajero sends something themselves.
      const incoming = newOnes.filter(m => m.sender !== 'admin').length;
      if (incoming > 0) setUnreadCount(c => c + incoming);
    } else if (hasNew && !prevSeen) {
      // First load — just record the last id without flagging unread.
      lastSeenMsgIdRef.current = lastId;
    }
  }, [messages, lead.id, scrollToBottom]);

  const sendMessage = async (sender = 'admin') => {
    if (!newMessage.trim()) return;
    setSending(true);
    try {
      await api.post(`/crm/leads/${lead.id}/messages`, { content: newMessage, sender });
      setNewMessage('');
      // Force scroll-to-bottom: if the cajero just sent something, they
      // expect to see it land at the bottom even if they were scrolled up.
      isNearBottomRef.current = true;
      setIsNearBottom(true);
      loadMessages();
    } catch { toast.error('Error enviando mensaje'); }
    finally {
      setSending(false);
      // Refocus the textarea AFTER the disabled flag is cleared so the
      // browser actually accepts the focus call. Cajero can keep typing
      // without re-clicking the input.
      setTimeout(() => {
        try { inputRef.current?.focus(); } catch { /* silent */ }
      }, 60);
    }
  };

  const fileInputRef = useRef(null);
  const inputRef = useRef(null);
  const handleImagePick = () => fileInputRef.current?.click();

  // Drag & drop + clipboard paste: el cajero arrastra una imagen desde su
  // escritorio o copia/pega un screenshot y se envía igual que con el botón
  // adjuntar. Solo se aceptan tipos image/*.
  const [isDragging, setIsDragging] = useState(false);
  const dragCounterRef = useRef(0);

  const handleDragEnter = (e) => {
    e.preventDefault(); e.stopPropagation();
    if (!e.dataTransfer?.types?.includes('Files')) return;
    dragCounterRef.current += 1;
    setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault(); e.stopPropagation();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragging(false);
    }
  };
  const handleDragOver = (e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
  };
  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragging(false);
    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length === 0) return;
    // Solo procesamos imágenes; ignoramos PDFs/zips/etc. (Meta Cloud API
    // exige endpoints distintos para otros tipos y para acá el caso de uso
    // es comprobantes/screenshots).
    const images = files.filter(f => f.type.startsWith('image/'));
    if (images.length === 0) {
      toast.error('Solo se permiten imágenes. Para otros archivos usá el botón adjuntar.');
      return;
    }
    if (images.length > 1) {
      toast.info(`Enviando ${images.length} imagen${images.length === 1 ? '' : 'es'}…`);
    }
    // Mandamos una por una respetando el orden del drop
    images.reduce((p, f) => p.then(() => sendImage(f)), Promise.resolve());
  };

  // Paste de imágenes desde el portapapeles (Ctrl+V con un screenshot)
  const handlePaste = (e) => {
    const items = Array.from(e.clipboardData?.items || []);
    const imgs = items
      .filter(it => it.type.startsWith('image/'))
      .map(it => it.getAsFile())
      .filter(Boolean);
    if (imgs.length === 0) return; // dejar que el paste normal de texto siga
    e.preventDefault();
    imgs.reduce((p, f) => p.then(() => sendImage(f)), Promise.resolve());
  };

  const sendImage = async (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      toast.error('La imagen supera los 10 MB');
      return;
    }
    setSending(true);
    const form = new FormData();
    form.append('file', file);
    if (newMessage.trim()) form.append('caption', newMessage.trim());
    try {
      await api.post(`/crm/leads/${lead.id}/messages/image`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setNewMessage('');
      toast.success('Imagen enviada');
      loadMessages();
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Error enviando imagen';
      toast.error(typeof detail === 'string' ? detail : 'Error enviando imagen');
    } finally {
      setSending(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ── Audio recording (voice note, WhatsApp style) ──────────────
  const [recording, setRecording] = useState(false);
  const [recordSecs, setRecordSecs] = useState(0);
  const mediaRecorderRef = useRef(null);
  const recordStartRef = useRef(null);
  const recordTimerRef = useRef(null);

  const pickAudioMime = () => {
    const candidates = [
      'audio/ogg;codecs=opus',
      'audio/webm;codecs=opus',
      'audio/mp4',
      'audio/mpeg',
    ];
    for (const mt of candidates) {
      try { if (window.MediaRecorder && MediaRecorder.isTypeSupported(mt)) return mt; } catch {}
    }
    return '';
  };

  const sendAudio = async (blob, mimeType) => {
    setSending(true);
    const ext = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('webm') ? 'webm' : mimeType.includes('mp4') ? 'm4a' : 'mp3';
    const file = new File([blob], `voice-${Date.now()}.${ext}`, { type: mimeType });
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post(`/crm/leads/${lead.id}/messages/audio`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      if (data && data.whatsapp_sent === false) {
        const waErr = data.whatsapp_result?.error?.message || JSON.stringify(data.whatsapp_result || {});
        toast.error(`Audio guardado, pero WhatsApp lo rechazó: ${waErr}`);
      } else {
        toast.success('Audio enviado');
      }
      loadMessages();
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Error enviando audio';
      toast.error(typeof detail === 'string' ? detail : 'Error enviando audio');
    } finally {
      setSending(false);
    }
  };

  const startRecording = async () => {
    if (recording || sending) return;
    try {
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        toast.error('Tu navegador no soporta grabación de audio');
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickAudioMime();
      const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks = [];
      mr.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        if (recordTimerRef.current) { clearInterval(recordTimerRef.current); recordTimerRef.current = null; }
        const elapsed = recordStartRef.current ? (Date.now() - recordStartRef.current) : 0;
        setRecording(false);
        setRecordSecs(0);
        mediaRecorderRef.current = null;
        if (elapsed < 500 || mr._cancelled) return;
        const blob = new Blob(chunks, { type: mr.mimeType || 'audio/ogg' });
        if (blob.size < 200) return;
        await sendAudio(blob, mr.mimeType || 'audio/ogg');
      };
      mediaRecorderRef.current = mr;
      recordStartRef.current = Date.now();
      setRecording(true);
      setRecordSecs(0);
      recordTimerRef.current = setInterval(() => {
        setRecordSecs(Math.floor((Date.now() - recordStartRef.current) / 1000));
      }, 500);
      mr.start();
    } catch (e) {
      toast.error('No se pudo acceder al micrófono');
    }
  };

  const stopRecording = (cancel = false) => {
    const mr = mediaRecorderRef.current;
    if (!mr) return;
    mr._cancelled = cancel;
    try { mr.stop(); } catch {}
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
    // Request a rotated/humanized variant from the backend. Same logic used
    // by the auto-welcome path, so manual clicks don't produce the identical
    // byte-for-byte message pattern that Meta Integrity flags.
    let mensaje = '';
    try {
      const { data } = await api.get('/auth/me/welcome-variant');
      mensaje = (data?.message || '').trim();
    } catch { /* fallthrough to template */ }
    if (!mensaje) {
      mensaje = userMessages.welcome_message || `¡Buenas!👋 Trabajamos con las plataformas MÁS COMPLETAS del país!  
💟 ¡GANAMOS! 💟 💜 GANAMOSvip 💜 🥇 OROPURO 🥇  
ℹ MINIMOS: $2000 Acreditación // $5000 Retiro. 
🏦 Retiras tus ganancias UNA vez cada 24hs! 
⛔ No abonamos ni trabajamos con Ruletas 
🎁B0N0 ¡Beneficio de bienvenida activado! B0N0🎁  
✨¡Decime tu nombre para generar el usuario!✨`;
    }
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
      await navigator.clipboard.writeText(clipboardText);
    } catch { toast.error('Error enviando datos de usuario'); }
  };

  const sendDerivar = async (number) => {
    const baseMsg = (userMessages.derivation_message || '').trim()
      || 'Genial! Para realizar la carga te pido que envíes comprobante y usuario al siguiente número:';
    const mensaje = `${baseMsg}\n${number}`;
    setShowDerivarMenu(false);
    try {
      await api.post(`/crm/leads/${lead.id}/messages`, { content: mensaje, sender: 'admin' });
      loadMessages();
      toast.success(`Derivado a ${number}`);
    } catch { toast.error('Error enviando derivación'); }
  };

  const sendCbu = async (item) => {
    setShowCbuMenu(false);
    const cbu = (item?.cbu || '').trim();
    const name = (item?.name || '').trim();
    if (!cbu) { toast.error('CBU inválido'); return; }
    try {
      // First message: CBU alone (so client can copy without line breaks)
      await api.post(`/crm/leads/${lead.id}/messages`, { content: cbu, sender: 'admin' });
      // Tiny delay so the two messages arrive in order on WhatsApp
      await new Promise(r => setTimeout(r, 350));
      if (name) {
        await api.post(`/crm/leads/${lead.id}/messages`, { content: name, sender: 'admin' });
      }
      loadMessages();
      toast.success(name ? `CBU enviado (${name})` : 'CBU enviado');
    } catch { toast.error('Error enviando CBU'); }
  };

  const startEditName = () => {
    setNameDraft(lead.name || '');
    setEditingName(true);
  };

  const cancelEditName = () => {
    setEditingName(false);
    setNameDraft('');
  };

  const saveEditName = async () => {
    const trimmed = nameDraft.trim();
    if (!trimmed) { toast.error('El nombre no puede estar vacío'); return; }
    if (trimmed === (lead.name || '').trim()) { cancelEditName(); return; }
    setSavingName(true);
    try {
      const { data } = await api.patch(`/crm/leads/${lead.id}/name`, {
        name: trimmed,
        refire_meta: true,
      });
      const refired = Array.isArray(data?.refired_events) ? data.refired_events : [];
      if (refired.length > 0) {
        toast.success(`Nombre actualizado · Meta re-enviado (${refired.join(', ')})`);
      } else {
        toast.success('Nombre actualizado');
      }
      setEditingName(false);
      setNameDraft('');
      if (onLeadUpdated && data?.lead) onLeadUpdated(data.lead);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error guardando el nombre');
    } finally {
      setSavingName(false);
    }
  };

  const deleteChat = async () => {
    const label = lead.name || lead.phone;
    if (!window.confirm(
      `¿Eliminar el chat con ${label}?\n\n` +
      `Se va a ocultar del CRM. Si el contacto vuelve a escribir, el chat reaparece con el historial completo.`
    )) return;
    try {
      await api.delete(`/crm/leads/${lead.id}`);
      toast.success('Chat eliminado');
      if (onLeadDeleted) onLeadDeleted(lead.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error eliminando el chat');
    }
  };

  // Close derivar/cbu dropdowns on outside click
  useEffect(() => {
    if (!showDerivarMenu && !showCbuMenu) return;
    const onClick = (e) => {
      if (showDerivarMenu && derivarRef.current && !derivarRef.current.contains(e.target)) {
        setShowDerivarMenu(false);
      }
      if (showCbuMenu && cbuRef.current && !cbuRef.current.contains(e.target)) {
        setShowCbuMenu(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [showDerivarMenu, showCbuMenu]);

  const dotColor = STATUS_CONFIG[lead.status]?.dot || 'bg-blue-400';

  return (
    <div
      className="flex flex-col h-full w-full flex-1 min-w-0 bg-slate-950 relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      data-testid="chat-drop-zone"
    >
      {/* Overlay visual cuando el usuario arrastra archivos sobre el chat */}
      {isDragging && (
        <div className="absolute inset-0 z-30 pointer-events-none flex items-center justify-center bg-emerald-500/10 backdrop-blur-sm border-4 border-dashed border-emerald-400/60 rounded-lg"
          data-testid="chat-drop-overlay">
          <div className="bg-slate-900/90 border border-emerald-500/60 rounded-xl px-6 py-4 text-center shadow-2xl">
            <ImageIcon className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
            <p className="text-sm font-semibold text-white">Soltá la imagen para enviarla</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Acepta JPG, PNG, WEBP, GIF</p>
          </div>
        </div>
      )}
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-slate-700 bg-slate-900/80 flex items-center justify-between shrink-0 backdrop-blur">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {showBackButton && (
            <button
              onClick={onBack}
              data-testid="chat-back-btn"
              className="p-2 -ml-1 text-slate-300 hover:text-white rounded-full hover:bg-slate-800 transition-colors shrink-0"
              aria-label="Volver a conversaciones"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}
          <LeadAvatar lead={lead} size="sm" statusClass={dotColor} />
          <div className="min-w-0 flex-1">
            {editingName ? (
              <div className="flex items-center gap-1.5">
                <Input
                  value={nameDraft}
                  onChange={e => setNameDraft(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') { e.preventDefault(); saveEditName(); }
                    else if (e.key === 'Escape') { e.preventDefault(); cancelEditName(); }
                  }}
                  autoFocus
                  disabled={savingName}
                  placeholder="Nombre real del cliente"
                  className="h-7 text-sm bg-slate-800 border-slate-600 text-white px-2 py-0"
                  data-testid="lead-name-input"
                />
                <button
                  type="button"
                  onClick={saveEditName}
                  disabled={savingName || !nameDraft.trim()}
                  className="p-1 text-emerald-400 hover:text-emerald-300 disabled:opacity-40 rounded hover:bg-emerald-500/10"
                  data-testid="lead-name-save"
                  title="Guardar (Enter)"
                >
                  <CheckIcon className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={cancelEditName}
                  disabled={savingName}
                  className="p-1 text-slate-400 hover:text-red-400 rounded hover:bg-red-500/10"
                  data-testid="lead-name-cancel"
                  title="Cancelar (Esc)"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1 group">
                <p className="text-sm font-semibold text-white leading-tight truncate" data-testid="lead-name-display">
                  {lead.name || lead.phone}
                </p>
                <button
                  type="button"
                  onClick={startEditName}
                  className="p-0.5 text-slate-500 hover:text-blue-400 opacity-60 hover:opacity-100 rounded shrink-0"
                  data-testid="lead-name-edit-btn"
                  title="Editar nombre del lead (re-envía a Meta con fn/ln corregidos)"
                >
                  <Pencil className="w-3 h-3" />
                </button>
              </div>
            )}
            <p className="text-xs text-slate-400 truncate">{lead.phone}{lead.line_name ? ` · ${lead.line_name}` : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <StatusSelector currentStatus={lead.status} onSelect={handleStatusChange} />
          <button
            type="button"
            onClick={deleteChat}
            data-testid="chat-delete-btn"
            className="p-1.5 text-slate-400 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"
            title="Eliminar chat del CRM (reaparece si el contacto vuelve a escribir)"
            aria-label="Eliminar chat"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          {showCloseButton && (
            <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Tags row */}
      <div className="px-3 py-1.5 border-b border-slate-800 bg-slate-900/40 shrink-0">
        <LeadTagsBar
          lead={lead}
          onChange={({ tags, tag_details }) => {
            onLeadUpdated?.({ ...lead, tags, tag_details });
          }}
        />
      </div>

      {/* Conversion value modal — centered overlay to avoid z-index issues
          with the chat panel layout. Cajero just clicks "Validar" and a
          clean dialog appears asking for the sale amount. */}
      {showConversionInput && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={() => { setShowConversionInput(false); setConversionValue(''); }}
          data-testid="conversion-modal-backdrop"
        >
          <div
            className="w-full max-w-sm rounded-xl border border-emerald-700/40 bg-slate-900 shadow-2xl p-5"
            onClick={e => e.stopPropagation()}
            data-testid="conversion-modal"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="w-9 h-9 rounded-full bg-emerald-500/15 flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">Marcar como Válido</p>
                <p className="text-[11px] text-slate-400">Ingresá el monto de la venta</p>
              </div>
            </div>
            <Input
              type="number"
              inputMode="decimal"
              placeholder="Ej: 1500"
              value={conversionValue}
              onChange={e => setConversionValue(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') confirmValido(); }}
              className="bg-slate-800 border-slate-600 text-white text-base h-10"
              autoFocus
              data-testid="conversion-amount-input"
            />
            <div className="mt-4 flex items-center gap-2 justify-end">
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setShowConversionInput(false); setConversionValue(''); }}
                className="border-slate-600 text-slate-300 hover:bg-slate-800"
                data-testid="conversion-cancel-btn"
              >
                Cancelar
              </Button>
              <Button
                size="sm"
                onClick={confirmValido}
                className="bg-emerald-600 hover:bg-emerald-500 text-white"
                data-testid="conversion-confirm-btn"
              >
                Confirmar venta
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Ad Preview */}
      <AdPreviewCard
        preview={adPreview}
        collapsed={adCollapsed}
        onToggle={() => setAdCollapsed(v => !v)}
      />

      {/* Quick actions bar */}
      <div className="px-3 py-2 border-b border-slate-800 bg-slate-800/30 flex items-center gap-2 shrink-0">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shrink-0" />
        <span className="text-xs text-slate-400 hidden sm:inline">Chat en tiempo real</span>
        <div className="flex items-center gap-1.5 ml-auto">
          <Button onClick={sendBienvenida} size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-2 sm:px-3 h-7">
            👋<span className="hidden sm:inline ml-1">Bienvenida</span>
          </Button>
          <Button onClick={sendUsuario} size="sm" className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-2 sm:px-3 h-7">
            👤<span className="hidden sm:inline ml-1">Usuario</span>
          </Button>
          <div className="relative" ref={derivarRef}>
            <Button
              onClick={() => setShowDerivarMenu(v => !v)}
              size="sm"
              className="bg-amber-600 hover:bg-amber-500 text-white text-xs px-2 sm:px-3 h-7"
              data-testid="chat-derivar-btn"
              disabled={!Array.isArray(userMessages.derivation_numbers) || userMessages.derivation_numbers.length === 0}
              title={
                Array.isArray(userMessages.derivation_numbers) && userMessages.derivation_numbers.length > 0
                  ? 'Derivar a un número'
                  : 'Cargá números de derivación en tu perfil'
              }
            >
              <Share2 className="w-3.5 h-3.5" /><span className="hidden sm:inline ml-1">Derivar</span>
            </Button>
            {showDerivarMenu && Array.isArray(userMessages.derivation_numbers) && userMessages.derivation_numbers.length > 0 && (
              <div
                className="absolute right-0 top-full mt-1.5 w-64 max-h-80 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl z-50"
                data-testid="chat-derivar-menu"
              >
                <div className="px-3 py-2 border-b border-slate-700 text-[11px] uppercase tracking-wide text-slate-400 sticky top-0 bg-slate-900">
                  Elegí un número ({userMessages.derivation_numbers.length})
                </div>
                {userMessages.derivation_numbers.map((num, idx) => (
                  <button
                    key={`${num}-${idx}`}
                    type="button"
                    onClick={() => sendDerivar(num)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-amber-500/15 border-b border-slate-800 last:border-b-0 text-left"
                    data-testid={`chat-derivar-option-${idx}`}
                  >
                    <Phone className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span className="font-mono">{num}</span>
                    <span className="ml-auto text-[10px] text-slate-500">#{idx + 1}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="relative" ref={cbuRef}>
            <Button
              onClick={() => setShowCbuMenu(v => !v)}
              size="sm"
              className="bg-purple-600 hover:bg-purple-500 text-white text-xs px-2 sm:px-3 h-7"
              data-testid="chat-cbu-btn"
              disabled={!Array.isArray(userMessages.cbu_list) || userMessages.cbu_list.length === 0}
              title={
                Array.isArray(userMessages.cbu_list) && userMessages.cbu_list.length > 0
                  ? 'Enviar CBU + nombre'
                  : 'Cargá CBUs en tu perfil'
              }
            >
              <Landmark className="w-3.5 h-3.5" /><span className="hidden sm:inline ml-1">CBU</span>
            </Button>
            {showCbuMenu && Array.isArray(userMessages.cbu_list) && userMessages.cbu_list.length > 0 && (
              <div
                className="absolute right-0 top-full mt-1.5 w-72 max-h-80 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl z-50"
                data-testid="chat-cbu-menu"
              >
                <div className="px-3 py-2 border-b border-slate-700 text-[11px] uppercase tracking-wide text-slate-400 sticky top-0 bg-slate-900">
                  Elegí un CBU ({userMessages.cbu_list.length})
                </div>
                {userMessages.cbu_list.map((item, idx) => (
                  <button
                    key={`${item?.cbu || ''}-${idx}`}
                    type="button"
                    onClick={() => sendCbu(item)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-purple-500/15 border-b border-slate-800 last:border-b-0 text-left"
                    data-testid={`chat-cbu-option-${idx}`}
                  >
                    <Landmark className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate">{item?.name || '(sin nombre)'}</div>
                      <div className="text-[10px] text-slate-500 font-mono truncate">{item?.cbu}</div>
                    </div>
                    <span className="text-[10px] text-slate-500 shrink-0">#{idx + 1}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button onClick={loadMessages} variant="ghost" size="sm" className="text-slate-400 hover:text-white h-7 w-7 p-0">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div className="relative flex-1 overflow-hidden">
        <div
          ref={messagesContainerRef}
          onScroll={handleScroll}
          className="absolute inset-0 overflow-y-auto p-3 sm:p-4 space-y-2"
          data-testid="chat-messages-container"
        >
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-slate-600">
              <MessageCircle className="w-8 h-8 mb-2 opacity-20" />
              <p className="text-xs">Sin mensajes aún</p>
            </div>
          ) : messages.map(msg => <ChatMessage key={msg.id} message={msg} />)}
          <div ref={messagesEndRef} />
        </div>

        {/* Floating "new messages" pill — only shows when cajero scrolled up
            AND new incoming messages arrived. Click jumps to the bottom. */}
        {!isNearBottom && (
          <button
            type="button"
            onClick={() => scrollToBottom('smooth')}
            data-testid="chat-jump-to-bottom"
            className={`absolute right-3 bottom-3 z-10 inline-flex items-center gap-1.5 rounded-full shadow-lg transition-all ${
              unreadCount > 0
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 text-xs font-semibold'
                : 'bg-slate-700/90 hover:bg-slate-600 text-slate-100 w-9 h-9 justify-center'
            }`}
            aria-label="Ir al final"
            title={unreadCount > 0 ? `${unreadCount} mensaje${unreadCount > 1 ? 's' : ''} nuevo${unreadCount > 1 ? 's' : ''}` : 'Ir al final'}
          >
            <ArrowDown className="w-4 h-4" />
            {unreadCount > 0 && (
              <span data-testid="chat-unread-count">
                {unreadCount} nuevo{unreadCount > 1 ? 's' : ''}
              </span>
            )}
          </button>
        )}
      </div>

      {/* Input */}
      <div className="p-2 sm:p-3 border-t border-slate-800 bg-slate-900/80 shrink-0">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/jpg,image/png,image/webp,image/gif"
          className="hidden"
          data-testid="chat-image-input"
          onChange={e => sendImage(e.target.files?.[0])}
        />
        {recording ? (
          <div className="flex items-center gap-2" data-testid="chat-recording-bar">
            <Button
              onClick={() => stopRecording(true)}
              variant="outline"
              size="icon"
              className="border-red-500/40 text-red-300 hover:bg-red-500/10 shrink-0"
              title="Cancelar grabación"
            >
              <X className="w-4 h-4" />
            </Button>
            <div className="flex-1 flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
              <span className="text-red-200 text-sm font-medium">Grabando…</span>
              <span className="text-red-200/70 text-xs font-mono ml-auto">
                {Math.floor(recordSecs / 60).toString().padStart(2, '0')}:{(recordSecs % 60).toString().padStart(2, '0')}
              </span>
            </div>
            <Button
              onClick={() => stopRecording(false)}
              size="icon"
              className="bg-red-600 hover:bg-red-700 shrink-0"
              title="Detener y enviar"
              data-testid="chat-stop-record-btn"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        ) : (
          <div className="flex gap-1.5 sm:gap-2 items-center">
            <Button
              onClick={handleImagePick}
              disabled={sending}
              variant="outline"
              size="icon"
              className="border-slate-600 text-slate-300 hover:text-white hover:bg-slate-800 shrink-0"
              title="Adjuntar imagen"
              data-testid="chat-attach-image-btn"
            >
              <ImageIcon className="w-4 h-4" />
            </Button>
            <Button
              onClick={startRecording}
              disabled={sending}
              variant="outline"
              size="icon"
              className="border-slate-600 text-slate-300 hover:text-white hover:bg-slate-800 shrink-0"
              title="Grabar audio"
              data-testid="chat-record-audio-btn"
            >
              <Mic className="w-4 h-4" />
            </Button>
            <Textarea
              ref={inputRef}
              placeholder={sending ? 'Enviando...' : 'Escribí un mensaje... (Shift+Enter = nueva línea, Ctrl+V para pegar imagen)'}
              value={newMessage}
              onChange={e => setNewMessage(e.target.value)}
              onPaste={handlePaste}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage('admin');
                }
              }}
              rows={1}
              className="flex-1 bg-slate-800 border-slate-600 text-white text-sm min-w-0 min-h-[36px] max-h-[160px] resize-none py-1.5 leading-tight"
              disabled={sending}
              data-testid="chat-input"
            />
            <Button
              onClick={() => sendMessage('lead')}
              disabled={sending || !newMessage.trim()}
              variant="outline"
              size="icon"
              className="border-slate-600 shrink-0 hidden sm:inline-flex"
              title="Registrar como mensaje del lead"
            >
              <Users className="w-4 h-4" />
            </Button>
            <Button
              onClick={() => sendMessage('admin')}
              disabled={sending || !newMessage.trim()}
              size="icon"
              className="bg-blue-600 hover:bg-blue-700 shrink-0"
              data-testid="chat-send-btn"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
