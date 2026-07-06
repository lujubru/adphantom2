import React, { useCallback, useEffect, useRef, useState } from 'react';
import { X, DollarSign, User, CheckCircle2, RotateCcw, Loader2, Info } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/utils/api';

const POLL_INTERVAL_MS = 15000;

function fmtMoney(amount, currency = 'ARS') {
  const n = Number(amount || 0);
  try {
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency }).format(n);
  } catch {
    return `$${n.toLocaleString('es-AR')}`;
  }
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-AR', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function payerName(p) {
  if (!p) return 'Anónimo';
  const full = [p.first_name, p.last_name].filter(Boolean).join(' ').trim();
  return full || p.email || 'Anónimo';
}

/**
 * MP inbox hook: polls every 15s. Emits toast on new payments.
 * Returns { data, unread, refresh, markSeen }
 */
export function useMPInbox({ enabled = true } = {}) {
  const [data, setData] = useState({ payments: [], unread: 0, total_pending: 0 });
  const knownIds = useRef(new Set());
  const firstLoadDone = useRef(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/mercadopago/inbox');
      setData(data);
      // Detect new payments after first load
      if (firstLoadDone.current) {
        (data.payments || []).forEach((p) => {
          if (!knownIds.current.has(p.mp_payment_id)) {
            toast.success(
              `💰 Nuevo pago ${fmtMoney(p.transaction_amount, p.currency_id)} de ${payerName(p.payer)}`,
              { duration: 8000 }
            );
          }
        });
      }
      knownIds.current = new Set((data.payments || []).map((p) => p.mp_payment_id));
      firstLoadDone.current = true;
    } catch {
      /* silent — cajero might just not have MP connected */
    }
  }, []);

  const markSeen = useCallback(async () => {
    try {
      await api.post('/mercadopago/inbox/mark-seen');
      setData((prev) => ({ ...prev, unread: 0 }));
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    load();
    const t = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [enabled, load]);

  return { data, refresh: load, markSeen };
}

/**
 * Modal panel that lists pending MP payments and lets the cashier assign
 * them to a lead (defaults to the currently-open lead if provided).
 */
export const MPInboxModal = ({ open, onClose, currentLead, onAssigned }) => {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [assigning, setAssigning] = useState(null);
  const [showAssigned, setShowAssigned] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/mercadopago/inbox', { params: { include_assigned: showAssigned } });
      setPayments(data.payments || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error cargando pagos MP');
    } finally { setLoading(false); }
  }, [showAssigned]);

  useEffect(() => {
    if (!open) return;
    load();
    api.post('/mercadopago/inbox/mark-seen').catch(() => {});
  }, [open, load]);

  const assignToCurrent = async (mp_payment_id) => {
    if (!currentLead) {
      toast.error('Abrí primero un chat para asignar');
      return;
    }
    setAssigning(mp_payment_id);
    try {
      await api.post(`/mercadopago/inbox/${mp_payment_id}/assign`, { lead_id: currentLead.id });
      toast.success(`✅ Pago asignado a ${currentLead.name || currentLead.phone}`);
      onAssigned?.(mp_payment_id, currentLead.id);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error asignando');
    } finally { setAssigning(null); }
  };

  const undo = async (mp_payment_id) => {
    setAssigning(mp_payment_id);
    try {
      await api.post(`/mercadopago/inbox/${mp_payment_id}/unassign`);
      toast.success('Asignación revertida');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error revirtiendo');
    } finally { setAssigning(null); }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4"
      onClick={onClose}
      data-testid="mp-inbox-modal"
    >
      <div
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto bg-slate-900 rounded-xl border border-slate-700 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-400" /> Pagos Mercado Pago
          </h2>
          <div className="flex items-center gap-3">
            <label className="text-[11px] text-slate-400 flex items-center gap-1 cursor-pointer" data-testid="mp-inbox-toggle-assigned">
              <input type="checkbox" checked={showAssigned} onChange={(e) => setShowAssigned(e.target.checked)} className="accent-emerald-500" />
              Ver asignados
            </label>
            <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800" data-testid="mp-inbox-close">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-4 space-y-2">
          {currentLead && (
            <div className="flex items-start gap-2 rounded-md bg-sky-500/10 border border-sky-500/30 text-sky-200 px-3 py-2 text-xs">
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                Chat abierto: <strong>{currentLead.name || currentLead.phone}</strong>. Los botones &quot;Asignar a chat&quot; van a linkear el pago a este lead.
              </span>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="w-5 h-5 text-slate-500 animate-spin" />
            </div>
          ) : payments.length === 0 ? (
            <div className="py-10 text-center text-xs text-slate-500">
              <DollarSign className="w-8 h-8 mx-auto opacity-20 mb-2" />
              {showAssigned ? 'No hay pagos todavía.' : 'No hay pagos pendientes de asignar. 🎉'}
            </div>
          ) : (
            payments.map((p) => {
              const isAssigned = !!p.assigned_lead_id;
              const isBusy = assigning === p.mp_payment_id;
              return (
                <div
                  key={p.mp_payment_id}
                  className={`rounded-lg border p-3 ${isAssigned ? 'border-emerald-700/50 bg-emerald-900/10' : 'border-slate-700 bg-slate-800/40'}`}
                  data-testid={`mp-payment-${p.mp_payment_id}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <div className="w-9 h-9 rounded-full bg-emerald-500/15 flex items-center justify-center shrink-0">
                        <DollarSign className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-white truncate">
                          {fmtMoney(p.transaction_amount, p.currency_id)}
                        </div>
                        <div className="text-[11px] text-slate-400 flex items-center gap-1 truncate">
                          <User className="w-3 h-3 shrink-0" />
                          <span className="truncate">{payerName(p.payer)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-[10px] text-slate-500">{fmtDate(p.date_approved || p.date_created)}</div>
                      <div className={`text-[10px] font-medium ${p.status === 'approved' ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {p.status || '—'}
                      </div>
                    </div>
                  </div>
                  {p.description && (
                    <div className="text-[11px] text-slate-500 mt-1.5 truncate" title={p.description}>{p.description}</div>
                  )}
                  <div className="mt-2 flex items-center gap-2">
                    {isAssigned ? (
                      <>
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-300">
                          <CheckCircle2 className="w-3 h-3" /> Asignado
                        </span>
                        <button
                          onClick={() => undo(p.mp_payment_id)}
                          disabled={isBusy}
                          className="ml-auto inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-red-300 hover:bg-red-500/10 border border-red-500/30"
                          data-testid={`mp-payment-undo-${p.mp_payment_id}`}
                        >
                          {isBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                          Revertir
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => assignToCurrent(p.mp_payment_id)}
                        disabled={isBusy || !currentLead}
                        className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-semibold bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed text-slate-900"
                        title={!currentLead ? 'Abrí un chat primero' : 'Asignar al chat abierto'}
                        data-testid={`mp-payment-assign-${p.mp_payment_id}`}
                      >
                        {isBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                        Asignar al chat abierto
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
