import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export const ImageLightbox = ({ src, onClose }) => {
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
