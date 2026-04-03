import React, { useState, useEffect, useCallback } from 'react';
import api from '@/utils/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { FileText, TrendingUp, Shield, Globe, Clock } from 'lucide-react';
import { toast } from 'sonner';

const Reports = () => {
  const [performanceData, setPerformanceData] = useState([]);
  const [fraudData, setFraudData] = useState(null);
  const [geoData, setGeoData] = useState([]);
  const [hourlyData, setHourlyData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDays, setSelectedDays] = useState(7);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    try {
      const [performance, fraud, geo, hourly] = await Promise.all([
        api.get(`/reports/performance?days=${selectedDays}`),
        api.get(`/reports/fraud-detection?days=${selectedDays}`),
        api.get(`/reports/geo-analysis?days=${selectedDays}`),
        api.get(`/reports/hourly-patterns?days=${selectedDays}`)
      ]);
      setPerformanceData(performance.data.data);
      setFraudData(fraud.data);
      setGeoData(geo.data.countries);
      setHourlyData(hourly.data.hourly_data);
    } catch (error) {
      toast.error('Error al cargar reportes');
    } finally {
      setLoading(false);
    }
  }, [selectedDays]);

  useEffect(() => { fetchReports(); }, [fetchReports]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div data-testid="reports-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Reportes</h1>
            <p className="text-slate-400">Análisis avanzado de tu tráfico</p>
          </div>
          <div className="flex gap-2">
            {[7, 14, 30].map((days) => (
              <Button key={days} data-testid={`report-days-${days}`} onClick={() => setSelectedDays(days)}
                className={`${selectedDays === days ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}>
                {days} días
              </Button>
            ))}
          </div>
        </div>

        {/* Performance */}
        <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-blue-500" />
            <h3 className="text-lg font-semibold text-white">Rendimiento Diario</h3>
          </div>
          {performanceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} labelStyle={{ color: '#e2e8f0' }} />
                <Legend />
                <Line type="monotone" dataKey="total_clicks" stroke="#3b82f6" name="Total Clicks" strokeWidth={2} />
                <Line type="monotone" dataKey="allowed_clicks" stroke="#10b981" name="Permitidos" strokeWidth={2} />
                <Line type="monotone" dataKey="blocked_clicks" stroke="#ef4444" name="Bloqueados" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-12 text-slate-500">No hay datos de rendimiento disponibles</div>
          )}
        </Card>

        {/* Fraud Detection */}
        {fraudData && (
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-5 h-5 text-red-500" />
              <h3 className="text-lg font-semibold text-white">Detección de Fraude</h3>
            </div>
            {fraudData.suspicious_ips.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="text-left py-2 px-3 text-slate-400">IP</th>
                      <th className="text-left py-2 px-3 text-slate-400">Clicks</th>
                      <th className="text-left py-2 px-3 text-slate-400">Bloqueados</th>
                      <th className="text-left py-2 px-3 text-slate-400">Score Promedio</th>
                      <th className="text-left py-2 px-3 text-slate-400">Riesgo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fraudData.suspicious_ips.map((ip, idx) => (
                      <tr key={idx} className="border-b border-slate-800/50">
                        <td className="py-2 px-3 text-slate-300 font-mono text-xs">{ip.ip}</td>
                        <td className="py-2 px-3 text-slate-300">{ip.click_count}</td>
                        <td className="py-2 px-3 text-slate-300">{ip.blocked_count}</td>
                        <td className="py-2 px-3 text-slate-300">{ip.avg_score}</td>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${ip.fraud_probability === 'HIGH' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'}`}>
                            {ip.fraud_probability}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">No se detectaron IPs sospechosas</div>
            )}
          </Card>
        )}

        {/* Geo Analysis */}
        <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Globe className="w-5 h-5 text-purple-500" />
            <h3 className="text-lg font-semibold text-white">Análisis Geográfico</h3>
          </div>
          {geoData.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="text-left py-2 px-3 text-slate-400">País</th>
                    <th className="text-left py-2 px-3 text-slate-400">Total Clicks</th>
                    <th className="text-left py-2 px-3 text-slate-400">Bloqueados</th>
                    <th className="text-left py-2 px-3 text-slate-400">Bots</th>
                    <th className="text-left py-2 px-3 text-slate-400">VPN</th>
                    <th className="text-left py-2 px-3 text-slate-400">Score</th>
                    <th className="text-left py-2 px-3 text-slate-400">Calidad</th>
                  </tr>
                </thead>
                <tbody>
                  {geoData.slice(0, 10).map((country, idx) => (
                    <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                      <td className="py-2 px-3 text-slate-300 font-semibold">{country.country}</td>
                      <td className="py-2 px-3 text-slate-300">{country.total_clicks}</td>
                      <td className="py-2 px-3 text-slate-300">{country.blocked}</td>
                      <td className="py-2 px-3 text-slate-300">{country.bots}</td>
                      <td className="py-2 px-3 text-slate-300">{country.vpn}</td>
                      <td className="py-2 px-3 text-slate-300">{country.avg_score}</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${country.quality === 'HIGH' ? 'bg-green-500/10 text-green-400 border border-green-500/20' : country.quality === 'MEDIUM' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                          {country.quality}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">No hay datos geográficos disponibles</div>
          )}
        </Card>

        {/* Hourly Patterns */}
        <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-green-500" />
            <h3 className="text-lg font-semibold text-white">Patrones por Hora</h3>
          </div>
          {hourlyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="hour" stroke="#94a3b8" label={{ value: 'Hora del día', position: 'insideBottom', offset: -5 }} />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} labelStyle={{ color: '#e2e8f0' }} />
                <Legend />
                <Bar dataKey="total_clicks" fill="#3b82f6" name="Total Clicks" radius={[8, 8, 0, 0]} />
                <Bar dataKey="allowed_clicks" fill="#10b981" name="Permitidos" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-12 text-slate-500">No hay datos de patrones horarios disponibles</div>
          )}
        </Card>

        <Card className="bg-slate-900/30 border-slate-800 p-6">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-5 h-5 text-blue-400" />
            <h4 className="text-white font-semibold">Insights y Recomendaciones</h4>
          </div>
          <div className="space-y-2 text-sm text-slate-400">
            <p><strong className="text-white">Rendimiento:</strong> Analiza tendencias diarias para detectar anomalías</p>
            <p><strong className="text-white">Fraude:</strong> IPs con más de 20 clicks son altamente sospechosas</p>
            <p><strong className="text-white">Geografía:</strong> Enfócate en países con score alto y bajo fraud</p>
            <p><strong className="text-white">Timing:</strong> Concentra presupuesto en horas de mejor conversión</p>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Reports;
