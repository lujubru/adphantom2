import React from 'react';
import { Megaphone, ChevronDown, ExternalLink, PlayCircle } from 'lucide-react';
import { BADGE_COLORS } from './constants';

export const AdPreviewCard = ({ preview, collapsed, onToggle }) => {
  if (!preview || !preview.has_preview) return null;
  const color = BADGE_COLORS[preview.badge_color] || BADGE_COLORS.blue;
  const isVideo = preview.media_type === 'video' && preview.video_url;
  const mediaUrl = preview.image_url || preview.thumbnail_url;

  return (
    <div
      data-testid="ad-preview-card"
      className={`mx-3 my-2 rounded-lg border ${color.border} ${color.bg} overflow-hidden shadow-sm`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors"
        data-testid="ad-preview-toggle"
      >
        <Megaphone className={`w-4 h-4 shrink-0 ${color.icon}`} />
        <span className={`text-[11px] font-bold uppercase tracking-wide ${color.text}`}>
          {preview.badge_label}
        </span>
        <span className={`w-1.5 h-1.5 rounded-full ${color.dot} animate-pulse`} />
        <span className="text-[11px] text-slate-400 truncate flex-1">
          {preview.headline}
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-slate-400 transition-transform ${collapsed ? '-rotate-90' : ''}`}
        />
      </button>

      {!collapsed && (
        <div className="px-3 pb-3 pt-1">
          <div className="flex gap-3">
            {mediaUrl && (
              <div className="relative w-20 h-20 shrink-0 rounded-md overflow-hidden bg-slate-800 border border-slate-700">
                <img
                  src={mediaUrl}
                  alt="ad preview"
                  className="w-full h-full object-cover"
                  onError={(e) => { e.target.style.display = 'none'; }}
                  data-testid="ad-preview-image"
                />
                {isVideo && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                    <PlayCircle className="w-8 h-8 text-white drop-shadow-lg" />
                  </div>
                )}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white leading-snug mb-1 line-clamp-2">
                {preview.headline}
              </p>
              {preview.body && (
                <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-3">
                  {preview.body}
                </p>
              )}
              <div className="mt-2 flex items-center gap-2 flex-wrap">
                {preview.source_url && (
                  <a
                    href={preview.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`inline-flex items-center gap-1 text-[11px] font-medium ${color.text} hover:underline`}
                    data-testid="ad-preview-source-link"
                  >
                    <ExternalLink className="w-3 h-3" />
                    {preview.source === 'meta_ctwa_ad' ? 'Ver anuncio' : preview.source === 'own_landing' ? 'Abrir landing' : 'Abrir'}
                  </a>
                )}
                {preview.ad_source && preview.ad_source !== preview.headline && (
                  <span className="text-[10px] text-slate-500 font-mono truncate">
                    {preview.ad_source}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
