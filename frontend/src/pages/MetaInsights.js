import React, { useState, useEffect, useCallback } from 'react';
import {
  Zap, RefreshCw, Check, X, BarChart3, Target,
  Phone, Smartphone, ArrowRight, DollarSign, Eye, MessageCircle,
  ChevronDown, TrendingUp
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/utils/api';
import { useTheme } from '@/contexts/ThemeContext';

// ─── EMQ Score by Line — tier breakdown 12+ / 10-11 / 8-9 / <8 ─────

const EMQByLine = ({ days }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const { data: d } = await api.get('/crm/emq/by-line', { params: { days } });
        setData(d);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, [days]);

  if (loading) return (
    <div className="bg-slate-900/50 rounded-xl p-6 border border-slate-800 flex items-center justify-center h-32">
      <RefreshCw className="w-5 h-5 text-blue-400 animate-spin" />
    </div>
  );

  if (!data || !data.lines || data.lines.length === 0) return (
    <div className="bg-slate-900/50 rounded-xl p-6 border border-slate-800 text-center" data-testid="emq-by-line-empty">
      <BarChart3 className="w-8 h-8 text-slate-600 mx-auto mb-2" />
      <p className="text-slate-400 text-sm">Sin eventos por línea en este período</p>
    </div>
  );

  const tierMeta = [
    { key: 'excellent', label: '12+ params',  color: 'bg-emerald-500', text: 'text-emerald-400', range: 'Excelente' },
    { key: 'good',      label: '10-11 params', color: 'bg-blue-500',    text: 'text-blue-400',    range: 'Buena' },
    { key: 'normal',    label: '8-9 params',   color: 'bg-amber-500',   text: 'text-amber-400',   range: 'Normal' },
    { key: 'low',       label: '<8 params',    color: 'bg-red-500',     text: 'text-red-400',     range: 'Baja' },
  ];

  const totals = data.totals;

  return (
    <div className="space-y-4" data-testid="emq-by-line">
      {/* Global tier summary — single horizontal stacked bar */}
      <div className="bg-slate-900/50 rounded-xl border border-slate-800 p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-white">Distribución global de calidad ({data.period_days} días)</p>
          <span className="text-xs text-slate-400">{totals.total} eventos · {totals.avg_params} params promedio</span>
        </div>
        <div className="flex h-4 rounded-md overflow-hidden bg-slate-800 mb-2" data-testid="emq-global-bar">
          {tierMeta.map(t => totals.tier_pct[t.key] > 0 && (
            <div
              key={t.key}
              className={`${t.color} transition-all`}
              style={{ width: `${totals.tier_pct[t.key]}%` }}
              title={`${t.label}: ${totals.tiers[t.key]} (${totals.tier_pct[t.key]}%)`}
            />
          ))}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
          {tierMeta.map(t => (
            <div key={t.key} className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-sm ${t.color}`} />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-400 truncate">{t.label}</p>
                <p className={`text-sm font-bold ${t.text}`}>{totals.tier_pct[t.key]}% <span className="text-slate-500 font-normal text-xs">({totals.tiers[t.key]})</span></p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Per-line breakdown */}
      <div className="bg-slate-900/50 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
          <p className="text-sm font-semibold text-white">EMQ Score por Línea</p>
          <span className="text-[11px] text-slate-500">Tu Pixel ranquea según estos parámetros</span>
        </div>
        <div className="divide-y divide-slate-800/50">
          {data.lines.map(line => {
            const dominant = ['excellent','good','normal','low'].reduce((a,b)=> line.tier_pct[a] >= line.tier_pct[b] ? a : b);
            const dominantMeta = tierMeta.find(t => t.key === dominant);
            return (
              <div key={line.line_id || 'none'} className="px-4 py-3 hover:bg-slate-800/30 transition-colors" data-testid={`emq-line-row-${line.line_id || 'none'}`}>
                {/* Header row */}
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{line.line_name}</p>
                    <p className="text-[11px] text-slate-500">{line.total} eventos · {line.events.Purchase || 0} Purchase · {line.events.Lead || 0} Lead · {line.events.Contact || 0} Contact</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className={`text-base font-bold ${dominantMeta.text}`}>{line.avg_emq_score}%</p>
                    <p className="text-[10px] text-slate-500">{line.avg_params} params</p>
                  </div>
                </div>

                {/* Stacked tier bar */}
                <div className="flex h-2.5 rounded-sm overflow-hidden bg-slate-800">
                  {tierMeta.map(t => line.tier_pct[t.key] > 0 && (
                    <div
                      key={t.key}
                      className={`${t.color} transition-all`}
                      style={{ width: `${line.tier_pct[t.key]}%` }}
                      title={`${t.label}: ${line.tiers[t.key]} (${line.tier_pct[t.key]}%)`}
                    />
                  ))}
                </div>

                {/* Signals + missing */}
                <div className="mt-2 flex items-center gap-3 flex-wrap text-[11px]">
                  <span className={`font-medium ${line.signals.fbp_rate >= 80 ? 'text-emerald-400' : line.signals.fbp_rate >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
                    fbp {line.signals.fbp_rate}%
                  </span>
                  <span className={`font-medium ${line.signals.fbc_rate >= 80 ? 'text-emerald-400' : line.signals.fbc_rate >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
                    fbc {line.signals.fbc_rate}%
                  </span>
                  <span className={`font-medium ${line.signals.email_rate >= 50 ? 'text-emerald-400' : line.signals.email_rate >= 20 ? 'text-amber-400' : 'text-slate-500'}`}>
                    email {line.signals.email_rate}%
                  </span>
                  <span className={`font-medium ${line.success_rate >= 95 ? 'text-emerald-400' : line.success_rate >= 80 ? 'text-amber-400' : 'text-red-400'}`}>
                    OK {line.success_rate}%
                  </span>
                  {line.top_missing.length > 0 && (
                    <span className="text-slate-500 ml-auto" title="Parámetros que más se pierden — agregalos para mejorar EMQ">
                      falta: <span className="text-slate-300 font-mono">{line.top_missing.join(', ')}</span>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ─── EMQ Dashboard ─────────────────────────────────────────────────

const EMQDashboard = ({ lineId, days }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const params = { days };
        if (lineId) params.line_id = lineId;
        const { data: d } = await api.get('/crm/emq/dashboard', { params });
        setData(d);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, [lineId, days]);

  if (loading) return (
    <div className="bg-slate-900/50 rounded-xl p-6 border border-slate-800 flex items-center justify-center h-40">
      <RefreshCw className="w-5 h-5 text-blue-400 animate-spin" />
    </div>
  );

  if (!data || data.total_events === 0) return (
    <div className="bg-slate-900/50 rounded-xl p-6 border border-slate-800 text-center">
      <Zap className="w-8 h-8 text-slate-600 mx-auto mb-2" />
      <p className="text-slate-400 text-sm">Sin eventos Meta registrados</p>
      <p className="text-slate-500 text-xs mt-1">Los eventos aparecen cuando se clasifica un lead como válido, spam o consultas</p>
    </div>
  );

  const scoreColor = data.avg_emq_score >= 80 ? 'text-emerald-400' : data.avg_emq_score >= 60 ? 'text-blue-400' : data.avg_emq_score >= 40 ? 'text-amber-400' : 'text-red-400';
  const scoreBg = data.avg_emq_score >= 80 ? 'bg-emerald-500' : data.avg_emq_score >= 60 ? 'bg-blue-500' : data.avg_emq_score >= 40 ? 'bg-amber-500' : 'bg-red-500';
  const scoreBorder = data.avg_emq_score >= 80 ? 'border-emerald-500/30' : data.avg_emq_score >= 60 ? 'border-blue-500/30' : data.avg_emq_score >= 40 ? 'border-amber-500/30' : 'border-red-500/30';

  return (
    <div className="space-y-4" data-testid="emq-dashboard">
      {/* Score principal */}
      <div className={`bg-slate-900/50 rounded-xl border ${scoreBorder} p-6`}>
        <div className="flex items-center gap-6">
          <div className="relative w-24 h-24 shrink-0">
            <svg className="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-700" />
              <circle cx="18" cy="18" r="15.9" fill="none" strokeWidth="2.5" strokeDasharray={`${data.avg_emq_score} ${100 - data.avg_emq_score}`} strokeLinecap="round" className={scoreBg} />
            </svg>
            <span className={`absolute inset-0 flex items-center justify-center text-xl font-bold ${scoreColor}`}>{data.avg_emq_score}%</span>
          </div>
          <div className="flex-1">
            <p className={`text-2xl font-bold ${scoreColor}`}>{data.avg_emq_quality}</p>
            <p className="text-sm text-slate-400 mt-1">Event Match Quality promedio</p>
            <div className="flex items-center gap-4 mt-3 text-xs text-slate-400">
              <span>{data.total_events} eventos totales</span>
              <span className={data.success_rate >= 80 ? 'text-emerald-400' : 'text-amber-400'}>{data.success_rate}% exitosos</span>
            </div>
          </div>
        </div>
      </div>

      {/* Por tipo de evento */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.by_event_type.map(ev => {
          const isP = ev.event === 'Purchase';
          const isL = ev.event === 'LowQualityLead';
          const accent = isP ? 'border-emerald-500/30 bg-emerald-950/20' : isL ? 'border-red-500/30 bg-red-950/20' : 'border-blue-500/30 bg-blue-950/20';
          return (
            <div key={ev.event} className={`rounded-xl border p-4 ${accent}`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-white">{ev.event}</span>
                <span className="text-xs text-slate-400">{ev.count}</span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Params promedio</span>
                  <span className="text-white font-medium">{ev.avg_params}</span>
                </div>
                {[
                  { label: 'Facebook Cookie (fbp)', value: ev.fbp_rate },
                  { label: 'Click ID (fbc)', value: ev.fbc_rate },
                  { label: 'Teléfono', value: ev.phone_rate },
                  { label: 'Email', value: ev.email_rate },
                ].map(param => (
                  <div key={param.label} className="flex items-center gap-2 text-xs">
                    <span className="text-slate-500 flex-1">{param.label}</span>
                    <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${param.value >= 80 ? 'bg-emerald-500' : param.value >= 40 ? 'bg-blue-500' : param.value > 0 ? 'bg-amber-500' : 'bg-slate-600'}`}
                        style={{ width: `${param.value}%` }} />
                    </div>
                    <span className={`w-8 text-right font-medium ${param.value >= 80 ? 'text-emerald-400' : param.value > 0 ? 'text-slate-300' : 'text-slate-600'}`}>{param.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Últimos eventos */}
      <div className="bg-slate-900/50 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700">
          <p className="text-sm font-medium text-white">Últimos eventos enviados a Meta</p>
        </div>
        <div className="divide-y divide-slate-800/50 max-h-[400px] overflow-y-auto">
          {data.recent_events.map((ev, i) => {
            const sc = ev.emq_score;
            const c = sc >= 80 ? 'text-emerald-400' : sc >= 60 ? 'text-blue-400' : sc >= 40 ? 'text-amber-400' : 'text-red-400';
            const bg = sc >= 80 ? 'bg-emerald-500' : sc >= 60 ? 'bg-blue-500' : sc >= 40 ? 'bg-amber-500' : 'bg-red-500';
            return (
              <div key={i} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-800/30 transition-colors">
                {/* Score circle */}
                <div className="relative w-10 h-10 shrink-0">
                  <svg className="w-10 h-10 -rotate-90" viewBox="0 0 36 36">
                    <circle cx="18" cy="18" r="15" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-700" />
                    <circle cx="18" cy="18" r="15" fill="none" strokeWidth="2.5" strokeDasharray={`${sc} ${100 - sc}`} strokeLinecap="round" className={bg} />
                  </svg>
                  <span className={`absolute inset-0 flex items-center justify-center text-[10px] font-bold ${c}`}>{sc}%</span>
                </div>
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white">{ev.event}</span>
                    {ev.value && <span className="text-xs text-emerald-400 font-medium">${ev.value.toLocaleString()}</span>}
                    {ev.success ? <Check className="w-3 h-3 text-emerald-400" /> : <X className="w-3 h-3 text-red-400" />}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="truncate">{ev.lead_name || ev.lead_phone}</span>
                    <span>{ev.params_sent} params</span>
                    {ev.missing.length > 0 && <span className="text-slate-500">falta: {ev.missing.slice(0, 3).join(', ')}</span>}
                  </div>
                </div>
                <span className="text-[10px] text-slate-500 shrink-0">{ev.created_at ? new Date(ev.created_at).toLocaleDateString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ─── Ad Performance ────────────────────────────────────────────────

const AdPerformanceDashboard = ({ lineId, days }) => {
  const [adStats, setAdStats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const params = { days };
        if (lineId) params.line_id = lineId;
        const { data } = await api.get('/crm/funnel/by-ad', { params });
        setAdStats(data || []);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, [lineId, days]);

  if (loading) return (
    <div className="bg-slate-900/50 rounded-xl p-6 border border-slate-800 flex items-center justify-center h-32">
      <RefreshCw className="w-5 h-5 text-purple-400 animate-spin" />
    </div>
  );

  if (adStats.length === 0) return (
    <div className="bg-slate-900/50 rounded-xl p-6 border border-slate-800 text-center">
      <Target className="w-8 h-8 text-slate-600 mx-auto mb-2" />
      <p className="text-slate-400 text-sm">Sin datos de anuncios</p>
      <p className="text-slate-500 text-xs mt-1">Los leads con utm_content o ad_source aparecen aquí</p>
    </div>
  );

  const totalLeads = adStats.reduce((sum, ad) => sum + ad.leads, 0);
  const totalConversiones = adStats.reduce((sum, ad) => sum + ad.conversiones, 0);
  const totalMonto = adStats.reduce((sum, ad) => sum + ad.monto_total, 0);

  return (
    <div className="space-y-4" data-testid="ad-performance">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total Leads', value: totalLeads, color: 'text-white', icon: Users },
          { label: 'Conversiones', value: totalConversiones, color: 'text-emerald-400', icon: Check },
          { label: 'Monto Total', value: `$${totalMonto.toLocaleString()}`, color: 'text-amber-400', icon: DollarSign },
        ].map(card => (
          <div key={card.label} className="bg-slate-900/50 rounded-xl border border-slate-800 p-4 text-center">
            <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
            <p className="text-xs text-slate-400 mt-1">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Ad list */}
      <div className="bg-slate-900/50 rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700">
          <p className="text-sm font-medium text-white">Rendimiento por Anuncio</p>
        </div>
        <div className="divide-y divide-slate-800/50 max-h-[400px] overflow-y-auto">
          {adStats.map((ad, idx) => (
            <div key={ad.ad_source || idx} className="px-4 py-3 hover:bg-slate-800/30 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-purple-400 font-mono text-xs bg-purple-500/10 px-2 py-0.5 rounded">{ad.ad_source || 'Sin ID'}</span>
                  <span className="text-white font-medium text-sm">{ad.leads} leads</span>
                </div>
                <span className={`text-xs font-medium ${ad.conversion_rate >= 10 ? 'text-emerald-400' : ad.conversion_rate >= 5 ? 'text-amber-400' : 'text-slate-400'}`}>
                  {ad.conversion_rate}% conv.
                </span>
              </div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-slate-400"><span className="text-emerald-400 font-medium">{ad.conversiones}</span> válidos</span>
                <span className="text-amber-400 font-medium">${ad.monto_total.toLocaleString()}</span>
              </div>
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-purple-500 to-emerald-500 rounded-full transition-all"
                  style={{ width: `${Math.min((ad.leads / totalLeads) * 100, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ─── Main Page ─────────────────────────────────────────────────────

export default function MetaInsights() {
  const { darkMode } = useTheme();
  const [lines, setLines] = useState([]);
  const [selectedLineId, setSelectedLineId] = useState(null);
  const [days, setDays] = useState(30);
  const [activeTab, setActiveTab] = useState('emq');

  const loadLines = useCallback(async () => {
    try {
      const { data } = await api.get('/crm/lines');
      setLines(data || []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { loadLines(); }, [loadLines]);

  const bgMain = darkMode ? 'bg-slate-950' : 'bg-gray-50';
  const textPrimary = darkMode ? 'text-white' : 'text-gray-900';
  const textSecondary = darkMode ? 'text-slate-400' : 'text-gray-600';

  return (
    <div className={`min-h-screen ${bgMain} p-6`}>
      <div className="max-w-[1400px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className={`text-2xl font-bold ${textPrimary} flex items-center gap-3`}>
              <TrendingUp className="w-7 h-7 text-blue-500" /> Meta Insights
            </h1>
            <p className={`${textSecondary} text-sm mt-1`}>Event Match Quality y Rendimiento de Anuncios</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Filtro por línea */}
            <select
              value={selectedLineId || ''}
              onChange={e => setSelectedLineId(e.target.value || null)}
              className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-2"
              data-testid="line-filter"
            >
              <option value="">Todas las líneas</option>
              {lines.map(l => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
            {/* Filtro por período */}
            <select
              value={days}
              onChange={e => setDays(parseInt(e.target.value))}
              className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-2"
              data-testid="days-filter"
            >
              <option value="7">7 días</option>
              <option value="30">30 días</option>
              <option value="90">90 días</option>
            </select>
            <Button onClick={loadLines} variant="outline" size="sm" className={darkMode ? 'border-slate-600' : 'border-gray-300'}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-slate-900/50 p-1 rounded-xl border border-slate-800 w-fit">
          {[
            { key: 'emq', label: 'Event Match Quality', icon: Zap },
            { key: 'ads', label: 'Rendimiento Anuncios', icon: Target },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              data-testid={`tab-${tab.key}`}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? 'bg-slate-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {activeTab === 'emq' && (
          <div className="space-y-4" data-testid="emq-tab-content">
            <EMQByLine days={days} />
            <EMQDashboard lineId={selectedLineId} days={days} />
          </div>
        )}
        {activeTab === 'ads' && <AdPerformanceDashboard lineId={selectedLineId} days={days} />}
      </div>
    </div>
  );
}
