import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Menu, X, BarChart3, Sun, Moon, RefreshCw, Radio, LogOut,
  Download, Bell, BellOff, Volume2, VolumeX,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// ── Draggable position persistence ────────────────────────────────
const POS_KEY = 'hamburger-pos-v1';
const BTN_SIZE = 36; // w-9 = 36px

const loadSavedPos = () => {
  try {
    const raw = localStorage.getItem(POS_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (typeof p?.x === 'number' && typeof p?.y === 'number') return p;
  } catch { /* silent */ }
  return null;
};

const clampPos = ({ x, y }) => {
  const maxX = Math.max(0, window.innerWidth - BTN_SIZE - 4);
  const maxY = Math.max(0, window.innerHeight - BTN_SIZE - 4);
  return {
    x: Math.min(Math.max(4, x), maxX),
    y: Math.min(Math.max(4, y), maxY),
  };
};

const defaultPos = () => ({ x: 8, y: 100 });

/**
 * Floating hamburger menu for the cajero desktop view.
 *
 * Draggable: hold & drag the button to move it anywhere. Position persists
 * in localStorage so it stays there across sessions. A short press (no drag)
 * opens the menu as before.
 */
export const HamburgerMenu = ({
  currentUser,
  darkMode,
  funnel,
  onFunnelOpen,
  soundEnabled,
  onSoundToggle,
  notifyEnabled,
  onNotifyToggle,
  pwaPrompt,
  pwaInstalled,
  onInstall,
  onBroadcast,
  onRefresh,
  onContactsExport,
  unreadCount = 0,
}) => {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState(() => clampPos(loadSavedPos() || defaultPos()));
  const [dragging, setDragging] = useState(false);
  const navigate = useNavigate();
  const panelRef = useRef(null);
  const dragStateRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    document.addEventListener('touchstart', handler);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('touchstart', handler);
    };
  }, [open]);

  // Keep the button inside the viewport when the window is resized
  useEffect(() => {
    const onResize = () => setPos(p => clampPos(p));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const close = () => setOpen(false);
  const action = (fn) => () => { try { fn?.(); } finally { close(); } };

  const handleLogout = () => {
    try { localStorage.removeItem('access_token'); } catch { /* silent */ }
    navigate('/login');
  };

  const handleThemeToggle = () => {
    try {
      if (typeof window.__toggleTheme === 'function') {
        window.__toggleTheme();
      } else {
        document.documentElement.classList.toggle('dark');
      }
    } catch { /* silent */ }
  };

  // ── Drag logic (mouse + touch) ──────────────────────────────────
  // Click vs drag: only treat as drag after moving >4px; otherwise it opens the menu.
  const onPointerDown = useCallback((clientX, clientY) => {
    dragStateRef.current = {
      startX: clientX,
      startY: clientY,
      offsetX: clientX - pos.x,
      offsetY: clientY - pos.y,
      moved: false,
    };
  }, [pos.x, pos.y]);

  const onPointerMove = useCallback((clientX, clientY) => {
    const s = dragStateRef.current;
    if (!s) return;
    const dx = clientX - s.startX;
    const dy = clientY - s.startY;
    if (!s.moved && Math.hypot(dx, dy) < 4) return; // still a click
    if (!s.moved) {
      s.moved = true;
      setDragging(true);
    }
    setPos(clampPos({ x: clientX - s.offsetX, y: clientY - s.offsetY }));
  }, []);

  const onPointerUp = useCallback(() => {
    const s = dragStateRef.current;
    dragStateRef.current = null;
    if (!s) return;
    if (s.moved) {
      setDragging(false);
      // Persist new position
      setPos(p => {
        try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch { /* silent */ }
        return p;
      });
      return 'dragged';
    }
    return 'click';
  }, []);

  // Attach global listeners while pressed so we keep tracking even if the
  // cursor leaves the tiny button.
  useEffect(() => {
    const mm = (e) => onPointerMove(e.clientX, e.clientY);
    const mu = () => {
      const kind = onPointerUp();
      if (kind === 'click') setOpen(true);
    };
    const tm = (e) => {
      if (!e.touches[0]) return;
      e.preventDefault();
      onPointerMove(e.touches[0].clientX, e.touches[0].clientY);
    };
    const tu = () => {
      const kind = onPointerUp();
      if (kind === 'click') setOpen(true);
    };
    window.addEventListener('mousemove', mm);
    window.addEventListener('mouseup', mu);
    window.addEventListener('touchmove', tm, { passive: false });
    window.addEventListener('touchend', tu);
    return () => {
      window.removeEventListener('mousemove', mm);
      window.removeEventListener('mouseup', mu);
      window.removeEventListener('touchmove', tm);
      window.removeEventListener('touchend', tu);
    };
  }, [onPointerMove, onPointerUp]);

  const resetPosition = () => {
    const p = clampPos(defaultPos());
    setPos(p);
    try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch { /* silent */ }
  };

  const itemBase = 'flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm transition-colors';
  const itemNormal = darkMode
    ? 'text-slate-200 hover:bg-slate-800 active:bg-slate-700'
    : 'text-gray-700 hover:bg-gray-100 active:bg-gray-200';
  const itemDanger = darkMode
    ? 'text-rose-300 hover:bg-rose-500/15'
    : 'text-rose-600 hover:bg-rose-50';

  return (
    <>
      <button
        onMouseDown={(e) => { e.preventDefault(); onPointerDown(e.clientX, e.clientY); }}
        onTouchStart={(e) => {
          if (!e.touches[0]) return;
          onPointerDown(e.touches[0].clientX, e.touches[0].clientY);
        }}
        data-testid="hamburger-btn"
        title="Menú · mantené apretado y arrastrá para mover"
        style={{
          left: pos.x,
          top: pos.y,
          cursor: dragging ? 'grabbing' : 'grab',
          userSelect: 'none',
          touchAction: 'none',
          transition: dragging ? 'none' : 'box-shadow 0.15s ease',
        }}
        className={`fixed z-40 w-9 h-9 rounded-full flex items-center justify-center shadow-md ${
          darkMode ? 'bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200' : 'bg-white hover:bg-gray-50 border border-gray-200 text-gray-700'
        } ${dragging ? 'ring-2 ring-blue-400/50 shadow-xl scale-105' : ''}`}
      >
        <Menu className="w-4 h-4 pointer-events-none" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center animate-pulse pointer-events-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div
            ref={panelRef}
            data-testid="hamburger-panel"
            className={`absolute top-0 left-0 h-full w-[280px] shadow-2xl flex flex-col ${
              darkMode ? 'bg-slate-950 border-r border-slate-800' : 'bg-white border-r border-gray-200'
            }`}
          >
            <div className={`px-4 py-3 flex items-center justify-between border-b ${darkMode ? 'border-slate-800' : 'border-gray-200'}`}>
              <div className="min-w-0 flex-1">
                <p className={`text-xs ${darkMode ? 'text-slate-500' : 'text-gray-500'}`}>Hola,</p>
                <p className={`text-sm font-medium truncate ${darkMode ? 'text-white' : 'text-gray-900'}`} title={currentUser?.email}>
                  {currentUser?.email}
                </p>
              </div>
              <button
                onClick={close}
                className={`p-1.5 rounded-lg ${darkMode ? 'hover:bg-slate-800 text-slate-400' : 'hover:bg-gray-100 text-gray-600'}`}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
              {funnel && (
                <button onClick={action(onFunnelOpen)} className={`${itemBase} ${itemNormal}`} data-testid="hm-funnel">
                  <BarChart3 className="w-4 h-4 shrink-0" />
                  <span>Embudo de conversión</span>
                </button>
              )}

              <button onClick={action(handleThemeToggle)} className={`${itemBase} ${itemNormal}`} data-testid="hm-theme">
                {darkMode ? <Sun className="w-4 h-4 shrink-0" /> : <Moon className="w-4 h-4 shrink-0" />}
                <span>{darkMode ? 'Tema claro' : 'Tema oscuro'}</span>
              </button>

              <button onClick={action(onNotifyToggle)} className={`${itemBase} ${itemNormal}`} data-testid="hm-notify">
                {notifyEnabled ? <Bell className="w-4 h-4 shrink-0 text-blue-400" /> : <BellOff className="w-4 h-4 shrink-0" />}
                <span>{notifyEnabled ? 'Notificaciones activas' : 'Activar notificaciones'}</span>
              </button>

              <button onClick={action(onSoundToggle)} className={`${itemBase} ${itemNormal}`} data-testid="hm-sound">
                {soundEnabled ? <Volume2 className="w-4 h-4 shrink-0 text-emerald-400" /> : <VolumeX className="w-4 h-4 shrink-0" />}
                <span>{soundEnabled ? 'Sonido activo' : 'Activar sonido'}</span>
              </button>

              <button onClick={action(onRefresh)} className={`${itemBase} ${itemNormal}`} data-testid="hm-refresh">
                <RefreshCw className="w-4 h-4 shrink-0" />
                <span>Actualizar leads</span>
              </button>

              {(currentUser?.role === 'admin' || (currentUser?.line_ids && currentUser.line_ids.length > 0)) && (
                <button onClick={action(onBroadcast)} className={`${itemBase} ${itemNormal}`} data-testid="hm-broadcast">
                  <Radio className="w-4 h-4 shrink-0 text-purple-400" />
                  <span>Envío masivo</span>
                </button>
              )}

              <button onClick={action(onContactsExport)} className={`${itemBase} ${itemNormal}`} data-testid="hm-contacts">
                <Download className="w-4 h-4 shrink-0 text-cyan-400" />
                <span>Descargar contactos (CSV)</span>
              </button>

              {pwaPrompt && !pwaInstalled && (
                <button onClick={action(onInstall)} className={`${itemBase} ${itemNormal}`} data-testid="hm-install">
                  <Download className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>Instalar app</span>
                </button>
              )}

              <div className={`my-2 border-t ${darkMode ? 'border-slate-800' : 'border-gray-200'}`} />

              <button
                onClick={() => { resetPosition(); close(); }}
                className={`${itemBase} ${itemNormal}`}
                data-testid="hm-reset-pos"
                title="Volver el botón a la posición por defecto"
              >
                <Menu className="w-4 h-4 shrink-0 text-slate-400" />
                <span>Resetear posición del menú</span>
              </button>

              <button onClick={handleLogout} className={`${itemBase} ${itemDanger}`} data-testid="hm-logout">
                <LogOut className="w-4 h-4 shrink-0" />
                <span>Cerrar sesión</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
