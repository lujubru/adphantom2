import React, { useState, useEffect, useCallback } from 'react';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Search, ChevronLeft, ChevronRight, Fingerprint, Globe, Monitor, Clock, AlertTriangle, CheckCircle, MessageCircle, Phone, Bot, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';

const WALandingForensics = () => {
  const [clicks, setClicks] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedClick, setSelectedClick] = useState(null);
  const [landings, setLandings] = useState([]);
  const [stats, setStats] = useState(null);
  const [filters, setFilters] = useState({
    ip: '', landing_code: '', wa_clicked: '', device: '', days: 7, page: 1
  });

  const fetchLandings = useCallback(async () => {
    try {
      const resp = await api.get('/wa-landings');
      setLandings(resp.data);
    } catch {}
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const resp = await api.get(`/wa-landings/forensics/stats?days=${filters.days}`);
      setStats(resp.data);
    } catch {}
  }, [filters.days]);

  const fetchClicks = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('days', filters.days);
      params.set('page', filters.page);
      params.set('limit', 30);
      if (filters.ip) params.set('ip', filters.ip);
      if (filters.landing_code) params.set('landing_code', filters.landing_code);
      if (filters.wa_clicked !== '') params.set('wa_clicked', filters.wa_clicked);
      if (filters.device) params.set('device', filters.device);
      const resp = await api.get(`/wa-landings/clicks/search?${params}`);
      setClicks(resp.data.clicks);
      setTotal(resp.data.total);
      setPages(resp.data.pages);
    } catch { toast.error('Error buscando clicks'); }
    finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { fetchLandings(); }, [fetchLandings]);
  useEffect(() => { fetchClicks(); fetchStats(); }, [fetchClicks, fetchStats]);

  const viewDetail = async (clickId) => {
    try {
      const resp = await api.get(`/wa-landings/clicks/${clickId}`);
      setSelectedClick(resp.data);
    } catch { toast.error('Error cargando detalle'); }
  };

  return (
    <div data-testid="wa-forensics-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Landing Forensics</h1>
          <p className="text-slate-400">Análisis detallado de clicks en landings WhatsApp - {total} resultados</p>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Card className="bg-slate-900/50 border-slate-800 p-3">
              <p className="text-slate-500 text-xs">Total Clicks</p>
              <p className="text-2xl font-bold text-white">{stats.total_clicks}</p>
            </Card>
            <Card className="bg-slate-900/50 border-slate-800 p-3">
              <p className="text-slate-500 text-xs">Conversiones WA</p>
              <p className="text-2xl font-bold text-green-400">{stats.wa_conversions}</p>
            </Card>
            <Card className="bg-slate-900/50 border-slate-800 p-3">
              <p className="text-slate-500 text-xs">Tasa Conversión</p>
              <p className="text-2xl font-bold text-cyan-400">{stats.conversion_rate}%</p>
            </Card>
            <Card className="bg-slate-900/50 border-slate-800 p-3">
              <p className="text-slate-500 text-xs">Bots Detectados</p>
              <p className="text-2xl font-bold text-amber-400">{stats.bot_clicks}</p>
            </Card>
            <Card className="bg-slate-900/50 border-slate-800 p-3">
              <p className="text-slate-500 text-xs">Score Promedio</p>
              <p className="text-2xl font-bold text-purple-400">{stats.avg_behavioral_score}</p>
            </Card>
          </div>
        )}

        {/* Filters */}
        <Card className="bg-slate-900/50 border-slate-800 p-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[150px]">
              <Label className="text-slate-400 text-xs">IP</Label>
              <Input value={filters.ip} onChange={e => setFilters({...filters, ip: e.target.value, page: 1})} className="bg-slate-800 border-slate-700 text-white h-9" placeholder="Buscar IP..." data-testid="filter-ip" />
            </div>
            <div className="min-w-[150px]">
              <Label className="text-slate-400 text-xs">Landing</Label>
              <select value={filters.landing_code} onChange={e => setFilters({...filters, landing_code: e.target.value, page: 1})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md h-9 px-2 text-sm" data-testid="filter-landing">
                <option value="">Todas</option>
                {landings.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}
              </select>
            </div>
            <div className="min-w-[130px]">
              <Label className="text-slate-400 text-xs">Conversión WA</Label>
              <select value={filters.wa_clicked} onChange={e => setFilters({...filters, wa_clicked: e.target.value, page: 1})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md h-9 px-2 text-sm" data-testid="filter-wa-clicked">
                <option value="">Todos</option>
                <option value="true">Convirtió</option>
                <option value="false">No convirtió</option>
              </select>
            </div>
            <div className="min-w-[120px]">
              <Label className="text-slate-400 text-xs">Dispositivo</Label>
              <select value={filters.device} onChange={e => setFilters({...filters, device: e.target.value, page: 1})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md h-9 px-2 text-sm" data-testid="filter-device">
                <option value="">Todos</option>
                <option value="Mobile">Mobile</option>
                <option value="Desktop">Desktop</option>
                <option value="Tablet">Tablet</option>
                <option value="Bot">Bot</option>
              </select>
            </div>
            <div className="min-w-[100px]">
              <Label className="text-slate-400 text-xs">Días</Label>
              <select value={filters.days} onChange={e => setFilters({...filters, days: parseInt(e.target.value), page: 1})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md h-9 px-2 text-sm" data-testid="filter-days">
                {[1, 3, 7, 14, 30, 60].map(d => <option key={d} value={d}>{d} días</option>)}
              </select>
            </div>
          </div>
        </Card>

        {/* Clicks table */}
        <Card className="bg-slate-900/50 border-slate-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/80">
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">IP</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">Landing</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">Dispositivo</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">SO</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">Browser</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">Score</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">WA Click</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium">Fecha</th>
                  <th className="text-left py-3 px-3 text-slate-400 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {clicks.map((click) => (
                  <tr key={click.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 cursor-pointer" onClick={() => viewDetail(click.id)} data-testid={`click-row-${click.id}`}>
                    <td className="py-2.5 px-3 text-slate-300 font-mono text-xs">{click.ip}</td>
                    <td className="py-2.5 px-3 text-slate-300 text-xs truncate max-w-[120px]">{click.landing_name}</td>
                    <td className="py-2.5 px-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${click.device === 'Bot' ? 'bg-amber-500/10 text-amber-400' : click.device === 'Mobile' ? 'bg-blue-500/10 text-blue-400' : 'bg-slate-700 text-slate-300'}`}>{click.device}</span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 text-xs">{click.os}</td>
                    <td className="py-2.5 px-3 text-slate-400 text-xs">{click.browser}</td>
                    <td className="py-2.5 px-3">
                      <span className={`text-xs font-medium ${(click.behavioral_score || 0) >= 70 ? 'text-green-400' : (click.behavioral_score || 0) >= 40 ? 'text-amber-400' : 'text-red-400'}`}>{click.behavioral_score?.toFixed(0) || '-'}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      {click.wa_clicked ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20">Sí</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-400">No</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500 text-xs whitespace-nowrap">{new Date(click.created_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</td>
                    <td className="py-2.5 px-3"><Search className="w-3.5 h-3.5 text-slate-600" /></td>
                  </tr>
                ))}
                {clicks.length === 0 && !loading && (
                  <tr><td colSpan={9} className="py-12 text-center text-slate-500">No se encontraron clicks</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800">
              <span className="text-xs text-slate-500">Página {filters.page} de {pages} ({total} clicks)</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={filters.page <= 1} onClick={() => setFilters({...filters, page: filters.page - 1})} className="border-slate-700 text-slate-300 h-8">
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button size="sm" variant="outline" disabled={filters.page >= pages} onClick={() => setFilters({...filters, page: filters.page + 1})} className="border-slate-700 text-slate-300 h-8">
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Click Detail Modal */}
      <Dialog open={!!selectedClick} onOpenChange={(open) => { if (!open) setSelectedClick(null); }}>
        <DialogContent className="bg-slate-900 border-slate-800 text-white max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg">Detalle del Click</DialogTitle>
          </DialogHeader>
          {selectedClick && (
            <div className="space-y-3">
              {/* Conversion Status */}
              <div className={`flex items-center gap-3 p-3 rounded-lg ${selectedClick.wa_clicked ? 'bg-green-500/10 border border-green-500/20' : 'bg-slate-800/50 border border-slate-700'}`}>
                {selectedClick.wa_clicked ? <MessageCircle className="w-5 h-5 text-green-400" /> : <MessageCircle className="w-5 h-5 text-slate-500" />}
                <div>
                  <p className={`font-semibold ${selectedClick.wa_clicked ? 'text-green-400' : 'text-slate-400'}`}>
                    {selectedClick.wa_clicked ? 'Convirtió a WhatsApp' : 'No convirtió'}
                  </p>
                  {selectedClick.wa_clicked_at && <p className="text-xs text-slate-400">Click WA: {new Date(selectedClick.wa_clicked_at).toLocaleString('es-AR')}</p>}
                </div>
              </div>

              {/* Bot/Quality Warning */}
              {(selectedClick.is_bot || selectedClick.is_meta) && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <Bot className="w-5 h-5 text-amber-400" />
                  <div>
                    <p className="font-semibold text-amber-400">
                      {selectedClick.is_meta ? 'Crawler de Meta' : 'Bot Detectado'}
                    </p>
                    <p className="text-xs text-slate-400">Este click fue identificado como tráfico automatizado</p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                {[
                  { icon: Globe, label: 'IP', value: selectedClick.ip, extra: selectedClick.is_meta_ip ? '(Meta)' : '' },
                  { icon: Monitor, label: 'Dispositivo', value: `${selectedClick.device} / ${selectedClick.os}` },
                  { icon: Globe, label: 'Browser', value: selectedClick.browser },
                  { icon: Fingerprint, label: 'Fingerprint', value: selectedClick.fingerprint_hash ? selectedClick.fingerprint_hash.slice(0, 16) + '...' : '-' },
                  { icon: Clock, label: 'Fecha', value: new Date(selectedClick.created_at).toLocaleString('es-AR') },
                  { icon: TrendingUp, label: 'Score', value: `${selectedClick.behavioral_score?.toFixed(1) || 0} / 100` },
                  { icon: AlertTriangle, label: 'Bot', value: selectedClick.is_bot ? 'Sí' : 'No' },
                  { icon: CheckCircle, label: 'VPN', value: selectedClick.is_vpn ? 'Sí' : 'No' },
                ].map((item, i) => (
                  <div key={i} className="p-2.5 bg-slate-800/50 rounded-lg">
                    <p className="text-slate-500 text-xs flex items-center gap-1"><item.icon className="w-3 h-3" />{item.label}</p>
                    <p className="text-slate-200 text-sm font-medium truncate">{item.value} {item.extra && <span className="text-blue-400 text-xs">{item.extra}</span>}</p>
                  </div>
                ))}
              </div>

              <div className="p-3 bg-slate-800/50 rounded-lg">
                <p className="text-slate-500 text-xs mb-1">Landing</p>
                <p className="text-white text-sm">{selectedClick.landing_name}</p>
                <p className="text-purple-400 text-xs mt-1">Código: {selectedClick.landing_code}</p>
              </div>

              {selectedClick.click_id && (
                <div className="p-3 bg-slate-800/50 rounded-lg">
                  <p className="text-slate-500 text-xs mb-1">Click ID (para correlacionar con WA CRM)</p>
                  <p className="text-cyan-400 text-sm font-mono">{selectedClick.click_id}</p>
                </div>
              )}

              {/* UTM Parameters */}
              {(selectedClick.utm_campaign || selectedClick.utm_content) && (
                <div className="p-3 bg-slate-800/50 rounded-lg">
                  <p className="text-slate-500 text-xs mb-1">Parámetros UTM</p>
                  {selectedClick.utm_campaign && <p className="text-slate-300 text-xs">Campaign: <span className="text-cyan-400">{selectedClick.utm_campaign}</span></p>}
                  {selectedClick.utm_content && <p className="text-slate-300 text-xs">Content: <span className="text-cyan-400">{selectedClick.utm_content}</span></p>}
                </div>
              )}

              {/* Facebook Pixel Data */}
              {(selectedClick.fbp || selectedClick.fbc) && (
                <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                  <p className="text-blue-400 text-xs font-medium mb-1">Meta Pixel Data</p>
                  {selectedClick.fbp && <p className="text-slate-300 text-xs">FBP: <span className="text-blue-300 font-mono">{selectedClick.fbp}</span></p>}
                  {selectedClick.fbc && <p className="text-slate-300 text-xs">FBC: <span className="text-blue-300 font-mono">{selectedClick.fbc}</span></p>}
                </div>
              )}

              {selectedClick.referrer && (
                <div className="p-3 bg-slate-800/50 rounded-lg">
                  <p className="text-slate-500 text-xs mb-1">Referrer</p>
                  <p className="text-cyan-400 text-xs break-all">{selectedClick.referrer}</p>
                </div>
              )}

              <details className="border border-slate-700 rounded-lg">
                <summary className="p-3 text-slate-400 text-xs cursor-pointer hover:text-white">User Agent completo</summary>
                <p className="p-3 pt-0 text-slate-500 text-xs break-all font-mono">{selectedClick.user_agent}</p>
              </details>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WALandingForensics;
