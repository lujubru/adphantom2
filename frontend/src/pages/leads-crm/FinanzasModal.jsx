import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Wallet, X, TrendingUp, TrendingDown, Gift, Coins, Plus, Trash2, Pencil, Check, BarChart3, ChevronDown, ChevronUp, ListChecks } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import api from '@/utils/api';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts';

const FILTERS = [
  { key: 'diario', label: 'Hoy' },
  { key: 'ayer', label: 'Ayer' },
  { key: 'semanal', label: 'Semana' },
  { key: 'ultimos_10', label: '10 días' },
  { key: 'mensual', label: 'Mes' },
  { key: 'mes_anterior', label: 'Mes ant.' },
  { key: 'custom', label: 'Personalizado' },
];

const fmtMoney = (n, cur) => {
  const num = Number(n || 0);
  try {
    return new Intl.NumberFormat('es-AR', {
      style: 'currency', currency: cur || 'USD', maximumFractionDigits: 2,
    }).format(num);
  } catch {
    return `${cur || ''} ${num.toFixed(2)}`;
  }
};

export const FinanzasModal = ({ onClose, currentUser, inline = false }) => {
  const [filter, setFilter] = useState('mensual');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [summary, setSummary] = useState(null);
  const [chart, setChart] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [cargas, setCargas] = useState([]);
  const [showCargas, setShowCargas] = useState(false);
  const [loading, setLoading] = useState(false);
  const [currency, setCurrency] = useState('USD');

  // Bono editor
  const [bonusInput, setBonusInput] = useState('');
  const [bonusApplyRetro, setBonusApplyRetro] = useState(false);
  const [savingBonus, setSavingBonus] = useState(false);
  const [bonusHistory, setBonusHistory] = useState([]);

  // Egreso form
  const [exAmount, setExAmount] = useState('');
  const [exObs, setExObs] = useState('');
  const [creatingEx, setCreatingEx] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const params = useMemo(() => {
    const p = { filter_type: filter };
    if (filter === 'custom' && customStart && customEnd) {
      p.start_date = customStart;
      p.end_date = customEnd;
    }
    return p;
  }, [filter, customStart, customEnd]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, c, e, b, cur, cg] = await Promise.all([
        api.get('/finanzas/summary', { params }),
        api.get('/finanzas/chart', { params }),
        api.get('/finanzas/expenses', { params }),
        api.get('/finanzas/bonus-rate'),
        api.get('/finanzas/currency'),
        api.get('/finanzas/cargas', { params: { ...params, limit: 500 } }),
      ]);
      setSummary(s.data);
      setChart(c.data.series || []);
      setExpenses(e.data.expenses || []);
      setBonusInput(String(b.data.percentage ?? 0));
      setBonusHistory(b.data.history || []);
      setCurrency(cur.data.currency || 'USD');
      setCargas(cg.data.cargas || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error cargando finanzas');
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const saveBonus = async () => {
    const pct = parseFloat(bonusInput);
    if (Number.isNaN(pct) || pct < 0 || pct > 200) {
      toast.error('El bono debe estar entre 0 y 200%');
      return;
    }
    if (bonusApplyRetro && !window.confirm(
      `¿Aplicar ${pct}% a TODO el histórico? Esto recalcula el bono de TODAS las cargas válidas previas (no se puede deshacer fácilmente).`
    )) return;
    setSavingBonus(true);
    try {
      const { data } = await api.put('/finanzas/bonus-rate', {
        percentage: pct,
        apply_retroactive: bonusApplyRetro,
      });
      if (data.retroactive) {
        toast.success(`Bono ${pct}% aplicado al histórico completo`);
      } else {
        toast.success(`Bono actualizado al ${pct}% desde hoy`);
      }
      setBonusApplyRetro(false);
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error guardando bono');
    } finally {
      setSavingBonus(false);
    }
  };

  const submitExpense = async () => {
    const amt = parseFloat(exAmount);
    if (Number.isNaN(amt) || amt <= 0) { toast.error('Monto inválido'); return; }
    if (!exObs.trim()) { toast.error('Poné una observación'); return; }
    setCreatingEx(true);
    try {
      if (editingId) {
        await api.put(`/finanzas/expenses/${editingId}`, { amount: amt, observation: exObs.trim() });
        toast.success('Egreso editado');
        setEditingId(null);
      } else {
        await api.post('/finanzas/expenses', { amount: amt, observation: exObs.trim() });
        toast.success('Egreso cargado');
      }
      setExAmount(''); setExObs('');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    } finally {
      setCreatingEx(false);
    }
  };

  const startEdit = (ex) => {
    setEditingId(ex.id);
    setExAmount(String(ex.amount));
    setExObs(ex.observation || '');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setExAmount(''); setExObs('');
  };

  const deleteExpense = async (id) => {
    if (!window.confirm('¿Borrar este egreso?')) return;
    try {
      await api.delete(`/finanzas/expenses/${id}`);
      toast.success('Egreso borrado');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error borrando');
    }
  };

  const totals = summary?.totals || {};
  const balance = totals.balance ?? 0;
  const balancePositive = balance >= 0;
  const fichasEntregadas = totals.fichas_entregadas ?? 0;

  return (
    <div className={inline
      ? "w-full"
      : "fixed inset-0 bg-black/70 backdrop-blur-sm z-[60] flex items-center justify-center sm:p-4"}>
      <div className={inline
        ? "bg-slate-900 w-full max-w-5xl mx-auto rounded-xl flex flex-col border border-slate-700 overflow-hidden"
        : "bg-slate-900 w-full h-full sm:rounded-xl sm:max-w-4xl sm:h-auto sm:max-h-[92vh] flex flex-col border border-slate-700 overflow-hidden"}>
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Wallet className="w-5 h-5 text-emerald-400" />
            <h2 className="text-white font-semibold">Finanzas</h2>
            <span className="text-xs text-slate-500 hidden sm:inline">· {currentUser?.email}</span>
          </div>
          {!inline && (
            <button onClick={onClose} className="text-slate-400 hover:text-white" data-testid="finanzas-close-btn">
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Filtros */}
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map(f => (
              <button key={f.key}
                onClick={() => setFilter(f.key)}
                data-testid={`finanzas-filter-${f.key}`}
                className={`px-2.5 py-1 rounded text-xs font-medium ${filter === f.key ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
                {f.label}
              </button>
            ))}
          </div>
          {filter === 'custom' && (
            <div className="flex gap-2 items-end">
              <div>
                <label className="text-[10px] text-slate-400 uppercase">Desde</label>
                <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)}
                  className="bg-slate-800 border border-slate-600 text-white rounded px-2 py-1.5 text-sm block"
                  data-testid="finanzas-custom-start" />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 uppercase">Hasta</label>
                <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)}
                  className="bg-slate-800 border border-slate-600 text-white rounded px-2 py-1.5 text-sm block"
                  data-testid="finanzas-custom-end" />
              </div>
            </div>
          )}

          {/* Dos balances separados: PLATA real vs FICHAS entregadas al cliente */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className={`rounded-xl p-4 border ${balancePositive
              ? 'bg-gradient-to-br from-emerald-950/40 to-slate-900 border-emerald-500/30'
              : 'bg-gradient-to-br from-red-950/40 to-slate-900 border-red-500/30'}`}>
              <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1">Balance de PLATA</div>
              <div className={`text-2xl sm:text-3xl font-bold ${balancePositive ? 'text-emerald-300' : 'text-red-300'}`}
                data-testid="finanzas-balance">
                {fmtMoney(balance, currency)}
              </div>
              <div className="text-[11px] text-slate-500 mt-1">Ingresos − Egresos</div>
            </div>
            <div className="rounded-xl p-4 border bg-gradient-to-br from-blue-950/40 to-slate-900 border-blue-500/30">
              <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1">Fichas entregadas al cliente</div>
              <div className="text-2xl sm:text-3xl font-bold text-blue-300"
                data-testid="finanzas-fichas-hero">
                {fmtMoney(fichasEntregadas, currency)}
              </div>
              <div className="text-[11px] text-slate-500 mt-1">Ingresos + bono regalado</div>
            </div>
          </div>

          {/* 5 cards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 uppercase font-semibold">
                <TrendingUp className="w-3.5 h-3.5" /> Ingresos
              </div>
              <div className="text-xl font-bold text-white mt-1" data-testid="finanzas-ingresos">
                {fmtMoney(totals.ingresos, currency)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Cargas efectivas (válidos)</div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[11px] text-red-400 uppercase font-semibold">
                <TrendingDown className="w-3.5 h-3.5" /> Egresos
              </div>
              <div className="text-xl font-bold text-white mt-1" data-testid="finanzas-egresos">
                {fmtMoney(totals.egresos, currency)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Cargados manualmente</div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[11px] text-amber-400 uppercase font-semibold">
                <Gift className="w-3.5 h-3.5" /> Bono entregado
              </div>
              <div className="text-xl font-bold text-white mt-1" data-testid="finanzas-bono">
                {fmtMoney(totals.bono, currency)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1" data-testid="finanzas-bono-count">
                {totals.total_cargas || 0} carga{totals.total_cargas === 1 ? '' : 's'} · {summary?.current_bonus_percentage ?? 0}% hoy
              </div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[11px] text-blue-400 uppercase font-semibold">
                <Coins className="w-3.5 h-3.5" /> Fichas entregadas
              </div>
              <div className="text-xl font-bold text-white mt-1" data-testid="finanzas-fichas">
                {fmtMoney(totals.fichas_entregadas, currency)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Ingresos + bono</div>
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[11px] text-violet-400 uppercase font-semibold">
                <BarChart3 className="w-3.5 h-3.5" /> Promedio
              </div>
              <div className="text-xl font-bold text-white mt-1" data-testid="finanzas-avg">
                {fmtMoney(totals.avg_por_carga, currency)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Por carga válida</div>
            </div>
          </div>

          {/* Configurar bono */}
          <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3">
            <div className="text-xs uppercase font-semibold text-slate-300 mb-2 flex items-center gap-2">
              <Gift className="w-3.5 h-3.5 text-amber-400" /> Mi % de bono
            </div>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <input type="number" min="0" max="200" step="0.5"
                  value={bonusInput} onChange={e => setBonusInput(e.target.value)}
                  data-testid="finanzas-bonus-input"
                  className="w-full bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
              </div>
              <Button onClick={saveBonus} disabled={savingBonus}
                className="bg-amber-600 hover:bg-amber-700 h-9"
                data-testid="finanzas-bonus-save-btn">
                {savingBonus ? 'Guardando...' : 'Guardar'}
              </Button>
            </div>
            <p className="text-[10px] text-slate-500 mt-1.5 leading-snug">
              El nuevo % rige desde HOY. Los días anteriores conservan el % que estuvo vigente cada día (no se recalculan).
            </p>
            <label className="flex items-start gap-2 mt-2 cursor-pointer bg-amber-950/20 border border-amber-700/30 rounded p-2 hover:bg-amber-950/30 transition-colors">
              <input type="checkbox" checked={bonusApplyRetro}
                onChange={e => setBonusApplyRetro(e.target.checked)}
                className="mt-0.5 cursor-pointer"
                data-testid="finanzas-bonus-retroactive-toggle" />
              <span className="text-[11px] text-amber-200 leading-snug">
                <strong>Aplicar también al histórico</strong> (recalcula el bono de TODAS las cargas previas con este %). Útil para tener un estimado retroactivo de lo que venías regalando antes de configurar el sistema.
              </span>
            </label>
            {bonusHistory.length > 1 && (
              <details className="mt-2">
                <summary className="text-[11px] text-slate-400 cursor-pointer hover:text-white">
                  Histórico de cambios ({bonusHistory.length})
                </summary>
                <ul className="mt-1.5 space-y-0.5 text-[11px] text-slate-400">
                  {bonusHistory.map(h => (
                    <li key={h.id || `${h.effective_from}-${h.percentage}`} className="font-mono">
                      <span className="text-amber-300">{h.percentage}%</span>
                      {' · '}
                      {h.effective_from} → {h.effective_to || 'hoy'}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>

          {/* Chart */}
          {chart.length > 0 && (
            <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3">
              <div className="text-xs uppercase font-semibold text-slate-300 mb-2">Ingresos vs Egresos por día</div>
              <div style={{ width: '100%', height: 220 }}>
                <ResponsiveContainer>
                  <BarChart data={chart} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }}
                      tickFormatter={d => d.slice(5)} />
                    <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }}
                      tickFormatter={v => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v)} />
                    <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 6, fontSize: 12 }}
                      formatter={(v) => fmtMoney(v, currency)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="ingresos" fill="#10b981" name="Ingresos" />
                    <Bar dataKey="egresos" fill="#ef4444" name="Egresos" />
                    <Bar dataKey="bono" fill="#f59e0b" name="Bono" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Detalle de cargas (expandible) */}
          <div className="bg-slate-800/40 border border-slate-700 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowCargas(s => !s)}
              data-testid="finanzas-cargas-toggle"
              className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-800/60 transition-colors"
            >
              <div className="flex items-center gap-2 text-xs uppercase font-semibold text-slate-300">
                <ListChecks className="w-3.5 h-3.5 text-violet-400" />
                Detalle de cargas válidas
                <span className="ml-1 text-slate-500 normal-case font-normal">
                  ({cargas.length})
                </span>
              </div>
              {showCargas ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>
            {showCargas && (
              <div className="border-t border-slate-700">
                {cargas.length === 0 ? (
                  <div className="text-center text-slate-500 text-xs py-6">
                    Sin cargas válidas en este período
                  </div>
                ) : (
                  <div className="max-h-72 overflow-y-auto">
                    <table className="w-full text-xs" data-testid="finanzas-cargas-table">
                      <thead className="sticky top-0 bg-slate-900/95 backdrop-blur text-slate-400 uppercase text-[10px]">
                        <tr>
                          <th className="text-left px-3 py-1.5 font-semibold">Fecha</th>
                          <th className="text-left px-2 py-1.5 font-semibold">Lead</th>
                          <th className="text-right px-2 py-1.5 font-semibold">Monto</th>
                          <th className="text-right px-2 py-1.5 font-semibold">Bono</th>
                          <th className="text-right px-3 py-1.5 font-semibold">Fichas</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {cargas.map(c => (
                          <tr key={c.lead_id} className="hover:bg-slate-800/40">
                            <td className="px-3 py-1.5 text-slate-300 font-mono whitespace-nowrap">
                              {c.classified_at?.slice(5, 16).replace('T', ' ')}
                            </td>
                            <td className="px-2 py-1.5 text-white">
                              <div className="truncate max-w-[160px]" title={c.name}>{c.name}</div>
                              {c.line_name && <div className="text-[10px] text-slate-500 truncate max-w-[160px]">{c.line_name}</div>}
                            </td>
                            <td className="px-2 py-1.5 text-right text-emerald-300 font-semibold whitespace-nowrap">
                              {fmtMoney(c.monto, currency)}
                            </td>
                            <td className="px-2 py-1.5 text-right whitespace-nowrap">
                              <span className="text-amber-300 font-semibold">{fmtMoney(c.bono, currency)}</span>
                              {c.bono_pct > 0 && (
                                <span className="text-[10px] text-slate-500 ml-1">({c.bono_pct}%)</span>
                              )}
                            </td>
                            <td className="px-3 py-1.5 text-right text-blue-300 font-bold whitespace-nowrap">
                              {fmtMoney(c.fichas_entregadas, currency)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-slate-900/80 text-[11px] font-bold sticky bottom-0">
                        <tr>
                          <td colSpan={2} className="px-3 py-1.5 text-slate-400 uppercase">Total</td>
                          <td className="px-2 py-1.5 text-right text-emerald-300">{fmtMoney(totals.ingresos, currency)}</td>
                          <td className="px-2 py-1.5 text-right text-amber-300">{fmtMoney(totals.bono, currency)}</td>
                          <td className="px-3 py-1.5 text-right text-blue-300">{fmtMoney(totals.fichas_entregadas, currency)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Egresos */}
          <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3">
            <div className="text-xs uppercase font-semibold text-slate-300 mb-2 flex items-center gap-2">
              <TrendingDown className="w-3.5 h-3.5 text-red-400" /> Egresos
            </div>
            <div className="grid grid-cols-12 gap-2 mb-2">
              <input type="number" min="0" step="0.01" placeholder="Monto"
                value={exAmount} onChange={e => setExAmount(e.target.value)}
                data-testid="finanzas-expense-amount"
                className="col-span-3 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
              <input type="text" placeholder="Observación (ej: sueldo personal, viático)"
                value={exObs} onChange={e => setExObs(e.target.value)} maxLength={300}
                data-testid="finanzas-expense-observation"
                className="col-span-7 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
              <Button onClick={submitExpense} disabled={creatingEx}
                data-testid="finanzas-expense-submit-btn"
                className="col-span-2 bg-red-600 hover:bg-red-700 h-9 flex items-center justify-center">
                {editingId ? <Check className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
              </Button>
            </div>
            {editingId && (
              <button onClick={cancelEdit} className="text-[11px] text-slate-400 hover:text-white mb-2">
                Cancelar edición
              </button>
            )}

            {expenses.length === 0 ? (
              <div className="text-center text-slate-500 text-xs py-4">Sin egresos en este período</div>
            ) : (
              <ul className="space-y-1 max-h-56 overflow-y-auto">
                {expenses.map(ex => (
                  <li key={ex.id} className="flex items-center gap-2 px-2 py-1.5 bg-slate-900/60 rounded text-sm">
                    <div className="flex-1 min-w-0">
                      <div className="text-white font-semibold">{fmtMoney(ex.amount, currency)}</div>
                      <div className="text-[11px] text-slate-400 truncate">{ex.observation}</div>
                      <div className="text-[10px] text-slate-500">{ex.created_at?.slice(0, 16).replace('T', ' ')}</div>
                    </div>
                    {ex.editable && (
                      <>
                        <button onClick={() => startEdit(ex)} title="Editar"
                          data-testid={`finanzas-expense-edit-${ex.id}`}
                          className="text-slate-400 hover:text-amber-400 p-1">
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => deleteExpense(ex.id)} title="Borrar"
                          data-testid={`finanzas-expense-delete-${ex.id}`}
                          className="text-slate-400 hover:text-red-400 p-1">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                    {!ex.editable && (
                      <span className="text-[10px] text-slate-600 italic" title="Solo se puede editar el día que se creó">
                        cerrado
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {!inline && (
          <div className="p-3 border-t border-slate-800 shrink-0">
            <Button onClick={onClose} className="w-full bg-slate-700 hover:bg-slate-600"
              data-testid="finanzas-close-btn-bottom">
              Cerrar
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
