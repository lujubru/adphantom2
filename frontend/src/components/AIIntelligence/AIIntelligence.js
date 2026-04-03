import React, { useState, useEffect, useCallback } from 'react';
import api from '@/utils/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import {
  Brain, Zap, ShieldCheck, AlertTriangle, TrendingUp,
  RefreshCw, Trash2, ChevronDown, ChevronUp, Info
} from 'lucide-react';
import { toast } from 'sonner';

const impactColors = {
  high: 'bg-red-500/10 text-red-400 border-red-500/20',
  medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  low: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
};

const categoryIcons = {
  country: '🌍', device: '📱', timing: '⏰', fraud: '🛡️', referrer: '🔗', general: '📊',
};

const AIIntelligence = () => {
  const [status, setStatus] = useState(null);
  const [insights, setInsights] = useState([]);
  const [rules, setRules] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [expandedInsight, setExpandedInsight] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, insightsRes, rulesRes] = await Promise.all([
        api.get('/intelligence/status'),
        api.get('/intelligence/insights'),
        api.get('/intelligence/rules'),
      ]);
      setStatus(statusRes.data);
      setInsights(insightsRes.data);
      setRules(rulesRes.data);
    } catch (error) {
      toast.error('Error al cargar datos de inteligencia');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runAnalysis = async () => {
    setAnalyzing(true);
    try {
      const res = await api.post('/intelligence/analyze');
      toast.success(`Análisis completado: ${res.data.rules_created} reglas generadas`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error en el análisis');
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleRule = async (ruleId, currentState) => {
    try {
      await api.put(`/intelligence/rules/${ruleId}/toggle`, { is_active: !currentState });
      setRules(prev => prev.map(r => r.id === ruleId ? { ...r, is_active: !currentState } : r));
      toast.success(!currentState ? 'Regla activada' : 'Regla desactivada');
    } catch (error) {
      toast.error('Error al cambiar estado de la regla');
    }
  };

  const deleteRule = async (ruleId) => {
    if (!window.confirm('¿Eliminar esta regla?')) return;
    try {
      await api.delete(`/intelligence/rules/${ruleId}`);
      setRules(prev => prev.filter(r => r.id !== ruleId));
      toast.success('Regla eliminada');
    } catch (error) {
      toast.error('Error al eliminar regla');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  const latestInsight = insights.length > 0 ? insights[0] : null;
  const profile = latestInsight?.audience_profile;

  return (
    <div data-testid="intelligence-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Inteligencia IA</h1>
            <p className="text-slate-400">IA que analiza y optimiza tu público automáticamente</p>
          </div>
          <Button
            data-testid="run-analysis-button"
            onClick={runAnalysis}
            disabled={analyzing || !status?.has_enough_data}
            className="bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white px-6"
          >
            {analyzing ? (
              <><RefreshCw className="w-4 h-4 mr-2 animate-spin" />Analizando...</>
            ) : (
              <><Brain className="w-4 h-4 mr-2" />Ejecutar Análisis</>
            )}
          </Button>
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-5">
            <div className="flex items-center gap-3">
              <div className="bg-violet-500/10 p-2.5 rounded-xl">
                <Brain className="w-5 h-5 text-violet-400" />
              </div>
              <div>
                <p className="text-slate-400 text-xs">Clicks Analizados</p>
                <p data-testid="clicks-analyzed" className="text-xl font-bold text-white">{status?.total_clicks_analyzed?.toLocaleString() || 0}</p>
              </div>
            </div>
          </Card>
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-5">
            <div className="flex items-center gap-3">
              <div className="bg-emerald-500/10 p-2.5 rounded-xl">
                <Zap className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-slate-400 text-xs">Reglas Activas</p>
                <p data-testid="active-rules-count" className="text-xl font-bold text-white">{status?.active_rules || 0} <span className="text-sm text-slate-500">/ {status?.total_rules || 0}</span></p>
              </div>
            </div>
          </Card>
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-5">
            <div className="flex items-center gap-3">
              <div className="bg-cyan-500/10 p-2.5 rounded-xl">
                <TrendingUp className="w-5 h-5 text-cyan-400" />
              </div>
              <div>
                <p className="text-slate-400 text-xs">Score Optimización</p>
                <p className="text-xl font-bold text-white">{profile?.optimization_score || '—'}<span className="text-sm text-slate-500">/100</span></p>
              </div>
            </div>
          </Card>
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-5">
            <div className="flex items-center gap-3">
              <div className="bg-amber-500/10 p-2.5 rounded-xl">
                <Info className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <p className="text-slate-400 text-xs">Último Análisis</p>
                <p className="text-sm font-bold text-white">{status?.last_analysis ? new Date(status.last_analysis).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Nunca'}</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Not enough data warning */}
        {!status?.has_enough_data && (
          <Card className="bg-amber-500/5 border-amber-500/20 p-6">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0" />
              <div>
                <h3 className="text-white font-semibold">Datos insuficientes</h3>
                <p className="text-slate-400 text-sm">Necesitas al menos 5 clicks registrados para ejecutar el análisis de IA. Crea campañas y genera tráfico primero.</p>
              </div>
            </div>
          </Card>
        )}

        {/* Audience Profile */}
        {profile && (
          <Card className="bg-gradient-to-br from-slate-900/80 to-violet-950/30 backdrop-blur-xl border-violet-500/20 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Brain className="w-5 h-5 text-violet-400" />
              <h3 className="text-lg font-semibold text-white">Perfil de Audiencia</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-slate-800/50 rounded-lg p-4 border border-emerald-500/10">
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <h4 className="text-emerald-400 font-medium text-sm">Tráfico de Alta Calidad</h4>
                </div>
                <p className="text-slate-300 text-sm leading-relaxed">{profile.high_value_summary}</p>
              </div>
              <div className="bg-slate-800/50 rounded-lg p-4 border border-red-500/10">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <h4 className="text-red-400 font-medium text-sm">Riesgos Detectados</h4>
                </div>
                <p className="text-slate-300 text-sm leading-relaxed">{profile.risk_summary}</p>
              </div>
            </div>
          </Card>
        )}

        {/* Insights */}
        {latestInsight?.insights?.length > 0 && (
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Insights de la IA</h3>
            <div className="space-y-3">
              {latestInsight.insights.map((insight, idx) => (
                <div
                  key={idx}
                  className="bg-slate-800/30 rounded-lg border border-slate-700/50 overflow-hidden"
                >
                  <button
                    onClick={() => setExpandedInsight(expandedInsight === idx ? null : idx)}
                    className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{categoryIcons[insight.category] || '📊'}</span>
                      <div>
                        <p className="text-white font-medium text-sm">{insight.title}</p>
                        <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium border ${impactColors[insight.impact] || impactColors.low}`}>
                          {insight.impact === 'high' ? 'Alto' : insight.impact === 'medium' ? 'Medio' : 'Bajo'}
                        </span>
                      </div>
                    </div>
                    {expandedInsight === idx ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </button>
                  {expandedInsight === idx && (
                    <div className="px-4 pb-4 pt-0 border-t border-slate-700/50">
                      <p className="text-slate-300 text-sm mb-2 mt-3">{insight.description}</p>
                      {insight.recommendation && (
                        <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3 mt-2">
                          <p className="text-blue-300 text-sm"><strong>Recomendación:</strong> {insight.recommendation}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Auto-Applied Rules */}
        <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-emerald-400" />
              <h3 className="text-lg font-semibold text-white">Reglas Auto-Aplicadas</h3>
            </div>
            <p className="text-xs text-slate-500">{rules.filter(r => r.is_active).length} activas de {rules.length}</p>
          </div>

          {rules.length === 0 ? (
            <div className="text-center py-10">
              <Brain className="w-14 h-14 text-slate-700 mx-auto mb-3" />
              <p className="text-slate-400 mb-1">No hay reglas generadas aún</p>
              <p className="text-slate-500 text-sm">Ejecuta un análisis para que la IA genere reglas automáticas</p>
            </div>
          ) : (
            <div className="space-y-2">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  data-testid={`ai-rule-${rule.id}`}
                  className={`flex items-center justify-between p-4 rounded-lg border transition-colors ${
                    rule.is_active
                      ? 'bg-slate-800/40 border-slate-700/50'
                      : 'bg-slate-800/20 border-slate-800/30 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-4 flex-1">
                    <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${
                      rule.type === 'block'
                        ? 'bg-red-500/15 text-red-400'
                        : 'bg-emerald-500/15 text-emerald-400'
                    }`}>
                      {rule.type === 'block' ? 'Bloquear' : 'Permitir'}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">
                        {rule.field} {rule.operator} <span className="text-slate-400">{typeof rule.value === 'string' ? rule.value : JSON.stringify(rule.value)}</span>
                      </p>
                      <p className="text-slate-500 text-xs truncate">{rule.reason}</p>
                    </div>
                    <div className="flex items-center gap-1">
                      <div className={`w-2 h-2 rounded-full ${rule.confidence >= 0.8 ? 'bg-emerald-400' : rule.confidence >= 0.6 ? 'bg-amber-400' : 'bg-red-400'}`} />
                      <span className="text-slate-500 text-xs">{Math.round(rule.confidence * 100)}%</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 ml-4">
                    <Switch
                      checked={rule.is_active}
                      onCheckedChange={() => toggleRule(rule.id, rule.is_active)}
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => deleteRule(rule.id)}
                      className="hover:bg-slate-800 text-slate-500 hover:text-red-400 h-8 w-8"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* How it works */}
        <Card className="bg-slate-900/30 border-slate-800 p-6">
          <h4 className="text-white font-semibold mb-3">Cómo funciona la Inteligencia IA</h4>
          <div className="space-y-2 text-sm text-slate-400">
            <p><strong className="text-white">1. Recolección:</strong> La IA analiza todos tus clicks (país, dispositivo, hora, referrer, score conductual)</p>
            <p><strong className="text-white">2. Análisis:</strong> Identifica patrones de tráfico de alta calidad vs fraudulento</p>
            <p><strong className="text-white">3. Reglas automáticas:</strong> Genera y aplica reglas para bloquear tráfico malo y priorizar el bueno</p>
            <p><strong className="text-white">4. Refinamiento:</strong> Cuanto más tráfico, más precisas son las reglas. Ejecuta análisis regularmente</p>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default AIIntelligence;
