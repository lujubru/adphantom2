import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, TrendingUp, DollarSign, Award, Target,
  RefreshCw, Filter, Sparkles, Percent,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import api from '@/utils/api';
import { KpiCard } from '@/pages/dashboard/KpiCard';
import { AdPerformanceTable } from '@/pages/dashboard/AdPerformanceTable';
import {
  TimelineChart, GenderPie, AgeBarChart, GeographyBar, HourlyHeatmap, DeviceChart,
} from '@/pages/dashboard/Charts';

const DATE_PRESETS = [
  { key: 'today', label: 'Hoy', days: 1 },
  { key: '7', label: '7 días', days: 7 },
  { key: '30', label: '30 días', days: 30 },
  { key: '90', label: '90 días', days: 90 },
];

const Dashboard = () => {
  const [lines, setLines] = useState([]);
  const [selectedLineId, setSelectedLineId] = useState('');
  const [periodKey, setPeriodKey] = useState('30');
  const [days, setDays] = useState(30);

  const [overview, setOverview] = useState(null);
  const [ads, setAds] = useState([]);
  const [demographics, setDemographics] = useState({ gender: [], age: [], age_unknown: 0 });
  const [geography, setGeography] = useState({ provinces: [], cities: [], countries: [] });
  const [timeline, setTimeline] = useState([]);
  const [heatmap, setHeatmap] = useState({ labels: [], matrix: [] });
  const [deviceStats, setDeviceStats] = useState({ devices: [], os: [], browsers: [] });

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const params = useCallback(() => {
    const p = { days };
    if (selectedLineId) p.line_id = selectedLineId;
    return p;
  }, [days, selectedLineId]);

  const loadAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const p = params();
      const [ov, ad, dm, ge, tl, hm, dv] = await Promise.all([
        api.get('/dashboard/overview', { params: p }),
        api.get('/dashboard/ad-performance', { params: p }),
        api.get('/dashboard/demographics', { params: p }),
        api.get('/dashboard/geography', { params: p }),
        api.get('/dashboard/timeline', { params: p }),
        api.get('/dashboard/hourly-heatmap', { params: p }),
        api.get('/dashboard/device-stats', { params: p }),
      ]);
      setOverview(ov.data);
      setAds(ad.data || []);
      setDemographics(dm.data || { gender: [], age: [], age_unknown: 0 });
      setGeography(ge.data || { provinces: [], cities: [], countries: [] });
      setTimeline(tl.data || []);
      setHeatmap(hm.data || { labels: [], matrix: [] });
      setDeviceStats(dv.data || { devices: [], os: [], browsers: [] });
    } catch (err) {
      if (!silent) toast.error('Error cargando dashboard');
      console.error('Dashboard load failed:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [params]);

  // Load lines once
  useEffect(() => {
    api.get('/crm/lines').then(({ data }) => setLines(data || [])).catch(() => {});
  }, []);

  // Reload whenever filters change
  useEffect(() => { loadAll(false); }, [loadAll]);

  // Auto refresh every 60s
  useEffect(() => {
    const iv = setInterval(() => loadAll(true), 60000);
    return () => clearInterval(iv);
  }, [loadAll]);

  const selectPeriod = (key) => {
    setPeriodKey(key);
    const preset = DATE_PRESETS.find(p => p.key === key);
    if (preset) setDays(preset.days);
  };

  const selectedLine = lines.find(l => l.id === selectedLineId);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Sticky filter bar */}
      <div className="sticky top-16 z-30 bg-slate-950/90 backdrop-blur-xl border-b border-slate-800">
        <div className="max-w-[1800px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-emerald-400" />
            <h1 className="text-lg font-bold">Panel de Marketing</h1>
          </div>

          <div className="ml-auto flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Filter className="w-3.5 h-3.5" />
              <span>Línea:</span>
            </div>
            <select
              value={selectedLineId}
              onChange={e => setSelectedLineId(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-white text-sm rounded-lg px-3 py-1.5 min-w-[160px]"
              data-testid="dashboard-line-select"
            >
              <option value="">Todas las líneas</option>
              {lines.map(l => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>

            <div className="flex items-center gap-0.5 bg-slate-900 border border-slate-700 rounded-lg p-0.5" data-testid="dashboard-period-toggle">
              {DATE_PRESETS.map(p => (
                <button
                  key={p.key}
                  onClick={() => selectPeriod(p.key)}
                  data-testid={`period-${p.key}`}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    periodKey === p.key ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <Button
              onClick={() => loadAll(false)}
              size="sm"
              variant="outline"
              className="border-slate-700 text-slate-300 hover:text-white"
              data-testid="dashboard-refresh-btn"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-4 sm:px-6 py-6 space-y-6">
        {selectedLine && (
          <div className="text-xs text-slate-400">
            Mostrando datos de <span className="text-white font-medium">{selectedLine.name}</span>
            {' · '}
            <span className="text-slate-500">
              {overview?.period?.start?.slice(0, 10)} → {overview?.period?.end?.slice(0, 10)}
            </span>
          </div>
        )}

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="kpi-row">
          <KpiCard
            testId="kpi-leads"
            icon={Users}
            label="Leads totales"
            value={overview?.kpis?.total_leads ?? 0}
            delta={overview?.deltas?.total_leads}
            color="blue"
          />
          <KpiCard
            testId="kpi-conversions"
            icon={Award}
            label="Conversiones"
            value={overview?.kpis?.conversiones ?? 0}
            delta={overview?.deltas?.conversiones}
            color="emerald"
          />
          <KpiCard
            testId="kpi-rate"
            icon={Percent}
            label="Tasa de conversión"
            value={overview?.kpis?.conversion_rate ?? 0}
            suffix="%"
            delta={overview?.deltas?.conversion_rate}
            color="purple"
          />
          <KpiCard
            testId="kpi-revenue"
            icon={DollarSign}
            label="Ingresos"
            value={overview?.kpis?.total_revenue ?? 0}
            prefix="$"
            color="amber"
          />
          <KpiCard
            testId="kpi-ticket"
            icon={Target}
            label="Ticket promedio"
            value={overview?.kpis?.avg_ticket ?? 0}
            prefix="$"
            color="cyan"
          />
        </div>

        {/* Insights banner */}
        {overview?.insights?.length > 0 && (
          <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-700/30 rounded-xl p-4 flex items-start gap-3" data-testid="insights-banner">
            <Sparkles className="w-5 h-5 text-purple-300 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-purple-300 uppercase tracking-wide mb-1">Insights automáticos</p>
              <ul className="space-y-1 text-sm text-slate-200">
                {overview.insights.map((ins, i) => <li key={i}>• {ins}</li>)}
              </ul>
            </div>
          </div>
        )}

        {/* Top ad highlight */}
        {overview?.top_ad && (
          <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800 flex items-center gap-4 flex-wrap" data-testid="top-ad">
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
              <Award className="w-5 h-5 text-amber-400" />
            </div>
            <div className="flex-1 min-w-[200px]">
              <p className="text-xs text-slate-400 uppercase tracking-wide">Mejor anuncio</p>
              <p className="text-white font-semibold truncate" title={overview.top_ad.ad_source}>
                {overview.top_ad.ad_source}
              </p>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <div>
                <p className="text-xs text-slate-500">Leads</p>
                <p className="text-white font-semibold">{overview.top_ad.leads}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Válidos</p>
                <p className="text-emerald-400 font-semibold">{overview.top_ad.conversiones}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Conv.</p>
                <p className="text-purple-400 font-semibold">{overview.top_ad.conversion_rate}%</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Ingresos</p>
                <p className="text-amber-400 font-semibold">${(overview.top_ad.revenue || 0).toLocaleString('es-AR')}</p>
              </div>
            </div>
          </div>
        )}

        {/* Timeline */}
        <TimelineChart data={timeline} loading={loading} />

        {/* Ad performance table */}
        <AdPerformanceTable ads={ads} loading={loading} />

        {/* Demographics row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GenderPie gender={demographics.gender} loading={loading} />
          <AgeBarChart age={demographics.age} ageUnknown={demographics.age_unknown} loading={loading} />
        </div>

        {/* Geography row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GeographyBar data={geography.provinces} title="Top provincias" loading={loading} />
          <GeographyBar data={geography.cities} title="Top ciudades" loading={loading} />
        </div>

        {/* Heatmap + Device */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <HourlyHeatmap matrix={heatmap.matrix} labels={heatmap.labels} loading={loading} />
          </div>
          <DeviceChart devices={deviceStats.devices} loading={loading} />
        </div>

        {/* Countries (if more than just AR) */}
        {geography.countries?.length > 1 && (
          <GeographyBar data={geography.countries} title="Distribución por país" loading={loading} />
        )}
      </div>
    </div>
  );
};

export default Dashboard;
