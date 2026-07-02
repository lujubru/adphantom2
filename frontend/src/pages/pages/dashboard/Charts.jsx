import React, { useMemo } from 'react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, Legend,
  BarChart, Bar,
} from 'recharts';

const CHART_COLORS = {
  leads: '#60a5fa',
  conversiones: '#34d399',
  revenue: '#fbbf24',
  male: '#60a5fa',
  female: '#f472b6',
  unknown: '#64748b',
};

const tooltipStyle = {
  background: '#0f172a',
  border: '1px solid #334155',
  borderRadius: 8,
  fontSize: 12,
  color: '#e2e8f0',
};

export const TimelineChart = ({ data, loading }) => {
  if (loading) return <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center text-slate-500 text-sm">Cargando...</div>;
  if (!data?.length) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center">
        <p className="text-slate-500 text-sm">Sin datos en este período</p>
      </div>
    );
  }
  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800" data-testid="timeline-chart">
      <h3 className="text-sm font-semibold text-white mb-3">Evolución de leads y conversiones</h3>
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="gradLeads" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={CHART_COLORS.leads} stopOpacity={0.4} />
              <stop offset="95%" stopColor={CHART_COLORS.leads} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradConv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={CHART_COLORS.conversiones} stopOpacity={0.5} />
              <stop offset="95%" stopColor={CHART_COLORS.conversiones} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickFormatter={d => d?.slice(5)} />
          <YAxis stroke="#64748b" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area type="monotone" dataKey="leads" name="Leads" stroke={CHART_COLORS.leads} fill="url(#gradLeads)" strokeWidth={2} />
          <Area type="monotone" dataKey="conversiones" name="Conversiones" stroke={CHART_COLORS.conversiones} fill="url(#gradConv)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export const GenderPie = ({ gender, loading }) => {
  const colors = { Masculino: CHART_COLORS.male, Femenino: CHART_COLORS.female, Desconocido: CHART_COLORS.unknown };
  const data = useMemo(() => gender?.filter(g => g.leads > 0) || [], [gender]);
  if (loading) return <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center text-slate-500 text-sm">Cargando...</div>;
  if (!data.length) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center">
        <p className="text-slate-500 text-sm">Sin datos demográficos</p>
      </div>
    );
  }
  const total = data.reduce((acc, d) => acc + d.leads, 0);
  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800" data-testid="gender-pie">
      <h3 className="text-sm font-semibold text-white mb-3">Distribución por género</h3>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie data={data} dataKey="leads" nameKey="label" cx="50%" cy="50%" innerRadius={45} outerRadius={80} paddingAngle={2}>
            {data.map((entry) => (
              <Cell key={entry.label} fill={colors[entry.label] || CHART_COLORS.unknown} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
      <div className="space-y-1.5 mt-2">
        {data.map(g => (
          <div key={g.label} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colors[g.label] || CHART_COLORS.unknown }} />
            <span className="text-slate-300 flex-1">{g.label}</span>
            <span className="text-white font-medium">{g.leads}</span>
            <span className="text-slate-500">({Math.round((g.leads / total) * 100)}%)</span>
            <span className="text-emerald-400 w-12 text-right">{g.conversion_rate}%</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export const AgeBarChart = ({ age, ageUnknown, loading }) => {
  if (loading) return <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center text-slate-500 text-sm">Cargando...</div>;
  const data = age || [];
  const hasData = data.some(d => d.leads > 0);
  if (!hasData) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
        <h3 className="text-sm font-semibold text-white mb-3">Rangos de edad</h3>
        <p className="text-slate-500 text-sm text-center py-6">Aún no se infiere edad de los leads.</p>
        {ageUnknown > 0 && <p className="text-slate-600 text-[11px] text-center">{ageUnknown} leads sin edad asignada</p>}
      </div>
    );
  }
  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800" data-testid="age-chart">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">Rangos de edad</h3>
        {ageUnknown > 0 && <span className="text-[11px] text-slate-500">{ageUnknown} sin edad</span>}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="range" stroke="#64748b" fontSize={11} />
          <YAxis stroke="#64748b" fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="leads" name="Leads" fill={CHART_COLORS.leads} radius={[4, 4, 0, 0]} />
          <Bar dataKey="conversiones" name="Válidos" fill={CHART_COLORS.conversiones} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export const GeographyBar = ({ data, title, loading }) => {
  if (loading) return <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center text-slate-500 text-sm">Cargando...</div>;
  if (!data?.length) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
        <h3 className="text-sm font-semibold text-white mb-3">{title}</h3>
        <p className="text-slate-500 text-sm text-center py-6">Sin datos geográficos</p>
      </div>
    );
  }
  const max = Math.max(...data.map(d => d.leads), 1);
  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
      <h3 className="text-sm font-semibold text-white mb-3">{title}</h3>
      <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
        {data.map(r => (
          <div key={r.name} className="group">
            <div className="flex items-center justify-between text-xs mb-0.5">
              <span className="text-slate-300 truncate flex-1">{r.name}</span>
              <span className="text-white font-medium ml-2">{r.leads}</span>
              <span className="text-emerald-400 w-12 text-right text-[11px]">{r.conversion_rate}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all group-hover:from-blue-400 group-hover:to-cyan-300"
                style={{ width: `${(r.leads / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const HourlyHeatmap = ({ matrix, labels, loading }) => {
  if (loading) return <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center text-slate-500 text-sm">Cargando...</div>;
  if (!matrix?.length) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
        <h3 className="text-sm font-semibold text-white mb-3">Horarios de entrada de leads</h3>
        <p className="text-slate-500 text-sm text-center py-6">Sin datos en este período</p>
      </div>
    );
  }
  const flat = matrix.flat();
  const max = Math.max(...flat, 1);
  const color = (val) => {
    if (!val) return 'bg-slate-800/40';
    const intensity = val / max;
    if (intensity > 0.75) return 'bg-emerald-500';
    if (intensity > 0.5) return 'bg-emerald-500/70';
    if (intensity > 0.25) return 'bg-emerald-500/40';
    if (intensity > 0.1) return 'bg-emerald-500/25';
    return 'bg-emerald-500/10';
  };
  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800" data-testid="heatmap">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">Horarios de entrada de leads</h3>
        <span className="text-[11px] text-slate-500">Zona horaria: Argentina (UTC-3)</span>
      </div>
      <div className="overflow-x-auto">
        <div className="inline-flex flex-col gap-1 min-w-full">
          {/* Hour header */}
          <div className="flex gap-0.5 pl-9">
            {Array.from({ length: 24 }, (_, h) => (
              <div key={h} className="w-5 text-center text-[9px] text-slate-500 font-mono">
                {h % 3 === 0 ? h : ''}
              </div>
            ))}
          </div>
          {matrix.map((row, dIdx) => (
            <div key={dIdx} className="flex items-center gap-0.5">
              <span className="w-8 text-[10px] text-slate-400 font-medium shrink-0">{labels[dIdx]}</span>
              {row.map((val, hIdx) => (
                <div
                  key={hIdx}
                  title={`${labels[dIdx]} ${hIdx}:00 — ${val} leads`}
                  className={`w-5 h-5 rounded ${color(val)} transition-colors hover:ring-1 hover:ring-white/30 cursor-help`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1.5 mt-3 text-[10px] text-slate-500">
        <span>Menos</span>
        <div className="w-3 h-3 rounded bg-emerald-500/10" />
        <div className="w-3 h-3 rounded bg-emerald-500/25" />
        <div className="w-3 h-3 rounded bg-emerald-500/40" />
        <div className="w-3 h-3 rounded bg-emerald-500/70" />
        <div className="w-3 h-3 rounded bg-emerald-500" />
        <span>Más</span>
      </div>
    </div>
  );
};

export const DeviceChart = ({ devices, loading }) => {
  const colors = ['#60a5fa', '#34d399', '#fbbf24', '#f472b6', '#a78bfa'];
  if (loading) return <div className="bg-slate-900/50 rounded-xl p-8 border border-slate-800 text-center text-slate-500 text-sm">Cargando...</div>;
  if (!devices?.length) {
    return (
      <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800">
        <h3 className="text-sm font-semibold text-white mb-3">Dispositivos</h3>
        <p className="text-slate-500 text-sm text-center py-6">Sin datos de dispositivos (requiere clicks de landing)</p>
      </div>
    );
  }
  return (
    <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800" data-testid="device-chart">
      <h3 className="text-sm font-semibold text-white mb-3">Dispositivos</h3>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie data={devices} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={70} paddingAngle={2}>
            {devices.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};
