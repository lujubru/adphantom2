import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Wallet, X, TrendingUp, TrendingDown, Gift, Plus, Trash2, Pencil, Check,
  BarChart3, ChevronDown, ChevronUp, ListChecks, Tag, Layers, PiggyBank,
} from 'lucide-react';
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

// Section: configurador de categorías por tipo (plataformas, ingresos manuales, egresos)
const CategoryManager = ({ type, label, items, onCreate, onDelete, color = 'slate' }) => {
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await onCreate(type, newName.trim());
      setNewName('');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-1.5">
      <div className="text-[10px] uppercase font-semibold text-slate-400">{label}</div>
      <div className="flex gap-1">
        <input
          type="text" value={newName} onChange={e => setNewName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleCreate(); }}
          placeholder="Nueva categoría..." maxLength={60}
          data-testid={`cat-input-${type}`}
          className="flex-1 bg-slate-900 border border-slate-700 text-white rounded px-2 py-1 text-xs" />
        <button onClick={handleCreate} disabled={creating || !newName.trim()}
          data-testid={`cat-add-${type}`}
          className={`px-2 py-1 rounded text-xs font-semibold bg-${color}-600 hover:bg-${color}-700 text-white disabled:opacity-50`}>
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>
      {items.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {items.map(c => (
            <span key={c.id}
              className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-800 border border-slate-700 rounded-full text-[11px] text-slate-200">
              {c.name}
              <button onClick={() => onDelete(c.id)}
                data-testid={`cat-del-${c.id}`}
                className="text-slate-500 hover:text-red-400">
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export const FinanzasModal = ({ onClose, currentUser, inline = false }) => {
  const [filter, setFilter] = useState('mensual');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [summary, setSummary] = useState(null);
  const [chart, setChart] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [manualIncomes, setManualIncomes] = useState([]);
  const [cargas, setCargas] = useState([]);
  const [categories, setCategories] = useState({ plataforma: [], ingreso_manual: [], egreso: [] });
  const [showCargas, setShowCargas] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [currency, setCurrency] = useState('USD');

  // Bono editor
  const [bonusInput, setBonusInput] = useState('');
  const [bonusApplyRetro, setBonusApplyRetro] = useState(false);
  const [savingBonus, setSavingBonus] = useState(false);
  const [bonusHistory, setBonusHistory] = useState([]);

  // Manual income form
  const [miAmount, setMiAmount] = useState('');
  const [miCategoryId, setMiCategoryId] = useState('');
  const [miObs, setMiObs] = useState('');
  const [creatingMI, setCreatingMI] = useState(false);

  // Bonos Panel — bono manual cargado al final del día (informativo, no afecta balance)
  const [bonosPanel, setBonosPanel] = useState([]);
  const [bpAmount, setBpAmount] = useState('');
  const [bpCategoryId, setBpCategoryId] = useState('');
  const [bpObs, setBpObs] = useState('');
  const [creatingBP, setCreatingBP] = useState(false);

  // Egreso form
  const [exAmount, setExAmount] = useState('');
  const [exCategoryId, setExCategoryId] = useState('');
  const [exObs, setExObs] = useState('');
  const [creatingEx, setCreatingEx] = useState(false);

  const params = useMemo(() => {
    const p = { filter_type: filter };
    if (filter === 'custom' && customStart && customEnd) {
      p.start_date = customStart;
      p.end_date = customEnd;
    }
    return p;
  }, [filter, customStart, customEnd]);

  const loadCategories = useCallback(async () => {
    try {
      const { data } = await api.get('/finanzas/categories');
      const grouped = { plataforma: [], ingreso_manual: [], egreso: [] };
      (data.categories || []).forEach(c => {
        if (grouped[c.type]) grouped[c.type].push(c);
      });
      setCategories(grouped);
    } catch (err) {
      // silencioso
    }
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [s, c, e, mi, b, cur, cg, bp] = await Promise.all([
        api.get('/finanzas/summary', { params }),
        api.get('/finanzas/chart', { params }),
        api.get('/finanzas/expenses', { params }),
        api.get('/finanzas/manual-incomes', { params }),
        api.get('/finanzas/bonus-rate'),
        api.get('/finanzas/currency'),
        api.get('/finanzas/cargas', { params: { ...params, limit: 500 } }),
        api.get('/finanzas/bonos-panel', { params }),
      ]);
      setSummary(s.data);
      setChart(c.data.series || []);
      setExpenses(e.data.expenses || []);
      setManualIncomes(mi.data.items || []);
      setBonusInput(String(b.data.percentage ?? 0));
      setBonusHistory(b.data.history || []);
      setCurrency(cur.data.currency || 'USD');
      setCargas(cg.data.cargas || []);
      setBonosPanel(bp.data.items || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error cargando finanzas');
    }
  }, [params]);

  useEffect(() => { loadAll(); loadCategories(); }, [loadAll, loadCategories]);

  // ─── Bono ────────────────────────────────────────────────────────
  const saveBonus = async () => {
    const pct = parseFloat(bonusInput);
    if (Number.isNaN(pct) || pct < 0 || pct > 200) {
      toast.error('El bono debe estar entre 0 y 200%');
      return;
    }
    if (bonusApplyRetro && !window.confirm(
      `¿Aplicar ${pct}% a TODO el histórico? Esto recalcula el bono de TODAS las cargas válidas previas.`
    )) return;
    setSavingBonus(true);
    try {
      const { data } = await api.put('/finanzas/bonus-rate', {
        percentage: pct, apply_retroactive: bonusApplyRetro,
      });
      toast.success(data.retroactive ? `Bono ${pct}% aplicado al histórico` : `Bono actualizado al ${pct}% desde hoy`);
      setBonusApplyRetro(false);
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error guardando bono');
    } finally {
      setSavingBonus(false);
    }
  };

  // ─── Categorías CRUD ─────────────────────────────────────────────
  const createCategory = async (type, name) => {
    try {
      await api.post('/finanzas/categories', { type, name });
      toast.success('Categoría creada');
      loadCategories();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    }
  };
  const deleteCategory = async (id) => {
    if (!window.confirm('¿Borrar esta categoría? Los registros previos conservan el nombre.')) return;
    try {
      await api.delete(`/finanzas/categories/${id}`);
      toast.success('Borrada');
      loadCategories();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    }
  };

  // ─── Ingresos manuales ───────────────────────────────────────────
  const submitManualIncome = async () => {
    const amt = parseFloat(miAmount);
    if (Number.isNaN(amt) || amt <= 0) { toast.error('Monto inválido'); return; }
    if (!miCategoryId) { toast.error('Elegí una plataforma/tipo'); return; }
    setCreatingMI(true);
    try {
      await api.post('/finanzas/manual-incomes', {
        amount: amt, category_id: miCategoryId, observation: miObs.trim(),
      });
      toast.success('Ingreso cargado');
      setMiAmount(''); setMiObs('');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    } finally {
      setCreatingMI(false);
    }
  };
  const deleteManualIncome = async (id) => {
    if (!window.confirm('¿Borrar este ingreso?')) return;
    try {
      await api.delete(`/finanzas/manual-incomes/${id}`);
      toast.success('Borrado');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    }
  };

  // ─── Bonos Panel ─────────────────────────────────────────────────
  const submitBonoPanel = async () => {
    const amt = parseFloat(bpAmount);
    if (Number.isNaN(amt) || amt <= 0) { toast.error('Monto inválido'); return; }
    setCreatingBP(true);
    try {
      await api.post('/finanzas/bonos-panel', {
        amount: amt,
        category_id: bpCategoryId || null,
        observation: bpObs.trim(),
      });
      toast.success(`Bono panel ${fmtMoney(amt, currency)} cargado`);
      setBpAmount(''); setBpObs(''); setBpCategoryId('');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    } finally {
      setCreatingBP(false);
    }
  };

  const deleteBonoPanel = async (id) => {
    if (!window.confirm('¿Borrar este bono?')) return;
    try {
      await api.delete(`/finanzas/bonos-panel/${id}`);
      toast.success('Borrado');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    }
  };

  // ─── Egresos ─────────────────────────────────────────────────────
  const submitExpense = async () => {
    const amt = parseFloat(exAmount);
    if (Number.isNaN(amt) || amt <= 0) { toast.error('Monto inválido'); return; }
    if (!exCategoryId && !exObs.trim()) { toast.error('Elegí una categoría o ponele observación'); return; }
    setCreatingEx(true);
    try {
      await api.post('/finanzas/expenses', {
        amount: amt, category_id: exCategoryId || null, observation: exObs.trim(),
      });
      toast.success('Egreso cargado');
      setExAmount(''); setExObs('');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    } finally {
      setCreatingEx(false);
    }
  };
  const deleteExpense = async (id) => {
    if (!window.confirm('¿Borrar este egreso?')) return;
    try {
      await api.delete(`/finanzas/expenses/${id}`);
      toast.success('Borrado');
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error');
    }
  };

  // ─── Asignar plataforma a una carga del embudo ───────────────────
  const assignPlatformToCarga = async (lead_id, category_id) => {
    try {
      await api.post('/finanzas/cargas/assign-platform', { lead_id, category_id: category_id || null });
      // Actualización optimista
      const cat = categories.plataforma.find(c => c.id === category_id);
      setCargas(prev => prev.map(c => c.lead_id === lead_id
        ? { ...c, plataforma_id: category_id || null, plataforma_name: cat?.name || null }
        : c));
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error asignando plataforma');
    }
  };

  const totals = summary?.totals || {};
  const balancePanel = totals.balance_panel ?? 0;
  const balanceGeneral = totals.balance_general ?? 0;
  const panelPositive = balancePanel >= 0;
  const generalPositive = balanceGeneral >= 0;

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
                  className="bg-slate-800 border border-slate-600 text-white rounded px-2 py-1.5 text-sm block" />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 uppercase">Hasta</label>
                <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)}
                  className="bg-slate-800 border border-slate-600 text-white rounded px-2 py-1.5 text-sm block" />
              </div>
            </div>
          )}

          {/* 2 hero cards: Balance Panel y Balance General */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className={`rounded-xl p-4 border ${panelPositive
              ? 'bg-gradient-to-br from-emerald-950/40 to-slate-900 border-emerald-500/30'
              : 'bg-gradient-to-br from-red-950/40 to-slate-900 border-red-500/30'}`}>
              <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1">Balance panel</div>
              <div className={`text-2xl sm:text-3xl font-bold ${panelPositive ? 'text-emerald-300' : 'text-red-300'}`}
                data-testid="finanzas-balance-panel">
                {fmtMoney(balancePanel, currency)}
              </div>
              <div className="text-[11px] text-slate-500 mt-1">Ingresos − bonos</div>
            </div>
            <div className={`rounded-xl p-4 border ${generalPositive
              ? 'bg-gradient-to-br from-blue-950/40 to-slate-900 border-blue-500/30'
              : 'bg-gradient-to-br from-red-950/40 to-slate-900 border-red-500/30'}`}>
              <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-1">Balance general</div>
              <div className={`text-2xl sm:text-3xl font-bold ${generalPositive ? 'text-blue-300' : 'text-red-300'}`}
                data-testid="finanzas-balance-general">
                {fmtMoney(balanceGeneral, currency)}
              </div>
              <div className="text-[11px] text-slate-500 mt-1">Ingresos − bonos − egresos</div>
            </div>
          </div>

          {/* 5 cards: Ingresos, Egresos, Bono CRM, Bonos Panel, Promedio */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 uppercase font-semibold">
                <TrendingUp className="w-3.5 h-3.5" /> Ingresos
              </div>
              <div className="text-xl font-bold text-white mt-1" data-testid="finanzas-ingresos">
                {fmtMoney(totals.ingresos, currency)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                Embudo: {fmtMoney(totals.ingresos_embudo, currency)}
                {totals.ingresos_manual > 0 && ` + Manual: ${fmtMoney(totals.ingresos_manual, currency)}`}
              </div>
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
              <div className="text-[10px] text-slate-500 mt-1">
                {totals.total_cargas || 0} carga{totals.total_cargas === 1 ? '' : 's'} · {summary?.current_bonus_percentage ?? 0}% hoy
              </div>
            </div>
            <div className="bg-slate-800/60 border border-amber-700/30 rounded-lg p-3">
              <div className="flex items-center gap-1.5 text-[11px] text-amber-300 uppercase font-semibold">
                <Gift className="w-3.5 h-3.5" /> Bonos Panel
              </div>
              <div className="text-xl font-bold text-amber-200 mt-1" data-testid="finanzas-bono-panel">
                {fmtMoney(totals.bono_panel, currency)}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Cargado a mano (informativo)</div>
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

          {/* Configurar % bono + categorías */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3">
              <div className="text-xs uppercase font-semibold text-slate-300 mb-2 flex items-center gap-2">
                <Gift className="w-3.5 h-3.5 text-amber-400" /> Mi % de bono
              </div>
              <div className="flex items-end gap-2">
                <input type="number" min="0" max="200" step="0.5"
                  value={bonusInput} onChange={e => setBonusInput(e.target.value)}
                  data-testid="finanzas-bonus-input"
                  className="flex-1 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
                <Button onClick={saveBonus} disabled={savingBonus}
                  className="bg-amber-600 hover:bg-amber-700 h-9"
                  data-testid="finanzas-bonus-save-btn">
                  {savingBonus ? '...' : 'Guardar'}
                </Button>
              </div>
              <label className="flex items-start gap-2 mt-2 cursor-pointer bg-amber-950/20 border border-amber-700/30 rounded p-2">
                <input type="checkbox" checked={bonusApplyRetro}
                  onChange={e => setBonusApplyRetro(e.target.checked)}
                  className="mt-0.5 cursor-pointer"
                  data-testid="finanzas-bonus-retroactive-toggle" />
                <span className="text-[11px] text-amber-200 leading-snug">
                  <strong>Aplicar al histórico</strong> (recalcula bono de TODAS las cargas previas).
                </span>
              </label>
            </div>

            <div className="bg-slate-800/40 border border-slate-700 rounded-lg overflow-hidden">
              <button onClick={() => setShowConfig(s => !s)}
                data-testid="finanzas-config-toggle"
                className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-800/60">
                <div className="flex items-center gap-2 text-xs uppercase font-semibold text-slate-300">
                  <Tag className="w-3.5 h-3.5 text-cyan-400" /> Configurar panel propio
                </div>
                {showConfig ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {showConfig && (
                <div className="border-t border-slate-700 p-3 space-y-3">
                  <CategoryManager type="plataforma" label="Plataformas (para cargas)"
                    items={categories.plataforma} onCreate={createCategory} onDelete={deleteCategory}
                    color="cyan" />
                  <CategoryManager type="ingreso_manual" label="Tipos de ingreso manual"
                    items={categories.ingreso_manual} onCreate={createCategory} onDelete={deleteCategory}
                    color="emerald" />
                  <CategoryManager type="egreso" label="Tipos de egreso"
                    items={categories.egreso} onCreate={createCategory} onDelete={deleteCategory}
                    color="red" />
                </div>
              )}
            </div>
          </div>

          {/* Detalle de cargas */}
          <div className="bg-slate-800/40 border border-slate-700 rounded-lg overflow-hidden">
            <button onClick={() => setShowCargas(s => !s)}
              data-testid="finanzas-cargas-toggle"
              className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-800/60">
              <div className="flex items-center gap-2 text-xs uppercase font-semibold text-slate-300">
                <ListChecks className="w-3.5 h-3.5 text-violet-400" />
                Detalle de cargas válidas
                <span className="ml-1 text-slate-500 normal-case font-normal">({cargas.length})</span>
              </div>
              {showCargas ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>
            {showCargas && (
              <div className="border-t border-slate-700">
                {cargas.length === 0 ? (
                  <div className="text-center text-slate-500 text-xs py-6">Sin cargas válidas en este período</div>
                ) : (
                  <div className="max-h-80 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-slate-900/95 backdrop-blur text-slate-400 uppercase text-[10px]">
                        <tr>
                          <th className="text-left px-2 py-1.5 font-semibold">Fecha</th>
                          <th className="text-left px-2 py-1.5 font-semibold">Lead</th>
                          <th className="text-left px-2 py-1.5 font-semibold">Plataforma</th>
                          <th className="text-right px-2 py-1.5 font-semibold">Monto</th>
                          <th className="text-right px-2 py-1.5 font-semibold">Bono</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {cargas.map(c => (
                          <tr key={c.lead_id} className="hover:bg-slate-800/40">
                            <td className="px-2 py-1 text-slate-300 font-mono whitespace-nowrap">
                              {c.classified_at?.slice(5, 16).replace('T', ' ')}
                            </td>
                            <td className="px-2 py-1 text-white">
                              <div className="truncate max-w-[140px]" title={c.name}>{c.name}</div>
                            </td>
                            <td className="px-2 py-1">
                              <select
                                value={c.plataforma_id || ''}
                                onChange={e => assignPlatformToCarga(c.lead_id, e.target.value)}
                                data-testid={`carga-platform-${c.lead_id}`}
                                className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-1 py-0.5 text-[11px] max-w-[120px]"
                              >
                                <option value="">— sin asignar —</option>
                                {categories.plataforma.map(p => (
                                  <option key={p.id} value={p.id}>{p.name}</option>
                                ))}
                              </select>
                            </td>
                            <td className="px-2 py-1 text-right text-emerald-300 font-semibold whitespace-nowrap">
                              {fmtMoney(c.monto, currency)}
                            </td>
                            <td className="px-2 py-1 text-right whitespace-nowrap">
                              <span className="text-amber-300 font-semibold">{fmtMoney(c.bono, currency)}</span>
                              {c.bono_pct > 0 && (
                                <span className="text-[10px] text-slate-500 ml-1">({c.bono_pct}%)</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-slate-900/80 text-[11px] font-bold sticky bottom-0">
                        <tr>
                          <td colSpan={3} className="px-2 py-1.5 text-slate-400 uppercase">Total</td>
                          <td className="px-2 py-1.5 text-right text-emerald-300">{fmtMoney(totals.ingresos_embudo, currency)}</td>
                          <td className="px-2 py-1.5 text-right text-amber-300">{fmtMoney(totals.bono, currency)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Ingresos manuales */}
          <div className="bg-slate-800/40 border border-slate-700 rounded-lg p-3">
            <div className="text-xs uppercase font-semibold text-slate-300 mb-2 flex items-center gap-2">
              <PiggyBank className="w-3.5 h-3.5 text-emerald-400" /> Ingresos manuales
            </div>
            <div className="grid grid-cols-12 gap-2 mb-2">
              <input type="number" min="0" step="0.01" placeholder="Monto"
                value={miAmount} onChange={e => setMiAmount(e.target.value)}
                data-testid="finanzas-mi-amount"
                className="col-span-3 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
              <select value={miCategoryId} onChange={e => setMiCategoryId(e.target.value)}
                data-testid="finanzas-mi-category"
                className="col-span-3 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm">
                <option value="">— plataforma/tipo —</option>
                <optgroup label="Plataformas">
                  {categories.plataforma.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </optgroup>
                <optgroup label="Tipos de ingreso">
                  {categories.ingreso_manual.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </optgroup>
              </select>
              <input type="text" placeholder="Observación (opcional)"
                value={miObs} onChange={e => setMiObs(e.target.value)} maxLength={300}
                data-testid="finanzas-mi-obs"
                className="col-span-4 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
              <Button onClick={submitManualIncome} disabled={creatingMI}
                data-testid="finanzas-mi-submit-btn"
                className="col-span-2 bg-emerald-600 hover:bg-emerald-700 h-9 flex items-center justify-center">
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {manualIncomes.length === 0 ? (
              <div className="text-center text-slate-500 text-xs py-3">Sin ingresos manuales en este período</div>
            ) : (
              <ul className="space-y-1 max-h-44 overflow-y-auto">
                {manualIncomes.map(it => (
                  <li key={it.id} className="flex items-center gap-2 px-2 py-1.5 bg-slate-900/60 rounded text-sm">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-emerald-300 font-semibold">{fmtMoney(it.amount, currency)}</span>
                        <span className="text-[10px] text-cyan-400 bg-cyan-950/30 px-1.5 py-0.5 rounded">
                          {it.category_name || 'sin cat.'}
                        </span>
                      </div>
                      {it.observation && <div className="text-[11px] text-slate-400 truncate">{it.observation}</div>}
                      <div className="text-[10px] text-slate-500">{it.created_at?.slice(0, 16).replace('T', ' ')}</div>
                    </div>
                    {it.editable && (
                      <button onClick={() => deleteManualIncome(it.id)} title="Borrar"
                        className="text-slate-400 hover:text-red-400 p-1">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Bonos Panel — bonos cargados manualmente al final del día (informativo) */}
          <div className="bg-slate-800/40 border border-amber-700/30 rounded-lg p-3">
            <div className="text-xs uppercase font-semibold text-slate-300 mb-1 flex items-center gap-2">
              <Gift className="w-3.5 h-3.5 text-amber-400" /> Bonos Panel
              <span className="ml-auto text-[10px] normal-case font-normal text-slate-500">
                Solo informativo, no afecta el balance
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mb-2">
              Cargá acá el total de bonos que entregaste desde el panel (cuando no llegás a procesar las 500+ cargas por el CRM).
            </p>
            <div className="grid grid-cols-12 gap-2 mb-2">
              <input type="number" min="0" step="0.01" placeholder="Monto"
                value={bpAmount} onChange={e => setBpAmount(e.target.value)}
                data-testid="finanzas-bp-amount"
                className="col-span-3 bg-slate-900 border border-amber-700/40 text-amber-200 rounded px-2 py-1.5 text-sm" />
              <select value={bpCategoryId} onChange={e => setBpCategoryId(e.target.value)}
                data-testid="finanzas-bp-category"
                className="col-span-3 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm">
                <option value="">— plataforma (opc) —</option>
                {categories.plataforma.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <input type="text" placeholder="Observación (opcional)"
                value={bpObs} onChange={e => setBpObs(e.target.value)} maxLength={300}
                data-testid="finanzas-bp-obs"
                className="col-span-4 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
              <Button onClick={submitBonoPanel} disabled={creatingBP}
                data-testid="finanzas-bp-submit-btn"
                className="col-span-2 bg-amber-600 hover:bg-amber-700 h-9 flex items-center justify-center">
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {bonosPanel.length === 0 ? (
              <div className="text-center text-slate-500 text-xs py-3">Sin bonos panel en este período</div>
            ) : (
              <ul className="space-y-1 max-h-44 overflow-y-auto">
                {bonosPanel.map(it => (
                  <li key={it.id} className="flex items-center gap-2 px-2 py-1.5 bg-slate-900/60 rounded text-sm">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-amber-300 font-semibold">{fmtMoney(it.amount, currency)}</span>
                        {it.category_name && (
                          <span className="text-[10px] text-cyan-400 bg-cyan-950/30 px-1.5 py-0.5 rounded">
                            {it.category_name}
                          </span>
                        )}
                      </div>
                      {it.observation && <div className="text-[11px] text-slate-400 truncate">{it.observation}</div>}
                      <div className="text-[10px] text-slate-500">{it.created_at?.slice(0, 16).replace('T', ' ')}</div>
                    </div>
                    {it.editable && (
                      <button onClick={() => deleteBonoPanel(it.id)} title="Borrar"
                        className="text-slate-400 hover:text-red-400 p-1">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
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
              <select value={exCategoryId} onChange={e => setExCategoryId(e.target.value)}
                data-testid="finanzas-expense-category"
                className="col-span-3 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm">
                <option value="">— tipo —</option>
                {categories.egreso.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <input type="text" placeholder="Observación (opcional)"
                value={exObs} onChange={e => setExObs(e.target.value)} maxLength={300}
                data-testid="finanzas-expense-observation"
                className="col-span-4 bg-slate-900 border border-slate-600 text-white rounded px-2 py-1.5 text-sm" />
              <Button onClick={submitExpense} disabled={creatingEx}
                data-testid="finanzas-expense-submit-btn"
                className="col-span-2 bg-red-600 hover:bg-red-700 h-9 flex items-center justify-center">
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {expenses.length === 0 ? (
              <div className="text-center text-slate-500 text-xs py-3">Sin egresos en este período</div>
            ) : (
              <ul className="space-y-1 max-h-44 overflow-y-auto">
                {expenses.map(ex => (
                  <li key={ex.id} className="flex items-center gap-2 px-2 py-1.5 bg-slate-900/60 rounded text-sm">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-red-300 font-semibold">{fmtMoney(ex.amount, currency)}</span>
                        {ex.category_name && (
                          <span className="text-[10px] text-red-300 bg-red-950/30 px-1.5 py-0.5 rounded">
                            {ex.category_name}
                          </span>
                        )}
                      </div>
                      {ex.observation && <div className="text-[11px] text-slate-400 truncate">{ex.observation}</div>}
                      <div className="text-[10px] text-slate-500">{ex.created_at?.slice(0, 16).replace('T', ' ')}</div>
                    </div>
                    {ex.editable && (
                      <button onClick={() => deleteExpense(ex.id)} title="Borrar"
                        className="text-slate-400 hover:text-red-400 p-1">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Gráfico */}
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
                    <Bar dataKey="ingresos" fill="#10b981" name="Ingresos (embudo)" />
                    <Bar dataKey="egresos" fill="#ef4444" name="Egresos" />
                    <Bar dataKey="bono" fill="#f59e0b" name="Bono" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
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
