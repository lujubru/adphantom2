import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import api from '@/utils/api';
import { BACKEND_URL } from './constants';
import { formatTime } from './utils';
import { ImageLightbox } from './ImageLightbox';

export const ChatMessage = ({ message }) => {
  const isAdmin = message.sender === 'admin';
  const [imgSrc, setImgSrc] = useState(null);
  const [loadingImg, setLoadingImg] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [docSrc, setDocSrc] = useState(null);
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [audioSrc, setAudioSrc] = useState(null);
  const [loadingAudio, setLoadingAudio] = useState(false);

  const adminImgUrl = message.image_path
    ? `${BACKEND_URL}/api/crm/chat-image/${message.image_path}`
    : null;

  const loadImage = useCallback(async () => {
    if (imgSrc || loadingImg) return;
    if (adminImgUrl) {
      setImgSrc(adminImgUrl);
      return;
    }
    setLoadingImg(true);
    try {
      const { data } = await api.get(`/crm/messages/${message.id}/image`);
      setImgSrc(`data:${data.mime_type};base64,${data.image_base64}`);
    } catch { /* silent */ }
    finally { setLoadingImg(false); }
  }, [message.id, imgSrc, loadingImg, adminImgUrl]);

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

  const loadAudio = useCallback(async () => {
    if (audioSrc || loadingAudio) return;
    if (message.audio_path) {
      setAudioSrc(`${BACKEND_URL}/api/crm/chat-audio/${message.audio_path}`);
      return;
    }
    setLoadingAudio(true);
    try {
      const { data } = await api.get(`/crm/messages/${message.id}/audio`);
      setAudioSrc(`data:${data.mime_type};base64,${data.audio_base64}`);
    } catch { /* silent */ }
    finally { setLoadingAudio(false); }
  }, [message.id, audioSrc, loadingAudio, message.audio_path]);

  useEffect(() => {
    if (message.message_type === 'image' && (message.media_id || message.image_path)) loadImage();
    if (message.message_type === 'document' && message.media_id) loadDocument();
    if (message.message_type === 'audio' && (message.media_id || message.audio_path)) loadAudio();
  }, [message.id]); // eslint-disable-line

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
          ) : message.message_type === 'audio' ? (
            loadingAudio ? (
              <div className="flex items-center gap-2 text-xs opacity-70"><RefreshCw className="w-3 h-3 animate-spin" />Cargando audio...</div>
            ) : audioSrc ? (
              <div className="flex items-center gap-2 min-w-[200px]">
                <span className="text-lg">🎤</span>
                <audio controls className="h-10 max-w-[250px]" preload="metadata">
                  <source src={audioSrc} type={message.mime_type || 'audio/ogg'} />
                  Tu navegador no soporta audio
                </audio>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs opacity-60">
                <span>🎤</span> Audio no disponible
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
