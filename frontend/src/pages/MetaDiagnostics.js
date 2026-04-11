import React, { useState, useEffect, useCallback } from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import { Activity, CheckCircle, XCircle, AlertTriangle, DollarSign, Wifi, WifiOff, RefreshCw, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const api = axios.create({ baseURL: `${BACKEND_URL}/api` });
api.interceptors.request.use(cfg => { const t = localStorage.getItem('token'); if (t) cfg.headers.Authorization = `Bearer ${t}`; return cfg; });

const MetaDiagnostics = () => {
  const { darkMode } = useTheme();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterLine, setFilterLine] = useState('');
  const [filterEvent, setFilterEvent] = useState('');
  const [expandedEvent, setExpandedEvent] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const loadDiagnostics = useCallback(async () => {
    try {
      const params = {};
      if (filterLine) params.line_id = filterLine;
      if (filterEvent) params.event_type = filterEvent;
      params.limit = 100;
      const { data: d } = await api.get('/crm/meta/diagnostics', { params });
      setData(d);
    } catch (e) { console.error('Error loading diagnostics', e); }
    finally { setLoading(false); }
  }, [filterLine, filterEvent]);

  useEffect(() => { loadDiagnostics(); }, [loadDiagnostics]);

  useEffect(() => {
    if (!autoRefresh) return;
    const iv = setInterval(loadDiagnostics, 8000);
    return () => clearInterval(iv);
  }, [autoRefresh, loadDiagnostics]);

  const d = darkMode;
  const card = `rounded-xl border transition-colors ${d ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-gray-200'}`;
  const text = d ? 'text-slate-300' : 'text-gray-600';
  const textBold = d ? 'text-white' : 'text-gray-900';
  const muted = d ? 'text-slate-500' : 'text-gray-400';

  if (loading) return (
    <div className={`flex items-center justify-center h-screen ${d ? 'bg-slate-950' : 'bg-gray-50'}`}>
      <RefreshCw className={`w-8 h-8 animate-spin ${muted}`} />
    </div>
  );

  const stats = data?.stats || {};
  const events = data?.events || [];
  const linesConfig = data?.lines_config || [];

  const timeSince = (ts) => {
    if (!ts) return '-';
    const diff = (Date.now() - new Date(ts).getTime()) / 1000;
    if (diff < 60) return `${Math.floor(diff)}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return `${Math.floor(diff / 86400)}d`;
  };

  return (
    <div className={`min-h-screen p-6 space-y-6 ${d ? 'bg-slate-950' : 'bg-gray-50'}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-xl ${d ? 'bg-indigo-500/20' : 'bg-indigo-100'}`}>
            <Activity className={`w-6 h-6 ${d ? 'text-indigo-400' : 'text-indigo-600'}`} />
          </div>
          <div>
            <h1 data-testid="meta-diag-title" className={`text-2xl font-bold ${textBold}`}>Diagnostico Meta</h1>
            <p className={`text-sm ${muted}`}>Eventos CAPI en tiempo real</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            data-testid="auto-refresh-toggle"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              autoRefresh
                ? (d ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-emerald-100 text-emerald-700 border border-emerald-300')
                : (d ? 'bg-slate-800 text-slate-400 border border-slate-700' : 'bg-gray-100 text-gray-500 border border-gray-300')
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-emerald-400 animate-pulse' : (d ? 'bg-slate-600' : 'bg-gray-400')}`} />
            {autoRefresh ? 'LIVE' : 'Auto'}
          </button>
          <button
            data-testid="refresh-button"
            onClick={() => { setLoading(true); loadDiagnostics(); }}
            className={`p-2 rounded-lg transition-colors ${d ? 'bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700' : 'bg-gray-100 text-gray-500 hover:text-gray-900 hover:bg-gray-200'}`}
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard d={d} label="Eventos totales" value={stats.total_events || 0} icon={<Activity className="w-4 h-4" />} color="indigo" />
        <StatCard d={d} label="Exitosos" value={stats.success || 0} icon={<CheckCircle className="w-4 h-4" />} color="emerald" />
        <StatCard d={d} label="Fallidos" value={stats.failed || 0} icon={<XCircle className="w-4 h-4" />} color="red" />
        <StatCard d={d} label="Tasa de exito" value={`${stats.success_rate || 0}%`} icon={<Wifi className="w-4 h-4" />} color="cyan" />
        <StatCard d={d} label="Valor total" value={`$${(stats.total_purchase_value || 0).toLocaleString()}`} icon={<DollarSign className="w-4 h-4" />} color="amber" />
      </div>

      {/* Event Type Breakdown */}
      {stats.event_type_counts && Object.keys(stats.event_type_counts).length > 0 && (
        <div className={`${card} p-4`}>
          <h3 className={`text-sm font-semibold mb-3 ${textBold}`}>Eventos por tipo</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.event_type_counts).map(([type, count]) => (
              <span key={type} className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${
                type === 'Purchase' ? (d ? 'bg-amber-500/15 text-amber-400' : 'bg-amber-100 text-amber-700')
                : type === 'Lead' ? (d ? 'bg-blue-500/15 text-blue-400' : 'bg-blue-100 text-blue-700')
                : type === 'Contact' ? (d ? 'bg-emerald-500/15 text-emerald-400' : 'bg-emerald-100 text-emerald-700')
                : type === 'LowQualityLead' ? (d ? 'bg-red-500/15 text-red-400' : 'bg-red-100 text-red-700')
                : (d ? 'bg-slate-700 text-slate-300' : 'bg-gray-200 text-gray-600')
              }`}>
                {type}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Lines Configuration */}
      <div className={`${card} p-4`}>
        <h3 className={`text-sm font-semibold mb-3 flex items-center gap-2 ${textBold}`}>
          Configuracion de lineas
          <span className={`text-xs font-normal px-2 py-0.5 rounded-full ${
            data?.total_configured_lines === data?.total_lines
              ? (d ? 'bg-emerald-500/15 text-emerald-400' : 'bg-emerald-100 text-emerald-700')
              : (d ? 'bg-amber-500/15 text-amber-400' : 'bg-amber-100 text-amber-700')
          }`}>
            {data?.total_configured_lines || 0}/{data?.total_lines || 0} configuradas
          </span>
        </h3>
        {linesConfig.length === 0 ? (
          <p className={`text-sm ${muted}`}>No hay lineas configuradas.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {linesConfig.map(line => (
              <div key={line.line_id} data-testid={`line-config-${line.line_id}`} className={`p-3 rounded-lg border ${
                line.configured
                  ? (d ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-emerald-300 bg-emerald-50')
                  : (d ? 'border-red-500/30 bg-red-500/5' : 'border-red-300 bg-red-50')
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-sm font-semibold ${textBold}`}>{line.line_name}</span>
                  {line.configured
                    ? <Wifi className="w-3.5 h-3.5 text-emerald-500" />
                    : <WifiOff className="w-3.5 h-3.5 text-red-500" />
                  }
                </div>
                <div className={`text-xs space-y-0.5 ${muted}`}>
                  <div className="flex items-center gap-1">
                    {line.has_pixel_id ? <CheckCircle className="w-3 h-3 text-emerald-500" /> : <XCircle className="w-3 h-3 text-red-500" />}
                    Pixel: {line.pixel_id_preview || 'No configurado'}
                  </div>
                  <div className="flex items-center gap-1">
                    {line.has_token ? <CheckCircle className="w-3 h-3 text-emerald-500" /> : <XCircle className="w-3 h-3 text-red-500" />}
                    Token: {line.token_preview || 'No configurado'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className={`${card} p-4`}>
        <div className="flex flex-wrap items-center gap-3">
          <Filter className={`w-4 h-4 ${muted}`} />
          <select
            data-testid="filter-line"
            value={filterLine}
            onChange={e => setFilterLine(e.target.value)}
            className={`text-sm rounded-lg px-3 py-1.5 border ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-gray-300 text-gray-900'}`}
          >
            <option value="">Todas las lineas</option>
            {linesConfig.map(l => <option key={l.line_id} value={l.line_id}>{l.line_name}</option>)}
          </select>
          <select
            data-testid="filter-event"
            value={filterEvent}
            onChange={e => setFilterEvent(e.target.value)}
            className={`text-sm rounded-lg px-3 py-1.5 border ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-gray-300 text-gray-900'}`}
          >
            <option value="">Todos los eventos</option>
            <option value="Purchase">Purchase</option>
            <option value="Lead">Lead</option>
            <option value="Contact">Contact</option>
            <option value="LowQualityLead">LowQualityLead</option>
          </select>
        </div>
      </div>

      {/* Events Feed */}
      <div className={`${card} overflow-hidden`}>
        <div className={`p-4 border-b ${d ? 'border-slate-800' : 'border-gray-200'}`}>
          <h3 className={`text-sm font-semibold ${textBold}`}>Eventos recientes ({events.length})</h3>
        </div>
        {events.length === 0 ? (
          <div className={`p-8 text-center ${muted}`}>
            <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No hay eventos registrados aun.</p>
            <p className="text-xs mt-1">Los eventos apareceran cuando se clasifiquen leads o se usen landing pages.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800/50">
            {events.map((ev, i) => {
              const isExpanded = expandedEvent === i;
              return (
                <div key={i} data-testid={`event-row-${i}`} className={`transition-colors ${d ? 'hover:bg-slate-800/40' : 'hover:bg-gray-50'}`}>
                  <div
                    className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                    onClick={() => setExpandedEvent(isExpanded ? null : i)}
                  >
                    {/* Status dot */}
                    <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${ev.success ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    {/* Event badge */}
                    <span className={`text-xs font-bold px-2 py-0.5 rounded flex-shrink-0 ${
                      ev.event === 'Purchase' ? (d ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-700')
                      : ev.event === 'Lead' ? (d ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700')
                      : ev.event === 'Contact' ? (d ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-700')
                      : (d ? 'bg-red-500/20 text-red-400' : 'bg-red-100 text-red-700')
                    }`}>
                      {ev.event}
                    </span>
                    {/* Lead info */}
                    <span className={`text-sm truncate flex-1 ${text}`}>
                      {ev.lead_name || ev.lead_phone || ev.lead_id?.slice(0, 8)}
                    </span>
                    {/* Value */}
                    {ev.event === 'Purchase' && ev.value != null && (
                      <span className={`text-sm font-semibold flex-shrink-0 ${d ? 'text-amber-400' : 'text-amber-600'}`}>
                        ${Number(ev.value).toLocaleString()} {ev.currency}
                      </span>
                    )}
                    {/* Line */}
                    <span className={`text-xs flex-shrink-0 ${muted}`}>{ev.line_name}</span>
                    {/* Time */}
                    <span className={`text-xs font-mono flex-shrink-0 ${muted}`}>{timeSince(ev.timestamp)}</span>
                    {isExpanded ? <ChevronUp className={`w-4 h-4 ${muted}`} /> : <ChevronDown className={`w-4 h-4 ${muted}`} />}
                  </div>
                  {isExpanded && (
                    <div className={`px-4 pb-3 ml-5 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs ${muted}`}>
                      <Detail label="Lead ID" value={ev.lead_id} />
                      <Detail label="Telefono" value={ev.lead_phone} />
                      <Detail label="Linea" value={ev.line_name} />
                      <Detail label="Pixel" value={ev.pixel_id || 'N/A'} />
                      <Detail label="Event ID" value={ev.event_id || 'Sin event_id'} />
                      <Detail label="Landing" value={ev.landing_code || '-'} />
                      <Detail label="fbp / fbc" value={`${ev.has_fbp ? 'SI' : 'NO'} / ${ev.has_fbc ? 'SI' : 'NO'}`} highlight={ev.has_fbp && ev.has_fbc ? 'green' : 'red'} />
                      <Detail label="Resultado" value={ev.success ? 'OK (200)' : 'ERROR'} highlight={ev.success ? 'green' : 'red'} />
                      <Detail label="Timestamp" value={ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '-'} />
                      {ev.source && <Detail label="Fuente" value={ev.source} />}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

const StatCard = ({ d, label, value, icon, color }) => {
  const colorMap = {
    indigo: d ? 'bg-indigo-500/15 text-indigo-400' : 'bg-indigo-100 text-indigo-600',
    emerald: d ? 'bg-emerald-500/15 text-emerald-400' : 'bg-emerald-100 text-emerald-600',
    red: d ? 'bg-red-500/15 text-red-400' : 'bg-red-100 text-red-600',
    cyan: d ? 'bg-cyan-500/15 text-cyan-400' : 'bg-cyan-100 text-cyan-600',
    amber: d ? 'bg-amber-500/15 text-amber-400' : 'bg-amber-100 text-amber-600',
  };
  return (
    <div className={`rounded-xl border p-3 ${d ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-gray-200'}`}>
      <div className="flex items-center gap-2 mb-1">
        <div className={`p-1.5 rounded-lg ${colorMap[color]}`}>{icon}</div>
        <span className={`text-xs ${d ? 'text-slate-500' : 'text-gray-400'}`}>{label}</span>
      </div>
      <div className={`text-xl font-bold ${d ? 'text-white' : 'text-gray-900'}`}>{value}</div>
    </div>
  );
};

const Detail = ({ label, value, highlight }) => {
  const hColor = highlight === 'green' ? 'text-emerald-400' : highlight === 'red' ? 'text-red-400' : '';
  return (
    <div>
      <div className="opacity-60 mb-0.5">{label}</div>
      <div className={`font-mono truncate ${hColor}`}>{value || '-'}</div>
    </div>
  );
};

export default MetaDiagnostics;
