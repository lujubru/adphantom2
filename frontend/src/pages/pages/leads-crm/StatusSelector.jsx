import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
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

/**
 * StatusSelector
 *
 * The dropdown is rendered via a React Portal to document.body, with a
 * position computed from the trigger button's getBoundingClientRect(). This
 * bypasses ALL parent stacking contexts (backdrop-blur, overflow-hidden,
 * transforms, filters, etc.), so the "Válido" option — previously covered
 * by the chat messages area — is now always fully visible on top of
 * everything.
 */
export const StatusSelector = ({ currentStatus, onSelect, disabled }) => {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, width: 140 });
  const btnRef = useRef(null);
  const menuRef = useRef(null);

  // Close on outside click / touch
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      const t = e.target;
      if (btnRef.current && btnRef.current.contains(t)) return;
      if (menuRef.current && menuRef.current.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    document.addEventListener('touchstart', handler);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('touchstart', handler);
    };
  }, [open]);

  // Close on scroll / resize so the floating menu doesn't end up detached
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [open]);

  // Position the menu right-aligned under the trigger, clamped to viewport
  useLayoutEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const menuWidth = Math.max(rect.width, 160);
    const menuHeight = Object.keys(STATUS_CONFIG).length * 36 + 8; // approx
    // Prefer below; if it would overflow bottom, open upward
    const spaceBelow = window.innerHeight - rect.bottom;
    const openUpward = spaceBelow < menuHeight + 8 && rect.top > menuHeight + 8;
    const top = openUpward ? rect.top - menuHeight - 4 : rect.bottom + 4;
    // Right-align to trigger but keep inside viewport
    let left = rect.right - menuWidth;
    if (left < 8) left = 8;
    if (left + menuWidth > window.innerWidth - 8) {
      left = window.innerWidth - menuWidth - 8;
    }
    setCoords({ top, left, width: menuWidth });
  }, [open]);

  const cfg = STATUS_CONFIG[currentStatus] || STATUS_CONFIG.nuevo;

  return (
    <>
      <button
        ref={btnRef}
        onClick={() => !disabled && setOpen(o => !o)}
        data-testid="status-selector-btn"
        className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${cfg.color} ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80'}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
        {cfg.label}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && typeof document !== 'undefined' && createPortal(
        <div
          ref={menuRef}
          data-testid="status-selector-menu"
          style={{
            position: 'fixed',
            top: coords.top,
            left: coords.left,
            width: coords.width,
            zIndex: 9999,
          }}
          className="bg-slate-800 border border-slate-700 rounded-lg shadow-2xl overflow-hidden"
        >
          {Object.entries(STATUS_CONFIG).map(([key, val]) => (
            <button
              key={key}
              onClick={() => { onSelect(key); setOpen(false); }}
              data-testid={`status-option-${key}`}
              className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-slate-700 transition-colors ${currentStatus === key ? 'bg-slate-700/50' : ''}`}
            >
              <span className={`w-2 h-2 rounded-full ${val.dot}`} />
              <span className="text-white">{val.label}</span>
              {currentStatus === key && <Check className="w-3 h-3 text-emerald-400 ml-auto" />}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
};
