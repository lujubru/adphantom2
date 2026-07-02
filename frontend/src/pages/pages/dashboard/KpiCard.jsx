import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

// Re-usable KPI card with delta vs previous period
export const KpiCard = ({ icon: Icon, label, value, prefix = '', suffix = '', delta, color = 'blue', testId }) => {
  const colorMap = {
    blue: 'text-blue-400 bg-blue-500/10',
    emerald: 'text-emerald-400 bg-emerald-500/10',
    purple: 'text-purple-400 bg-purple-500/10',
    amber: 'text-amber-400 bg-amber-500/10',
    rose: 'text-rose-400 bg-rose-500/10',
    cyan: 'text-cyan-400 bg-cyan-500/10',
  };
  const DeltaIcon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
  const deltaColor = delta > 0 ? 'text-emerald-400' : delta < 0 ? 'text-rose-400' : 'text-slate-500';

  return (
    <div
      data-testid={testId}
      className="bg-slate-900/60 backdrop-blur rounded-xl p-4 border border-slate-800 hover:border-slate-700 transition-colors"
    >
      <div className="flex items-start justify-between mb-2">
        <div className={`p-2 rounded-lg ${colorMap[color]}`}>
          {Icon && <Icon className="w-4 h-4" />}
        </div>
        {delta !== null && delta !== undefined && (
          <div className={`flex items-center gap-1 text-xs font-medium ${deltaColor}`}>
            <DeltaIcon className="w-3.5 h-3.5" />
            <span>{Math.abs(delta)}%</span>
          </div>
        )}
      </div>
      <p className="text-slate-400 text-xs uppercase tracking-wide font-medium mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">
        {prefix}{typeof value === 'number' ? value.toLocaleString('es-AR', { maximumFractionDigits: 2 }) : value}{suffix}
      </p>
    </div>
  );
};
