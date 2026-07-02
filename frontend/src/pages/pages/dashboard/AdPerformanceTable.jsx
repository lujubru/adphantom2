import React from 'react';
import { Megaphone, TrendingUp, ExternalLink, Image as ImageIcon } from 'lucide-react';

const rateColor = (rate) => {
  if (rate >= 15) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  if (rate >= 8) return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
  if (rate >= 3) return 'text-blue-400 bg-blue-500/10 border-blue-500/30';
  return 'text-slate-500 bg-slate-800 border-slate-700';
};

export const AdPerformanceTable = ({ ads, loading }) => {
  if (loading) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center text-slate-500 text-sm">
        Cargando rendimiento por anuncio...
      </div>
    );
  }
  if (!ads?.length) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center">
        <Megaphone className="w-8 h-8 mx-auto mb-2 text-slate-600" />
        <p className="text-slate-500 text-sm">Sin datos de anuncios en este período.</p>
        <p className="text-slate-600 text-xs mt-1">Los leads con ad_source aparecerán acá.</p>
      </div>
    );
  }
  const maxLeads = Math.max(...ads.map(a => a.leads), 1);

  return (
    <div className="bg-slate-900/50 rounded-xl border border-slate-800 overflow-hidden" data-testid="ad-performance-table">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Megaphone className="w-4 h-4 text-purple-400" /> Rendimiento por Anuncio
        </h3>
        <span className="text-xs text-slate-500">{ads.length} anuncios</span>
      </div>

      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-800/40">
            <tr className="text-left text-xs uppercase text-slate-400">
              <th className="px-4 py-2 font-medium">Anuncio</th>
              <th className="px-4 py-2 font-medium text-right">Leads</th>
              <th className="px-4 py-2 font-medium text-right">Válidos</th>
              <th className="px-4 py-2 font-medium text-right">Conv.</th>
              <th className="px-4 py-2 font-medium text-right">Ingresos</th>
              <th className="px-4 py-2 font-medium text-right">Ticket</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {ads.map((ad, i) => (
              <tr key={ad.ad_source || i} className="hover:bg-slate-800/30 transition-colors group">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    {ad.preview_image ? (
                      <img
                        src={ad.preview_image}
                        alt=""
                        loading="lazy"
                        className="w-12 h-12 rounded-lg object-cover shrink-0 bg-slate-800"
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-lg bg-slate-800 shrink-0 flex items-center justify-center">
                        <ImageIcon className="w-4 h-4 text-slate-600" />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-white text-sm font-medium truncate max-w-[260px]" title={ad.headline}>
                        {ad.headline || ad.ad_source}
                      </p>
                      <p className="text-[11px] text-slate-500 font-mono truncate max-w-[260px]" title={ad.ad_source}>
                        {ad.ad_source}
                      </p>
                      <div className="mt-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-purple-500 to-emerald-500"
                          style={{ width: `${(ad.leads / maxLeads) * 100}%` }} />
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-right text-white font-semibold tabular-nums">{ad.leads}</td>
                <td className="px-4 py-3 text-right text-emerald-400 font-semibold tabular-nums">{ad.conversiones}</td>
                <td className="px-4 py-3 text-right">
                  <span className={`inline-flex px-2 py-0.5 rounded border text-xs font-semibold ${rateColor(ad.conversion_rate)}`}>
                    {ad.conversion_rate}%
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-amber-400 font-medium tabular-nums">
                  ${(ad.revenue || 0).toLocaleString('es-AR')}
                </td>
                <td className="px-4 py-3 text-right text-slate-400 tabular-nums">
                  ${(ad.avg_ticket || 0).toLocaleString('es-AR')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden divide-y divide-slate-800/60">
        {ads.map((ad, i) => (
          <div key={ad.ad_source || i} className="p-3">
            <div className="flex gap-3">
              {ad.preview_image ? (
                <img src={ad.preview_image} alt="" className="w-14 h-14 rounded-lg object-cover shrink-0 bg-slate-800"
                  onError={(e) => { e.target.style.display = 'none'; }} />
              ) : (
                <div className="w-14 h-14 rounded-lg bg-slate-800 shrink-0 flex items-center justify-center">
                  <ImageIcon className="w-4 h-4 text-slate-600" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm font-medium truncate" title={ad.headline}>
                  {ad.headline || ad.ad_source}
                </p>
                <p className="text-[10px] text-slate-500 font-mono truncate">{ad.ad_source}</p>
                <div className="flex items-center gap-3 mt-1.5 text-xs">
                  <span className="text-slate-300">{ad.leads} leads</span>
                  <span className="text-emerald-400">{ad.conversiones} válidos</span>
                  <span className={`ml-auto px-1.5 py-0.5 rounded border text-[10px] font-bold ${rateColor(ad.conversion_rate)}`}>
                    {ad.conversion_rate}%
                  </span>
                </div>
                <p className="text-amber-400 text-xs mt-1">${(ad.revenue || 0).toLocaleString('es-AR')}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
