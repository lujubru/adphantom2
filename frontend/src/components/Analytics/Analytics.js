import React, { useState, useEffect, useCallback } from 'react';
import api from '@/utils/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, AreaChart, Area, PieChart, Pie, Cell
} from 'recharts';
import { Activity, ShieldAlert, Bot, Wifi, TrendingUp, Target, Monitor, Clock, Globe } from 'lucide-react';
import { toast } from 'sonner';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];

const Analytics = () => {
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState([]);
  const [topCampaigns, setTopCampaigns] = useState([]);
  const [devices, setDevices] = useState([]);
  const [osData, setOsData] = useState([]);
  const [browsers, setBrowsers] = useState([]);
  const [hourly, setHourly] = useState([]);
  const [topIps, setTopIps] = useState([]);
  const [referrers, setReferrers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, tr, tc, dv, os, br, hr, ips, refs] = await Promise.all([
        api.get(`/analytics/overview?days=${days}`),
        api.get(`/analytics/trends?days=${days}`),
        api.get('/analytics/top-campaigns'),
        api.get(`/analytics/devices?days=${days}`),
        api.get(`/analytics/os?days=${days}`),
        api.get(`/analytics/browsers?days=${days}`),
        api.get(`/analytics/hourly?days=${Math.min(days, 30)}`),
        api.get(`/analytics/top-ips?days=${Math.min(days, 30)}`),
        api.get(`/analytics/referrers?days=${days}`),
      ]);
      setOverview(ov.data);
      setTrends(tr.data.trends);
      setTopCampaigns(tc.data.top_campaigns);
      setDevices(dv.data);
      setOsData(os.data);
      setBrowsers(br.data);
      setHourly(hr.data);
      setTopIps(ips.data);
      setReferrers(refs.data);
    } catch {
      toast.error('Error al cargar analiticas');
    } finally { setLoading(false); }
  }, [days]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen bg-slate-950"><div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div></div>;
  }

  const tooltipStyle = { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' };

  return (
    <div data-testid="analytics-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Analiticas</h1>
            <p className="text-slate-400">Vista general del rendimiento de tu trafico</p>
          </div>
          <div className="flex gap-2">
            {[7, 14, 30, 60].map(d => (
              <Button key={d} data-testid={`analytics-days-${d}`} onClick={() => setDays(d)}
                className={days === d ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}>
                {d}d
              </Button>
            ))}
          </div>
        </div>

        {/* Overview Cards */}
        {overview && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Total Clicks', value: overview.total_clicks.toLocaleString(), icon: Activity, color: 'blue' },
              { label: 'Bloqueados', value: overview.blocked_clicks.toLocaleString(), icon: ShieldAlert, color: 'red', extra: `${overview.block_rate}%` },
              { label: 'Bots', value: overview.bot_clicks.toLocaleString(), icon: Bot, color: 'amber' },
              { label: 'Score Promedio', value: overview.avg_behavioral_score, icon: TrendingUp, color: 'emerald', extra: '/100' },
            ].map((item, i) => (
              <Card key={i} className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-slate-400 text-xs mb-1">{item.label}</p>
                    <p className={`text-2xl font-bold text-${item.color}-400`}>{item.value}<span className="text-xs text-slate-500 ml-1">{item.extra || ''}</span></p>
                  </div>
                  <div className={`bg-${item.color}-500/10 p-2.5 rounded-xl`}>
                    <item.icon className={`w-5 h-5 text-${item.color}-500`} />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Traffic Trend */}
        <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Tendencia de Trafico</h3>
          {trends.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={trends}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#e2e8f0' }} />
                <Legend />
                <Area type="monotone" dataKey="total" stroke="#3b82f6" fill="#3b82f640" name="Total" />
                <Area type="monotone" dataKey="allowed" stroke="#10b981" fill="#10b98130" name="Permitidos" />
                <Area type="monotone" dataKey="blocked" stroke="#ef4444" fill="#ef444430" name="Bloqueados" />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p className="text-center py-8 text-slate-500">Sin datos</p>}
        </Card>

        {/* Device + OS + Browser Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Devices Pie */}
          <Card className="bg-slate-900/50 border-slate-800 p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2"><Monitor className="w-4 h-4 text-blue-400" />Dispositivos</h3>
            {devices.length > 0 ? (
              <div>
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie data={devices} dataKey="total" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({name, percent}) => `${name} ${(percent*100).toFixed(0)}%`} labelLine={false}>
                      {devices.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-1 mt-2">
                  {devices.map((d, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{backgroundColor: COLORS[i % COLORS.length]}}></span><span className="text-slate-300">{d.name}</span></span>
                      <span className="text-slate-400">{d.total}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : <p className="text-center py-8 text-slate-500 text-xs">Sin datos</p>}
          </Card>

          {/* OS */}
          <Card className="bg-slate-900/50 border-slate-800 p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Sistemas Operativos</h3>
            {osData.length > 0 ? (
              <div className="space-y-2">
                {osData.slice(0, 6).map((item, i) => {
                  const max = osData[0]?.total || 1;
                  return (
                    <div key={i}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300">{item.name}</span>
                        <span className="text-slate-400">{item.total}</span>
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${(item.total / max) * 100}%`, backgroundColor: COLORS[i % COLORS.length] }}></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : <p className="text-center py-8 text-slate-500 text-xs">Sin datos</p>}
          </Card>

          {/* Browsers */}
          <Card className="bg-slate-900/50 border-slate-800 p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Navegadores</h3>
            {browsers.length > 0 ? (
              <div className="space-y-2">
                {browsers.slice(0, 6).map((item, i) => {
                  const max = browsers[0]?.total || 1;
                  return (
                    <div key={i}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300">{item.name}</span>
                        <span className="text-slate-400">{item.total}</span>
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${(item.total / max) * 100}%`, backgroundColor: COLORS[(i + 3) % COLORS.length] }}></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : <p className="text-center py-8 text-slate-500 text-xs">Sin datos</p>}
          </Card>
        </div>

        {/* Hourly Traffic */}
        <Card className="bg-slate-900/50 border-slate-800 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2"><Clock className="w-5 h-5 text-cyan-400" />Trafico por Hora</h3>
          {hourly.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={hourly}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="hour" stroke="#94a3b8" tick={{ fontSize: 10 }} />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Bar dataKey="allowed" fill="#10b981" name="Permitidos" stackId="a" />
                <Bar dataKey="blocked" fill="#ef4444" name="Bloqueados" stackId="a" />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-center py-8 text-slate-500">Sin datos horarios</p>}
        </Card>

        {/* Top IPs + Referrers */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="bg-slate-900/50 border-slate-800 p-5">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2"><Globe className="w-4 h-4 text-purple-400" />Top IPs</h3>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {topIps.map((item, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800/50">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-300 font-mono">{item.ip}</span>
                    {item.is_meta && <span className="text-blue-400 text-[10px] bg-blue-500/10 px-1 rounded">Meta</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400">{item.count}x</span>
                    {item.blocked > 0 && <span className="text-red-400 text-[10px]">{item.blocked} bloq</span>}
                  </div>
                </div>
              ))}
              {topIps.length === 0 && <p className="text-slate-500 text-xs py-4 text-center">Sin datos</p>}
            </div>
          </Card>

          <Card className="bg-slate-900/50 border-slate-800 p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Top Referrers</h3>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {referrers.map((item, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800/50">
                  <span className="text-cyan-400 truncate max-w-[250px]">{item.referrer}</span>
                  <span className="text-slate-400 flex-shrink-0">{item.count}</span>
                </div>
              ))}
              {referrers.length === 0 && <p className="text-slate-500 text-xs py-4 text-center">Sin datos de referrer</p>}
            </div>
          </Card>
        </div>

        {/* Top Campaigns */}
        <Card className="bg-slate-900/50 border-slate-800 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2"><Target className="w-5 h-5 text-cyan-400" />Top Campanas</h3>
          {topCampaigns.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Campana</th>
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Total</th>
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Bloqueados</th>
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">Tasa</th>
                  </tr>
                </thead>
                <tbody>
                  {topCampaigns.map((c, i) => (
                    <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                      <td className="py-3 px-4 text-slate-300">{c.campaign_name}</td>
                      <td className="py-3 px-4 text-slate-300">{c.total_clicks.toLocaleString()}</td>
                      <td className="py-3 px-4 text-slate-300">{c.blocked.toLocaleString()}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${(c.blocked / c.total_clicks * 100) > 50 ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'}`}>
                          {c.total_clicks > 0 ? ((c.blocked / c.total_clicks) * 100).toFixed(1) : 0}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-center py-8 text-slate-500">Sin datos</p>}
        </Card>
      </div>
    </div>
  );
};

export default Analytics;
