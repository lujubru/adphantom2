import React, { useState, useRef, useEffect } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { STATUS_CONFIG } from './constants';

export const StatusBadge = ({ status }) => {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.nuevo;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cfg.color}`}>
      {cfg.label}
    </span>
  );
};

export const StatusSelector = ({ currentStatus, onSelect, disabled }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const cfg = STATUS_CONFIG[currentStatus] || STATUS_CONFIG.nuevo;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => !disabled && setOpen(o => !o)}
        data-testid="status-selector-btn"
        className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${cfg.color} ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80'}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
        {cfg.label}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 min-w-[140px] overflow-hidden">
          {Object.entries(STATUS_CONFIG).map(([key, val]) => (
            <button key={key} onClick={() => { onSelect(key); setOpen(false); }}
              data-testid={`status-option-${key}`}
              className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-slate-700 transition-colors ${currentStatus === key ? 'bg-slate-700/50' : ''}`}>
              <span className={`w-2 h-2 rounded-full ${val.dot}`} />
              <span className="text-white">{val.label}</span>
              {currentStatus === key && <Check className="w-3 h-3 text-emerald-400 ml-auto" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
