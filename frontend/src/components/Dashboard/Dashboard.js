import React, { useState, useEffect } from 'react';
import api from '@/utils/api';
import { formatNumber, calculatePercentage, formatDate } from '@/utils/helpers';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Activity, ShieldAlert, Globe, Monitor, Download } from 'lucide-react';
import { toast } from 'sonner';

const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b', '#ef4444'];

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [recentClicks, setRecentClicks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, clicksRes] = await Promise.all([
        api.get('/dashboard/stats'),
        api.get('/dashboard/recent-clicks?limit=20')
      ]);
      setStats(statsRes.data);
      setRecentClicks(clicksRes.data);
    } catch (error) {
      toast.error('Error al cargar datos del panel');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await api.get('/dashboard/export-csv', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `clicks_export_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('CSV exportado correctamente');
    } catch (error) {
      toast.error('Error al exportar CSV');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  const blockedPercentage = calculatePercentage(stats?.blocked_clicks || 0, stats?.total_clicks || 0);

  return (
    <div data-testid="dashboard-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Panel de Control</h1>
            <p className="text-slate-400">Análisis de tráfico e insights</p>
          </div>
          <Button
            onClick={handleExport}
            data-testid="export-csv-button"
            className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white"
          >
            <Download className="w-4 h-4 mr-2" />
            Exportar CSV
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm mb-1">Total Clicks</p>
                <p data-testid="dashboard-total-clicks" className="text-3xl font-bold text-white">{formatNumber(stats?.total_clicks || 0)}</p>
              </div>
              <div className="bg-blue-500/10 p-3 rounded-xl">
                <Activity className="w-6 h-6 text-blue-500" />
              </div>
            </div>
          </Card>

          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm mb-1">Bloqueados</p>
                <p data-testid="dashboard-blocked" className="text-3xl font-bold text-red-400">{formatNumber(stats?.blocked_clicks || 0)}</p>
                <p className="text-xs text-slate-500 mt-1">{blockedPercentage}% del total</p>
              </div>
              <div className="bg-red-500/10 p-3 rounded-xl">
                <ShieldAlert className="w-6 h-6 text-red-500" />
              </div>
            </div>
          </Card>

          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm mb-1">Hoy</p>
                <p data-testid="dashboard-today" className="text-3xl font-bold text-green-400">{formatNumber(stats?.clicks_today || 0)}</p>
              </div>
              <div className="bg-green-500/10 p-3 rounded-xl">
                <Activity className="w-6 h-6 text-green-500" />
              </div>
            </div>
          </Card>

          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-slate-400 text-sm mb-1">Países</p>
                <p data-testid="dashboard-countries" className="text-3xl font-bold text-purple-400">{stats?.by_country?.length || 0}</p>
              </div>
              <div className="bg-purple-500/10 p-3 rounded-xl">
                <Globe className="w-6 h-6 text-purple-500" />
              </div>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Top Países</h3>
            {(stats?.by_country?.length > 0) ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={stats.by_country}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="country" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} labelStyle={{ color: '#e2e8f0' }} />
                  <Bar dataKey="count" fill="#3b82f6" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center py-12 text-slate-500">No hay datos de países</div>
            )}
          </Card>

          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Distribución por Dispositivo</h3>
            {(stats?.by_device?.length > 0) ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={stats.by_device} cx="50%" cy="50%" labelLine={false}
                    label={({ device, percent }) => `${device} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={100} fill="#8884d8" dataKey="count" nameKey="device">
                    {stats.by_device.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center py-12 text-slate-500">No hay datos de dispositivos</div>
            )}
          </Card>
        </div>

        <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Clicks Recientes</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">IP</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">País</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Dispositivo</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">SO</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Estado</th>
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {recentClicks.length > 0 ? recentClicks.map((click) => (
                  <tr key={click.id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="py-3 px-4 text-slate-300 font-mono text-xs">{click.ip}</td>
                    <td className="py-3 px-4 text-slate-300">{click.country}</td>
                    <td className="py-3 px-4 text-slate-300">{click.device}</td>
                    <td className="py-3 px-4 text-slate-300">{click.os}</td>
                    <td className="py-3 px-4">
                      {click.is_blocked ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">Bloqueado</span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">Permitido</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-400 text-xs">{formatDate(click.created_at)}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan="6" className="py-8 text-center text-slate-500">No hay clicks registrados aún</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
